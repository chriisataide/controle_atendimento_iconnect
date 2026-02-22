#!/usr/bin/env python
"""
Script para popular o banco de dados com dados realistas de tickets.
Cria: Categorias, Clientes, Agentes, Tickets (vários status/prioridades),
      Interações, SLA Policies, e dados de meses anteriores para alimentar dashboards.
"""

import os
import sys
import django
import random
from datetime import timedelta
from decimal import Decimal

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django.setup()

from django.utils import timezone
from django.contrib.auth.models import User
from dashboard.models import (
    Cliente, Ticket, CategoriaTicket, InteracaoTicket,
    StatusTicket, PrioridadeTicket, PerfilAgente, PerfilUsuario,
    SLAPolicy, Notification,
)

# Desconectar signals que dependem de WebSocket/Channels durante o seed
from django.db.models.signals import post_save, pre_save
receivers_backup = []
for signal in [post_save, pre_save]:
    for receiver in signal.receivers[:]:
        receivers_backup.append((signal, receiver))
    signal.receivers = []
print("  ⚠ Signals desconectados para evitar erros de WebSocket durante seed")

now = timezone.now()

print("=" * 60)
print("  SEED DE DADOS — Módulo de Tickets iConnect")
print("=" * 60)

# ─────────────────────────────────────────────────
# 1. CATEGORIAS DE TICKET
# ─────────────────────────────────────────────────
print("\n[1/7] Criando categorias de ticket...")
categorias_data = [
    {"nome": "Suporte Técnico", "descricao": "Problemas técnicos e manutenção", "cor": "#06b6d4"},
    {"nome": "Financeiro", "descricao": "Dúvidas e problemas financeiros", "cor": "#10b981"},
    {"nome": "Instalação", "descricao": "Instalação e configuração de produtos", "cor": "#8b5cf6"},
    {"nome": "Reclamação", "descricao": "Reclamações e insatisfações", "cor": "#ef4444"},
    {"nome": "Solicitação", "descricao": "Solicitações gerais de serviços", "cor": "#f59e0b"},
    {"nome": "Dúvida", "descricao": "Dúvidas sobre produtos e serviços", "cor": "#3b82f6"},
    {"nome": "Melhoria", "descricao": "Sugestões de melhoria", "cor": "#ec4899"},
]
categorias = []
for cat_data in categorias_data:
    cat, created = CategoriaTicket.objects.get_or_create(
        nome=cat_data["nome"],
        defaults=cat_data,
    )
    categorias.append(cat)
    status = "✓ criada" if created else "  existente"
    print(f"  {status}: {cat.nome}")

# ─────────────────────────────────────────────────
# 2. CLIENTES
# ─────────────────────────────────────────────────
print("\n[2/7] Criando clientes...")
clientes_data = [
    {"nome": "Maria Silva", "email": "maria.silva@techcorp.com.br", "telefone": "(11) 98765-4321", "empresa": "TechCorp"},
    {"nome": "João Santos", "email": "joao.santos@innovatech.com.br", "telefone": "(21) 97654-3210", "empresa": "InnovaTech"},
    {"nome": "Ana Oliveira", "email": "ana.oliveira@megastore.com.br", "telefone": "(31) 96543-2109", "empresa": "MegaStore"},
    {"nome": "Carlos Mendes", "email": "carlos.mendes@startupx.com.br", "telefone": "(41) 95432-1098", "empresa": "StartupX"},
    {"nome": "Fernanda Lima", "email": "fernanda.lima@globalnet.com.br", "telefone": "(51) 94321-0987", "empresa": "GlobalNet"},
    {"nome": "Roberto Alves", "email": "roberto.alves@dataflow.com.br", "telefone": "(61) 93210-9876", "empresa": "DataFlow"},
    {"nome": "Juliana Costa", "email": "juliana.costa@webprime.com.br", "telefone": "(71) 92109-8765", "empresa": "WebPrime"},
    {"nome": "Pedro Nunes", "email": "pedro.nunes@cloudbase.com.br", "telefone": "(81) 91098-7654", "empresa": "CloudBase"},
    {"nome": "Luciana Ferreira", "email": "luciana.ferreira@nexusit.com.br", "telefone": "(91) 90987-6543", "empresa": "NexusIT"},
    {"nome": "Ricardo Souza", "email": "ricardo.souza@alphatech.com.br", "telefone": "(11) 99876-5432", "empresa": "AlphaTech"},
    {"nome": "Camila Rocha", "email": "camila.rocha@bitwise.com.br", "telefone": "(21) 98765-4320", "empresa": "Bitwise"},
    {"nome": "Bruno Martins", "email": "bruno.martins@techcorp.com.br", "telefone": "(31) 97654-3211", "empresa": "TechCorp"},
    {"nome": "Patrícia Gomes", "email": "patricia.gomes@innovatech.com.br", "telefone": "(41) 96543-2100", "empresa": "InnovaTech"},
    {"nome": "Diego Carvalho", "email": "diego.carvalho@megastore.com.br", "telefone": "(51) 95432-1099", "empresa": "MegaStore"},
    {"nome": "Tatiana Ribeiro", "email": "tatiana.ribeiro@globalnet.com.br", "telefone": "(61) 94321-0988", "empresa": "GlobalNet"},
]
clientes = []
for c_data in clientes_data:
    c, created = Cliente.objects.get_or_create(
        email=c_data["email"],
        defaults=c_data,
    )
    clientes.append(c)
