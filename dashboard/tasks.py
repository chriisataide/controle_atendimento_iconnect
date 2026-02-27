"""
Celery Tasks — Tarefas assincronas para o helpdesk iConnect
"""
import json
import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Webhook delivery
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def deliver_webhook(self, endpoint_id: int, event_type: str, payload: dict):
    """Entregar webhook de forma assincrona com retry"""
    from dashboard.models import WebhookEndpoint
    from dashboard.services.webhook_service import WebhookService

    try:
        endpoint = WebhookEndpoint.objects.get(id=endpoint_id, is_active=True)
        delivery = WebhookService._deliver(endpoint, event_type, payload, attempt=self.request.retries + 1)
        if not delivery.success:
            raise Exception(f"Webhook delivery failed: {delivery.response_status}")
    except WebhookEndpoint.DoesNotExist:
        logger.warning(f"Webhook endpoint {endpoint_id} nao encontrado ou inativo")
    except Exception as exc:
        logger.error(f"Webhook delivery error: {exc}")
        self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Email inbound polling
# ---------------------------------------------------------------------------

@shared_task
def check_inbound_emails():
    """Verificar emails inbound de todas as contas configuradas"""
    from dashboard.services.email_inbound_service import email_inbound_service
    count = email_inbound_service.check_all_accounts()
    logger.info(f"Processados {count} emails inbound")
    return count


# ---------------------------------------------------------------------------
# Scheduled rules execution
# ---------------------------------------------------------------------------

@shared_task
def execute_scheduled_rules():
    """Executar regras agendadas ativas"""
    from dashboard.models import ScheduledRule, Ticket
    from django.db.models import Q

    rules = ScheduledRule.objects.filter(is_active=True)
    executed = 0

    for rule in rules:
        try:
            conditions = rule.conditions or {}
            actions = rule.actions or []

            # Construir queryset baseado em conditions
            qs = Ticket.objects.all()

            if 'status' in conditions:
                qs = qs.filter(status=conditions['status'])
            if 'prioridade' in conditions:
                qs = qs.filter(prioridade=conditions['prioridade'])
            if 'older_than_days' in conditions:
                cutoff = timezone.now() - timezone.timedelta(days=conditions['older_than_days'])
                qs = qs.filter(atualizado_em__lt=cutoff)
            if 'no_response_hours' in conditions:
                cutoff = timezone.now() - timezone.timedelta(hours=conditions['no_response_hours'])
                qs = qs.filter(atualizado_em__lt=cutoff, status='aberto')

            tickets = qs[:rule.max_executions_per_hour]

            for ticket in tickets:
                for action in actions:
                    _apply_action(ticket, action)

            rule.last_run = timezone.now()
            rule.run_count += tickets.count()
            rule.save(update_fields=['last_run', 'run_count'])
            executed += 1

        except Exception as e:
            logger.error(f"Erro ao executar regra {rule.nome}: {e}")

    return executed


def _apply_action(ticket, action: dict):
    """Aplicar uma acao a um ticket"""
    action_type = action.get('type')

    if action_type == 'change_status':
        ticket.status = action.get('value', ticket.status)
        ticket.save(update_fields=['status', 'atualizado_em'])

    elif action_type == 'change_priority':
        ticket.prioridade = action.get('value', ticket.prioridade)
        ticket.save(update_fields=['prioridade', 'atualizado_em'])

    elif action_type == 'assign':
        from django.contrib.auth.models import User
        try:
            user = User.objects.get(id=action.get('user_id'))
            ticket.agente = user
            ticket.save(update_fields=['agente', 'atualizado_em'])
        except User.DoesNotExist:
            pass

    elif action_type == 'add_comment':
        from dashboard.models import InteracaoTicket
        InteracaoTicket.objects.create(
            ticket=ticket,
            mensagem=action.get('message', 'Ação automática executada.'),
            tipo='sistema',
            canal='api',
        )

    elif action_type == 'notify':
        logger.info(f"Notificação: {action.get('message')} para ticket {ticket.numero}")

    elif action_type == 'close':
        ticket.status = 'fechado'
        ticket.fechado_em = timezone.now()
        ticket.save(update_fields=['status', 'fechado_em', 'atualizado_em'])


# ---------------------------------------------------------------------------
# Scheduled reports
# ---------------------------------------------------------------------------

