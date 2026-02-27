from django.core.management.base import BaseCommand
from django.utils import timezone
from dashboard.models import (
    WhatsAppBusinessAccount, WhatsAppTemplate, WhatsAppAutoResponse
)


class Command(BaseCommand):
    help = 'Configura dados iniciais para WhatsApp Business'

    def add_arguments(self, parser):
        parser.add_argument(
            '--account-name',
            type=str,
            default='Conta Principal',
            help='Nome da conta WhatsApp Business'
        )
        parser.add_argument(
            '--phone-id',
            type=str,
            help='Phone Number ID do WhatsApp Business'
        )
        parser.add_argument(
            '--business-id',
            type=str,
            help='Business Account ID'
        )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('🔧 Configurando WhatsApp Business...')
        )

        # Criar conta exemplo (se não existir)
        if not WhatsAppBusinessAccount.objects.exists():
            account = WhatsAppBusinessAccount.objects.create(
                nome=options['account_name'],
                phone_number_id=options.get('phone_id', 'PHONE_NUMBER_ID_PLACEHOLDER'),
                business_account_id=options.get('business_id', 'BUSINESS_ACCOUNT_ID_PLACEHOLDER'),
                access_token='YOUR_ACCESS_TOKEN_HERE',
                webhook_verify_token='your_webhook_verify_token',
                webhook_url='https://your-domain.com/api/whatsapp/webhook/',
                ativo=False  # Desabilitado até configurar corretamente
            )
            self.stdout.write(
                self.style.SUCCESS(f'✅ Conta criada: {account.nome}')
            )
        else:
            account = WhatsAppBusinessAccount.objects.first()
            self.stdout.write(
                self.style.WARNING(f'ℹ️  Usando conta existente: {account.nome}')
            )

        # Criar templates de exemplo
        templates_data = [
            {
                'nome': 'boas_vindas',
                'categoria': 'utility',
                'descricao': 'Mensagem de boas-vindas para novos contatos',
                'conteudo': {
                    "type": "text",
                    "text": "Olá! Bem-vindo(a) ao nosso atendimento via WhatsApp. Como posso ajudá-lo(a) hoje?"
                }
            },
            {
                'nome': 'confirmacao_ticket',
                'categoria': 'utility',
                'descricao': 'Confirmação de criação de ticket',
                'conteudo': {
                    "type": "text",
                    "text": "✅ Seu ticket foi criado com sucesso!\n\n🎫 Número: {{ticket_id}}\n📝 Título: {{ticket_title}}\n⏰ Criado em: {{created_at}}\n\nEm breve nossa equipe entrará em contato."
                }
            },
            {
                'nome': 'fora_horario',
                'categoria': 'utility',
                'descricao': 'Mensagem para atendimento fora do horário comercial',
                'conteudo': {
                    "type": "text",
                    "text": "🕐 Nosso horário de atendimento é de segunda a sexta, das 8h às 18h.\n\nSua mensagem foi recebida e será respondida no próximo dia útil. Para urgências, ligue para (11) 99999-9999."
                }
            }
        ]

        for template_data in templates_data:
            template, created = WhatsAppTemplate.objects.get_or_create(
                account=account,
                nome=template_data['nome'],
                defaults={
                    'categoria': template_data['categoria'],
                    'descricao': template_data['descricao'],
                    'conteudo': template_data['conteudo'],
                    'status': 'pending',
                    'ativo': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Template criado: {template.nome}')
                )

        # Criar respostas automáticas
        auto_responses_data = [
            {
                'nome': 'Primeira Mensagem',
                'tipo_trigger': 'first_message',
                'trigger_value': '',
                'mensagem_texto': 'Olá! Obrigado por entrar em contato conosco. Em que posso ajudá-lo(a)?',
                'prioridade': 10
            },
            {
                'nome': 'Fora do Horário',
                'tipo_trigger': 'business_hours',
                'trigger_value': '',
                'mensagem_texto': '🕐 Estamos fora do horário de atendimento. Nossa equipe retornará em breve!',
                'prioridade': 5
            },
            {
                'nome': 'Palavra Ajuda',
                'tipo_trigger': 'keyword',
                'trigger_value': 'ajuda',
                'mensagem_texto': 'Como posso ajudá-lo(a)? Digite uma das opções:\n\n1️⃣ Criar ticket\n2️⃣ Status do ticket\n3️⃣ Falar com atendente\n4️⃣ Informações de contato',
                'prioridade': 8
            },
            {
                'nome': 'Palavra Ticket',
                'tipo_trigger': 'keyword',
                'trigger_value': 'ticket',
                'mensagem_texto': 'Para criar um ticket, descreva seu problema ou necessidade que nossa equipe criará um chamado para você.',
                'prioridade': 7
            }
        ]

        for response_data in auto_responses_data:
            auto_response, created = WhatsAppAutoResponse.objects.get_or_create(
                account=account,
                nome=response_data['nome'],
                defaults={
                    'tipo_trigger': response_data['tipo_trigger'],
                    'trigger_value': response_data['trigger_value'],
                    'mensagem_texto': response_data['mensagem_texto'],
                    'prioridade': response_data['prioridade'],
                    'ativo': True
                }
            )
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Resposta automática criada: {auto_response.nome}')
                )

        self.stdout.write('\n' + '='*50)
        self.stdout.write(
            self.style.SUCCESS('🎉 WhatsApp Business configurado com sucesso!')
        )
        
        self.stdout.write('\n📋 Próximos passos:')
        self.stdout.write('1. Configure as credenciais da API do WhatsApp Business')
        self.stdout.write('2. Atualize o access_token e phone_number_id')
        self.stdout.write('3. Configure o webhook_url para seu domínio')
        self.stdout.write('4. Ative a conta alterando "ativo" para True')
        self.stdout.write('5. Teste o webhook e as respostas automáticas')
        
        self.stdout.write(f'\n🔧 Conta ID: {account.id}')
        self.stdout.write(f'📱 Phone Number ID: {account.phone_number_id}')
        self.stdout.write(f'🌐 Webhook URL: {account.webhook_url}')
        
        self.stdout.write('\n' + '='*50)