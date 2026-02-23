"""
Sistema de SLA (Service Level Agreement) para o iConnect.
Monitora prazos de resposta e escalação automática.
"""
import logging
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
from django.db.models import Q, F
from celery import shared_task
from .models import Ticket, SLAPolicy, SLAViolation
from .notifications import notification_service

logger = logging.getLogger(__name__)


class SLAManager:
    """Gerenciador do sistema de SLA"""
    
    def __init__(self):
        self.sla_config = getattr(settings, 'SLA_CONFIG', {})
    
    def calculate_sla_deadline(self, ticket):
        """Calcula o prazo de SLA para um ticket"""
        try:
            # Buscar política de SLA específica ou usar configuração padrão
            sla_policy = SLAPolicy.objects.filter(
                categoria=ticket.categoria,
                prioridade=ticket.prioridade
            ).first()
            
            if sla_policy:
                # first_response_time está em minutos no modelo → converter para horas
                response_time_hours = sla_policy.first_response_time / 60
            else:
                # Usar configuração padrão
                response_times = self.sla_config.get('RESPONSE_TIMES', {})
                response_time_hours = response_times.get(
                    ticket.prioridade, 
                    {'hours': 24}
                )['hours']
            
            # Calcular deadline considerando apenas horário comercial
            deadline = self._calculate_business_deadline(
                ticket.criado_em, 
                response_time_hours
            )
            
            return deadline
            
        except Exception as e:
            logger.error(f"Erro ao calcular prazo SLA: {str(e)}")
            return timezone.now() + timedelta(hours=24)  # Fallback
    
    def _calculate_business_deadline(self, start_time, hours_to_add):
        """Calcula deadline considerando apenas horário comercial"""
        # Configuração do horário comercial (9h às 18h, segunda a sexta)
        business_hours_per_day = 9  # 18h - 9h
        business_start_hour = 9
        business_end_hour = 18
        
        current_time = start_time
        remaining_hours = hours_to_add
        
        while remaining_hours > 0:
            # Se é fim de semana, pular para segunda-feira
            if current_time.weekday() >= 5:  # Sábado (5) ou Domingo (6)
                days_to_monday = 7 - current_time.weekday()
                current_time = current_time.replace(
                    hour=business_start_hour, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                ) + timedelta(days=days_to_monday)
                continue
            
            # Se está fora do horário comercial
            if current_time.hour < business_start_hour:
                current_time = current_time.replace(
                    hour=business_start_hour, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                )
            elif current_time.hour >= business_end_hour:
                current_time = current_time.replace(
                    hour=business_start_hour, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                ) + timedelta(days=1)
                continue
            
            # Calcular horas até o fim do dia útil
            hours_until_end = business_end_hour - current_time.hour - (current_time.minute / 60)
            
            if remaining_hours <= hours_until_end:
                # Cabe no dia atual
                current_time += timedelta(hours=remaining_hours)
                remaining_hours = 0
            else:
                # Ir para o próximo dia útil
                remaining_hours -= hours_until_end
                current_time = current_time.replace(
                    hour=business_start_hour, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                ) + timedelta(days=1)
        
        return current_time
    
    def check_sla_status(self, ticket):
        """Verifica o status atual do SLA do ticket"""
        try:
            if not hasattr(ticket, 'sla_deadline') or not ticket.sla_deadline:
                ticket.sla_deadline = self.calculate_sla_deadline(ticket)
                ticket.save()
            
            now = timezone.now()
            time_remaining = ticket.sla_deadline - now
            
            # Determinar status do SLA
            if time_remaining.total_seconds() < 0:
                status = 'violated'
            elif time_remaining.total_seconds() < 3600:  # Menos de 1 hora
                status = 'critical'
            elif time_remaining.total_seconds() < 7200:  # Menos de 2 horas
                status = 'warning'
            else:
                status = 'ok'
            
            return {
                'status': status,
                'deadline': ticket.sla_deadline,
                'time_remaining': time_remaining,
                'time_remaining_formatted': self._format_time_remaining(time_remaining)
            }
            
        except Exception as e:
            logger.error(f"Erro ao verificar status SLA: {str(e)}")
            return {
                'status': 'unknown',
                'deadline': None,
                'time_remaining': None,
                'time_remaining_formatted': 'N/A'
            }
    
    def _format_time_remaining(self, time_delta):
        """Formata tempo restante de forma amigável"""
        if time_delta.total_seconds() < 0:
            return f"Atrasado há {abs(time_delta)}"
        
        total_seconds = int(time_delta.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}min"
        elif minutes > 0:
            return f"{minutes}min"
        else:
            return "Menos de 1 minuto"
    
    def get_sla_violations(self, days=7):
        """Retorna violações de SLA dos últimos N dias"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            violations = SLAViolation.objects.filter(
                created_at__gte=cutoff_date
            ).select_related('ticket', 'ticket__cliente', 'ticket__agente')
            
            return violations
            
        except Exception as e:
            logger.error(f"Erro ao buscar violações SLA: {str(e)}")
            return []
    
    def get_sla_metrics(self, days=30):
        """Calcula métricas de SLA para dashboard"""
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            # Tickets do período
            tickets = Ticket.objects.filter(
                criado_em__gte=cutoff_date,
                status__in=['resolvido', 'fechado']
            )
            
            total_tickets = tickets.count()
            if total_tickets == 0:
                return {'compliance_rate': 100, 'avg_resolution_time': 0, 'violations': 0}
            
            # Violações do período
            violations = SLAViolation.objects.filter(
                created_at__gte=cutoff_date
            ).count()
            
            # Taxa de cumprimento
            compliance_rate = ((total_tickets - violations) / total_tickets) * 100
            
            # Tempo médio de resolução
            avg_resolution_time = self._calculate_avg_resolution_time(tickets)
            
            return {
                'compliance_rate': round(compliance_rate, 2),
                'avg_resolution_time': avg_resolution_time,
                'violations': violations,
                'total_tickets': total_tickets
            }
            
        except Exception as e:
            logger.error(f"Erro ao calcular métricas SLA: {str(e)}")
            return {'compliance_rate': 0, 'avg_resolution_time': 0, 'violations': 0}
    
    def _calculate_avg_resolution_time(self, tickets):
        """Calcula tempo médio de resolução em horas"""
        try:
            resolution_times = []
            
            for ticket in tickets:
                if ticket.resolvido_em:
                    time_diff = ticket.resolvido_em - ticket.criado_em
                    resolution_times.append(time_diff.total_seconds() / 3600)  # Converter para horas
            
            if resolution_times:
                return round(sum(resolution_times) / len(resolution_times), 2)
            else:
                return 0
                
        except Exception as e:
            logger.error(f"Erro ao calcular tempo médio de resolução: {str(e)}")
            return 0


@shared_task
def monitor_sla_violations():
    """Task do Celery para monitorar violações de SLA"""
    try:
        sla_manager = SLAManager()
        
        # Buscar tickets ativos que podem ter violações
        active_tickets = Ticket.objects.filter(
            status__in=['aberto', 'em_andamento', 'aguardando_cliente']
        ).exclude(
            sla_deadline__isnull=True
        )
        
        violations_found = 0
        warnings_sent = 0
        
        for ticket in active_tickets:
            sla_status = sla_manager.check_sla_status(ticket)
            
            if sla_status['status'] == 'violated':
                # Verificar se já foi registrada violação
                existing_violation = SLAViolation.objects.filter(
                    ticket=ticket,
                    violation_type='deadline_missed'
                ).exists()
                
                if not existing_violation:
                    # Registrar nova violação
                    SLAViolation.objects.create(
                        ticket=ticket,
                        violation_type='deadline_missed',
                        expected_deadline=ticket.sla_deadline,
                        actual_time=timezone.now(),
                        severity='high'
                    )
                    
                    violations_found += 1
                    
                    # Enviar notificação de violação
                    notification_service.send_ticket_notification(
                        ticket=ticket,
                        event_type='sla_breach',
                        recipient_email=ticket.agente.email if ticket.agente else None,
                        extra_context={'time_exceeded': sla_status['time_remaining_formatted']}
                    )
                    
                    logger.warning(f"Violação SLA detectada - Ticket #{ticket.numero}")
            
            elif sla_status['status'] in ['warning', 'critical']:
                # Enviar aviso de SLA próximo do prazo
                notification_service.send_ticket_notification(
                    ticket=ticket,
                    event_type='sla_warning',
                    recipient_email=ticket.agente.email if ticket.agente else None,
                    extra_context={'time_remaining': sla_status['time_remaining_formatted']}
                )
                
                warnings_sent += 1
        
        logger.info(f"Monitor SLA executado - {violations_found} violações, {warnings_sent} avisos")
        
        return {
            'violations_found': violations_found,
            'warnings_sent': warnings_sent,
            'tickets_checked': active_tickets.count()
        }
        
    except Exception as e:
        logger.error(f"Erro no monitor de SLA: {str(e)}")
        return {'error': str(e)}


# Instância global do gerenciador SLA
sla_manager = SLAManager()
