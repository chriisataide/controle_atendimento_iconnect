"""
WebSocket Consumers para Sistema de Notificações e Chat em Tempo Real
iConnect - Sistema de Atendimento Competitivo
"""

import json
import logging
from typing import Any, Dict

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.core.serializers.json import DjangoJSONEncoder
from django.utils import timezone

from .models import ChatMessage, ChatParticipant, ChatRoom, Notification, PerfilAgente, Ticket

logger = logging.getLogger("dashboard")


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer para notificações em tempo real
    """

    async def connect(self):
        """Conecta o cliente WebSocket"""

        # Verificar autenticação
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        self.user = self.scope["user"]
        self.user_group_name = f"user_{self.user.id}"

        # Adicionar às notificações gerais
        await self.channel_layer.group_add("notifications_general", self.channel_name)

        # Adicionar ao grupo específico do usuário
        await self.channel_layer.group_add(self.user_group_name, self.channel_name)

        # Se for agente, adicionar ao grupo de agentes
        agent = await self.get_user_agent()
        if agent:
            await self.channel_layer.group_add("agents", self.channel_name)

            # Marcar agente como ativo
            await self.update_agent_activity(agent, True)

        await self.accept()

        # Enviar notificações não lidas
        await self.send_unread_notifications()

        # Enviar estatísticas iniciais
        await self.send_dashboard_stats()

        logger.info("WebSocket conectado: %s", self.user.username)

    async def disconnect(self, close_code):
        """Desconecta o cliente WebSocket"""

        # Remover dos grupos
        await self.channel_layer.group_discard("notifications_general", self.channel_name)

        await self.channel_layer.group_discard(self.user_group_name, self.channel_name)

        # Se for agente, remover do grupo e marcar como inativo
        agent = await self.get_user_agent()
        if agent:
            await self.channel_layer.group_discard("agents", self.channel_name)
            await self.update_agent_activity(agent, False)

        logger.info("WebSocket desconectado: %s", self.user.username)

    async def receive(self, text_data):
        """Recebe mensagens do cliente"""

        try:
            data = json.loads(text_data)
            message_type = data.get("type", "")

            # Roteamento de mensagens
            if message_type == "ping":
                await self.send_pong()

            elif message_type == "mark_notification_read":
                await self.mark_notification_read(data.get("notification_id"))

            elif message_type == "mark_all_notifications_read":
                await self.mark_all_notifications_read()

            elif message_type == "request_stats":
                await self.send_dashboard_stats()

            elif message_type == "subscribe_ticket":
                await self.subscribe_ticket(data.get("ticket_id"))

            elif message_type == "unsubscribe_ticket":
                await self.unsubscribe_ticket(data.get("ticket_id"))

            elif message_type == "agent_typing":
                await self.broadcast_agent_typing(data.get("ticket_id"))

            else:
                logger.warning("Tipo de mensagem desconhecido: %s", message_type)

        except json.JSONDecodeError:
            logger.error("Erro ao decodificar JSON do WebSocket")
        except Exception as e:
            logger.error("Erro no WebSocket: %s", e, exc_info=True)

    # ====================================
    # HANDLERS DE MENSAGENS
    # ====================================

    async def send_pong(self):
        """Responde ao ping do cliente"""
        await self.send(
            text_data=json.dumps({"type": "pong", "timestamp": timezone.now().isoformat()}, cls=DjangoJSONEncoder)
        )

    async def send_notification(self, event):
        """Envia notificação para o cliente"""
        await self.send(text_data=json.dumps({"type": "notification", "data": event["data"]}, cls=DjangoJSONEncoder))

    async def send_dashboard_update(self, event):
        """Envia atualização do dashboard"""
        await self.send(
            text_data=json.dumps({"type": "dashboard_update", "data": event["data"]}, cls=DjangoJSONEncoder)
        )

    async def send_ticket_update(self, event):
        """Envia atualização de ticket"""
        await self.send(text_data=json.dumps({"type": "ticket_update", "data": event["data"]}, cls=DjangoJSONEncoder))

    async def send_agent_status(self, event):
        """Envia status de agente (online/offline/typing)"""
        await self.send(text_data=json.dumps({"type": "agent_status", "data": event["data"]}, cls=DjangoJSONEncoder))

    # ====================================
    # MÉTODOS DE NOTIFICAÇÃO
    # ====================================

    async def send_unread_notifications(self):
        """Envia notificações não lidas do usuário"""
        notifications = await self.get_unread_notifications()

        await self.send(
            text_data=json.dumps(
                {"type": "unread_notifications", "data": {"notifications": notifications, "count": len(notifications)}},
                cls=DjangoJSONEncoder,
            )
        )

    async def mark_notification_read(self, notification_id):
        """Marca notificação específica como lida"""
        success = await self.mark_notification_as_read(notification_id)

        if success:
            unread_count = await self.get_unread_count()
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "notification_marked_read",
                        "data": {"notification_id": notification_id, "unread_count": unread_count},
                    },
                    cls=DjangoJSONEncoder,
                )
            )

    async def mark_all_notifications_read(self):
        """Marca todas as notificações como lidas"""
        count = await self.mark_all_notifications_as_read()

        await self.send(
            text_data=json.dumps(
                {"type": "all_notifications_marked_read", "data": {"marked_count": count, "unread_count": 0}},
                cls=DjangoJSONEncoder,
            )
        )

    # ====================================
    # ESTATÍSTICAS DO DASHBOARD
    # ====================================

    async def send_dashboard_stats(self):
        """Envia estatísticas atualizadas do dashboard"""
        stats = await self.get_dashboard_statistics()

        await self.send(text_data=json.dumps({"type": "dashboard_stats", "data": stats}, cls=DjangoJSONEncoder))

    # ====================================
    # SUBSCRIÇÃO DE TICKETS
    # ====================================

    async def subscribe_ticket(self, ticket_id):
        """Inscreve o usuário para receber atualizações de um ticket específico"""
        if ticket_id:
            ticket_group = f"ticket_{ticket_id}"
            await self.channel_layer.group_add(ticket_group, self.channel_name)

            await self.send(
                text_data=json.dumps(
                    {"type": "subscribed_ticket", "data": {"ticket_id": ticket_id}}, cls=DjangoJSONEncoder
                )
            )

    async def unsubscribe_ticket(self, ticket_id):
        """Desinscreve o usuário das atualizações de um ticket"""
        if ticket_id:
            ticket_group = f"ticket_{ticket_id}"
            await self.channel_layer.group_discard(ticket_group, self.channel_name)

            await self.send(
                text_data=json.dumps(
                    {"type": "unsubscribed_ticket", "data": {"ticket_id": ticket_id}}, cls=DjangoJSONEncoder
                )
            )

    async def broadcast_agent_typing(self, ticket_id):
        """Broadcasts que um agente está digitando em um ticket"""
        if ticket_id:
            agent = await self.get_user_agent()
            if agent:
                ticket_group = f"ticket_{ticket_id}"
                await self.channel_layer.group_send(
                    ticket_group,
                    {
                        "type": "send_agent_status",
                        "data": {
                            "agent_id": agent.id,
                            "agent_name": agent.user.get_full_name(),
                            "status": "typing",
                            "ticket_id": ticket_id,
                            "timestamp": timezone.now().isoformat(),
                        },
                    },
                )

    # ====================================
    # DATABASE OPERATIONS (ASYNC)
    # ====================================

    @database_sync_to_async
    def get_user_agent(self):
        """Busca o agente associado ao usuário"""
        try:
            return PerfilAgente.objects.get(user=self.user)
        except PerfilAgente.DoesNotExist:
            return None

    @database_sync_to_async
    def update_agent_activity(self, agent, is_active):
        """Atualiza o status de atividade do agente"""
        agent.is_active = is_active
        agent.last_activity = timezone.now()
        agent.save(update_fields=["is_active", "last_activity"])

    @database_sync_to_async
    def get_unread_notifications(self):
        """Busca notificações não lidas do usuário"""
        notifications = Notification.objects.filter(user=self.user, read=False).order_by("-created_at")[:20]

        return [
            {
                "id": notif.id,
                "type": notif.type,
                "title": notif.title,
                "message": notif.message,
                "url": notif.url,
                "created_at": notif.created_at.isoformat(),
                "metadata": notif.metadata,
            }
            for notif in notifications
        ]

    @database_sync_to_async
    def get_unread_count(self):
        """Conta notificações não lidas"""
        return Notification.objects.filter(user=self.user, read=False).count()

    @database_sync_to_async
    def mark_notification_as_read(self, notification_id):
        """Marca notificação específica como lida"""
        try:
            notification = Notification.objects.get(id=notification_id, user=self.user, read=False)
            notification.read = True
            notification.read_at = timezone.now()
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False

    @database_sync_to_async
    def mark_all_notifications_as_read(self):
        """Marca todas as notificações como lidas"""
        return Notification.objects.filter(user=self.user, read=False).update(read=True, read_at=timezone.now())

    @database_sync_to_async
    def get_dashboard_statistics(self):
        """Busca estatísticas do dashboard"""
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0)

        # Contar tickets por status
        tickets_today = Ticket.objects.filter(created_at__gte=today).count()
        tickets_open = Ticket.objects.filter(status__in=["NOVO", "ABERTO", "EM_ANDAMENTO"]).count()
        tickets_pending = Ticket.objects.filter(status="NOVO").count()
        tickets_resolved_today = Ticket.objects.filter(status="FECHADO", resolved_at__gte=today).count()

        # Agentes ativos (atividade nos últimos 15 minutos)
        active_agents = PerfilAgente.objects.filter(status__in=["online", "ocupado"]).count()

        return {
            "tickets_today": tickets_today,
            "tickets_open": tickets_open,
            "tickets_pending": tickets_pending,
            "tickets_resolved_today": tickets_resolved_today,
            "active_agents": active_agents,
            "updated_at": now.isoformat(),
        }


# ====================================
# FUNÇÕES AUXILIARES PARA BROADCASTING
# ====================================


async def broadcast_notification(user_id: int, notification_data: Dict[str, Any]):
    """
    Envia notificação para um usuário específico
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    user_group = f"user_{user_id}"

    await channel_layer.group_send(user_group, {"type": "send_notification", "data": notification_data})