@shared_task
def send_scheduled_reports():
    """Enviar relatorios agendados"""
    from dashboard.models import ScheduledReport
    from django.core.mail import EmailMessage

    reports = ScheduledReport.objects.filter(is_active=True)
    sent = 0

    for report in reports:
        if report.next_run and report.next_run > timezone.now():
            continue

        try:
            # Gerar relatório
            content = _generate_report(report)

            # Enviar email
            recipients = report.recipients or []
            if recipients:
                email_msg = EmailMessage(
                    subject=f"[iConnect] Relatório: {report.nome}",
                    body=f"Relatório {report.nome} em anexo.",
                    to=recipients,
                )

                if report.output_format == 'excel':
                    email_msg.attach(
                        f"{report.nome}.xlsx",
                        content,
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    )
                elif report.output_format == 'csv':
                    email_msg.attach(f"{report.nome}.csv", content, 'text/csv')
                elif report.output_format == 'pdf':
                    email_msg.attach(f"{report.nome}.pdf", content, 'application/pdf')

                email_msg.send()

            report.last_sent = timezone.now()
            # Calcular próximo envio
            if report.frequency == 'daily':
                report.next_run = timezone.now() + timezone.timedelta(days=1)
            elif report.frequency == 'weekly':
                report.next_run = timezone.now() + timezone.timedelta(weeks=1)
            elif report.frequency == 'monthly':
                report.next_run = timezone.now() + timezone.timedelta(days=30)
            report.save()
            sent += 1

        except Exception as e:
            logger.error(f"Erro ao enviar relatório {report.nome}: {e}")

    return sent


def _generate_report(report):
    """Gerar conteudo do relatorio"""
    from dashboard.models import Ticket
    from io import BytesIO

    period_days = report.filters.get('days', 30)
    since = timezone.now() - timezone.timedelta(days=period_days)
    tickets = Ticket.objects.filter(criado_em__gte=since)

    if report.output_format == 'excel':
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Tickets"
        ws.append(['Numero', 'Titulo', 'Status', 'Prioridade', 'Criado em'])

        for t in tickets.order_by('-criado_em'):
            ws.append([
                t.numero, t.titulo, t.status, t.prioridade,
                t.criado_em.strftime('%Y-%m-%d %H:%M')
            ])

        output = BytesIO()
        wb.save(output)
        return output.getvalue()

    elif report.output_format == 'csv':
        import csv
        from io import StringIO
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(['Numero', 'Titulo', 'Status', 'Prioridade', 'Criado em'])
        for t in tickets.order_by('-criado_em'):
            writer.writerow([
                t.numero, t.titulo, t.status, t.prioridade,
                t.criado_em.strftime('%Y-%m-%d %H:%M')
            ])
        return output.getvalue()

    return f"Relatório {report.nome}: {tickets.count()} tickets no período."


# ---------------------------------------------------------------------------
# Customer Health Score
# ---------------------------------------------------------------------------

@shared_task
def recalculate_customer_health():
    """Recalcular health scores de todos os clientes"""
    from dashboard.services.customer_health_service import customer_health_service
    return customer_health_service.calculate_all()


# ---------------------------------------------------------------------------
# Gamification
# ---------------------------------------------------------------------------

@shared_task
def update_agent_leaderboard():
    """Atualizar leaderboard de agentes"""
    from dashboard.services.gamification_service import gamification_service
    gamification_service.update_leaderboard()


# ---------------------------------------------------------------------------
# KPI Alerts
# ---------------------------------------------------------------------------

