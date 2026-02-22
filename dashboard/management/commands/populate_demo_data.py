"""
Comando personalizado para popular o sistema com dados de exemplo
"""

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from datetime import datetime, timedelta
import json
from django.utils import timezone
from dashboard.models import Ticket, Cliente, Notification, CategoriaTicket

class Command(BaseCommand):
    help = 'Popula o sistema com dados de exemplo para demonstração'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('🚀 Iniciando população de dados...'))
        
        # Criar alguns clientes de exemplo
        clientes_dados = [
            {
                'nome': 'Tech Solutions LTDA',
                'email': 'contato@techsolutions.com',
                'telefone': '(11) 9999-8888',
                'empresa': 'Tech Solutions LTDA'
            },
            {
                'nome': 'Digital Corp',
                'email': 'suporte@digitalcorp.com.br', 
                'telefone': '(21) 7777-6666',
                'empresa': 'Digital Corp'
            },
            {
                'nome': 'Inovação Sistemas',
                'email': 'admin@inovacao.com',
                'telefone': '(31) 5555-4444',
                'empresa': 'Inovação Sistemas'
            }
        ]
        
        # Criar agentes se não existirem
        if not User.objects.filter(username='agente1').exists():
            agente1 = User.objects.create_user(
                username='agente1',
                first_name='João',
                last_name='Silva',
                email='joao@iconnect.com',
                password='agente123',
                is_staff=True
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Agente criado: {agente1.get_full_name()}'))
        
        if not User.objects.filter(username='agente2').exists():
            agente2 = User.objects.create_user(
                username='agente2',
                first_name='Maria',
                last_name='Santos',
                email='maria@iconnect.com',
                password='agente123',
                is_staff=True
            )
            self.stdout.write(self.style.SUCCESS(f'✅ Agente criado: {agente2.get_full_name()}'))
        
        # Criar clientes
        clientes_criados = []
        for dados in clientes_dados:
            cliente, created = Cliente.objects.get_or_create(
                email=dados['email'],
                defaults=dados
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Cliente criado: {cliente.nome}'))
            clientes_criados.append(cliente)
        
        # Criar categorias de exemplo
        categorias_dados = [
            {'nome': 'Técnico', 'descricao': 'Problemas técnicos e bugs', 'cor': '#dc3545'},
            {'nome': 'Dúvida', 'descricao': 'Dúvidas sobre funcionalidades', 'cor': '#28a745'},
            {'nome': 'Melhoria', 'descricao': 'Solicitações de melhoria', 'cor': '#007bff'},
            {'nome': 'Acesso', 'descricao': 'Problemas de acesso e login', 'cor': '#ffc107'},
        ]
        
        categorias_criadas = []
        for dados in categorias_dados:
            categoria, created = CategoriaTicket.objects.get_or_create(
                nome=dados['nome'],
                defaults=dados
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'✅ Categoria criada: {categoria.nome}'))
            categorias_criadas.append(categoria)
        
        # Criar tickets de exemplo
        agentes = User.objects.filter(is_staff=True)
        tickets_dados = [
            {
                'titulo': 'Sistema lento na tela de relatórios',
                'descricao': 'O sistema está apresentando lentidão significativa na tela de relatórios, principalmente nos filtros avançados. O problema começou após a última atualização.',
                'prioridade': 'alta',
                'categoria_nome': 'Técnico',
                'status': 'aberto'
            },
            {
                'titulo': 'Erro ao gerar backup automático',
                'descricao': 'O backup automático está falhando há 3 dias. Mensagem de erro: "Falha na conexão com servidor de backup". Necessário urgente.',
                'prioridade': 'critica',
                'categoria_nome': 'Técnico',
                'status': 'em_andamento'
            },
            {
                'titulo': 'Dúvida sobre integração com API',
                'descricao': 'Preciso de ajuda para configurar a integração com a API de pagamentos. Seguindo a documentação mas não consigo autenticar.',
                'prioridade': 'media',
                'categoria_nome': 'Dúvida',
                'status': 'aberto'
            },
            {
                'titulo': 'Solicitação de nova funcionalidade - Dashboard',
                'descricao': 'Gostaria de solicitar uma nova funcionalidade no dashboard: gráficos de vendas por região. Seria muito útil para nossa análise.',
                'prioridade': 'baixa',
                'categoria_nome': 'Melhoria',
                'status': 'aberto'
            },
            {
                'titulo': 'Problema no login - usuário bloqueado',
                'descricao': 'Meu usuário foi bloqueado após várias tentativas de login. Não consigo acessar o sistema. Por favor, desbloqueiem.',
                'prioridade': 'alta',
                'categoria_nome': 'Acesso',
                'status': 'fechado'
            }
        ]
        
        # Criar tickets
        for i, dados in enumerate(tickets_dados):
            cliente = clientes_criados[i % len(clientes_criados)]
            agente = agentes[i % len(agentes)] if agentes.exists() else None
            categoria = CategoriaTicket.objects.get(nome=dados['categoria_nome'])
            
            # Ajustar datas para simular tickets em diferentes períodos
            dias_atras = i * 2 + 1
            data_criacao = timezone.now() - timedelta(days=dias_atras)
            
            ticket = Ticket.objects.create(
                titulo=dados['titulo'],
                descricao=dados['descricao'],
                prioridade=dados['prioridade'],
                categoria=categoria,
                status=dados['status'],
                cliente=cliente,
                agente=agente,
                criado_em=data_criacao,
                atualizado_em=data_criacao
            )
            
            # Para tickets fechados, simular tempo de resolução
            if dados['status'] == 'fechado':
                # Adicionar campo resolution_time_hours se existir
                try:
                    tempo_resolucao = 4 + (i * 2)  # Entre 4-12 horas
                    if hasattr(ticket, 'resolution_time_hours'):
                        ticket.resolution_time_hours = tempo_resolucao
                        ticket.save()
                except (AttributeError, Exception):
                    pass  # Ignore se o campo não existir
            
            self.stdout.write(self.style.SUCCESS(f'✅ Ticket criado: {ticket.titulo}'))
        
        # Criar algumas notificações de exemplo
        for user in User.objects.filter(is_staff=True)[:2]:
            Notification.objects.create(
                user=user,
                type='TICKET_NEW',
                title='Novo ticket recebido',
                message='Um novo ticket de alta prioridade foi criado e atribuído a você.',
                icon='fas fa-ticket-alt',
                color='success'
            )
            
            Notification.objects.create(
                user=user,
                type='SYSTEM',
                title='Atualização do sistema',
                message='O sistema iConnect foi atualizado com novas funcionalidades.',
                icon='fas fa-system',
                color='info'
            )
        
        self.stdout.write(self.style.SUCCESS('🎉 População de dados concluída!'))
        self.stdout.write(self.style.WARNING('📝 Credenciais dos agentes:'))
        self.stdout.write(self.style.WARNING('   • Usuário: agente1, Senha: agente123'))
        self.stdout.write(self.style.WARNING('   • Usuário: agente2, Senha: agente123'))
        self.stdout.write(self.style.SUCCESS('🌐 Acesse: http://localhost:8000'))