async def broadcast_dashboard_update(stats_data: Dict[str, Any]):
    """
    Envia atualizações do dashboard para todos os usuários conectados
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    await channel_layer.group_send("notifications_general", {"type": "send_dashboard_update", "data": stats_data})


async def broadcast_ticket_update(ticket_id: int, update_data: Dict[str, Any]):
    """
    Envia atualizações de ticket para usuários interessados
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    ticket_group = f"ticket_{ticket_id}"

    await channel_layer.group_send(
        ticket_group, {"type": "send_ticket_update", "data": {"ticket_id": ticket_id, **update_data}}
    )


async def broadcast_to_agents(data: Dict[str, Any], message_type: str = "notification"):
    """
    Envia mensagem para todos os agentes conectados
    """
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()

    await channel_layer.group_send("agents", {"type": f"send_{message_type}", "data": data})


class TicketChatConsumer(AsyncWebsocketConsumer):
    """
    Consumer para chat de tickets em tempo real
    """

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        self.ticket_id = self.scope["url_route"]["kwargs"]["ticket_id"]
        self.ticket_group_name = f"ticket_chat_{self.ticket_id}"

        # Verificar se usuário tem acesso ao ticket
        try:
            from .models import Ticket

            ticket = await database_sync_to_async(Ticket.objects.get)(id=self.ticket_id)

            # Verificar permissões
            user = self.scope["user"]
            has_access = False

            if user.is_superuser:
                has_access = True
            elif hasattr(user, "perfilusuario"):
                if user.perfilusuario.tipo in ["agente", "administrador"]:
                    has_access = True
                elif user.perfilusuario.tipo == "cliente" and ticket.cliente.user == user:
                    has_access = True

            if not has_access:
                await self.close()
                return

        except Exception:
            await self.close()
            return

        # Adicionar ao grupo do ticket
        await self.channel_layer.group_add(self.ticket_group_name, self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "ticket_group_name"):
            await self.channel_layer.group_discard(self.ticket_group_name, self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "chat_message":
                await self.handle_chat_message(data)
            elif message_type == "typing_start":
                await self.handle_typing_start(data)
            elif message_type == "typing_stop":
                await self.handle_typing_stop(data)

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"type": "error", "message": "Invalid JSON format"}))

    async def handle_chat_message(self, data):
        message = data.get("message", "").strip()
        if not message:
            return

        user = self.scope["user"]

        # Salvar mensagem
        try:
            from .models import InteracaoTicket, Ticket

            ticket = await database_sync_to_async(Ticket.objects.get)(id=self.ticket_id)

            interaction = await database_sync_to_async(InteracaoTicket.objects.create)(
                ticket=ticket, usuario=user, conteudo=message, tipo="mensagem"
            )

            # Broadcast para o grupo
            await self.channel_layer.group_send(
                self.ticket_group_name,
                {
                    "type": "chat_message",
                    "data": {
                        "id": interaction.id,
                        "message": message,
                        "user_id": user.id,
                        "username": user.get_full_name() or user.username,
                        "timestamp": interaction.criado_em.isoformat(),
                        "is_agent": hasattr(user, "perfilusuario") and user.perfilusuario.tipo == "agente",
                    },
                },
            )

        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": "Erro ao enviar mensagem"}))

    async def handle_typing_start(self, data):
        user = self.scope["user"]
        await self.channel_layer.group_send(
            self.ticket_group_name,
            {
                "type": "typing_indicator",
                "data": {"user_id": user.id, "username": user.get_full_name() or user.username, "typing": True},
            },
        )

    async def handle_typing_stop(self, data):
        user = self.scope["user"]
        await self.channel_layer.group_send(
            self.ticket_group_name,
            {
                "type": "typing_indicator",
                "data": {"user_id": user.id, "username": user.get_full_name() or user.username, "typing": False},
            },
        )

    # Handlers for group messages
    async def chat_message(self, event):
        await self.send(text_data=json.dumps({"type": "chat_message", "data": event["data"]}))

    async def typing_indicator(self, event):
        # Não enviar indicador de digitação para o próprio usuário
        if event["data"]["user_id"] != self.scope["user"].id:
            await self.send(text_data=json.dumps({"type": "typing_indicator", "data": event["data"]}))


