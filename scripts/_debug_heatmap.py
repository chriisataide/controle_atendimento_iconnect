import os, sys, django, json
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controle_atendimento.settings")
sys.path.insert(0, "/app")
django.setup()

from dashboard.models import Ticket
from django.db.models import Count
from django.db.models.functions import ExtractWeekDay, ExtractHour

heatmap_qs = (
    Ticket.objects.annotate(dia=ExtractWeekDay("criado_em"), hora=ExtractHour("criado_em"))
    .values("dia", "hora")
    .annotate(count=Count("id"))
)
print("Raw query results:")
for item in heatmap_qs:
    print(f"  dia={item['dia']} hora={item['hora']} count={item['count']}")

heatmap_lookup = {}
for item in heatmap_qs:
    heatmap_lookup[(item["dia"], item["hora"])] = item["count"]

print(f"\nLookup dict: {dict(heatmap_lookup)}")

day_order = [2, 3, 4, 5, 6, 7, 1]
heatmap_data = []
for db_day in day_order:
    linha = []
    for hora in range(0, 24, 2):
        total = sum(heatmap_lookup.get((db_day, h), 0) for h in range(hora, hora + 2))
        linha.append(total)
    heatmap_data.append(linha)

result = json.dumps(heatmap_data)
print(f"\nFinal JSON: {result}")
print(f"Has data: {any(any(v > 0 for v in row) for row in heatmap_data)}")
