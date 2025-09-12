"""
Signals para Sistema de Notificações Automáticas
iConnect - Automatização de Eventos
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone
from datetime import timedelta

from .models import Ticket, InteracaoTicket, Notification, PerfilAgente, Cliente
from django.contrib.auth.models import User
from .services.sla_calculator import sla_calculator


channel_layer = get_channel_layer()


@receiver(post_save, sender=Ticket)
def ticket_created_or_updated(sender, instance, created, **kwargs):
    """Notificações automáticas para tickets"""
    
    if created:
        # 🎫 NOVO TICKET CRIADO
        # Notificar todos os agentes disponíveis
        async_to_sync(channel_layer.group_send)(
            "agents",
            {
                'type': 'notification_message',
                'data': {
                    'id': f'ticket_new_{instance.id}',
                    'title': '🎫 Novo Ticket Criado',
                    'message': f'#{instance.numero}: {instance.titulo}',
                    'type': 'new_ticket',
                    'priority': instance.prioridade,
                    'ticket_id': instance.id,
                    'category': instance.categoria.nome if instance.categoria else 'Sem categoria',
                    'timestamp': instance.criado_em.isoformat()
                }
            }
        )
        
        # Criar notificações no banco para agentes
        agents = User.objects.filter(perfilagente__isnull=False, is_active=True)
        for agent in agents:
            Notification.objects.create(
                user=agent,
                title='Novo Ticket Criado',
                message=f'Ticket #{instance.numero}: {instance.titulo}',
                type='new_ticket',
                ticket=instance
            )
    
    else:
        # 🔄 TICKET ATUALIZADO
        async_to_sync(channel_layer.group_send)(
            f"ticket_chat_{instance.id}",
            {
                'type': 'ticket_update',
                'data': {
                    'ticket_id': instance.id,
                    'status': instance.status,
                    'priority': instance.prioridade,
                    'agent': instance.agente.get_full_name() if instance.agente else None,
                    'updated_at': instance.atualizado_em.isoformat()
                }
            }
        )
        
        # Notificar cliente sobre mudanças de status
        if instance.cliente:
            try:
                client_user = User.objects.get(email=instance.cliente.email)
                
                # Criar notificação
                Notification.objects.create(
                    user=client_user,
                    title='Ticket Atualizado',
                    message=f'Seu ticket #{instance.numero} foi atualizado: {instance.get_status_display()}',
                    type='ticket_update',
                    ticket=instance
                )
                
                # Enviar via WebSocket
                async_to_sync(channel_layer.group_send)(
                    f"user_{client_user.id}",
                    {
                        'type': 'notification_message',
                        'data': {
                            'title': 'Seu Ticket foi Atualizado',
                            'message': f'Status: {instance.get_status_display()}',
                            'type': 'ticket_update',
                            'ticket_id': instance.id,
                            'timestamp': timezone.now().isoformat()
                        }
                    }
                )
            except User.DoesNotExist:
                pass


@receiver(post_save, sender=InteracaoTicket)
def interaction_created(sender, instance, created, **kwargs):
    """Notificações para novas interações"""
    
    if not created:
        return
    
    ticket = instance.ticket
    
    # 💬 NOVA MENSAGEM NO CHAT
    async_to_sync(channel_layer.group_send)(
        f"ticket_chat_{ticket.id}",
        {
            'type': 'chat_message_broadcast',
            'data': {
                'id': instance.id,
                'message': instance.mensagem,
                'author': instance.usuario.get_full_name() or instance.usuario.username,
                'author_id': instance.usuario.id,
                'is_public': instance.eh_publico,
                'timestamp': instance.criado_em.isoformat(),
                'is_agent': hasattr(instance.usuario, 'perfilagente') or instance.usuario.is_staff
            }
        }
    )
    
    # Notificar cliente se for mensagem pública de agente
    if instance.eh_publico and ticket.cliente:
        try:
            client_user = User.objects.get(email=ticket.cliente.email)
            if client_user != instance.usuario:  # Não notificar o próprio autor
                
                Notification.objects.create(
                    user=client_user,
                    title='Nova Resposta no seu Ticket',
                    message=f'Ticket #{ticket.numero}: Nova resposta disponível',
                    type='new_response',
                    ticket=ticket
                )
                
                async_to_sync(channel_layer.group_send)(
                    f"user_{client_user.id}",
                    {
                        'type': 'notification_message',
                        'data': {
                            'title': '💬 Nova Resposta',
                            'message': f'Ticket #{ticket.numero}: Nova resposta disponível',
                            'type': 'new_response',
                            'ticket_id': ticket.id,
                            'timestamp': instance.criado_em.isoformat()
                        }
                    }
                )
        except User.DoesNotExist:
            pass
    
    # Notificar agente atribuído se não for o autor
    if ticket.agente and ticket.agente != instance.usuario:
        Notification.objects.create(
            user=ticket.agente,
            title='Nova Mensagem no Ticket',
            message=f'Ticket #{ticket.numero}: Nova mensagem adicionada',
            type='new_message',
            ticket=ticket
        )
        
        async_to_sync(channel_layer.group_send)(
            f"user_{ticket.agente.id}",
            {
                'type': 'notification_message',
                'data': {
                    'title': '💬 Nova Mensagem',
                    'message': f'Ticket #{ticket.numero}: Nova mensagem',
                    'type': 'new_message',
                    'ticket_id': ticket.id,
                    'timestamp': instance.criado_em.isoformat()
                }
            }
        )


# ========== FUNÇÕES AUXILIARES PARA SLA ==========

def send_sla_warning(ticket):
    """⚠️ Alerta de SLA próximo do vencimento"""
    
    async_to_sync(channel_layer.group_send)(
        "agents",
        {
            'type': 'sla_alert',
            'data': {
                'title': '⚠️ SLA Próximo do Vencimento',
                'message': f'Ticket #{ticket.numero} vence em breve!',
                'type': 'sla_warning',
                'ticket_id': ticket.id,
                'priority': 'high',
                'deadline': ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
                'time_remaining': '30 minutos'
            }
        }
    )
    
    # Notificar agente atribuído
    if ticket.agente:
        Notification.objects.create(
            user=ticket.agente,
            title='SLA Próximo do Vencimento',
            message=f'Ticket #{ticket.numero} vence em 30 minutos!',
            type='sla_warning',
            ticket=ticket
        )


def send_sla_breach(ticket):
    """🚨 Alerta de violação de SLA"""
    
    async_to_sync(channel_layer.group_send)(
        "agents",
        {
            'type': 'sla_alert',
            'data': {
                'title': '🚨 SLA VIOLADO',
                'message': f'Ticket #{ticket.numero} excedeu o prazo!',
                'type': 'sla_breach',
                'ticket_id': ticket.id,
                'priority': 'critical',
                'overdue_time': 'Atrasado'
            }
        }
    )
    
    # Notificar supervisores
    supervisors = User.objects.filter(is_staff=True, is_active=True)
    for supervisor in supervisors:
        Notification.objects.create(
            user=supervisor,
            title='SLA VIOLADO',
            message=f'Ticket #{ticket.numero} excedeu o prazo de atendimento!',
            type='sla_breach',
            ticket=ticket
        )
        
        # Notificação WebSocket individual
        async_to_sync(channel_layer.group_send)(
            f"user_{supervisor.id}",
            {
                'type': 'sla_alert',
                'data': {
                    'title': '🚨 SLA VIOLADO',
                    'message': f'Ticket #{ticket.numero} excedeu o prazo!',
                    'type': 'sla_breach',
                    'ticket_id': ticket.id,
                    'priority': 'critical'
                }
            }
        )


@receiver(post_save, sender=PerfilAgente)
def agent_status_changed(sender, instance, **kwargs):
    """Notificação de mudança de status do agente"""
    
    async_to_sync(channel_layer.group_send)(
        "agent_status",
        {
            'type': 'agent_status_update',
            'data': {
                'user_id': instance.user.id,
                'name': instance.user.get_full_name() or instance.user.username,
                'status': instance.status,
                'max_tickets': instance.max_tickets_simultaneos,
                'timestamp': timezone.now().isoformat()
            }
        }
    )


# ========== FUNÇÃO PARA ATUALIZAÇÃO DO DASHBOARD ==========

def send_dashboard_update():
    """Atualizar métricas do dashboard em tempo real"""
    
    from django.db.models import Count
    
    # Estatísticas atuais
    stats = {
        'total_tickets': Ticket.objects.count(),
        'open_tickets': Ticket.objects.filter(status='aberto').count(),
        'in_progress': Ticket.objects.filter(status='em_andamento').count(),
        'resolved_today': Ticket.objects.filter(
            status='resolvido',
            resolvido_em__date=timezone.now().date()
        ).count(),
        'agents_online': PerfilAgente.objects.filter(status='online').count(),
        'timestamp': timezone.now().isoformat()
    }
    
    async_to_sync(channel_layer.group_send)(
        "dashboard_updates",
        {
            'type': 'metrics_update',
            'data': stats
        }
    )


# ========== SIGNALS PARA SISTEMA DE SLA ==========

@receiver(post_save, sender=Ticket)
def setup_sla_for_new_ticket(sender, instance, created, **kwargs):
    """Configura SLA automaticamente para novos tickets"""
    if created:
        try:
            # Cria histórico de SLA para o novo ticket
            sla_history = sla_calculator.create_sla_history(instance)
            
            if sla_history:
                print(f"✅ SLA configurado para ticket #{instance.numero}")
                
                # Envia notificação sobre a criação do SLA
                if instance.agente:
                    Notification.objects.create(
                        user=instance.agente,
                        type='new_ticket',
                        title=f'Novo Ticket com SLA - #{instance.numero}',
                        message=f'Ticket atribuído com prazo SLA: {sla_history.first_response_deadline.strftime("%H:%M")}',
                        icon='schedule',
                        color='info',
                        ticket=instance,
                        metadata={
                            'sla_deadline': sla_history.first_response_deadline.isoformat(),
                            'sla_policy': sla_history.sla_policy.name
                        }
                    )
            else:
                print(f"⚠️  Nenhuma política SLA encontrada para ticket #{instance.numero}")
                
        except Exception as e:
            print(f"❌ Erro ao configurar SLA para ticket #{instance.numero}: {str(e)}")


@receiver(pre_save, sender=Ticket)
def track_first_response(sender, instance, **kwargs):
    """Marca o momento da primeira resposta do agente"""
    if instance.pk:  # Ticket já existe
        try:
            old_ticket = Ticket.objects.get(pk=instance.pk)
            
            # Se o status mudou para "em_andamento" e não há primeira resposta registrada
            if (old_ticket.status != 'em_andamento' and 
                instance.status == 'em_andamento' and 
                not instance.first_response_at):
                
                instance.first_response_at = timezone.now()
                print(f"✅ Primeira resposta registrada para ticket #{instance.numero}")
                
                # Atualiza métricas de SLA
                sla_history = instance.sla_history.first()
                if sla_history:
                    sla_history.first_response_time = instance.first_response_at - instance.criado_em
                    
                    # Verifica se cumpriu o SLA de primeira resposta
                    if instance.first_response_at <= sla_history.first_response_deadline:
                        sla_history.sla_compliance = True
                        print(f"✅ SLA de primeira resposta cumprido para ticket #{instance.numero}")
                    else:
                        sla_history.sla_compliance = False
                        print(f"❌ SLA de primeira resposta violado para ticket #{instance.numero}")
                    
                    sla_history.save()
                    
        except Ticket.DoesNotExist:
            pass  # Ticket novo, não há nada para comparar
        except Exception as e:
            print(f"❌ Erro ao rastrear primeira resposta: {str(e)}")


@receiver(post_save, sender=Ticket)
def track_resolution_time(sender, instance, created, **kwargs):
    """Rastreia o tempo de resolução do ticket"""
    if not created and instance.status in ['resolvido', 'fechado']:
        try:
            sla_history = instance.sla_history.first()
            if sla_history and not sla_history.resolution_time:
                
                # Calcula tempo de resolução
                resolution_time = timezone.now() - instance.criado_em
                sla_history.resolution_time = resolution_time
                
                # Verifica se cumpriu o SLA de resolução
                resolution_sla_met = timezone.now() <= sla_history.resolution_deadline
                
                # Atualiza compliance geral
                first_response_ok = (sla_history.first_response_time and 
                                   instance.first_response_at <= sla_history.first_response_deadline)
                
                sla_history.sla_compliance = first_response_ok and resolution_sla_met
                sla_history.status = 'completed'
                sla_history.save()
                
                # Log do resultado
                if sla_history.sla_compliance:
                    print(f"✅ SLA totalmente cumprido para ticket #{instance.numero}")
                else:
                    print(f"❌ SLA violado para ticket #{instance.numero}")
                    
                    # Cria notificação de violação se necessário
                    if instance.agente:
                        Notification.objects.create(
                            user=instance.agente,
                            type='system_alert',
                            title=f'SLA Violado - #{instance.numero}',
                            message=f'Ticket resolvido fora do prazo SLA estabelecido.',
                            icon='error_outline',
                            color='danger',
                            ticket=instance
                        )
                        
        except Exception as e:
            print(f"❌ Erro ao rastrear tempo de resolução: {str(e)}")


def send_sla_dashboard_update():
    """Envia atualização para o dashboard de SLA"""
    try:
        from .services.sla_monitor import sla_monitor
        
        dashboard_data = sla_monitor.get_sla_dashboard_data()
        
        async_to_sync(channel_layer.group_send)(
            "sla_dashboard",
            {
                'type': 'sla_update',
                'data': dashboard_data
            }
        )
        
    except Exception as e:
        print(f"❌ Erro ao enviar atualização do dashboard SLA: {str(e)}")
