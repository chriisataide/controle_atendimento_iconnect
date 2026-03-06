"""Vincula SLA a tickets sem policy e executa monitor"""
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controle_atendimento.settings")
django.setup()

from dashboard.models import SLAPolicy, SLAHistory, SLAAlert, Ticket, StatusTicket
from dashboard.services.sla_calculator import sla_calculator
from dashboard.services.sla_monitor import sla_monitor

# 1) Vincular SLA a tickets ativos sem SLAHistory
active = Ticket.objects.filter(status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO])
print(f"Tickets ativos: {active.count()}")

created_count = 0
for ticket in active:
    existing = SLAHistory.objects.filter(ticket=ticket).exists()
    if not existing:
        sla_history = sla_calculator.create_sla_history(ticket)
        if sla_history:
            print(f"  CRIADO SLAHistory para ticket #{ticket.numero} -> policy={sla_history.sla_policy.name}")
            created_count += 1
        else:
            print(f"  SEM POLICY para ticket #{ticket.numero} (prioridade={ticket.prioridade})")
    else:
        print(f"  OK ticket #{ticket.numero} ja tem SLAHistory")

print(f"\nCriados: {created_count}")

# 2) Executar monitor SLA
print("\nExecutando monitor SLA...")
stats = sla_monitor.monitor_all_tickets()
print(f"Monitorados: {stats.get('tickets_monitored', 0)}")
print(f"Warnings: {stats.get('warnings_sent', 0)}")
print(f"Breaches: {stats.get('breaches_detected', 0)}")
print(f"Escalacoes: {stats.get('escalations_made', 0)}")

# 3) Status final
print("\n=== Estado Final ===")
for h in SLAHistory.objects.select_related("ticket", "sla_policy").all():
    print(f"  Ticket #{h.ticket.numero} | Status SLA: {h.status} | Policy: {h.sla_policy.name} | Deadline resp: {h.first_response_deadline} | Deadline res: {h.resolution_deadline}")
