"""
Management command para monitoramento automático de SLA
Executa verificações de SLA, envia alertas e realiza escalações
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.services.sla_monitor import sla_monitor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Monitora SLAs dos tickets e executa ações automáticas"

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Exibe informações detalhadas durante a execução",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa em modo simulação (não realiza alterações)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Força execução mesmo que tenha sido executado recentemente",
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        verbose = options["verbose"]
        dry_run = options["dry_run"]
        options["force"]

        if dry_run:
            self.stdout.write(self.style.WARNING("MODO SIMULAÇÃO ATIVADO - Nenhuma alteração será feita"))

        if verbose:
            self.stdout.write(f"Iniciando monitoramento SLA em {start_time}")

        try:
            # Executa o monitoramento
            if not dry_run:
                stats = sla_monitor.monitor_all_tickets()
            else:
                # Em modo dry-run, só coleta informações sem executar ações
                stats = self._simulate_monitoring()

            # Exibe resultados
            self._display_results(stats, verbose)

            # Log da execução
            execution_time = (timezone.now() - start_time).total_seconds()

            if verbose:
                self.stdout.write(f"Monitoramento concluído em {execution_time:.2f}s")

            logger.info(f"SLA monitoring completed: {stats}, execution_time: {execution_time}s")

        except Exception as e:
            error_msg = f"Erro durante monitoramento SLA: {str(e)}"
            self.stdout.write(self.style.ERROR(error_msg))
            logger.error(error_msg, exc_info=True)
            raise

    def _simulate_monitoring(self):
        """Simula o monitoramento sem executar ações"""
        from dashboard.models import StatusTicket, Ticket
        from dashboard.services.sla_calculator import sla_calculator

        active_tickets = Ticket.objects.filter(
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE]
        )

        stats = {"tickets_monitored": 0, "warnings_sent": 0, "breaches_detected": 0, "escalations_made": 0, "errors": 0}

        for ticket in active_tickets:
            stats["tickets_monitored"] += 1

            # Simula verificação de SLA
            sla_history = ticket.sla_history.first()
            if sla_history:
                current_status = sla_calculator.get_sla_status(sla_history)

                if current_status == "warning" and not sla_history.warning_sent:
                    stats["warnings_sent"] += 1
                elif current_status == "breached":
                    stats["breaches_detected"] += 1
                    if sla_history.sla_policy.escalation_enabled and not sla_history.escalated:
                        stats["escalations_made"] += 1

        return stats

    def _display_results(self, stats, verbose):
        """Exibe os resultados da execução"""
        self.stdout.write(self.style.SUCCESS(f"✓ Monitoramento SLA concluído com sucesso!"))

        self.stdout.write(f'  📊 Tickets monitorados: {stats["tickets_monitored"]}')

        if stats["warnings_sent"] > 0:
            self.stdout.write(self.style.WARNING(f'  ⚠️  Alertas enviados: {stats["warnings_sent"]}'))

        if stats["breaches_detected"] > 0:
            self.stdout.write(self.style.ERROR(f'  🚨 Violações detectadas: {stats["breaches_detected"]}'))

        if stats["escalations_made"] > 0:
            self.stdout.write(self.style.HTTP_INFO(f'  📈 Escalações realizadas: {stats["escalations_made"]}'))

        if stats["errors"] > 0:
            self.stdout.write(self.style.ERROR(f'  ❌ Erros encontrados: {stats["errors"]}'))

        if verbose:
            self.stdout.write("\nDetalhes da execução:")
            for key, value in stats.items():
                self.stdout.write(f"  {key}: {value}")
