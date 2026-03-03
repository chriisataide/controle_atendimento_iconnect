import logging
from typing import Dict, List, Tuple

import requests
from django.db import models
from django.utils import timezone

from ..models import (
    Cliente,
    Ticket,
    WhatsAppAnalytics,
    WhatsAppBusinessAccount,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppMessage,
)

logger = logging.getLogger(__name__)


class WhatsAppBusinessAPI:
    """Cliente para API do WhatsApp Business"""

    # Timeout padrão para requisições (connect, read) em segundos
    DEFAULT_TIMEOUT = (5, 30)

    def __init__(self, account: WhatsAppBusinessAccount):
        self.account = account
        self.base_url = "https://graph.facebook.com/v18.0"
        self.headers = {"Authorization": f"Bearer {account.access_token}", "Content-Type": "application/json"}

    def send_message(self, to: str, message_data: Dict) -> Dict:
        """Envia mensagem via WhatsApp Business API"""
        url = f"{self.base_url}/{self.account.phone_number_id}/messages"

        payload = {"messaging_product": "whatsapp", "to": to, **message_data}

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao enviar mensagem WhatsApp: {e}")
            raise

    def send_text_message(self, to: str, text: str) -> Dict:
        """Envia mensagem de texto"""
        message_data = {"type": "text", "text": {"body": text}}
        return self.send_message(to, message_data)

    def send_template_message(
        self, to: str, template_name: str, language: str = "pt_BR", components: List = None
    ) -> Dict:
        """Envia mensagem template"""
        message_data = {"type": "template", "template": {"name": template_name, "language": {"code": language}}}

        if components:
            message_data["template"]["components"] = components

        return self.send_message(to, message_data)

    def send_interactive_message(self, to: str, interactive_data: Dict) -> Dict:
        """Envia mensagem interativa (botões/lista)"""
        message_data = {"type": "interactive", "interactive": interactive_data}
        return self.send_message(to, message_data)

    def mark_message_as_read(self, message_id: str) -> Dict:
        """Marca mensagem como lida"""
        url = f"{self.base_url}/{self.account.phone_number_id}/messages"

        payload = {"messaging_product": "whatsapp", "status": "read", "message_id": message_id}

        try:
            response = requests.post(url, headers=self.headers, json=payload, timeout=self.DEFAULT_TIMEOUT)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro ao marcar mensagem como lida: {e}")
            raise

    def get_media(self, media_id: str) -> Tuple[bytes, str]:
        """Baixa mídia do WhatsApp"""
        # Primeiro, pega a URL da mídia
        url = f"{self.base_url}/{media_id}"
        response = requests.get(url, headers=self.headers, timeout=self.DEFAULT_TIMEOUT)
        response.raise_for_status()

        media_data = response.json()
        media_url = media_data.get("url")
        mime_type = media_data.get("mime_type")

        # Depois, baixa o arquivo
        media_response = requests.get(media_url, headers=self.headers, timeout=(5, 60))
        media_response.raise_for_status()

        return media_response.content, mime_type