print(f"  Total: {len(clientes)} clientes ({Cliente.objects.count()} no banco)")

# ─────────────────────────────────────────────────
# 3. AGENTES (Usuários staff com PerfilAgente)
# ─────────────────────────────────────────────────
print("\n[3/7] Criando agentes de suporte...")
agentes_data = [
    {"username": "agente_marcos", "first_name": "Marcos", "last_name": "Oliveira", "email": "marcos@iconnect.com"},
    {"username": "agente_paula", "first_name": "Paula", "last_name": "Santos", "email": "paula@iconnect.com"},
    {"username": "agente_lucas", "first_name": "Lucas", "last_name": "Ferreira", "email": "lucas@iconnect.com"},
    {"username": "agente_carla", "first_name": "Carla", "last_name": "Mendes", "email": "carla@iconnect.com"},
]
agentes = []
for ag_data in agentes_data:
    user, created = User.objects.get_or_create(
        username=ag_data["username"],
        defaults={
            "first_name": ag_data["first_name"],
            "last_name": ag_data["last_name"],
            "email": ag_data["email"],
            "is_staff": True,
            "is_active": True,
        },
    )
    if created:
        user.set_password("agente123")
        user.save()
    
    perfil, _ = PerfilAgente.objects.get_or_create(
        user=user,
        defaults={
            "status": random.choice(["online", "online", "online", "ocupado", "ausente"]),
            "max_tickets_simultaneos": random.choice([5, 8, 10]),
        }
    )
    # Associar especialidades aleatórias
    if not perfil.especialidades.exists():
        perfil.especialidades.set(random.sample(categorias, k=random.randint(2, 4)))
    
    agentes.append(user)
    status_txt = "✓ criado" if created else "  existente"
    print(f"  {status_txt}: {user.get_full_name()} ({user.username})")

# Incluir admin como agente também
admin_user = User.objects.filter(is_superuser=True).first()
if admin_user:
    PerfilAgente.objects.get_or_create(
        user=admin_user,
        defaults={"status": "online", "max_tickets_simultaneos": 999}
    )
    agentes.append(admin_user)
    print(f"  + admin ({admin_user.username}) registrado como agente")

