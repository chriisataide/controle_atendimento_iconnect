"""
SLA Monitoring Service
Monitora tickets, envia alertas e gerencia escalações automáticas
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from django.utils import timezone
from django.contrib.auth.models import User
from django.db import transaction
from django.template.loader import render_to_string

from ..models import (
    Ticket, SLAHistory, SLAAlert, SLAPolicy, 
    Notification, StatusTicket
)
from .sla_calculator import sla_calculator

logger = logging.getLogger(__name__)


class SLAMonitor:
    """Classe principal para monitoramento de SLA"""
    
    def __init__(self):
        self.alerts_sent = []
        self.escalations_processed = []
    
    def monitor_all_tickets(self) -> Dict[str, int]:
        """
        Monitora todos os tickets ativos e processa alertas/escalações
        Retorna estatísticas da execução
        """
        stats = {
            'tickets_monitored': 0,
            'warnings_sent': 0,
            'breaches_detected': 0,
            'escalations_made': 0,
            'errors': 0
        }
        
        try:
            # Busca todos os tickets ativos
            active_tickets = Ticket.objects.filter(
                status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE]
            ).select_related('sla_policy', 'agente', 'categoria', 'cliente')
            
            for ticket in active_tickets:
                try:
                    result = self.monitor_ticket(ticket)
                    stats['tickets_monitored'] += 1
                    
                    if result.get('warning_sent'):
                        stats['warnings_sent'] += 1
                    if result.get('breach_detected'):
                        stats['breaches_detected'] += 1
                    if result.get('escalation_made'):
                        stats['escalations_made'] += 1
                        
                except Exception as e:
                    logger.error(f"Erro ao monitorar ticket {ticket.numero}: {str(e)}")
                    stats['errors'] += 1
            
            logger.info(f"Monitoramento SLA concluído: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Erro no monitoramento geral de SLA: {str(e)}")
            stats['errors'] += 1
            return stats
    
    def monitor_ticket(self, ticket: Ticket) -> Dict[str, bool]:
        """
        Monitora um ticket específico
        """
        result = {
            'warning_sent': False,
            'breach_detected': False,
            'escalation_made': False
        }
        
        # Garante que o ticket tem SLA configurado
        sla_history = self.ensure_sla_history(ticket)
        if not sla_history:
            return result
        
        # Atualiza status do SLA
        current_status = sla_calculator.get_sla_status(sla_history)
        old_status = sla_history.status
        
        if current_status != old_status:
            sla_history.status = current_status
            sla_history.save(update_fields=['status', 'updated_at'])
        
        # Processa de acordo com o status
        if current_status == 'warning' and not sla_history.warning_sent:
            result['warning_sent'] = self.send_warning_alert(sla_history)
        
        elif current_status == 'breached':
            result['breach_detected'] = True
            self.handle_sla_breach(sla_history)
            
            # Verifica se precisa escalar
            if (sla_history.sla_policy.escalation_enabled and 
                not sla_history.escalated and 
                self.should_escalate(sla_history)):
                result['escalation_made'] = self.escalate_ticket(sla_history)
        
        return result
    
    def ensure_sla_history(self, ticket: Ticket) -> Optional[SLAHistory]:
        """Garante que o ticket tem um histórico de SLA"""
        try:
            # Verifica se já existe
            sla_history = SLAHistory.objects.filter(ticket=ticket).first()
            if sla_history:
                return sla_history
            
            # Cria novo se não existir
            return sla_calculator.create_sla_history(ticket)
            
        except Exception as e:
            logger.error(f"Erro ao criar SLA history para ticket {ticket.numero}: {str(e)}")
            return None
    
    def send_warning_alert(self, sla_history: SLAHistory) -> bool:
        """Envia alerta de warning de SLA"""
        try:
            ticket = sla_history.ticket
            now = timezone.now()
            
            # Calcula métricas
            metrics = sla_calculator.calculate_sla_metrics(sla_history)
            time_remaining = metrics.get('time_to_breach', timedelta(0))
            
            # Cria o alerta
            alert = SLAAlert.objects.create(
                ticket=ticket,
                sla_history=sla_history,
                alert_type='warning',
                message=f"Ticket #{ticket.numero} está próximo do vencimento do SLA. "
                       f"Tempo restante: {self._format_timedelta(time_remaining)}"
            )
            
            # Envia notificações
            self._send_sla_notifications(ticket, alert, 'warning')
            
            # Marca como enviado
            sla_history.warning_sent = True
            sla_history.save(update_fields=['warning_sent'])
            
            logger.info(f"Alerta de warning enviado para ticket {ticket.numero}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao enviar alerta de warning: {str(e)}")
            return False
    
    def handle_sla_breach(self, sla_history: SLAHistory) -> bool:
        """Trata violação de SLA"""
        try:
            ticket = sla_history.ticket
            
            # Cria alerta de violação
            alert = SLAAlert.objects.create(
                ticket=ticket,
                sla_history=sla_history,
                alert_type='breach',
                message=f"SLA VIOLADO - Ticket #{ticket.numero} ultrapassou o prazo estabelecido."
            )
            
            # Envia notificações críticas
            self._send_sla_notifications(ticket, alert, 'breach')
            
            logger.warning(f"SLA violado para ticket {ticket.numero}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao tratar violação de SLA: {str(e)}")
            return False
    
    def should_escalate(self, sla_history: SLAHistory) -> bool:
        """Determina se o ticket deve ser escalado"""
        now = timezone.now()
        
        # Escalação por tempo (passou do prazo de escalação)
        if now > sla_history.escalation_deadline:
            return True
        
        # Escalação por violação de SLA crítica
        if (sla_history.ticket.prioridade == 'critica' and 
            sla_history.status == 'breached'):
            return True
        
        return False
    
    def escalate_ticket(self, sla_history: SLAHistory) -> bool:
        """Escala o ticket para supervisor"""
        try:
            ticket = sla_history.ticket
            policy = sla_history.sla_policy
            
            if not policy.escalation_to:
                logger.warning(f"Nenhum supervisor configurado para escalação do ticket {ticket.numero}")
                return False
            
            with transaction.atomic():
                # Atualiza o ticket
                old_agent = ticket.agente
                ticket.agente = policy.escalation_to
                ticket.is_escalated = True
                ticket.escalated_to = policy.escalation_to
                ticket.escalated_at = timezone.now()
                ticket.save()
                
                # Atualiza SLA history
                sla_history.escalated = True
                sla_history.escalated_to = policy.escalation_to
                sla_history.escalated_at = timezone.now()
                sla_history.status = 'escalated'
                sla_history.save()
                
                # Cria alerta de escalação
                alert = SLAAlert.objects.create(
                    ticket=ticket,
                    sla_history=sla_history,
                    alert_type='escalation',
                    message=f"Ticket #{ticket.numero} foi escalado de {old_agent} para {policy.escalation_to} "
                           f"devido à violação de SLA."
                )
                
                # Envia notificações
                self._send_escalation_notifications(ticket, alert, old_agent, policy.escalation_to)
                
                logger.info(f"Ticket {ticket.numero} escalado para {policy.escalation_to}")
                return True
                
        except Exception as e:
            logger.error(f"Erro ao escalar ticket {sla_history.ticket.numero}: {str(e)}")
            return False
    
    def _send_sla_notifications(self, ticket: Ticket, alert: SLAAlert, alert_type: str):
        """Envia notificações de SLA para os usuários relevantes"""
        try:
            # Notificação para o agente
            if ticket.agente:
                Notification.objects.create(
                    user=ticket.agente,
                    type='sla_warning' if alert_type == 'warning' else 'system_alert',
                    title=f"SLA - Ticket #{ticket.numero}",
                    message=alert.message,
                    icon='schedule' if alert_type == 'warning' else 'warning',
                    color='warning' if alert_type == 'warning' else 'danger',
                    ticket=ticket,
                    metadata={
                        'alert_type': alert_type,
                        'sla_alert_id': alert.id
                    }
                )
            
            # Notificação para supervisores (se violação)
            if alert_type == 'breach' and ticket.sla_policy and ticket.sla_policy.escalation_to:
                Notification.objects.create(
                    user=ticket.sla_policy.escalation_to,
                    type='system_alert',
                    title=f"SLA VIOLADO - Ticket #{ticket.numero}",
                    message=alert.message,
                    icon='error',
                    color='danger',
                    ticket=ticket,
                    metadata={
                        'alert_type': alert_type,
                        'sla_alert_id': alert.id,
                        'requires_action': True
                    }
                )
            
            # Marca destinatários no alerta
            alert.sent_to_agent = True
            if alert_type == 'breach':
                alert.sent_to_supervisor = True
            alert.save()
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificações SLA: {str(e)}")
    
    def _send_escalation_notifications(self, ticket: Ticket, alert: SLAAlert, 
                                     old_agent: User, new_agent: User):
        """Envia notificações de escalação"""
        try:
            # Notificação para o agente anterior
            if old_agent:
                Notification.objects.create(
                    user=old_agent,
                    type='system_alert',
                    title=f"Ticket Escalado - #{ticket.numero}",
                    message=f"O ticket foi escalado para {new_agent.get_full_name() or new_agent.username} "
                           f"devido à violação de SLA.",
                    icon='trending_up',
                    color='warning',
                    ticket=ticket
                )
            
            # Notificação para o novo agente (supervisor)
            Notification.objects.create(
                user=new_agent,
                type='ticket_assigned',
                title=f"Ticket Escalado - #{ticket.numero}",
                message=f"Ticket escalado devido à violação de SLA. Prioridade: {ticket.get_prioridade_display()}",
                icon='assignment_ind',
                color='danger',
                ticket=ticket,
                metadata={
                    'escalated': True,
                    'previous_agent': old_agent.username if old_agent else None
                }
            )
            
        except Exception as e:
            logger.error(f"Erro ao enviar notificações de escalação: {str(e)}")
    
    def _format_timedelta(self, td: timedelta) -> str:
        """Formata timedelta para exibição amigável"""
        if td.total_seconds() < 0:
            return "Prazo vencido"
        
        hours, remainder = divmod(int(td.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    def get_sla_dashboard_data(self) -> Dict:
        """Retorna dados para o dashboard de SLA"""
        try:
            now = timezone.now()
            
            # Tickets ativos
            active_tickets = Ticket.objects.filter(
                status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE]
            )
            
            # SLA Histories correspondentes
            sla_histories = SLAHistory.objects.filter(
                ticket__in=active_tickets
            ).select_related('ticket', 'sla_policy')
            
            # Estatísticas
            total_active = active_tickets.count()
            on_track = sla_histories.filter(status='on_track').count()
            warnings = sla_histories.filter(status='warning').count()
            breached = sla_histories.filter(status='breached').count()
            escalated = sla_histories.filter(status='escalated').count()
            
            # Tickets críticos (próximos ao vencimento)
            critical_tickets = []
            for sla_history in sla_histories.filter(status__in=['warning', 'breached']):
                metrics = sla_calculator.calculate_sla_metrics(sla_history)
                critical_tickets.append({
                    'ticket': sla_history.ticket,
                    'sla_history': sla_history,
                    'time_remaining': metrics.get('time_to_breach'),
                    'percentage_elapsed': metrics.get('sla_percentage_elapsed', 0)
                })
            
            # Ordena por urgência (menos tempo restante primeiro)
            critical_tickets.sort(key=lambda x: x['time_remaining'] or timedelta(0))
            
            return {
                'total_active_tickets': total_active,
                'sla_stats': {
                    'on_track': on_track,
                    'warnings': warnings,
                    'breached': breached,
                    'escalated': escalated
                },
                'compliance_rate': (on_track / total_active * 100) if total_active > 0 else 100,
                'critical_tickets': critical_tickets[:10],  # Top 10 mais críticos
                'alerts_last_24h': SLAAlert.objects.filter(
                    created_at__gte=now - timedelta(hours=24)
                ).count(),
                'escalations_last_24h': SLAHistory.objects.filter(
                    escalated_at__gte=now - timedelta(hours=24)
                ).count()
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter dados do dashboard SLA: {str(e)}")
            return {}


# Instância global do monitor
sla_monitor = SLAMonitor()