class WhatsAppMessageProcessor:
    """Processador de mensagens do WhatsApp"""

    def __init__(self):
        self.api_clients = {}

    def get_api_client(self, account: WhatsAppBusinessAccount) -> WhatsAppBusinessAPI:
        """Obtém cliente da API para uma conta"""
        if account.id not in self.api_clients:
            self.api_clients[account.id] = WhatsAppBusinessAPI(account)
        return self.api_clients[account.id]

    def process_webhook(self, webhook_data: Dict) -> Dict:
        """Processa webhook do WhatsApp"""
        try:
            entry = webhook_data.get("entry", [{}])[0]
            changes = entry.get("changes", [{}])[0]
            value = changes.get("value", {})

            # Identifica a conta
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            if not phone_number_id:
                return {"status": "error", "message": "Phone number ID não encontrado"}

            account = WhatsAppBusinessAccount.objects.filter(phone_number_id=phone_number_id, ativo=True).first()

            if not account:
                return {"status": "error", "message": "Conta não encontrada"}

            # Processa mensagens
            if "messages" in value:
                for message in value["messages"]:
                    self.process_incoming_message(account, message)

            # Processa status de mensagens
            if "statuses" in value:
                for status in value["statuses"]:
                    self.process_message_status(account, status)

            return {"status": "success"}

        except Exception as e:
            logger.error(f"Erro ao processar webhook: {e}")
            return {"status": "error", "message": str(e)}

    def process_incoming_message(self, account: WhatsAppBusinessAccount, message_data: Dict):
        """Processa mensagem recebida"""
        try:
            # Identifica ou cria contato
            contact_info = message_data.get("from")
            contact = self.get_or_create_contact(contact_info, message_data.get("profile", {}))

            # Identifica ou cria conversa
            conversation = self.get_or_create_conversation(account, contact)

            # Cria mensagem
            message = WhatsAppMessage.objects.create(
                whatsapp_message_id=message_data.get("id"),
                conversation=conversation,
                contact=contact,
                direcao="inbound",
                tipo=message_data.get("type", "text"),
                conteudo=self.extract_message_content(message_data),
                metadata=message_data,
                timestamp=timezone.now(),
                processada=False,
            )

            # Processa conteúdo da mensagem
            self.process_message_content(message)

            # Auto-resposta se necessário
            self.check_auto_response(account, conversation, message)

            # Marca como lida se configurado
            api_client = self.get_api_client(account)
            api_client.mark_message_as_read(message.whatsapp_message_id)

        except Exception as e:
            logger.error(f"Erro ao processar mensagem recebida: {e}")

    def process_message_status(self, account: WhatsAppBusinessAccount, status_data: Dict):
        """Processa status de mensagem"""
        try:
            message_id = status_data.get("id")
            status = status_data.get("status")

            WhatsAppMessage.objects.filter(whatsapp_message_id=message_id).update(status=status)

        except Exception as e:
            logger.error(f"Erro ao processar status da mensagem: {e}")

    def get_or_create_contact(self, whatsapp_id: str, profile_data: Dict) -> WhatsAppContact:
        """Obtém ou cria contato"""
        contact, created = WhatsAppContact.objects.get_or_create(
            whatsapp_id=whatsapp_id,
            defaults={
                "phone_number": whatsapp_id,
                "profile_name": profile_data.get("name", ""),
                "metadados": profile_data,
            },
        )

        if not created and profile_data:
            # Atualiza dados do perfil
            contact.profile_name = profile_data.get("name", contact.profile_name)
            contact.metadados.update(profile_data)
            contact.save()

        return contact

    def get_or_create_conversation(
        self, account: WhatsAppBusinessAccount, contact: WhatsAppContact
    ) -> WhatsAppConversation:
        """Obtém ou cria conversa ativa"""
        conversation = WhatsAppConversation.objects.filter(account=account, contact=contact, estado="ativa").first()

        if not conversation:
            conversation = WhatsAppConversation.objects.create(
                account=account, contact=contact, estado="ativa", titulo=f"Conversa com {contact}"
            )

        return conversation

    def extract_message_content(self, message_data: Dict) -> str:
        """Extrai conteúdo da mensagem"""
        message_type = message_data.get("type")

        if message_type == "text":
            return message_data.get("text", {}).get("body", "")
        elif message_type == "button":
            return message_data.get("button", {}).get("text", "")
        elif message_type == "interactive":
            interactive = message_data.get("interactive", {})
            if interactive.get("type") == "button_reply":
                return interactive.get("button_reply", {}).get("title", "")
            elif interactive.get("type") == "list_reply":
                return interactive.get("list_reply", {}).get("title", "")
        elif message_type in ["image", "audio", "video", "document"]:
            media = message_data.get(message_type, {})
            caption = media.get("caption", "")
            return f"[{message_type.upper()}] {caption}".strip()

        return f"[{message_type.upper()}]"

    def process_message_content(self, message: WhatsAppMessage):
        """Processa conteúdo da mensagem para ações automáticas"""
        content = message.conteudo.lower().strip()

        # Verifica se é uma solicitação de ticket
        ticket_keywords = ["problema", "ajuda", "suporte", "ticket", "chamado", "erro", "bug"]
        if any(keyword in content for keyword in ticket_keywords):
            self.create_ticket_from_message(message)

        # Marca como processada
        message.processada = True
        message.save()

    def create_ticket_from_message(self, message: WhatsAppMessage):
        """Cria ticket a partir da mensagem"""
        try:
            # Verifica se já existe ticket para esta conversa
            if message.conversation.ticket:
                return message.conversation.ticket

            # Cria ou obtém cliente
            cliente = self.get_or_create_cliente(message.contact)

            # Cria ticket
            ticket = Ticket.objects.create(
                titulo=f"Suporte WhatsApp - {message.contact}",
                descricao=message.conteudo,
                cliente=cliente,
                canal="whatsapp",
                prioridade="media",
                status="aberto",
            )

            # Vincula à conversa
            message.conversation.ticket = ticket
            message.conversation.save()

            # Envia confirmação
            self.send_ticket_confirmation(message.conversation, ticket)

            return ticket

        except Exception as e:
            logger.error(f"Erro ao criar ticket da mensagem: {e}")

    def get_or_create_cliente(self, contact: WhatsAppContact) -> Cliente:
        """Obtém ou cria cliente a partir do contato"""
        # Verifica se já existe cliente vinculado
        if contact.usuario and hasattr(contact.usuario, "cliente"):
            return contact.usuario.cliente

        # Cria cliente
        cliente, created = Cliente.objects.get_or_create(
            telefone=contact.phone_number,
            defaults={
                "nome": contact.nome or contact.profile_name or f"Cliente {contact.phone_number}",
                "email": f"{contact.whatsapp_id}@whatsapp.placeholder",
                "ativo": True,
            },
        )

        return cliente

    def send_ticket_confirmation(self, conversation: WhatsAppConversation, ticket: Ticket):
        """Envia confirmação de criação do ticket"""
        try:
            api_client = self.get_api_client(conversation.account)

            message = f"""✅ *Ticket criado com sucesso!*

🎫 *Número:* {ticket.id}
📝 *Título:* {ticket.titulo}
⏰ *Criado em:* {ticket.criado_em.strftime('%d/%m/%Y às %H:%M')}

Em breve nossa equipe entrará em contato. Obrigado!"""

            api_client.send_text_message(to=conversation.contact.whatsapp_id, text=message)

        except Exception as e:
            logger.error(f"Erro ao enviar confirmação do ticket: {e}")

    def check_auto_response(
        self, account: WhatsAppBusinessAccount, conversation: WhatsAppConversation, message: WhatsAppMessage
    ):
        """Verifica e envia respostas automáticas"""
        try:
            from ..models import WhatsAppAutoResponse

            # Busca respostas automáticas
            auto_responses = WhatsAppAutoResponse.objects.filter(account=account, ativo=True).order_by("-prioridade")

            for auto_response in auto_responses:
                if self.should_trigger_auto_response(auto_response, conversation, message):
                    self.send_auto_response(auto_response, conversation)
                    break

        except Exception as e:
            logger.error(f"Erro ao verificar auto-resposta: {e}")

    def should_trigger_auto_response(
        self, auto_response, conversation: WhatsAppConversation, message: WhatsAppMessage
    ) -> bool:
        """Verifica se deve disparar resposta automática"""
        if auto_response.tipo_trigger == "keyword":
            return auto_response.trigger_value.lower() in message.conteudo.lower()
        elif auto_response.tipo_trigger == "first_message":
            return conversation.mensagens.count() == 1
        elif auto_response.tipo_trigger == "business_hours":
            # Implementar lógica de horário comercial
            return False
        elif auto_response.tipo_trigger == "agent_unavailable":
            return not conversation.agente

        return False

    def send_auto_response(self, auto_response, conversation: WhatsAppConversation):
        """Envia resposta automática"""
        try:
            api_client = self.get_api_client(conversation.account)

            if auto_response.template:
                # Envia template
                api_client.send_template_message(
                    to=conversation.contact.whatsapp_id, template_name=auto_response.template.nome
                )
            elif auto_response.mensagem_texto:
                # Envia texto
                api_client.send_text_message(to=conversation.contact.whatsapp_id, text=auto_response.mensagem_texto)

        except Exception as e:
            logger.error(f"Erro ao enviar auto-resposta: {e}")