# ─────────────────────────────────────────────────
# 4. SLA POLICIES
# ─────────────────────────────────────────────────
print("\n[4/7] Criando políticas de SLA...")
sla_data = [
    {"name": "SLA Crítico", "prioridade": "critica", "first_response_time": 30, "resolution_time": 240, "escalation_time": 60, "warning_percentage": 70},
    {"name": "SLA Alta", "prioridade": "alta", "first_response_time": 60, "resolution_time": 480, "escalation_time": 120, "warning_percentage": 75},
    {"name": "SLA Média", "prioridade": "media", "first_response_time": 240, "resolution_time": 1440, "escalation_time": 480, "warning_percentage": 80},
    {"name": "SLA Baixa", "prioridade": "baixa", "first_response_time": 480, "resolution_time": 2880, "escalation_time": 960, "warning_percentage": 85},
]
sla_policies = []
for sla in sla_data:
    policy, created = SLAPolicy.objects.get_or_create(
        prioridade=sla["prioridade"],
        categoria=None,
        defaults={
            "name": sla["name"],
            "first_response_time": sla["first_response_time"],
            "resolution_time": sla["resolution_time"],
            "escalation_time": sla["escalation_time"],
            "warning_percentage": sla["warning_percentage"],
            "escalation_enabled": True,
            "escalation_to": random.choice(agentes),
        }
    )
    sla_policies.append(policy)
    status_txt = "✓ criada" if created else "  existente"
    print(f"  {status_txt}: {policy.name} (Resposta: {policy.first_response_time}min, Resolução: {policy.resolution_time}min)")

# ─────────────────────────────────────────────────
# 5. TICKETS — com distribuição realista ao longo dos últimos 90 dias
# ─────────────────────────────────────────────────
print("\n[5/7] Criando tickets...")

titulos_por_categoria = {
    "Suporte Técnico": [
        "Sistema não carrega após atualização",
        "Erro 500 ao acessar relatórios",
        "Lentidão no módulo de faturamento",
        "Impressora não está imprimindo boletos",
        "Tela congela ao salvar pedido",
        "Conexão com banco de dados instável",
        "Módulo de backup não funciona",
        "Erro ao sincronizar dados com ERP",
        "Problema de autenticação 2FA",
        "API retornando timeout frequente",
    ],
    "Financeiro": [
        "Divergência no valor da fatura",
        "Boleto não gerado corretamente",
        "Solicitação de estorno de pagamento",
        "Nota fiscal com dados incorretos",
        "Dúvida sobre cobrança adicional",
        "Pagamento não reconhecido pelo sistema",
        "Taxa indevida na mensalidade",
    ],
    "Instalação": [
        "Instalação do software em novo servidor",
        "Configuração de ambiente de homologação",
        "Migração de dados do sistema legado",
        "Setup de VPN para acesso remoto",
        "Instalação de módulo adicional",
        "Configuração de certificado SSL",
    ],
    "Reclamação": [
        "Atendimento demorado no último chamado",
        "Problema recorrente não resolvido",
        "SLA não cumprido no ticket anterior",
        "Qualidade do suporte abaixo do esperado",
        "Sistema instável há mais de uma semana",
    ],
    "Solicitação": [
        "Criação de novo usuário no sistema",
        "Reset de senha de administrador",
        "Liberação de acesso ao módulo financeiro",
        "Solicitação de treinamento para equipe",
        "Backup dos dados do último trimestre",
        "Relatório personalizado de vendas",
        "Alteração de permissões de usuário",
    ],
    "Dúvida": [
        "Como exportar relatório em PDF?",
        "Qual o limite de usuários simultâneos?",
        "Como configurar notificações por email?",
        "Integração com WhatsApp está disponível?",
        "Onde encontro o manual do sistema?",
    ],
    "Melhoria": [
        "Sugestão: Adicionar filtro por data nos relatórios",
        "Melhoria: Dashboard mais intuitivo",
        "Sugestão: Notificações push no celular",
        "Melhoria: Modo escuro no sistema",
        "Sugestão: Integração com Google Calendar",
    ],
}

