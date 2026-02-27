"""
Signals para Sistema de Notificações Automáticas
iConnect - Automatização de Eventos

As operações pesadas (bulk_create de notificações, envio de
email/Slack/WhatsApp) são delegadas para Celery tasks sempre que o
broker estiver disponível.  Se o Celery não estiver configurado, os
signals executam a lógica de maneira síncrona como fallback.
"""

from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
from datetime import timedelta

from .models import Ticket, InteracaoTicket, Notification, PerfilAgente, Cliente, ItemAtendimento
from .models import MovimentacaoEstoque, TipoMovimentacao, Produto
from django.contrib.auth.models import User
from .services.sla_calculator import sla_calculator

import logging
logger = logging.getLogger('dashboard')


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_channel_layer():
    """Lazy-load channel layer para evitar falha se Redis não estiver disponível no import."""
    try:
        from channels.layers import get_channel_layer
        return get_channel_layer()
    except Exception:
        return None


def _safe_group_send(group, message):
    """Send to channel group only when layer is available (not in tests/dev without Redis)."""
    layer = _get_channel_layer()
    if layer is not None:
        try:
            from asgiref.sync import async_to_sync
            async_to_sync(layer.group_send)(group, message)
        except Exception:
            logger.debug("Channel layer send failed (no backend?)")


def _dispatch_task(task_func, *args, **kwargs):
    """Tenta enviar para o Celery; se falhar, executa síncrono como fallback."""
    try:
        task_func.delay(*args, **kwargs)
    except Exception:
        # Celery indisponível — executar síncronamente
        logger.debug("Celery indisponível; executando %s síncronamente", task_func.name)
        task_func(*args, **kwargs)


