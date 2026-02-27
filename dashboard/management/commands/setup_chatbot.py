from django.core.management.base import BaseCommand
from dashboard.models import ChatbotConfiguration, ChatbotKnowledgeBase


class Command(BaseCommand):
    help = 'Popula dados iniciais do chatbot IA'

    def handle(self, *args, **options):
        self.stdout.write('Criando configurações iniciais do chatbot...')
        
        # Configurações iniciais
        configs = [
            ('confidence_threshold', '0.7', 'float', 'Limite mínimo de confiança para respostas automáticas'),
            ('max_suggestions', '3', 'integer', 'Número máximo de sugestões por resposta'),
            ('enable_training', 'true', 'boolean', 'Habilitar aprendizado automático'),
            ('welcome_message', 'Olá! 👋 Sou o assistente virtual da iConnect. Como posso ajudá-lo hoje?', 'string', 'Mensagem de boas-vindas'),
            ('transfer_threshold', '0.3', 'float', 'Limite de confiança para transferir para humano'),
            ('max_conversation_length', '50', 'integer', 'Número máximo de mensagens por conversa'),
        ]
        
        for nome, valor, tipo, descricao in configs:
            config, created = ChatbotConfiguration.objects.get_or_create(
                nome=nome,
                defaults={
                    'valor': valor,
                    'tipo': tipo,
                    'descricao': descricao,
                    'ativo': True
                }
            )
            if created:
                self.stdout.write(f'  ✓ Configuração criada: {nome}')
            else:
                self.stdout.write(f'  - Configuração já existe: {nome}')
        
        # Base de conhecimento inicial
        self.stdout.write('Criando base de conhecimento inicial...')
        
        kb_items = [
            {
                'categoria': 'Saudação',
                'pergunta': 'Como posso ajudá-lo?',
                'resposta': 'Olá! Posso ajudá-lo com informações sobre tickets, criar novos chamados, ou conectá-lo com nossa equipe de suporte. Em que posso ser útil?',
                'tags': 'ajuda, suporte, início',
                'confianca': 1.0
            },
            {
                'categoria': 'Tickets',
                'pergunta': 'Como verificar o status do meu ticket?',
                'resposta': 'Para verificar o status do seu ticket, você pode:\n\n1. Fazer login no sistema\n2. Acessar a seção "Meus Tickets"\n3. Ou simplesmente me perguntar "qual o status do meu ticket?"\n\nSe você souber o número do ticket, pode me informar e eu busco as informações para você.',
                'tags': 'ticket, status, verificar, consultar',
                'confianca': 0.9
            },
            {
                'categoria': 'Tickets',
                'pergunta': 'Como criar um novo ticket?',
                'resposta': 'Para criar um novo ticket você pode:\n\n1. **Pelo sistema**: Faça login e clique em "Novo Ticket"\n2. **Comigo**: Me descreva seu problema e eu ajudo a criar o chamado\n3. **Por email**: Envie um email para suporte@iconnect.com\n\nQual problema você está enfrentando?',
                'tags': 'ticket, criar, novo, chamado, problema',
                'confianca': 0.9
            },
            {
                'categoria': 'Suporte',
                'pergunta': 'Qual o horário de funcionamento do suporte?',
                'resposta': 'Nosso suporte funciona:\n\n📞 **Telefone**: Segunda a Sexta, 8h às 18h\n💬 **Chat**: 24/7 (este assistente virtual)\n👨‍💼 **Atendentes humanos**: Segunda a Sexta, 8h às 18h\n📧 **Email**: Respondemos em até 24h\n\nPosso ajudá-lo agora mesmo!',
                'tags': 'horário, funcionamento, suporte, atendimento',
                'confianca': 1.0
            },
            {
                'categoria': 'Serviços',
                'pergunta': 'Quais serviços vocês oferecem?',
                'resposta': 'A iConnect oferece:\n\n🔧 **Suporte Técnico**: Problemas com equipamentos e sistemas\n🌐 **Conectividade**: Internet, redes e telecomunicações\n💻 **TI**: Infraestrutura e consultoria em tecnologia\n📱 **Sistemas**: Desenvolvimento e manutenção\n🛡️ **Segurança**: Proteção de dados e redes\n\nSobre qual serviço você gostaria de saber mais?',
                'tags': 'serviços, ofertas, produtos, ti, tecnologia',
                'confianca': 0.8
            },
            {
                'categoria': 'Problemas',
                'pergunta': 'Internet não está funcionando',
                'resposta': 'Vamos resolver esse problema de internet! 🌐\n\nPrimeiro, vamos fazer alguns testes:\n\n1. **Reinicie o modem/roteador**: Desligue por 30 segundos e ligue novamente\n2. **Teste outros dispositivos**: O problema é só em um aparelho?\n3. **Verifique os cabos**: Estão todos bem conectados?\n\nSe o problema persistir, posso criar um ticket técnico para você. Como está a situação agora?',
                'tags': 'internet, conexão, não funciona, lento, problema',
                'confianca': 0.8
            },
            {
                'categoria': 'Financeiro',
                'pergunta': 'Como emitir segunda via da fatura?',
                'resposta': 'Para emitir a segunda via da sua fatura:\n\n💻 **Online**: \n1. Acesse o portal do cliente\n2. Vá em "Financeiro" > "Faturas"\n3. Clique em "Baixar" na fatura desejada\n\n📧 **Por email**: Posso enviar por email\n📞 **Por telefone**: (11) 1234-5678\n\nQual fatura você precisa? (mês/ano)',
                'tags': 'fatura, segunda via, boleto, pagamento, cobrança',
                'confianca': 0.9
            },
            {
                'categoria': 'Urgência',
                'pergunta': 'Emergência técnica',
                'resposta': '🚨 **EMERGÊNCIA TÉCNICA DETECTADA**\n\nPara emergências, vou conectá-lo imediatamente com nossa equipe especializada.\n\n📞 **Suporte 24h**: (11) 9999-0000\n⚡ **Prioridade máxima** ativada\n\nDescreva brevemente o problema enquanto preparo seu atendimento prioritário.',
                'tags': 'emergência, urgente, crítico, parou, emergencial',
                'confianca': 1.0
            }
        ]
        
        created_count = 0
        for item_data in kb_items:
            item, created = ChatbotKnowledgeBase.objects.get_or_create(
                categoria=item_data['categoria'],
                pergunta=item_data['pergunta'],
                defaults={
                    'resposta': item_data['resposta'],
                    'tags': item_data['tags'],
                    'confianca': item_data['confianca'],
                    'ativo': True
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Item criado: {item_data["categoria"]} - {item_data["pergunta"][:50]}...')
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n✅ Dados iniciais do chatbot criados com sucesso!\n'
                f'   - {len(configs)} configurações\n'
                f'   - {created_count} itens na base de conhecimento'
            )
        )