descricoes = [
    "Estou enfrentando este problema desde ontem pela manhã. Já tentei reiniciar o sistema mas continua com o mesmo comportamento. Preciso de ajuda urgente, pois isso está impactando a operação.",
    "O problema acontece de forma intermitente, às vezes funciona normalmente e outras vezes apresenta o erro descrito. Já limpei cache e cookies do navegador mas não resolveu.",
    "Após a última atualização do sistema, notei que essa funcionalidade parou de funcionar corretamente. Antes funcionava perfeitamente.",
    "Preciso que essa solicitação seja atendida com urgência pois afeta diretamente nossa operação comercial. Cerca de 15 colaboradores estão impactados.",
    "Gostaria de solicitar uma melhoria no sistema conforme descrito. Acredito que isso beneficiaria toda a equipe e aumentaria a produtividade.",
    "Já é a terceira vez que abro chamado sobre este assunto. Os dois chamados anteriores foram fechados sem solução definitiva.",
    "O cliente final está reclamando desse problema e precisamos resolver o quanto antes para não perder o contrato.",
    "Estamos em período de fechamento contábil e esse erro está travando todo o processo. Necessitamos resolução imediata.",
    "Observei esse comportamento ontem durante o horário de pico (14h-16h). Anexo prints do erro. Logs do servidor não estão mostrando nada relevante.",
    "Conforme conversado por telefone com o suporte, estou abrindo este ticket para formalizar a solicitação e ter um número de protocolo.",
]

mensagens_interacao = [
    "Olá! Recebi seu ticket e já estou analisando o problema. Vou precisar de mais informações para prosseguir.",
    "Verifiquei os logs do servidor e encontrei o erro mencionado. Estou trabalhando na correção.",
    "Consegui reproduzir o problema no ambiente de testes. A causa raiz está identificada.",
    "A correção foi aplicada no ambiente de homologação. Poderia validar se está tudo correto?",
    "Problema resolvido! A causa era uma configuração incorreta no arquivo de parâmetros do módulo.",
    "Encaminhei para a equipe de desenvolvimento pois requer uma correção no código.",
    "Obrigado pelo retorno. Estarei acompanhando e dou retorno assim que tiver novidades.",
    "Consultei a documentação e o procedimento correto é o descrito abaixo. Segue tutorial.",
    "Realizei o ajuste solicitado. O sistema já deve estar funcionando normalmente.",
    "Agradeço a paciência. Estamos priorizando este ticket internamente.",
    "Identifiquei que o problema está relacionado à última atualização. Vamos reverter temporariamente.",
    "Favor verificar se o problema persiste. Caso positivo, agendar uma sessão remota.",
    "Atualização: a equipe de infraestrutura identificou uma instabilidade no servidor. Correção em andamento.",
    "A solicitação foi encaminhada para aprovação da gerência. Prazo estimado: 2 dias úteis.",
    "Confirmo que o procedimento foi realizado com sucesso. Podemos encerrar este ticket?",
]

# Distribuição de status desejada para os tickets
# Para 90 dias de dados, vamos criar ~150 tickets com distribuição realista
tickets_criados = 0
interacoes_criadas = 0

# Verificar se já existem tickets
existing_count = Ticket.objects.count()
if existing_count > 0:
    print(f"  ⚠ Já existem {existing_count} tickets. Pulando criação para não duplicar.")