@shared_task
def check_kpi_alerts():
    """Verificar alertas de KPI e notificar"""
    from dashboard.models import KPIAlert, Ticket
    from django.core.mail import send_mail
    from django.db.models import Avg, Count

    alerts = KPIAlert.objects.filter(is_active=True)
    triggered = 0

    for alert in alerts:
        # Cooldown check
        if alert.last_triggered:
            cooldown = timezone.timedelta(minutes=alert.cooldown_minutes)
            if timezone.now() - alert.last_triggered < cooldown:
                continue

        value = None

        if alert.metric == 'open_tickets_above':
            value = Ticket.objects.filter(status='aberto').count()
        elif alert.metric == 'queue_above':
            value = Ticket.objects.filter(status='aberto', agente__isnull=True).count()
        elif alert.metric == 'sla_compliance_below':
            from dashboard.models import SLAViolation
            total = Ticket.objects.filter(
                criado_em__gte=timezone.now() - timezone.timedelta(days=30)
            ).count()
            violations = SLAViolation.objects.filter(
                created_at__gte=timezone.now() - timezone.timedelta(days=30)
            ).count()
            value = round((1 - violations / total) * 100, 1) if total else 100

        if value is not None:
            should_trigger = False
            if 'above' in alert.metric:
                should_trigger = value > alert.threshold
            elif 'below' in alert.metric:
                should_trigger = value < alert.threshold

            if should_trigger:
                # Enviar notificação
                recipients = alert.recipients or []
                if recipients:
                    send_mail(
                        f"[iConnect KPI Alert] {alert.nome}",
                        f"Alerta: {alert.get_metric_display()} {alert.threshold}\nValor atual: {value}",
                        None,
                        recipients,
                        fail_silently=True,
                    )

                alert.last_triggered = timezone.now()
                alert.trigger_count += 1
                alert.save(update_fields=['last_triggered', 'trigger_count'])
                triggered += 1

    return triggered


# ---------------------------------------------------------------------------
# SLA Monitor
# ---------------------------------------------------------------------------

@shared_task
def monitor_sla_breaches():
    """Monitorar violacoes de SLA e disparar webhooks"""
    from dashboard.models import Ticket, SLAViolation
    from dashboard.services.webhook_service import webhook_service

    now = timezone.now()
    at_risk = Ticket.objects.filter(
        status__in=['aberto', 'em_andamento'],
        sla_deadline__isnull=False,
        sla_deadline__lt=now,
    ).exclude(
        id__in=SLAViolation.objects.values_list('ticket_id', flat=True)
    )

    for ticket in at_risk:
        SLAViolation.objects.create(
            ticket=ticket,
            sla_policy=ticket.sla_policy,
            violation_type='response_time',
            hours_exceeded=round((now - ticket.sla_deadline).total_seconds() / 3600, 1),
        )

        webhook_service.trigger_event('sla_breach', {
            'ticket_id': ticket.id,
            'ticket_numero': ticket.numero,
            'ticket_titulo': ticket.titulo,
            'deadline': ticket.sla_deadline.isoformat(),
        })

    return at_risk.count()


# ---------------------------------------------------------------------------
# Signal-offloaded tasks (pesados demais para execução síncrona)
# ---------------------------------------------------------------------------

@shared_task(ignore_result=True)
def notify_agents_new_ticket(ticket_id: int):
    """Cria notificações em banco para todos os agentes ativos (bulk_create).

    Chamada a partir do signal ``ticket_created_or_updated`` para não
    bloquear o request que criou o ticket.
    """
    from dashboard.models import Ticket, Notification, PerfilAgente
    from django.contrib.auth.models import User

    try:
        ticket = Ticket.objects.select_related('categoria').get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return

    agents = User.objects.filter(perfilagente__isnull=False, is_active=True)
    notifications = [
        Notification(
            user=agent,
            title='Novo Ticket Criado',
            message=f'Ticket #{ticket.numero}: {ticket.titulo}',
            type='new_ticket',
            ticket=ticket,
        )
        for agent in agents
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)
    logger.info("notify_agents_new_ticket: %d notificações criadas para ticket #%s",
                len(notifications), ticket.numero)


@shared_task(ignore_result=True)
def notify_client_ticket_updated(ticket_id: int):
    """Notifica o cliente sobre atualização de status do ticket."""
    from dashboard.models import Ticket, Notification
    from django.contrib.auth.models import User

    try:
        ticket = Ticket.objects.get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return

    if not ticket.cliente:
        return

    try:
        client_user = User.objects.get(email=ticket.cliente.email)
        Notification.objects.create(
            user=client_user,
            title='Ticket Atualizado',
            message=f'Seu ticket #{ticket.numero} foi atualizado: {ticket.get_status_display()}',
            type='ticket_status_change',
            ticket=ticket,
        )
    except User.DoesNotExist:
        pass


