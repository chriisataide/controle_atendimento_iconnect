"""
Management command para monitorar SLA
Este comando deve ser executado periodicamente (ex: a cada 5 minutos) via cron
"""

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.services.sla_monitor import sla_monitor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Monitora SLA de todos os tickets ativos e executa alertas/escalações"

    def add_arguments(self, parser):
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Exibe informações detalhadas durante a execução",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Executa em modo de teste (não envia alertas nem faz escalações)",
        )

    def handle(self, *args, **options):
        start_time = timezone.now()
        self.verbose = options["verbose"]
        self.dry_run = options["dry_run"]

        if self.dry_run:
            self.stdout.write(self.style.WARNING("🧪 MODO TESTE - Nenhuma ação será executada"))

        if self.verbose:
            self.stdout.write(f'⏰ Iniciando monitoramento SLA em {start_time.strftime("%Y-%m-%d %H:%M:%S")}')

        try:
            # Executa o monitoramento
            if self.dry_run:
                stats = self._dry_run_monitor()
            else:
                stats = sla_monitor.monitor_all_tickets()

            # Calcula tempo de execução
            execution_time = timezone.now() - start_time

            # Exibe resultados
            self._display_results(stats, execution_time)

            # Log dos resultados
            logger.info(f"SLA Monitor executado: {stats}")

        except Exception as e:
            error_msg = f"Erro durante monitoramento SLA: {str(e)}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            logger.error(error_msg, exc_info=True)
            return

    def _dry_run_monitor(self):
        """Executa monitoramento em modo teste"""
        from dashboard.models import StatusTicket, Ticket
        from dashboard.services.sla_calculator import sla_calculator

        stats = {"tickets_monitored": 0, "warnings_sent": 0, "breaches_detected": 0, "escalations_made": 0, "errors": 0}

        # Busca tickets ativos
        active_tickets = Ticket.objects.filter(
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE]
        ).select_related("sla_policy", "agente", "categoria", "cliente")

        for ticket in active_tickets:
            try:
                stats["tickets_monitored"] += 1

                # Simula verificação de SLA
                policy = sla_calculator.get_sla_policy(ticket)
                if not policy:
                    if self.verbose:
                        self.stdout.write(f"⚠️  Ticket #{ticket.numero} sem política SLA")
                    continue

                # Simula cálculo de status
                from dashboard.models import SLAHistory

                sla_history = SLAHistory.objects.filter(ticket=ticket).first()
                if sla_history:
                    current_status = sla_calculator.get_sla_status(sla_history)

                    if current_status == "warning":
                        stats["warnings_sent"] += 1
                        if self.verbose:
                            self.stdout.write(f"⚠️  Ticket #{ticket.numero} precisa de alerta")

                    elif current_status == "breached":
                        stats["breaches_detected"] += 1
                        if self.verbose:
                            self.stdout.write(f"🚨 Ticket #{ticket.numero} violou SLA")

                        # Verifica se precisaria escalar
                        if (
                            policy.escalation_enabled
                            and not sla_history.escalated
                            and sla_monitor.should_escalate(sla_history)
                        ):
                            stats["escalations_made"] += 1
                            if self.verbose:
                                self.stdout.write(f"📈 Ticket #{ticket.numero} precisaria ser escalado")

                if self.verbose:
                    self.stdout.write(f"✅ Ticket #{ticket.numero} monitorado")

            except Exception as e:
                stats["errors"] += 1
                if self.verbose:
                    self.stdout.write(f"❌ Erro no ticket #{ticket.numero}: {str(e)}")

        return stats

    def _display_results(self, stats, execution_time):
        """Exibe os resultados do monitoramento"""
        self.stdout.write(self.style.SUCCESS("\n📊 RESULTADOS DO MONITORAMENTO SLA"))
        self.stdout.write("=" * 50)

        # Estatísticas principais
        self.stdout.write(f'🎫 Tickets monitorados: {stats["tickets_monitored"]}')
        self.stdout.write(f'⚠️  Alertas enviados: {stats["warnings_sent"]}')
        self.stdout.write(f'🚨 Violações detectadas: {stats["breaches_detected"]}')
        self.stdout.write(f'📈 Escalações realizadas: {stats["escalations_made"]}')

        if stats["errors"] > 0:
            self.stdout.write(self.style.ERROR(f'❌ Erros: {stats["errors"]}'))

        # Tempo de execução
        exec_seconds = execution_time.total_seconds()
        self.stdout.write(f"⏱️  Tempo de execução: {exec_seconds:.2f} segundos")

        # Status geral
        if stats["errors"] == 0:
            self.stdout.write(self.style.SUCCESS("\n✅ Monitoramento concluído com sucesso!"))
        else:
            self.stdout.write(self.style.WARNING("\n⚠️  Monitoramento concluído com alguns erros"))

        # Recomendações
        if stats["breaches_detected"] > 0:
            self.stdout.write(
                self.style.WARNING(f'\n📋 AÇÃO NECESSÁRIA: {stats["breaches_detected"]} ticket(s) violaram SLA')
            )

        if stats["warnings_sent"] > 0:
            self.stdout.write(
                self.style.WARNING(f'📋 ATENÇÃO: {stats["warnings_sent"]} ticket(s) próximos do vencimento')
            )

    def _get_summary_stats(self):
        """Obtém estatísticas resumidas para exibição"""
        try:
            dashboard_data = sla_monitor.get_sla_dashboard_data()

            self.stdout.write("\n📈 RESUMO DO SISTEMA SLA")
            self.stdout.write("-" * 30)
            self.stdout.write(f'Total de tickets ativos: {dashboard_data.get("total_active_tickets", 0)}')

            sla_stats = dashboard_data.get("sla_stats", {})
            self.stdout.write(f'No prazo: {sla_stats.get("on_track", 0)}')
            self.stdout.write(f'Em alerta: {sla_stats.get("warnings", 0)}')
            self.stdout.write(f'Violados: {sla_stats.get("breached", 0)}')
            self.stdout.write(f'Escalados: {sla_stats.get("escalated", 0)}')

            compliance_rate = dashboard_data.get("compliance_rate", 0)
            self.stdout.write(f"Taxa de compliance: {compliance_rate:.1f}%")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Erro ao obter estatísticas: {str(e)}"))