else:
    # Criar tickets distribuídos nos últimos 90 dias
    for dias_atras in range(90, -1, -1):
        # Mais tickets em dias úteis, menos no fim de semana
        data_base = now - timedelta(days=dias_atras)
        dia_semana = data_base.weekday()
        
        if dia_semana < 5:  # Seg-Sex
            num_tickets = random.choices([0, 1, 2, 3, 4], weights=[5, 25, 35, 25, 10])[0]
        else:  # Fim de semana
            num_tickets = random.choices([0, 1], weights=[70, 30])[0]
        
        for _ in range(num_tickets):
            categoria = random.choice(categorias)
            cat_nome = categoria.nome
            titulo = random.choice(titulos_por_categoria.get(cat_nome, titulos_por_categoria["Suporte Técnico"]))
            cliente = random.choice(clientes)
            prioridade = random.choices(
                ["baixa", "media", "alta", "critica"],
                weights=[15, 45, 30, 10]
            )[0]
            
            # Status baseado na "idade" do ticket
            if dias_atras > 30:
                # Tickets antigos: maioria fechados/resolvidos
                status = random.choices(
                    ["resolvido", "fechado"],
                    weights=[30, 70]
                )[0]
            elif dias_atras > 14:
                # Tickets de 2-4 semanas: mistura
                status = random.choices(
                    ["em_andamento", "resolvido", "fechado", "aguardando_cliente"],
                    weights=[15, 30, 45, 10]
                )[0]
            elif dias_atras > 3:
                # Tickets recentes (1-2 semanas): mais ativos
                status = random.choices(
                    ["aberto", "em_andamento", "resolvido", "fechado", "aguardando_cliente"],
                    weights=[20, 30, 25, 15, 10]
                )[0]
            else:
                # Tickets muito recentes (últimos 3 dias): muitos abertos
                status = random.choices(
                    ["aberto", "em_andamento", "aguardando_cliente"],
                    weights=[50, 35, 15]
                )[0]
            
            # Hora aleatória em horário comercial (com alguma variação)
            hora = random.choices(
                range(7, 22),
                weights=[2, 8, 12, 15, 15, 12, 10, 8, 6, 5, 3, 2, 1, 1, 1]
            )[0]
            minuto = random.randint(0, 59)
            data_criacao = data_base.replace(hour=hora, minute=minuto, second=random.randint(0, 59))
            
            # Atribuir agente (a maioria tem agente)
            if status in ["aberto"] and random.random() < 0.4:
                agente = None  # Alguns abertos ainda não atribuídos
            else:
                agente = random.choice(agentes)
            
            # Encontrar SLA policy
            sla_policy = next((p for p in sla_policies if p.prioridade == prioridade), None)
            
            ticket = Ticket(
                cliente=cliente,
                agente=agente,
                categoria=categoria,
                titulo=titulo,
                descricao=random.choice(descricoes),
                tags=",".join(random.sample(["urgente", "cliente-vip", "recorrente", "sla", "infraestrutura", "software", "hardware", "rede", "segurança"], k=random.randint(0, 3))),
                status=status,
                prioridade=prioridade,
                origem=random.choices(["web", "email", "whatsapp", "telefone"], weights=[40, 25, 20, 15])[0],
                sla_policy=sla_policy,
            )
            
            # Salvar sem auto_now_add para poder definir criado_em
            ticket.save()
            # Atualizar criado_em diretamente (bypass auto_now_add)
            Ticket.objects.filter(pk=ticket.pk).update(criado_em=data_criacao)
            
            # Definir timestamps de resolução/fechamento
            if status in ["resolvido", "fechado"]:
                tempo_resolucao = timedelta(
                    hours=random.randint(1, 72),
                    minutes=random.randint(0, 59)
                )
                resolvido_em = data_criacao + tempo_resolucao
                if resolvido_em > now:
                    resolvido_em = now - timedelta(hours=random.randint(1, 24))
                
                update_fields = {"resolvido_em": resolvido_em, "atualizado_em": resolvido_em}
                
                if status == "fechado":
                    fechado_em = resolvido_em + timedelta(hours=random.randint(1, 48))
                    if fechado_em > now:
                        fechado_em = now - timedelta(hours=random.randint(0, 12))
                    update_fields["fechado_em"] = fechado_em
                    update_fields["atualizado_em"] = fechado_em
                
                Ticket.objects.filter(pk=ticket.pk).update(**update_fields)
            
            # First response
            if agente and status != "aberto":
                first_resp_delta = timedelta(
                    minutes=random.randint(5, sla_policy.first_response_time if sla_policy else 240)
                )
                first_response_at = data_criacao + first_resp_delta
                if first_response_at > now:
                    first_response_at = data_criacao + timedelta(minutes=random.randint(5, 60))
                Ticket.objects.filter(pk=ticket.pk).update(first_response_at=first_response_at)
            
            # SLA deadlines
            if sla_policy:
                sla_deadline = data_criacao + timedelta(minutes=sla_policy.first_response_time)
                sla_resolution_deadline = data_criacao + timedelta(minutes=sla_policy.resolution_time)
                Ticket.objects.filter(pk=ticket.pk).update(
                    sla_deadline=sla_deadline,
                    sla_resolution_deadline=sla_resolution_deadline,
                )
            
            # Escalation para tickets críticos antigos
            if prioridade == "critica" and status in ["aberto", "em_andamento"] and dias_atras > 2:
                Ticket.objects.filter(pk=ticket.pk).update(
                    is_escalated=True,
                    escalated_to=random.choice(agentes),
                    escalated_at=data_criacao + timedelta(hours=random.randint(1, 4)),
                )
            
            tickets_criados += 1
            
            # --- INTERAÇÕES para este ticket ---
            if status == "aberto":
                num_interacoes = random.randint(0, 2)
            elif status in ["em_andamento", "aguardando_cliente"]:
                num_interacoes = random.randint(1, 5)
            else:
                num_interacoes = random.randint(2, 8)
            
            ticket_obj = Ticket.objects.get(pk=ticket.pk)  # refresh
            for i in range(num_interacoes):
                delta_horas = random.randint(1, max(1, dias_atras * 6))
                data_interacao = data_criacao + timedelta(hours=delta_horas // num_interacoes * (i + 1) if num_interacoes > 0 else delta_horas)
                if data_interacao > now:
                    data_interacao = now - timedelta(minutes=random.randint(1, 60))
                
                # Alternar entre agente e "sistema"
                if agente and random.random() < 0.7:
                    usuario_interacao = agente
                else:
                    usuario_interacao = admin_user or agentes[0]
                
                interacao = InteracaoTicket.objects.create(
                    ticket=ticket_obj,
                    usuario=usuario_interacao,
                    mensagem=random.choice(mensagens_interacao),
                    eh_publico=random.random() < 0.75,
                )
                InteracaoTicket.objects.filter(pk=interacao.pk).update(criado_em=data_interacao)
                interacoes_criadas += 1

    print(f"  ✓ {tickets_criados} tickets criados com {interacoes_criadas} interações")

# ─────────────────────────────────────────────────
# 6. NOTIFICAÇÕES
# ─────────────────────────────────────────────────
print("\n[6/7] Criando notificações...")
notif_count = 0
if admin_user and Notification.objects.count() == 0:
    recent_tickets = Ticket.objects.order_by('-criado_em')[:10]
    for t in recent_tickets:
        Notification.objects.create(
            user=admin_user,
            title=f"Novo ticket #{t.numero}",
            message=f"{t.titulo} - Cliente: {t.cliente.nome}",
            type="new_ticket",
            icon="confirmation_number",
            color=random.choice(["primary", "info", "warning"]),
            read=random.random() < 0.5,
            ticket=t,
        )
        notif_count += 1
    print(f"  ✓ {notif_count} notificações criadas")
else:
    print(f"  ⚠ Notificações já existem ({Notification.objects.count()})")

# ─────────────────────────────────────────────────
# 7. RESUMO FINAL
# ─────────────────────────────────────────────────
print("\n[7/7] Resumo dos dados no banco:")
print(f"  Categorias:    {CategoriaTicket.objects.count()}")
print(f"  Clientes:      {Cliente.objects.count()}")
print(f"  Agentes:       {PerfilAgente.objects.count()}")
print(f"  SLA Policies:  {SLAPolicy.objects.count()}")
print(f"  Tickets:       {Ticket.objects.count()}")
print(f"  Interações:    {InteracaoTicket.objects.count()}")
print(f"  Notificações:  {Notification.objects.count()}")
print(f"  Usuários:      {User.objects.count()}")

# Status breakdown
print("\n  Distribuição de tickets por status:")
for status_val, status_label in StatusTicket.choices:
    count = Ticket.objects.filter(status=status_val).count()
    bar = "█" * (count // 2) if count > 0 else ""
    print(f"    {status_label:20s}: {count:4d} {bar}")

print("\n  Distribuição por prioridade:")
for prio_val, prio_label in PrioridadeTicket.choices:
    count = Ticket.objects.filter(prioridade=prio_val).count()
    bar = "█" * (count // 2) if count > 0 else ""
    print(f"    {prio_label:10s}: {count:4d} {bar}")

print("\n" + "=" * 60)
print("  Seed concluído com sucesso!")
print("=" * 60)

# Restaurar signals
for signal, receiver in receivers_backup:
    signal.receivers.append(receiver)
print("  ✓ Signals restaurados")