@receiver(post_save, sender=Ticket)
def ticket_created_or_updated(sender, instance, created, **kwargs):
    """Notificações automáticas para tickets"""
    
    if created:
        # 🎫 NOVO TICKET CRIADO
        # WebSocket: notificar todos os agentes disponíveis (leve, fica no signal)
        _safe_group_send(
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
        
        # Criar notificações no banco via Celery (pesado: bulk_create para N agentes)
        from .tasks import notify_agents_new_ticket
        _dispatch_task(notify_agents_new_ticket, instance.id)
    
    else:
        # 🔄 TICKET ATUALIZADO
        _safe_group_send(
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
        
        # Notificar cliente sobre mudanças de status via Celery
        if instance.cliente:
            from .tasks import notify_client_ticket_updated
            _dispatch_task(notify_client_ticket_updated, instance.id)

            # WebSocket imediato para o cliente (leve)
            try:
                client_user = User.objects.get(email=instance.cliente.email)
                _safe_group_send(
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
    _safe_group_send(
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
    
    # Notificações DB para cliente e agente via Celery (pesado)
    from .tasks import notify_interaction
    _dispatch_task(notify_interaction, ticket.id, instance.id, instance.usuario.id)

    # WebSocket imediato para usuários conectados (leve)
    if instance.eh_publico and ticket.cliente:
        try:
            client_user = User.objects.get(email=ticket.cliente.email)
            if client_user != instance.usuario:
                _safe_group_send(
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

    if ticket.agente and ticket.agente != instance.usuario:
        _safe_group_send(
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
    
    _safe_group_send(
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
    
    # WebSocket imediato (leve)
    _safe_group_send(
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
    
    # Notificações DB para supervisores via Celery (pesado: N supervisores)
    from .tasks import send_sla_breach_notifications
    _dispatch_task(send_sla_breach_notifications, ticket.id)


@receiver(post_save, sender=PerfilAgente)
def agent_status_changed(sender, instance, **kwargs):
    """Notificação de mudança de status do agente"""
    
    _safe_group_send(
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
    
    _safe_group_send(
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
                logger.info("SLA configurado para ticket #%s", instance.numero)
                
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
                logger.warning("Nenhuma politica SLA encontrada para ticket #%s", instance.numero)
                
        except Exception as e:
            logger.error("Erro ao configurar SLA para ticket #%s: %s", instance.numero, str(e), exc_info=True)


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
                logger.info("Primeira resposta registrada para ticket #%s", instance.numero)
                
                # Atualiza métricas de SLA
                sla_history = instance.sla_history.first()
                if sla_history:
                    sla_history.first_response_time = instance.first_response_at - instance.criado_em
                    
                    # Verifica se cumpriu o SLA de primeira resposta
                    if instance.first_response_at <= sla_history.first_response_deadline:
                        sla_history.sla_compliance = True
                        logger.info("SLA de primeira resposta cumprido para ticket #%s", instance.numero)
                    else:
                        sla_history.sla_compliance = False
                        logger.error("SLA de primeira resposta violado para ticket #%s", instance.numero)
                    
                    sla_history.save()
                    
        except Ticket.DoesNotExist:
            pass  # Ticket novo, não há nada para comparar
        except Exception as e:
            logger.error("Erro ao rastrear primeira resposta: %s", str(e), exc_info=True)


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
                    logger.info("SLA totalmente cumprido para ticket #%s", instance.numero)
                else:
                    logger.error("SLA violado para ticket #%s", instance.numero)
                    
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
            logger.error("Erro ao rastrear tempo de resolucao: %s", str(e), exc_info=True)


def send_sla_dashboard_update():
    """Envia atualização para o dashboard de SLA"""
    try:
        from .services.sla_monitor import sla_monitor
        
        dashboard_data = sla_monitor.get_sla_dashboard_data()
        
        _safe_group_send(
            "sla_dashboard",
            {
                'type': 'sla_update',
                'data': dashboard_data
            }
        )
        
    except Exception as e:
        logger.error("Erro ao enviar atualizacao do dashboard SLA: %s", str(e), exc_info=True)


# ========== CONTROLE DE ESTOQUE ==========

@receiver(post_save, sender=ItemAtendimento)
def item_atendimento_created(sender, instance, created, **kwargs):
    """Controla estoque quando item é adicionado ao atendimento"""
    
    if created and instance.produto.controla_estoque:
        try:
            # Verificar se existe tipo de movimentação para atendimento
            tipo_movimentacao, created_tipo = TipoMovimentacao.objects.get_or_create(
                nome='Utilização em Atendimento',
                defaults={
                    'tipo_operacao': 'saida',
                    'descricao': 'Saída de produtos utilizados em atendimentos aos clientes',
                    'automatico': True,
                    'ativo': True
                }
            )
            
            # Criar movimentação de saída do estoque
            MovimentacaoEstoque.objects.create(
                tipo_movimentacao=tipo_movimentacao,
                tipo_operacao='saida',
                produto=instance.produto,
                quantidade=instance.quantidade,
                valor_unitario=instance.valor_unitario,
                ticket_relacionado=instance.ticket,
                observacoes=f'Utilização no atendimento #{instance.ticket.numero}: {instance.ticket.titulo}',
                usuario=instance.adicionado_por,
                data_movimentacao=timezone.now()
            )
            
            logger.info("Estoque reduzido: %s (-%s)", instance.produto.nome, instance.quantidade)
            
        except Exception as e:
            logger.error("Erro ao reduzir estoque para item %s: %s", instance.id, str(e), exc_info=True)


@receiver(post_save, sender=ItemAtendimento)
def item_atendimento_updated(sender, instance, created, **kwargs):
    """Atualiza estoque quando item é modificado"""
    
    if not created and instance.produto.controla_estoque:
        # Para atualizações, seria necessário controlar a diferença
        # Por simplicidade, vamos apenas registrar a alteração
        try:
            # Buscar a movimentação original
            movimentacao_original = MovimentacaoEstoque.objects.filter(
                ticket_relacionado=instance.ticket,
                produto=instance.produto,
                tipo_operacao='saida'
            ).order_by('-criado_em').first()
            
            if movimentacao_original:
                # Calcular diferença
                diferenca = instance.quantidade - movimentacao_original.quantidade
                
                if diferenca != 0:
                    # Criar nova movimentação para a diferença
                    tipo_movimentacao = TipoMovimentacao.objects.get(nome='Utilização em Atendimento')
                    
                    MovimentacaoEstoque.objects.create(
                        tipo_movimentacao=tipo_movimentacao,
                        tipo_operacao='saida' if diferenca > 0 else 'entrada',
                        produto=instance.produto,
                        quantidade=abs(diferenca),
                        valor_unitario=instance.valor_unitario,
                        ticket_relacionado=instance.ticket,
                        observacoes=f'Ajuste de quantidade no atendimento #{instance.ticket.numero}',
                        usuario=instance.adicionado_por,
                        data_movimentacao=timezone.now()
                    )
                    
                    logger.info("Estoque ajustado: %s (%s%s)", instance.produto.nome, '+' if diferenca < 0 else '-', abs(diferenca))
                    
        except Exception as e:
            logger.error("Erro ao ajustar estoque para item %s: %s", instance.id, str(e), exc_info=True)


@receiver(pre_delete, sender=ItemAtendimento)
def item_atendimento_deleted(sender, instance, **kwargs):
    """Devolve estoque quando item é removido do atendimento"""
    
    if instance.produto.controla_estoque:
        try:
            # Verificar se existe tipo de movimentação para devolução
            tipo_movimentacao, created_tipo = TipoMovimentacao.objects.get_or_create(
                nome='Devolução de Atendimento',
                defaults={
                    'tipo_operacao': 'entrada',
                    'descricao': 'Devolução de produtos removidos de atendimentos',
                    'automatico': True,
                    'ativo': True
                }
            )
            
            # Criar movimentação de entrada no estoque (devolução)
            MovimentacaoEstoque.objects.create(
                tipo_movimentacao=tipo_movimentacao,
                tipo_operacao='entrada',
                produto=instance.produto,
                quantidade=instance.quantidade,
                valor_unitario=instance.valor_unitario,
                ticket_relacionado=instance.ticket,
                observacoes=f'Devolução do atendimento #{instance.ticket.numero}: item removido',
                usuario=instance.adicionado_por,
                data_movimentacao=timezone.now()
            )
            
            logger.info("Estoque devolvido: %s (+%s)", instance.produto.nome, instance.quantidade)
            
        except Exception as e:
            logger.error("Erro ao devolver estoque para item %s: %s", instance.id, str(e), exc_info=True)


# ---------------------------------------------------------------------------
# Audit signals - login / logout / login_failed
# ---------------------------------------------------------------------------
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed


def _get_ip(request):
    if request is None:
        return "0.0.0.0"
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    if xff:
        return xff.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "0.0.0.0")


@receiver(user_logged_in)
def audit_user_logged_in(sender, request, user, **kwargs):
    """Registrar login bem-sucedido"""
    try:
        from .models.audit import AuditEvent
        AuditEvent.objects.create(
            event_type="login",
            severity="low",
            user=user,
            action="login",
            description=f"Login bem-sucedido: {user.username}",
            ip_address=_get_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
        )
    except Exception as e:
        logger.error("Erro ao registrar audit login: %s", e)


@receiver(user_logged_out)
def audit_user_logged_out(sender, request, user, **kwargs):
    """Registrar logout"""
    try:
        from .models.audit import AuditEvent
        if user:
            AuditEvent.objects.create(
                event_type="logout",
                severity="low",
                user=user,
                action="logout",
                description=f"Logout: {user.username}",
                ip_address=_get_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
            )
    except Exception as e:
        logger.error("Erro ao registrar audit logout: %s", e)


@receiver(user_login_failed)
def audit_user_login_failed(sender, credentials, request, **kwargs):
    """Registrar tentativa de login falha"""
    try:
        from .models.audit import AuditEvent
        username = credentials.get("username", "desconhecido")
        AuditEvent.objects.create(
            event_type="security_event",
            severity="medium",
            action="login_failed",
            description=f"Tentativa de login falha: {username}",
            ip_address=_get_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", "")[:500] if request else "",
            additional_data={"username_attempted": username},
            is_suspicious=True,
        )
    except Exception as e:
        logger.error("Erro ao registrar audit login_failed: %s", e)


# ---------------------------------------------------------------------------
# Audit signals - model changes (Ticket, SLAPolicy)
# ---------------------------------------------------------------------------

@receiver(post_save, sender=Ticket)
def audit_ticket_change(sender, instance, created, **kwargs):
    """Registrar criacao/alteracao de tickets para audit trail"""
    try:
        from .models.audit import AuditEvent
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Ticket)
        AuditEvent.objects.create(
            event_type="create" if created else "update",
            severity="low",
            action="ticket_created" if created else "ticket_updated",
            description=f"Ticket #{instance.numero}: {'criado' if created else 'atualizado'} - {instance.titulo}",
            content_type=ct,
            object_id=instance.pk,
            additional_data={
                "numero": instance.numero,
                "status": instance.status,
                "prioridade": instance.prioridade,
            },
        )
    except Exception as e:
        logger.error("Erro ao registrar audit ticket: %s", e)