@shared_task(ignore_result=True)
def notify_interaction(ticket_id: int, interaction_id: int, author_id: int):
    """Notifica agente e/ou cliente sobre nova interação."""
    from dashboard.models import Ticket, InteracaoTicket, Notification
    from django.contrib.auth.models import User

    try:
        ticket = Ticket.objects.get(pk=ticket_id)
        interaction = InteracaoTicket.objects.get(pk=interaction_id)
        author = User.objects.get(pk=author_id)
    except (Ticket.DoesNotExist, InteracaoTicket.DoesNotExist, User.DoesNotExist):
        return

    # Notificar cliente se mensagem pública de agente
    if interaction.eh_publico and ticket.cliente:
        try:
            client_user = User.objects.get(email=ticket.cliente.email)
            if client_user != author:
                Notification.objects.create(
                    user=client_user,
                    title='Nova Resposta no seu Ticket',
                    message=f'Ticket #{ticket.numero}: Nova resposta disponível',
                    type='new_interaction',
                    ticket=ticket,
                )
        except User.DoesNotExist:
            pass

    # Notificar agente atribuído se não for o autor
    if ticket.agente and ticket.agente != author:
        Notification.objects.create(
            user=ticket.agente,
            title='Nova Mensagem no Ticket',
            message=f'Ticket #{ticket.numero}: Nova mensagem adicionada',
            type='new_interaction',
            ticket=ticket,
        )


@shared_task(ignore_result=True)
def send_sla_breach_notifications(ticket_id: int):
    """Notifica supervisores sobre violação de SLA."""
    from dashboard.models import Ticket, Notification
    from django.contrib.auth.models import User

    try:
        ticket = Ticket.objects.get(pk=ticket_id)
    except Ticket.DoesNotExist:
        return

    supervisors = User.objects.filter(is_staff=True, is_active=True)
    notifications = [
        Notification(
            user=sup,
            title='SLA VIOLADO',
            message=f'Ticket #{ticket.numero} excedeu o prazo de atendimento!',
            type='sla_breach',
            ticket=ticket,
        )
        for sup in supervisors
    ]
    if notifications:
        Notification.objects.bulk_create(notifications)


# ---------------------------------------------------------------------------
# Equipment alert checking (runs hourly)
# ---------------------------------------------------------------------------

@shared_task(ignore_result=True)
def check_equipment_alerts():
    """
    Verifica automaticamente equipamentos que ultrapassaram limiares
    de chamados, trocas ou garantia prestes a vencer.
    Roda de hora em hora via Celery Beat ou chamada manual.
    """
    from dashboard.models import (
        Equipamento, HistoricoEquipamento,
        AlertaEquipamento, ConfiguracaoAlertaEquipamento
    )
    from datetime import timedelta

    config = ConfiguracaoAlertaEquipamento.get_config()
    if not config.ativo:
        logger.info("Verificação de alertas de equipamentos desativada.")
        return 0

    agora = timezone.now()
    alertas_criados = 0

    # 1. Excesso de chamados no período
    limite_chamados = agora - timedelta(days=config.chamados_periodo_dias)
    equipamentos_ativos = Equipamento.objects.filter(status='ativo')

    for equip in equipamentos_ativos:
        chamados_periodo = equip.tickets.filter(criado_em__gte=limite_chamados).count()

        if chamados_periodo >= config.chamados_limiar:
            ja_existe = AlertaEquipamento.objects.filter(
                equipamento=equip,
                tipo='excesso_chamados',
                resolvido=False
            ).exists()
            if not ja_existe:
                AlertaEquipamento.objects.create(
                    equipamento=equip,
                    tipo='excesso_chamados',
                    severidade='critical' if chamados_periodo >= config.chamados_limiar * 2 else 'warning',
                    titulo=f'Excesso de chamados: {equip.tipo} {equip.modelo}',
                    descricao=(
                        f'Equipamento {equip.numero_serie} ({equip.tipo} {equip.marca} {equip.modelo}) '
                        f'tem {chamados_periodo} chamados nos últimos {config.chamados_periodo_dias} dias '
                        f'(limiar: {config.chamados_limiar}).'
                    ),
                    valor_atual=chamados_periodo,
                    limiar=config.chamados_limiar,
                )
                alertas_criados += 1
                logger.info(f"Alerta excesso_chamados criado para equipamento {equip.numero_serie}")

    # 2. Troca frequente
    limite_trocas = agora - timedelta(days=config.trocas_periodo_dias)
    for equip in equipamentos_ativos:
        trocas_periodo = equip.historico.filter(
            tipo_movimentacao='troca',
            realizado_em__gte=limite_trocas
        ).count()

        if trocas_periodo >= config.trocas_limiar:
            ja_existe = AlertaEquipamento.objects.filter(
                equipamento=equip,
                tipo='troca_frequente',
                resolvido=False
            ).exists()
            if not ja_existe:
                AlertaEquipamento.objects.create(
                    equipamento=equip,
                    tipo='troca_frequente',
                    severidade='warning',
                    titulo=f'Troca frequente: {equip.tipo} {equip.modelo}',
                    descricao=(
                        f'Equipamento {equip.numero_serie} foi trocado {trocas_periodo} vezes '
                        f'nos últimos {config.trocas_periodo_dias} dias '
                        f'(limiar: {config.trocas_limiar}).'
                    ),
                    valor_atual=trocas_periodo,
                    limiar=config.trocas_limiar,
                )
                alertas_criados += 1
                logger.info(f"Alerta troca_frequente criado para equipamento {equip.numero_serie}")

    # 3. Garantia vencendo
    limite_garantia = (agora + timedelta(days=config.garantia_dias_aviso)).date()
    equips_garantia = Equipamento.objects.filter(
        status='ativo',
        data_garantia__isnull=False,
        data_garantia__lte=limite_garantia,
        data_garantia__gte=agora.date(),
    )
    for equip in equips_garantia:
        ja_existe = AlertaEquipamento.objects.filter(
            equipamento=equip,
            tipo='garantia_vencendo',
            resolvido=False
        ).exists()
        if not ja_existe:
            dias_restantes = (equip.data_garantia - agora.date()).days
            AlertaEquipamento.objects.create(
                equipamento=equip,
                tipo='garantia_vencendo',
                severidade='info' if dias_restantes > 15 else 'warning',
                titulo=f'Garantia vencendo: {equip.tipo} {equip.modelo}',
                descricao=(
                    f'A garantia do equipamento {equip.numero_serie} '
                    f'vence em {dias_restantes} dias ({equip.data_garantia:%d/%m/%Y}).'
                ),
                valor_atual=dias_restantes,
                limiar=config.garantia_dias_aviso,
            )
            alertas_criados += 1
            logger.info(f"Alerta garantia_vencendo criado para equipamento {equip.numero_serie}")

    # Atualizar contadores dos equipamentos
    for equip in Equipamento.objects.filter(status='ativo'):
        equip.atualizar_contadores()

    logger.info(f"Verificação de alertas concluída: {alertas_criados} alertas criados.")
    return alertas_criados


