"""Quick check financial data."""
import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django.setup()

from dashboard.models import Ticket, ItemAtendimento, Contrato, Fatura
from django.db.models import Sum, F, DecimalField, ExpressionWrapper

valor_expr = ExpressionWrapper(
    F('quantidade') * F('valor_unitario') * (1 - F('desconto_percentual') / 100),
    output_field=DecimalField(max_digits=12, decimal_places=2)
)

print('=== TICKETS POR STATUS ===')
for s in ['aberto','em_andamento','aguardando_cliente','resolvido','fechado']:
    c = Ticket.objects.filter(status=s).count()
    if c:
        print(f'  {s}: {c}')

print('\n=== ITENS POR STATUS DO TICKET ===')
for s in ['aberto','em_andamento','resolvido','fechado']:
    itens = ItemAtendimento.objects.filter(ticket__status=s)
    c = itens.count()
    total = itens.aggregate(t=Sum(valor_expr))['t'] or 0
    if c:
        print(f'  {s}: {c} itens, R$ {total}')

print('\n=== TICKETS COM ITENS ===')
for t in Ticket.objects.filter(itens_atendimento__isnull=False).distinct().select_related('cliente'):
    itens = t.itens_atendimento.all()
    total = itens.aggregate(t=Sum(valor_expr))['t'] or 0
    nome = t.cliente.nome if t.cliente else '?'
    print(f'  #{t.id} ({t.status}) - {nome} - {itens.count()} itens - R$ {total}')

print(f'\nContratos ativos: {Contrato.objects.filter(status="ativo").count()}')
print(f'Faturas: {Fatura.objects.count()} total')
print(f'  pendentes: {Fatura.objects.filter(status="pendente").count()}')
print(f'  vencidas: {Fatura.objects.filter(status="vencido").count()}')
