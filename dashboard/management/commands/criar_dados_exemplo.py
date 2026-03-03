import random
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from dashboard.models import CategoriaTicket, Cliente, InteracaoTicket, PerfilAgente, Ticket


class Command(BaseCommand):
    help = "Cria dados de exemplo para o sistema de atendimento"

    def handle(self, *args, **options):
        # Criar categorias
        categorias = [
            ("Suporte Técnico", "Problemas técnicos e bugs", "#dc3545"),
            ("Dúvida Comercial", "Informações sobre produtos e vendas", "#28a745"),
            ("Solicitação de Feature", "Pedidos de novas funcionalidades", "#007bff"),
            ("Cancelamento", "Solicitações de cancelamento", "#ffc107"),
        ]

        categoria_objects = []
        for nome, desc, cor in categorias:
            categoria, created = CategoriaTicket.objects.get_or_create(
                nome=nome, defaults={"descricao": desc, "cor": cor}
            )
            categoria_objects.append(categoria)
            if created:
                self.stdout.write(f"Categoria criada: {nome}")

        # Criar clientes
        clientes_data = [
            ("João Silva", "joao.silva@email.com", "(11) 98765-4321", "Empresa ABC"),
            ("Maria Santos", "maria.santos@email.com", "(21) 99876-5432", "Tech Corp"),
            ("Pedro Oliveira", "pedro.oliveira@email.com", "(31) 97654-3210", "StartupXYZ"),
            ("Ana Costa", "ana.costa@email.com", "(41) 96543-2109", "Inovação Ltda"),
            ("Carlos Souza", "carlos.souza@email.com", "(51) 95432-1098", "Digital Solutions"),
        ]

        cliente_objects = []
        for nome, email, telefone, empresa in clientes_data:
            cliente, created = Cliente.objects.get_or_create(
                email=email, defaults={"nome": nome, "telefone": telefone, "empresa": empresa}
            )
            cliente_objects.append(cliente)
            if created:
                self.stdout.write(f"Cliente criado: {nome}")

        # Criar agentes
        agentes_data = [
            ("carlos.agente", "carlos.agente@iconnect.com", "Carlos", "Oliveira"),
            ("ana.agente", "ana.agente@iconnect.com", "Ana", "Costa"),
            ("pedro.agente", "pedro.agente@iconnect.com", "Pedro", "Souza"),
        ]

        agente_objects = []
        for username, email, first_name, last_name in agentes_data:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"email": email, "first_name": first_name, "last_name": last_name, "is_staff": True},
            )
            if created:
                user.set_password("123456")
                user.save()

            perfil, perfil_created = PerfilAgente.objects.get_or_create(
                user=user,
                defaults={
                    "status": random.choice(["online", "ocupado", "ausente"]),
                    "max_tickets_simultaneos": random.randint(3, 7),
                },
            )

            agente_objects.append(user)
            if created:
                self.stdout.write(f"Agente criado: {first_name} {last_name}")

        # Criar tickets
        tickets_data = [
            ("Erro no sistema de login", "Não consigo acessar minha conta, aparece erro 500", "alta", "resolvido"),
            ("Dúvida sobre preços", "Gostaria de saber sobre os planos disponíveis", "media", "em_andamento"),
            ("Solicitação de nova feature", "Seria possível adicionar relatórios customizados?", "baixa", "aberto"),
            ("Problema com pagamento", "Cobrança duplicada no cartão de crédito", "critica", "em_andamento"),
            ("Bug no mobile", "App trava ao tentar fazer upload de arquivos", "alta", "aberto"),
            ("Cancelamento de conta", "Gostaria de cancelar minha assinatura", "media", "aguardando_cliente"),
            ("Lentidão no sistema", "Sistema muito lento para carregar relatórios", "media", "resolvido"),
        ]

        for i, (titulo, descricao, prioridade, status) in enumerate(tickets_data):
            cliente = random.choice(cliente_objects)
            categoria = random.choice(categoria_objects)
            agente = random.choice(agente_objects) if random.choice([True, False]) else None

            # Calcular datas
            dias_atras = random.randint(1, 30)
            criado_em = timezone.now() - timedelta(days=dias_atras)

            ticket, created = Ticket.objects.get_or_create(
                titulo=titulo,
                cliente=cliente,
                defaults={
                    "descricao": descricao,
                    "categoria": categoria,
                    "agente": agente,
                    "prioridade": prioridade,
                    "status": status,
                    "criado_em": criado_em,
                },
            )

            if created:
                # Criar algumas interações
                if agente:
                    InteracaoTicket.objects.create(
                        ticket=ticket,
                        usuario=agente,
                        mensagem=f"Ticket atribuído para {agente.get_full_name()}. Analisando o problema...",
                        eh_publico=True,
                        criado_em=criado_em + timedelta(hours=1),
                    )

                if status in ["resolvido", "fechado"]:
                    InteracaoTicket.objects.create(
                        ticket=ticket,
                        usuario=agente or random.choice(agente_objects),
                        mensagem="Problema resolvido com sucesso. Cliente satisfeito.",
                        eh_publico=True,
                        criado_em=criado_em + timedelta(days=1),
                    )

                self.stdout.write(f"Ticket criado: #{ticket.numero} - {titulo}")

        self.stdout.write(self.style.SUCCESS(f"""
Dados de exemplo criados com sucesso!
- {CategoriaTicket.objects.count()} categorias
- {Cliente.objects.count()} clientes  
- {User.objects.filter(perfilagente__isnull=False).count()} agentes
- {Ticket.objects.count()} tickets
- {InteracaoTicket.objects.count()} interações

Para acessar o admin: http://127.0.0.1:8000/admin/
Usuário: admin
Senha: (a que você definiu)

Agentes criados (senha: 123456):
- carlos.agente
- ana.agente  
- pedro.agente
                """))
