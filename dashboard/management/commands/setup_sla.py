"""
Management command para criar dados exemplo de SLA
Cria políticas de SLA padrão e configura exemplos
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from dashboard.models import SLAPolicy, CategoriaTicket, PrioridadeTicket


class Command(BaseCommand):
    help = 'Cria dados exemplo para sistema de SLA'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Remove todas as políticas SLA existentes antes de criar novas',
        )

    def handle(self, *args, **options):
        reset = options['reset']

        if reset:
            self.stdout.write('Removendo políticas SLA existentes...')
            SLAPolicy.objects.all().delete()

        self.stdout.write('Criando políticas de SLA padrão...')

        # Busca ou cria categorias
        categoria_tecnico, _ = CategoriaTicket.objects.get_or_create(
            nome='Técnico',
            defaults={'descricao': 'Problemas técnicos e suporte', 'cor': '#007bff'}
        )
        
        categoria_comercial, _ = CategoriaTicket.objects.get_or_create(
            nome='Comercial',
            defaults={'descricao': 'Questões comerciais e vendas', 'cor': '#28a745'}
        )
        
        categoria_financeiro, _ = CategoriaTicket.objects.get_or_create(
            nome='Financeiro',
            defaults={'descricao': 'Questões financeiras e cobrança', 'cor': '#ffc107'}
        )

        # Busca supervisor para escalação (primeiro usuário staff)
        supervisor = User.objects.filter(is_staff=True).first()
        if not supervisor:
            self.stdout.write(
                self.style.WARNING('Nenhum usuário supervisor encontrado. Algumas políticas não terão escalação.')
            )

        # Políticas por prioridade (genéricas)
        policies_data = [
            {
                'name': 'SLA Crítico - Genérico',
                'categoria': None,
                'prioridade': PrioridadeTicket.CRITICA,
                'first_response_time': 15,  # 15 minutos
                'resolution_time': 240,     # 4 horas
                'escalation_time': 120,     # 2 horas
            },
            {
                'name': 'SLA Alto - Genérico',
                'categoria': None,
                'prioridade': PrioridadeTicket.ALTA,
                'first_response_time': 60,  # 1 hora
                'resolution_time': 480,     # 8 horas
                'escalation_time': 360,     # 6 horas
            },
            {
                'name': 'SLA Médio - Genérico',
                'categoria': None,
                'prioridade': PrioridadeTicket.MEDIA,
                'first_response_time': 240, # 4 horas
                'resolution_time': 1440,    # 24 horas
                'escalation_time': 720,     # 12 horas
            },
            {
                'name': 'SLA Baixo - Genérico',
                'categoria': None,
                'prioridade': PrioridadeTicket.BAIXA,
                'first_response_time': 480, # 8 horas
                'resolution_time': 2880,    # 48 horas
                'escalation_time': 1440,    # 24 horas
            }
        ]

        # Políticas específicas por categoria
        specific_policies = [
            # Técnico - tempos mais rápidos
            {
                'name': 'SLA Técnico - Crítico',
                'categoria': categoria_tecnico,
                'prioridade': PrioridadeTicket.CRITICA,
                'first_response_time': 10,  # 10 minutos
                'resolution_time': 120,     # 2 horas
                'escalation_time': 60,      # 1 hora
            },
            {
                'name': 'SLA Técnico - Alto',
                'categoria': categoria_tecnico,
                'prioridade': PrioridadeTicket.ALTA,
                'first_response_time': 30,  # 30 minutos
                'resolution_time': 360,     # 6 horas
                'escalation_time': 240,     # 4 horas
            },
            
            # Comercial - tempos intermediários
            {
                'name': 'SLA Comercial - Crítico',
                'categoria': categoria_comercial,
                'prioridade': PrioridadeTicket.CRITICA,
                'first_response_time': 30,  # 30 minutos
                'resolution_time': 480,     # 8 horas
                'escalation_time': 240,     # 4 horas
            },
            
            # Financeiro - tempos mais longos (apenas prioridade alta)
            {
                'name': 'SLA Financeiro - Alto',
                'categoria': categoria_financeiro,
                'prioridade': PrioridadeTicket.ALTA,
                'first_response_time': 120, # 2 horas
                'resolution_time': 1440,    # 24 horas
                'escalation_time': 720,     # 12 horas
            }
        ]

        # Combina todas as políticas
        all_policies = policies_data + specific_policies

        created_count = 0
        for policy_data in all_policies:
            policy, created = SLAPolicy.objects.get_or_create(
                name=policy_data['name'],
                defaults={
                    'categoria': policy_data['categoria'],
                    'prioridade': policy_data['prioridade'],
                    'first_response_time': policy_data['first_response_time'],
                    'resolution_time': policy_data['resolution_time'],
                    'escalation_time': policy_data['escalation_time'],
                    'business_hours_only': True,
                    'warning_percentage': 80,
                    'escalation_enabled': True,
                    'escalation_to': supervisor,
                    'is_active': True
                }
            )
            
            if created:
                created_count += 1
                categoria_name = policy_data['categoria'].nome if policy_data['categoria'] else 'Genérico'
                self.stdout.write(f'  ✓ {policy.name} ({categoria_name} - {policy.get_prioridade_display()})')

        self.stdout.write(
            self.style.SUCCESS(f'\n✅ {created_count} políticas de SLA criadas com sucesso!')
        )

        # Exibe resumo
        total_policies = SLAPolicy.objects.count()
        active_policies = SLAPolicy.objects.filter(is_active=True).count()
        
        self.stdout.write(f'\n📊 Resumo:')
        self.stdout.write(f'  Total de políticas: {total_policies}')
        self.stdout.write(f'  Políticas ativas: {active_policies}')
        self.stdout.write(f'  Políticas por categoria: {SLAPolicy.objects.filter(categoria__isnull=False).count()}')
        self.stdout.write(f'  Políticas genéricas: {SLAPolicy.objects.filter(categoria__isnull=True).count()}')

        if supervisor:
            escalation_policies = SLAPolicy.objects.filter(escalation_to=supervisor).count()
            self.stdout.write(f'  Políticas com escalação: {escalation_policies}')

        self.stdout.write(
            self.style.HTTP_INFO('\n💡 Para testar o sistema de SLA:')
        )
        self.stdout.write('  1. Crie alguns tickets com diferentes prioridades')
        self.stdout.write('  2. Execute: python manage.py monitor_sla --verbose')
        self.stdout.write('  3. Acesse o dashboard SLA em /dashboard/sla/')
        self.stdout.write('  4. Configure um cron job para executar o monitor automaticamente')