class WhatsAppAnalyticsService:
    """Serviço de analytics do WhatsApp"""

    @staticmethod
    def update_daily_analytics(account: WhatsAppBusinessAccount, date=None):
        """Atualiza analytics diários"""
        if not date:
            date = timezone.now().date()

        try:
            analytics, created = WhatsAppAnalytics.objects.get_or_create(account=account, data=date)

            # Calcula métricas do dia
            start_datetime = timezone.datetime.combine(date, timezone.datetime.min.time())
            end_datetime = start_datetime + timezone.timedelta(days=1)

            messages = WhatsAppMessage.objects.filter(
                conversation__account=account, timestamp__gte=start_datetime, timestamp__lt=end_datetime
            )

            analytics.mensagens_enviadas = messages.filter(direcao="outbound").count()
            analytics.mensagens_recebidas = messages.filter(direcao="inbound").count()
            analytics.mensagens_entregues = messages.filter(status="delivered").count()
            analytics.mensagens_lidas = messages.filter(status="read").count()

            conversations = WhatsAppConversation.objects.filter(
                account=account, iniciada_em__gte=start_datetime, iniciada_em__lt=end_datetime
            )

            analytics.conversas_iniciadas = conversations.count()
            analytics.conversas_encerradas = conversations.filter(estado="encerrada").count()
            analytics.tickets_criados = conversations.filter(ticket__isnull=False).count()

            # Calcula tempo médio de resposta
            response_times = []
            for conv in conversations:
                times = conv.get_response_times()
                response_times.extend(times)

            if response_times:
                analytics.tempo_resposta_medio = sum(response_times) / len(response_times)

            analytics.save()

        except Exception as e:
            logger.error(f"Erro ao atualizar analytics: {e}")

    @staticmethod
    def get_account_metrics(account: WhatsAppBusinessAccount, days: int = 30) -> Dict:
        """Obtém métricas da conta"""
        end_date = timezone.now().date()
        start_date = end_date - timezone.timedelta(days=days)

        analytics = WhatsAppAnalytics.objects.filter(account=account, data__gte=start_date, data__lte=end_date)

        return {
            "total_mensagens_enviadas": sum(a.mensagens_enviadas for a in analytics),
            "total_mensagens_recebidas": sum(a.mensagens_recebidas for a in analytics),
            "total_conversas": sum(a.conversas_iniciadas for a in analytics),
            "total_tickets": sum(a.tickets_criados for a in analytics),
            "tempo_resposta_medio": analytics.aggregate(avg_response=models.Avg("tempo_resposta_medio"))[
                "avg_response"
            ],
            "taxa_entrega": analytics.aggregate(
                total_sent=models.Sum("mensagens_enviadas"), total_delivered=models.Sum("mensagens_entregues")
            ),
        }
