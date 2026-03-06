from dashboard.services.sla_monitor import sla_monitor
data = sla_monitor.get_sla_dashboard_data()
print("TOTAL_ACTIVE:", data.get("total_active_tickets"))
print("SLA_STATS:", data.get("sla_stats"))
print("COMPLIANCE:", data.get("compliance_rate"))
print("CRITICAL_COUNT:", len(data.get("critical_tickets", [])))
print("ALERTS_24H:", data.get("alerts_last_24h"))
print("ESCALATIONS_24H:", data.get("escalations_last_24h"))
for ct in data.get("critical_tickets", []):
    print(f"  CRIT: #{ct['ticket'].numero} status={ct['sla_history'].status} pct={ct['percentage_elapsed']:.1f}%")
