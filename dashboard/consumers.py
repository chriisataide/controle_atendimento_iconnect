"""
WebSocket Consumer para iConnect
Implementa comunicação em tempo real para notificações e atualizações
"""

import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.serializers.json import DjangoJSONEncoder

from .models import Ticket, Notification, Agent

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
        await self.channel_layer.group_add(
            "notifications_general",
            self.channel_name
        )
        
        # Adicionar ao grupo específico do usuário
        await self.channel_layer.group_add(
            self.user_group_name,
            self.channel_name
        )
        
        # Se for agente, adicionar ao grupo de agentes
        agent = await self.get_user_agent()
        if agent:
            await self.channel_layer.group_add(
                "agents",
                self.channel_name
            )
            
            # Marcar agente como ativo
            await self.update_agent_activity(agent, True)
        
        await self.accept()
        
        # Enviar notificações não lidas
        await self.send_unread_notifications()
        
        # Enviar estatísticas iniciais
        await self.send_dashboard_stats()
        
        print(f"✅ WebSocket conectado: {self.user.username}")
    
    async def disconnect(self, close_code):
        """Desconecta o cliente WebSocket"""
        
        # Remover dos grupos
        await self.channel_layer.group_discard(
            "notifications_general",
            self.channel_name
        )
        
        await self.channel_layer.group_discard(
            self.user_group_name,
            self.channel_name
        )
        
        # Se for agente, remover do grupo e marcar como inativo
        agent = await self.get_user_agent()
        if agent:
            await self.channel_layer.group_discard(
                "agents",
                self.channel_name
            )
            await self.update_agent_activity(agent, False)
        
        print(f"❌ WebSocket desconectado: {self.user.username}")
    
    async def receive(self, text_data):
        """Recebe mensagens do cliente"""
        
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            
            # Roteamento de mensagens
            if message_type == 'ping':
                await self.send_pong()
                
            elif message_type == 'mark_notification_read':
                await self.mark_notification_read(data.get('notification_id'))
                
            elif message_type == 'mark_all_notifications_read':
                await self.mark_all_notifications_read()
                
            elif message_type == 'request_stats':
                await self.send_dashboard_stats()
                
            elif message_type == 'subscribe_ticket':
                await self.subscribe_ticket(data.get('ticket_id'))
                
            elif message_type == 'unsubscribe_ticket':
                await self.unsubscribe_ticket(data.get('ticket_id'))
                
            elif message_type == 'agent_typing':
                await self.broadcast_agent_typing(data.get('ticket_id'))
                
            else:
                print(f"⚠️ Tipo de mensagem desconhecido: {message_type}")
                
        except json.JSONDecodeError:
            print("❌ Erro ao decodificar JSON do WebSocket")
        except Exception as e:
            print(f"❌ Erro no WebSocket: {e}")
    
    # ====================================
    # HANDLERS DE MENSAGENS
    # ====================================
    
    async def send_pong(self):
        """Responde ao ping do cliente"""
        await self.send(text_data=json.dumps({
            'type': 'pong',
            'timestamp': timezone.now().isoformat()
        }, cls=DjangoJSONEncoder))
    
    async def send_notification(self, event):
        """Envia notificação para o cliente"""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'data': event['data']
        }, cls=DjangoJSONEncoder))
    
    async def send_dashboard_update(self, event):
        """Envia atualização do dashboard"""
        await self.send(text_data=json.dumps({
            'type': 'dashboard_update',
            'data': event['data']
        }, cls=DjangoJSONEncoder))
    
    async def send_ticket_update(self, event):
        """Envia atualização de ticket"""
        await self.send(text_data=json.dumps({
            'type': 'ticket_update',
            'data': event['data']
        }, cls=DjangoJSONEncoder))
    
    async def send_agent_status(self, event):
        """Envia status de agente (online/offline/typing)"""
        await self.send(text_data=json.dumps({
            'type': 'agent_status',
            'data': event['data']
        }, cls=DjangoJSONEncoder))
    
    # ====================================
    # MÉTODOS DE NOTIFICAÇÃO
    # ====================================
    
    async def send_unread_notifications(self):
        """Envia notificações não lidas do usuário"""
        notifications = await self.get_unread_notifications()
        
        await self.send(text_data=json.dumps({
            'type': 'unread_notifications',
            'data': {
                'notifications': notifications,
                'count': len(notifications)
            }
        }, cls=DjangoJSONEncoder))
    
    async def mark_notification_read(self, notification_id):
        """Marca notificação específica como lida"""
        success = await self.mark_notification_as_read(notification_id)
        
        if success:
            unread_count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'notification_marked_read',
                'data': {
                    'notification_id': notification_id,
                    'unread_count': unread_count
                }
            }, cls=DjangoJSONEncoder))
    
    async def mark_all_notifications_read(self):
        """Marca todas as notificações como lidas"""
        count = await self.mark_all_notifications_as_read()
        
        await self.send(text_data=json.dumps({
            'type': 'all_notifications_marked_read',
            'data': {
                'marked_count': count,
                'unread_count': 0
            }
        }, cls=DjangoJSONEncoder))
    
    # ====================================
    # ESTATÍSTICAS DO DASHBOARD
    # ====================================
    
    async def send_dashboard_stats(self):
        """Envia estatísticas atualizadas do dashboard"""
        stats = await self.get_dashboard_statistics()
        
        await self.send(text_data=json.dumps({
            'type': 'dashboard_stats',
            'data': stats
        }, cls=DjangoJSONEncoder))
    
    # ====================================
    # SUBSCRIÇÃO DE TICKETS
    # ====================================
    
    async def subscribe_ticket(self, ticket_id):
        """Inscreve o usuário para receber atualizações de um ticket específico"""
        if ticket_id:
            ticket_group = f"ticket_{ticket_id}"
            await self.channel_layer.group_add(ticket_group, self.channel_name)
            
            await self.send(text_data=json.dumps({
                'type': 'subscribed_ticket',
                'data': {'ticket_id': ticket_id}
            }, cls=DjangoJSONEncoder))
    
    async def unsubscribe_ticket(self, ticket_id):
        """Desinscreve o usuário das atualizações de um ticket"""
        if ticket_id:
            ticket_group = f"ticket_{ticket_id}"
            await self.channel_layer.group_discard(ticket_group, self.channel_name)
            
            await self.send(text_data=json.dumps({
                'type': 'unsubscribed_ticket',
                'data': {'ticket_id': ticket_id}
            }, cls=DjangoJSONEncoder))
    
    async def broadcast_agent_typing(self, ticket_id):
        """Broadcasts que um agente está digitando em um ticket"""
        if ticket_id:
            agent = await self.get_user_agent()
            if agent:
                ticket_group = f"ticket_{ticket_id}"
                await self.channel_layer.group_send(ticket_group, {
                    'type': 'send_agent_status',
                    'data': {
                        'agent_id': agent.id,
                        'agent_name': agent.user.get_full_name(),
                        'status': 'typing',
                        'ticket_id': ticket_id,
                        'timestamp': timezone.now().isoformat()
                    }
                })
    
    # ====================================
    # DATABASE OPERATIONS (ASYNC)
    # ====================================
    
    @database_sync_to_async
    def get_user_agent(self):
        """Busca o agente associado ao usuário"""
        try:
            return Agent.objects.get(user=self.user)
        except Agent.DoesNotExist:
            return None
    
    @database_sync_to_async
    def update_agent_activity(self, agent, is_active):
        """Atualiza o status de atividade do agente"""
        agent.is_active = is_active
        agent.last_activity = timezone.now()
        agent.save(update_fields=['is_active', 'last_activity'])
    
    @database_sync_to_async
    def get_unread_notifications(self):
        """Busca notificações não lidas do usuário"""
        notifications = Notification.objects.filter(
            user=self.user,
            read=False
        ).order_by('-created_at')[:20]
        
        return [
            {
                'id': notif.id,
                'type': notif.type,
                'title': notif.title,
                'message': notif.message,
                'url': notif.url,
                'created_at': notif.created_at.isoformat(),
                'metadata': notif.metadata
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
            notification = Notification.objects.get(
                id=notification_id,
                user=self.user,
                read=False
            )
            notification.read = True
            notification.read_at = timezone.now()
            notification.save()
            return True
        except Notification.DoesNotExist:
            return False
    
    @database_sync_to_async
    def mark_all_notifications_as_read(self):
        """Marca todas as notificações como lidas"""
        return Notification.objects.filter(
            user=self.user,
            read=False
        ).update(
            read=True,
            read_at=timezone.now()
        )
    
    @database_sync_to_async
    def get_dashboard_statistics(self):
        """Busca estatísticas do dashboard"""
        now = timezone.now()
        today = now.replace(hour=0, minute=0, second=0)
        
        # Contar tickets por status
        tickets_today = Ticket.objects.filter(created_at__gte=today).count()
        tickets_open = Ticket.objects.filter(
            status__in=['NOVO', 'ABERTO', 'EM_ANDAMENTO']
        ).count()
        tickets_pending = Ticket.objects.filter(status='NOVO').count()
        tickets_resolved_today = Ticket.objects.filter(
            status='FECHADO',
            resolved_at__gte=today
        ).count()
        
        # Agentes ativos (atividade nos últimos 15 minutos)
        active_agents = Agent.objects.filter(
            is_active=True,
            last_activity__gte=now - timedelta(minutes=15)
        ).count()
        
        return {
            'tickets_today': tickets_today,
            'tickets_open': tickets_open,
            'tickets_pending': tickets_pending,
            'tickets_resolved_today': tickets_resolved_today,
            'active_agents': active_agents,
            'updated_at': now.isoformat()
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
    
    await channel_layer.group_send(user_group, {
        'type': 'send_notification',
        'data': notification_data
    })

async def broadcast_dashboard_update(stats_data: Dict[str, Any]):
    """
    Envia atualizações do dashboard para todos os usuários conectados
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send("notifications_general", {
        'type': 'send_dashboard_update',
        'data': stats_data
    })

async def broadcast_ticket_update(ticket_id: int, update_data: Dict[str, Any]):
    """
    Envia atualizações de ticket para usuários interessados
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    ticket_group = f"ticket_{ticket_id}"
    
    await channel_layer.group_send(ticket_group, {
        'type': 'send_ticket_update',
        'data': {
            'ticket_id': ticket_id,
            **update_data
        }
    })

async def broadcast_to_agents(data: Dict[str, Any], message_type: str = 'notification'):
    """
    Envia mensagem para todos os agentes conectados
    """
    from channels.layers import get_channel_layer
    
    channel_layer = get_channel_layer()
    
    await channel_layer.group_send("agents", {
        'type': f'send_{message_type}',
        'data': data
    })
