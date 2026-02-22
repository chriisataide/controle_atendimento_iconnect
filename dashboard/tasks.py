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
