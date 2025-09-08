"""
Script para criar dados iniciais do sistema iConnect
"""
import os
import sys
import django
from datetime import datetime, timedelta

# Configura o Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django.setup()

from django.contrib.auth.models import User
from dashboard.models import (
    Cliente, CategoriaTicket, Ticket, PerfilAgente,
    SLAPolicy, WorkflowRule, KnowledgeBase, SystemMetrics
)

def create_sample_data():
    print("🔄 Criando dados iniciais do sistema iConnect...")
    
    # 1. Criar usuários
    if not User.objects.filter(username='admin').exists():
        admin = User.objects.create_superuser(
            username='admin',
            email='admin@iconnect.com',
            password='admin123',
            first_name='Administrador',
            last_name='Sistema'
        )
        print(f"✅ Usuário admin criado")
    
    if not User.objects.filter(username='agente1').exists():
        agente1 = User.objects.create_user(
            username='agente1',
            email='agente1@iconnect.com',
            password='agente123',
            first_name='João',
            last_name='Silva'
        )
        print(f"✅ Usuário agente1 criado")
    
    # 2. Criar categorias
    categorias_data = [
        {'nome': 'Suporte Técnico', 'descricao': 'Problemas técnicos e bugs'},
        {'nome': 'Financeiro', 'descricao': 'Questões de cobrança e pagamento'},
        {'nome': 'Dúvidas', 'descricao': 'Dúvidas gerais sobre produtos/serviços'},
        {'nome': 'Reclamação', 'descricao': 'Reclamações e feedbacks negativos'},
        {'nome': 'Elogio', 'descricao': 'Elogios e feedbacks positivos'},
    ]
    
    for cat_data in categorias_data:
        categoria, created = CategoriaTicket.objects.get_or_create(
            nome=cat_data['nome'],
            defaults={'descricao': cat_data['descricao']}
        )
        if created:
            print(f"✅ Categoria '{categoria.nome}' criada")
    
    # 3. Criar clientes
    clientes_data = [
        {
            'nome': 'Maria Santos',
            'email': 'maria.santos@email.com',
            'telefone': '(11) 98765-4321',
            'empresa': 'Empresa ABC Ltda'
        },
        {
            'nome': 'José Silva',
            'email': 'jose.silva@email.com',
            'telefone': '(11) 91234-5678',
            'empresa': 'Tech Solutions Inc'
        },
        {
            'nome': 'Ana Costa',
            'email': 'ana.costa@email.com',
            'telefone': '(11) 95555-1234',
            'empresa': 'Digital Marketing Pro'
        }
    ]
    
    for cliente_data in clientes_data:
        cliente, created = Cliente.objects.get_or_create(
            email=cliente_data['email'],
            defaults=cliente_data
        )
        if created:
            print(f"✅ Cliente '{cliente.nome}' criado")
    
    # 4. Criar perfis de agente
    agentes = User.objects.filter(username__in=['agente1', 'admin'])
    for user in agentes:
        perfil, created = PerfilAgente.objects.get_or_create(
            user=user,
            defaults={
                'status': 'disponivel',
                'max_tickets_simultaneos': 10
            }
        )
        if created:
            print(f"✅ Perfil do agente '{user.first_name}' criado")
    
    # 5. Criar políticas de SLA
    sla_policies_data = [
        {
            'name': 'SLA Crítico',
            'prioridade': 'critica',
            'response_time_hours': 1,
            'resolution_time_hours': 4,
            'business_hours_only': False,
            'categoria': CategoriaTicket.objects.get(nome='Suporte Técnico')
        },
        {
            'name': 'SLA Alta',
            'prioridade': 'alta',
            'response_time_hours': 2,
            'resolution_time_hours': 8,
            'business_hours_only': True,
            'categoria': CategoriaTicket.objects.get(nome='Financeiro')
        },
        {
            'name': 'SLA Normal',
            'prioridade': 'normal',
            'response_time_hours': 4,
            'resolution_time_hours': 24,
            'business_hours_only': True,
            'categoria': None
        }
    ]
    
    for sla_data in sla_policies_data:
        sla, created = SLAPolicy.objects.get_or_create(
            name=sla_data['name'],
            defaults=sla_data
        )
        if created:
            print(f"✅ Política SLA '{sla.name}' criada")
    
    # 6. Criar regras de workflow
    workflow_rules_data = [
        {
            'name': 'Auto-atribuir tickets críticos',
            'description': 'Atribui automaticamente tickets críticos para o melhor agente disponível',
            'trigger_event': 'ticket_created',
            'conditions': {
                'prioridade': 'critica'
            },
            'actions': {
                'assign_to_best_agent': True,
                'send_notification': ['email', 'slack']
            },
            'priority': 1,
            'is_active': True
        },
        {
            'name': 'Notificar violação de SLA',
            'description': 'Envia notificação quando SLA está próximo do vencimento',
            'trigger_event': 'sla_warning',
            'conditions': {
                'sla_remaining_hours': 1
            },
            'actions': {
                'notify_supervisor': True,
                'send_notification': ['email', 'whatsapp']
            },
            'priority': 2,
            'is_active': True
        }
    ]
    
    for rule_data in workflow_rules_data:
        rule, created = WorkflowRule.objects.get_or_create(
            name=rule_data['name'],
            defaults=rule_data
        )
        if created:
            print(f"✅ Regra de workflow '{rule.name}' criada")
    
    # 7. Criar base de conhecimento
    kb_data = [
        {
            'title': 'Como redefinir senha',
            'content': '''
            Para redefinir sua senha, siga os passos:
            1. Clique em "Esqueci minha senha" na tela de login
            2. Digite seu email cadastrado
            3. Verifique seu email e clique no link recebido
            4. Digite uma nova senha segura
            5. Confirme a nova senha
            ''',
            'keywords': ['senha', 'redefinir', 'login', 'esqueci'],
            'category': 'Acesso',
            'is_public': True,
            'created_by': User.objects.get(username='admin')
        },
        {
            'title': 'Problemas de conectividade',
            'content': '''
            Se você está enfrentando problemas de conexão:
            1. Verifique sua conexão com a internet
            2. Tente acessar outros sites
            3. Limpe o cache do seu navegador
            4. Tente usar outro navegador
            5. Reinicie seu roteador se necessário
            ''',
            'keywords': ['conexão', 'internet', 'conectividade', 'offline'],
            'category': 'Técnico',
            'is_public': True,
            'created_by': User.objects.get(username='admin')
        }
    ]
    
    for kb_item in kb_data:
        kb, created = KnowledgeBase.objects.get_or_create(
            title=kb_item['title'],
            defaults=kb_item
        )
        if created:
            print(f"✅ Artigo da base de conhecimento '{kb.title}' criado")
    
    # 8. Criar métricas iniciais
    today = datetime.now().date()
    metrics, created = SystemMetrics.objects.get_or_create(
        date=today,
        defaults={
            'total_tickets': 0,
            'new_tickets': 0,
            'resolved_tickets': 0,
            'sla_compliance_rate': 95.0,
            'avg_resolution_time': 4.5,
            'customer_satisfaction': 4.2,
            'agent_productivity': {
                'tickets_per_agent': 12,
                'avg_response_time': 2.3
            }
        }
    )
    if created:
        print(f"✅ Métricas do sistema criadas para {today}")
    
    # 9. Criar alguns tickets de exemplo
    agente1 = User.objects.get(username='agente1')
    cliente1 = Cliente.objects.first()
    categoria_suporte = CategoriaTicket.objects.get(nome='Suporte Técnico')
    
    tickets_data = [
        {
            'titulo': 'Sistema lento após atualização',
            'descricao': 'Após a última atualização, o sistema ficou muito lento para carregar as páginas.',
            'prioridade': 'alta',
            'status': 'aberto',
            'cliente': cliente1,
            'categoria': categoria_suporte,
            'agente': agente1,
            'origem': 'web'
        },
        {
            'titulo': 'Erro ao gerar relatório',
            'descricao': 'Quando tento gerar o relatório mensal, aparece uma mensagem de erro.',
            'prioridade': 'normal',
            'status': 'em_andamento',
            'cliente': Cliente.objects.all()[1],
            'categoria': categoria_suporte,
            'agente': agente1,
            'origem': 'email'
        }
    ]
    
    for i, ticket_data in enumerate(tickets_data, 1):
        if not Ticket.objects.filter(titulo=ticket_data['titulo']).exists():
            ticket = Ticket.objects.create(**ticket_data)
            print(f"✅ Ticket de exemplo #{ticket.numero} criado")
    
    print("\n🎉 Dados iniciais criados com sucesso!")
    print("\n📋 Resumo do que foi criado:")
    print(f"   • {User.objects.count()} usuários")
    print(f"   • {CategoriaTicket.objects.count()} categorias")
    print(f"   • {Cliente.objects.count()} clientes")
    print(f"   • {PerfilAgente.objects.count()} perfis de agente")
    print(f"   • {SLAPolicy.objects.count()} políticas de SLA")
    print(f"   • {WorkflowRule.objects.count()} regras de workflow")
    print(f"   • {KnowledgeBase.objects.count()} artigos na base de conhecimento")
    print(f"   • {Ticket.objects.count()} tickets de exemplo")
    print("\n🔐 Credenciais de acesso:")
    print("   • Admin: username=admin, password=admin123")
    print("   • Agente: username=agente1, password=agente123")

if __name__ == '__main__':
    create_sample_data()
