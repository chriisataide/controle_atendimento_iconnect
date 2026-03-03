"""
Management command para configurar dados exemplo de SLA
"""

from datetime import time

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from dashboard.models import CategoriaTicket, PrioridadeTicket, SLAPolicy, StatusTicket, Ticket
from dashboard.services.sla_calculator import sla_calculator


class Command(BaseCommand):
    help = "Configura dados exemplo para o sistema de SLA"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Remove políticas de SLA existentes antes de criar novas",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("🚀 Configurando sistema SLA..."))

        if options["reset"]:
            self.stdout.write("🗑️  Removendo políticas SLA existentes...")
            SLAPolicy.objects.all().delete()

        # Cria categorias se não existirem
        self.create_categories()

        # Cria políticas SLA
        self.create_sla_policies()

        # Aplica SLA aos tickets existentes
        self.apply_sla_to_existing_tickets()

        self.stdout.write(self.style.SUCCESS("✅ Sistema SLA configurado com sucesso!"))

    def create_categories(self):
        """Cria categorias exemplo se não existirem"""
        categories_data = [
            {"nome": "Suporte Técnico", "descricao": "Problemas técnicos e bugs", "cor": "#dc3545"},
            {"nome": "Suporte Comercial", "descricao": "Questões comerciais e vendas", "cor": "#28a745"},
            {"nome": "Financeiro", "descricao": "Questões financeiras e cobrança", "cor": "#ffc107"},
            {"nome": "Infraestrutura", "descricao": "Problemas de infraestrutura e servidores", "cor": "#6f42c1"},
            {"nome": "Recursos Humanos", "descricao": "Questões de RH e pessoal", "cor": "#17a2b8"},
        ]

        for cat_data in categories_data:
            categoria, created = CategoriaTicket.objects.get_or_create(
                nome=cat_data["nome"], defaults={"descricao": cat_data["descricao"], "cor": cat_data["cor"]}
            )
            if created:
                self.stdout.write(f"📁 Categoria criada: {categoria.nome}")

    def create_sla_policies(self):
        """Cria políticas de SLA padrão"""

        # Busca um supervisor (usuário staff) para escalação
        supervisor = User.objects.filter(is_staff=True, is_active=True).first()
        if not supervisor:
            self.stdout.write(self.style.WARNING("⚠️  Nenhum usuário supervisor encontrado para escalação"))

        # Políticas gerais (sem categoria específica)
        general_policies = [
            {
                "name": "SLA Crítico Geral",
                "prioridade": PrioridadeTicket.CRITICA,
                "first_response_time": 30,  # 30 minutos
                "resolution_time": 240,  # 4 horas
                "escalation_time": 120,  # 2 horas
                "warning_percentage": 70,
            },
            {
                "name": "SLA Alto Geral",
                "prioridade": PrioridadeTicket.ALTA,
                "first_response_time": 120,  # 2 horas
                "resolution_time": 480,  # 8 horas
                "escalation_time": 360,  # 6 horas
                "warning_percentage": 75,
            },
            {
                "name": "SLA Médio Geral",
                "prioridade": PrioridadeTicket.MEDIA,
                "first_response_time": 240,  # 4 horas
                "resolution_time": 1440,  # 24 horas
                "escalation_time": 720,  # 12 horas
                "warning_percentage": 80,
            },
            {
                "name": "SLA Baixo Geral",
                "prioridade": PrioridadeTicket.BAIXA,
                "first_response_time": 480,  # 8 horas
                "resolution_time": 2880,  # 48 horas
                "escalation_time": 1440,  # 24 horas
                "warning_percentage": 85,
            },
        ]

        for policy_data in general_policies:
            policy, created = SLAPolicy.objects.get_or_create(
                categoria=None,
                prioridade=policy_data["prioridade"],
                defaults={
                    "name": policy_data["name"],
                    "first_response_time": policy_data["first_response_time"],
                    "resolution_time": policy_data["resolution_time"],
                    "escalation_time": policy_data["escalation_time"],
                    "warning_percentage": policy_data["warning_percentage"],
                    "escalation_to": supervisor,
                    "start_hour": time(8, 0),
                    "end_hour": time(18, 0),
                    "work_days": "12345",  # Segunda a sexta
                    "business_hours_only": True,
                    "escalation_enabled": True,
                },
            )
            if created:
                self.stdout.write(f"⏰ Política SLA criada: {policy.name}")

        # Políticas específicas por categoria
        suporte_tecnico = CategoriaTicket.objects.filter(nome="Suporte Técnico").first()
        if suporte_tecnico:
            tech_policies = [
                {
                    "name": "SLA Técnico Crítico",
                    "prioridade": PrioridadeTicket.CRITICA,
                    "first_response_time": 15,  # 15 minutos
                    "resolution_time": 120,  # 2 horas
                    "escalation_time": 60,  # 1 hora
                    "warning_percentage": 60,
                },
                {
                    "name": "SLA Técnico Alto",
                    "prioridade": PrioridadeTicket.ALTA,
                    "first_response_time": 60,  # 1 hora
                    "resolution_time": 240,  # 4 horas
                    "escalation_time": 180,  # 3 horas
                    "warning_percentage": 70,
                },
            ]

            for policy_data in tech_policies:
                policy, created = SLAPolicy.objects.get_or_create(
                    categoria=suporte_tecnico,
                    prioridade=policy_data["prioridade"],
                    defaults={
                        "name": policy_data["name"],
                        "first_response_time": policy_data["first_response_time"],
                        "resolution_time": policy_data["resolution_time"],
                        "escalation_time": policy_data["escalation_time"],
                        "warning_percentage": policy_data["warning_percentage"],
                        "escalation_to": supervisor,
                        "start_hour": time(7, 0),  # Suporte técnico 7h-19h
                        "end_hour": time(19, 0),
                        "work_days": "1234567",  # Todos os dias
                        "business_hours_only": False,  # Suporte 24/7 para críticos
                        "escalation_enabled": True,
                    },
                )
                if created:
                    self.stdout.write(f"🔧 Política SLA técnica criada: {policy.name}")

    def apply_sla_to_existing_tickets(self):
        """Aplica SLA aos tickets existentes que não possuem"""
        tickets_sem_sla = Ticket.objects.filter(
            sla_policy__isnull=True,
            status__in=[StatusTicket.ABERTO, StatusTicket.EM_ANDAMENTO, StatusTicket.AGUARDANDO_CLIENTE],
        )

        count = 0
        for ticket in tickets_sem_sla:
            try:
                sla_history = sla_calculator.create_sla_history(ticket)
                if sla_history:
                    count += 1
                    self.stdout.write(f"🎯 SLA aplicado ao ticket #{ticket.numero}")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Erro ao aplicar SLA ao ticket #{ticket.numero}: {str(e)}"))

        if count > 0:
            self.stdout.write(self.style.SUCCESS(f"✅ SLA aplicado a {count} tickets existentes"))
        else:
            self.stdout.write("ℹ️  Nenhum ticket necessita de SLA ou todos já possuem SLA configurado")

    def create_sample_data(self):
        """Cria dados exemplo adicionais se necessário"""
        # Esta função pode ser expandida para criar tickets de exemplo
        # ou outros dados necessários para demonstração do SLA