class DashboardConsumer(AsyncWebsocketConsumer):
    """
    Consumer para atualizações do dashboard em tempo real
    """

    async def connect(self):
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        await self.channel_layer.group_add("dashboard_updates", self.channel_name)

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("dashboard_updates", self.channel_name)

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            if data.get("type") == "request_update":
                await self.send_dashboard_update()

        except json.JSONDecodeError:
            pass

    async def send_dashboard_update(self):
        """Envia dados atualizados do dashboard"""
        try:
            from .models import Ticket

            # Estatísticas básicas
            total_tickets = await database_sync_to_async(Ticket.objects.count)()
            open_tickets = await database_sync_to_async(
                Ticket.objects.filter(status__nome__in=["Aberto", "Em Andamento"]).count
            )()

            await self.send(
                text_data=json.dumps(
                    {
                        "type": "dashboard_update",
                        "data": {
                            "total_tickets": total_tickets,
                            "open_tickets": open_tickets,
                            "timestamp": timezone.now().isoformat(),
                        },
                    }
                )
            )

        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": "Erro ao atualizar dashboard"}))


class AgentStatusConsumer(AsyncWebsocketConsumer):
    """
    Consumer para status de agentes em tempo real
    """

    async def connect(self):
        user = self.scope["user"]
        if not user.is_authenticated:
            await self.close()
            return

        # Verificar se é agente
        try:
            profile = await database_sync_to_async(lambda: user.perfilusuario)()
            if profile.tipo not in ["agente", "administrador"]:
                await self.close()
                return
        except Exception:
            await self.close()
            return

        self.user_id = user.id

        await self.channel_layer.group_add("agent_status", self.channel_name)

        await self.accept()

        # Marcar como online
        await self.update_agent_status("online")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("agent_status", self.channel_name)

        # Marcar como offline
        await self.update_agent_status("offline")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)

            if data.get("type") == "status_update":
                status = data.get("status", "online")
                await self.update_agent_status(status)

        except json.JSONDecodeError:
            pass

    async def update_agent_status(self, status):
        """Atualizar status do agente"""
        user = self.scope["user"]

        try:
            from .models import PerfilAgente

            agent = await database_sync_to_async(PerfilAgente.objects.get)(user=user)
            agent.status = status
            agent.ultima_atividade = timezone.now()
            await database_sync_to_async(agent.save)()

            # Broadcast para outros agentes
            await self.channel_layer.group_send(
                "agent_status",
                {
                    "type": "agent_status_update",
                    "data": {
                        "agent_id": agent.id,
                        "user_id": user.id,
                        "username": user.get_full_name() or user.username,
                        "status": status,
                        "timestamp": timezone.now().isoformat(),
                    },
                },
            )

        except Exception as e:
            await self.send(text_data=json.dumps({"type": "error", "message": "Erro ao atualizar status"}))

    # Handler for group messages
    async def agent_status_update(self, event):
        # Não enviar update para o próprio agente
        if event["data"]["user_id"] != self.scope["user"].id:
            await self.send(text_data=json.dumps({"type": "agent_status_update", "data": event["data"]}))


class ChatConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer para Sistema de Chat Avançado
    """

    async def connect(self):
        """Conecta ao chat room"""

        # Verificar autenticação
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        self.user = self.scope["user"]
        self.room_id = self.scope["url_route"]["kwargs"]["room_id"]
        self.room_group_name = f"chat_{self.room_id}"

        # Verificar se o usuário tem acesso à sala
        room_access = await self.check_room_access()
        if not room_access:
            await self.close()
            return

        # Adicionar ao grupo da sala
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        # Marcar usuário como online na sala
        await self.set_user_online(True)

        await self.accept()

        # Notificar outros usuários que o usuário entrou
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_joined",
                "user_id": self.user.id,
                "username": self.user.username,
                "full_name": self.user.get_full_name(),
                "timestamp": timezone.now().isoformat(),
            },
        )

    async def disconnect(self, close_code):
        """Desconecta do chat room"""

        # Marcar usuário como offline
        await self.set_user_online(False)

        # Notificar outros usuários que o usuário saiu
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "user_left",
                "user_id": self.user.id,
                "username": self.user.username,
                "timestamp": timezone.now().isoformat(),
            },
        )

        # Remover do grupo
        await self.channel_layer.group_discard(self.room_group_name, self.channel_name)

    async def receive(self, text_data):
        """Recebe mensagem do WebSocket"""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "chat_message":
                await self.handle_chat_message(data)
            elif message_type == "typing_start":
                await self.handle_typing_start()
            elif message_type == "typing_stop":
                await self.handle_typing_stop()
            elif message_type == "message_read":
                await self.handle_message_read(data)
            elif message_type == "file_upload":
                await self.handle_file_upload(data)
            elif message_type == "reaction":
                await self.handle_reaction(data)

        except json.JSONDecodeError:
            await self.send_error("Invalid JSON format")
        except Exception as e:
            await self.send_error("Error processing message")

    async def handle_chat_message(self, data):
        """Processa mensagem de chat"""
        content = data.get("content", "").strip()
        if not content:
            return

        reply_to_id = data.get("reply_to")
        message_type = data.get("message_type", "text")

        # Salvar mensagem no banco
        message = await self.save_message(content, message_type, reply_to_id)

        if message:
            # Enviar mensagem para todos na sala
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "chat_message",
                    "message": {
                        "id": str(message.id),
                        "content": message.content,
                        "message_type": message.message_type,
                        "sender_id": message.sender.id,
                        "sender_name": message.sender.get_full_name() or message.sender.username,
                        "sender_avatar": await self.get_user_avatar(message.sender),
                        "timestamp": message.created_at.isoformat(),
                        "reply_to": str(message.reply_to.id) if message.reply_to else None,
                        "is_edited": message.is_edited,
                        "file_url": message.file.url if message.file else None,
                    },
                },
            )

            # Atualizar atividade da sala
            await self.update_room_activity()

    async def handle_typing_start(self):
        """Usuário começou a digitar"""
        await self.set_user_typing(True)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_start",
                "user_id": self.user.id,
                "username": self.user.username,
            },
        )

    async def handle_typing_stop(self):
        """Usuário parou de digitar"""
        await self.set_user_typing(False)
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "typing_stop",
                "user_id": self.user.id,
                "username": self.user.username,
            },
        )

    async def handle_message_read(self, data):
        """Marca mensagem como lida"""
        message_id = data.get("message_id")
        if message_id:
            await self.mark_message_as_read(message_id)

            # Notificar remetente sobre leitura
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_read",
                    "message_id": message_id,
                    "reader_id": self.user.id,
                    "reader_name": self.user.get_full_name() or self.user.username,
                },
            )

    async def handle_file_upload(self, data):
        """Processa upload de arquivo"""
        file_data = data.get("file_data")
        file_name = data.get("file_name")
        file_type = data.get("file_type", "file")

        # Salvar arquivo e criar mensagem
        message = await self.save_file_message(file_data, file_name, file_type)

        if message:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "file_message",
                    "message": {
                        "id": str(message.id),
                        "content": message.content,
                        "message_type": message.message_type,
                        "sender_id": message.sender.id,
                        "sender_name": message.sender.get_full_name() or message.sender.username,
                        "timestamp": message.created_at.isoformat(),
                        "file_url": message.file.url,
                        "file_name": message.file_name,
                        "file_size": message.file_size,
                    },
                },
            )

    async def handle_reaction(self, data):
        """Adiciona reação a mensagem"""
        message_id = data.get("message_id")
        reaction = data.get("reaction")

        if message_id and reaction:
            await self.add_reaction(message_id, reaction)

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    "type": "message_reaction",
                    "message_id": message_id,
                    "reaction": reaction,
                    "user_id": self.user.id,
                    "username": self.user.username,
                },
            )

    # WebSocket message handlers
    async def chat_message(self, event):
        """Envia mensagem de chat"""
        await self.send(text_data=json.dumps({"type": "chat_message", "message": event["message"]}))

    async def file_message(self, event):
        """Envia mensagem de arquivo"""
        await self.send(text_data=json.dumps({"type": "file_message", "message": event["message"]}))

    async def typing_start(self, event):
        """Notifica que usuário começou a digitar"""
        if event["user_id"] != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {"type": "typing_start", "user_id": event["user_id"], "username": event["username"]}
                )
            )

    async def typing_stop(self, event):
        """Notifica que usuário parou de digitar"""
        if event["user_id"] != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {"type": "typing_stop", "user_id": event["user_id"], "username": event["username"]}
                )
            )

    async def message_read(self, event):
        """Notifica leitura de mensagem"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_read",
                    "message_id": event["message_id"],
                    "reader_id": event["reader_id"],
                    "reader_name": event["reader_name"],
                }
            )
        )

    async def message_reaction(self, event):
        """Notifica reação em mensagem"""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "message_reaction",
                    "message_id": event["message_id"],
                    "reaction": event["reaction"],
                    "user_id": event["user_id"],
                    "username": event["username"],
                }
            )
        )

    async def user_joined(self, event):
        """Notifica que usuário entrou na sala"""
        if event["user_id"] != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "user_joined",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "full_name": event["full_name"],
                        "timestamp": event["timestamp"],
                    }
                )
            )

    async def user_left(self, event):
        """Notifica que usuário saiu da sala"""
        if event["user_id"] != self.user.id:
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "user_left",
                        "user_id": event["user_id"],
                        "username": event["username"],
                        "timestamp": event["timestamp"],
                    }
                )
            )

    async def send_error(self, message):
        """Envia mensagem de erro"""
        await self.send(text_data=json.dumps({"type": "error", "message": message}))

    # Database operations
    @database_sync_to_async
    def check_room_access(self):
        """Verifica se usuário tem acesso à sala"""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            participant = ChatParticipant.objects.filter(room=room, user=self.user, is_active=True).exists()
            return participant or self.user.is_staff
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, content, message_type="text", reply_to_id=None):
        """Salva mensagem no banco"""
        try:
            room = ChatRoom.objects.get(id=self.room_id)

            reply_to = None
            if reply_to_id:
                try:
                    reply_to = ChatMessage.objects.get(id=reply_to_id)
                except ChatMessage.DoesNotExist:
                    pass

            message = ChatMessage.objects.create(
                room=room, sender=self.user, content=content, message_type=message_type, reply_to=reply_to
            )

            # Incrementar contador de mensagens da sala
            room.message_count += 1
            room.last_activity = timezone.now()
            room.save(update_fields=["message_count", "last_activity"])

            return message

        except Exception as e:
            logger.error("Error saving message: %s", e, exc_info=True)
            return None

    @database_sync_to_async
    def save_file_message(self, file_data, file_name, file_type):
        """Salva mensagem com arquivo"""
        # Implementar upload de arquivo
        # Por enquanto, retorna None
        return None

    @database_sync_to_async
    def set_user_online(self, is_online):
        """Define status online do usuário"""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            participant, created = ChatParticipant.objects.get_or_create(
                room=room, user=self.user, defaults={"is_online": is_online, "last_seen": timezone.now()}
            )

            if not created:
                participant.is_online = is_online
                participant.last_seen = timezone.now()
                participant.save(update_fields=["is_online", "last_seen"])

        except Exception as e:
            logger.error("Error setting user online status: %s", e, exc_info=True)

    @database_sync_to_async
    def set_user_typing(self, is_typing):
        """Define status de digitação do usuário"""
        try:
            participant = ChatParticipant.objects.get(room_id=self.room_id, user=self.user)
            participant.is_typing = is_typing
            participant.save(update_fields=["is_typing"])
        except Exception as e:
            logger.error("Error setting typing status: %s", e, exc_info=True)

    @database_sync_to_async
    def mark_message_as_read(self, message_id):
        """Marca mensagem como lida"""
        try:
            message = ChatMessage.objects.get(id=message_id)
            message.mark_as_read_by(self.user)
        except Exception as e:
            logger.error("Error marking message as read: %s", e, exc_info=True)

    @database_sync_to_async
    def add_reaction(self, message_id, reaction):
        """Adiciona reação a mensagem"""
        try:
            from .models import ChatReaction

            message = ChatMessage.objects.get(id=message_id)
            reaction_obj, created = ChatReaction.objects.get_or_create(
                message=message, user=self.user, reaction=reaction
            )
            return reaction_obj
        except Exception as e:
            logger.error("Error adding reaction: %s", e, exc_info=True)
            return None

    @database_sync_to_async
    def update_room_activity(self):
        """Atualiza última atividade da sala"""
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            room.last_activity = timezone.now()
            room.save(update_fields=["last_activity"])
        except Exception as e:
            logger.error("Error updating room activity: %s", e, exc_info=True)

    @database_sync_to_async
    def get_user_avatar(self, user):
        """Retorna avatar do usuário"""
        # Implementar lógica de avatar
        return f"https://ui-avatars.com/api/?name={user.get_full_name() or user.username}&background=667eea&color=fff"