# ---------------------------------------------------------------------------
# LGPD Data Retention — exclusão automática de dados expirados
# ---------------------------------------------------------------------------

@shared_task
def lgpd_data_retention():
    """
    Verifica consentimentos expirados e solicitações de exclusão pendentes.
    Remove dados pessoais conforme LGPD Art. 15 e Art. 16.
    Roda diariamente via Celery Beat.
    """
    from dashboard.models import LGPDConsent, LGPDDataRequest

    now = timezone.now()
    processed = 0

    # 1. Revocar consentimentos expirados automaticamente
    expired_consents = LGPDConsent.objects.filter(
        is_active=True,
        expires_at__isnull=False,
        expires_at__lt=now,
    )
    count = expired_consents.update(is_active=False, revoked_at=now)
    if count:
        logger.info(f"LGPD: {count} consentimentos expirados revogados automaticamente.")
        processed += count

    # 2. Processar solicitações de exclusão pendentes com prazo expirado (15 dias - Art. 18 §5)
    from datetime import timedelta
    overdue_requests = LGPDDataRequest.objects.filter(
        request_type='exclusao',
        status='pendente',
        created_at__lt=now - timedelta(days=15),
    )
    for req in overdue_requests:
        logger.warning(
            f"LGPD: Solicitação de exclusão #{req.id} do titular "
            f"{req.titular_email} está em atraso (>15 dias). Requer ação imediata."
        )
        # Escalar para administradores
        from django.core.mail import mail_admins
        try:
            mail_admins(
                f"[LGPD URGENTE] Solicitação de exclusão em atraso #{req.id}",
                f"A solicitação de exclusão de dados #{req.id} ultrapassou o prazo legal de 15 dias.\n"
                f"Titular: {req.titular_email}\n"
                f"Data da solicitação: {req.created_at:%d/%m/%Y}\n"
                f"Dias em atraso: {(now - req.created_at).days}\n\n"
                f"Ação imediata é necessária para conformidade LGPD.",
                fail_silently=True,
            )
        except Exception:
            pass
        processed += 1

    logger.info(f"LGPD data retention: {processed} itens processados.")
    return processed

