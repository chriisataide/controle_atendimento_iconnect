import django, os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django.setup()
from dashboard.models import PontoDeVenda, Ticket
from dashboard.models_equipamento import Equipamento, HistoricoEquipamento

pdv_fields = [f.name for f in PontoDeVenda._meta.get_fields()]
print('PdV has cliente:', 'cliente' in pdv_fields)

ticket_fields = [f.name for f in Ticket._meta.get_fields()]
print('Ticket has ponto_de_venda:', 'ponto_de_venda' in ticket_fields)

equip_fields = [f.name for f in Equipamento._meta.get_fields()]
print('Equip has ponto_de_venda:', 'ponto_de_venda' in equip_fields)
print('Equip has cliente (old):', 'cliente' in equip_fields)

hist_fields = [f.name for f in HistoricoEquipamento._meta.get_fields()]
print('Hist has pdv_anterior:', 'pdv_anterior' in hist_fields)
print('Hist has pdv_novo:', 'pdv_novo' in hist_fields)
print('Hist has cliente_anterior (old):', 'cliente_anterior' in hist_fields)
