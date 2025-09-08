"""
Sistema de notificações do iConnect.
Suporte para email, Slack e WhatsApp.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
import requests
import json

logger = logging.getLogger(__name__)


class NotificationService:
    """Serviço centralizado de notificações"""
    
    def __init__(self):
        self.slack_config = getattr(settings, 'SLACK_CONFIG', {})
        self.whatsapp_config = getattr(settings, 'WHATSAPP_CONFIG', {})
    
    def send_ticket_notification(self, ticket, event_type, recipient_email=None, extra_context=None):
        """Envia notificação relacionada a tickets"""
        context = {
            'ticket': ticket,
            'event_type': event_type,
            'site_url': getattr(settings, 'SITE_URL', 'http://localhost:8000'),
            **(extra_context or {})
        }
        
        # Email
        if recipient_email:
            self._send_email_notification(recipient_email, event_type, context)
        
        # Slack
        if self.slack_config.get('WEBHOOK_URL'):
            self._send_slack_notification(event_type, context)
        
        # WhatsApp (se telefone disponível)
        phone = getattr(ticket.cliente, 'telefone', None)
        if phone and self.whatsapp_config.get('ACCESS_TOKEN'):
            self._send_whatsapp_notification(phone, event_type, context)
    
    def _send_email_notification(self, recipient_email, event_type, context):
        """Envia notificação por email"""
        try:
            email_templates = {
                'ticket_created': {
                    'subject': f'Novo Ticket #{context["ticket"].numero} Criado',
                    'template': 'notifications/email/ticket_created.html'
                },
                'ticket_updated': {
                    'subject': f'Ticket #{context["ticket"].numero} Atualizado',
                    'template': 'notifications/email/ticket_updated.html'
                },
                'ticket_assigned': {
                    'subject': f'Ticket #{context["ticket"].numero} Atribuído a Você',
                    'template': 'notifications/email/ticket_assigned.html'
                },
                'ticket_resolved': {
                    'subject': f'Ticket #{context["ticket"].numero} Resolvido',
                    'template': 'notifications/email/ticket_resolved.html'
                },
                'sla_warning': {
                    'subject': f'⚠️ SLA Alert - Ticket #{context["ticket"].numero}',
                    'template': 'notifications/email/sla_warning.html'
                },
                'sla_breach': {
                    'subject': f'🚨 SLA BREACH - Ticket #{context["ticket"].numero}',
                    'template': 'notifications/email/sla_breach.html'
                }
            }
            
            template_config = email_templates.get(event_type)
            if not template_config:
                logger.warning(f"Template de email não encontrado para evento: {event_type}")
                return
            
            html_content = render_to_string(template_config['template'], context)
            text_content = strip_tags(html_content)
            
            send_mail(
                subject=template_config['subject'],
                message=text_content,
                html_message=html_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                fail_silently=False
            )
            
            logger.info(f"Email enviado para {recipient_email}: {event_type}")
            
        except Exception as e:
            logger.error(f"Erro ao enviar email: {str(e)}")
    
    def _send_slack_notification(self, event_type, context):
        """Envia notificação para Slack"""
        try:
            ticket = context['ticket']
            
            slack_messages = {
                'ticket_created': {
                    'text': f'🆕 Novo Ticket Criado',
                    'color': 'good',
                    'fields': [
                        {'title': 'Número', 'value': ticket.numero, 'short': True},
                        {'title': 'Cliente', 'value': ticket.cliente.nome, 'short': True},
                        {'title': 'Título', 'value': ticket.titulo, 'short': False},
                        {'title': 'Prioridade', 'value': ticket.prioridade.upper(), 'short': True}
                    ]
                },
                'sla_warning': {
                    'text': f'⚠️ Aviso de SLA',
                    'color': 'warning',
                    'fields': [
                        {'title': 'Ticket', 'value': f'#{ticket.numero}', 'short': True},
                        {'title': 'Tempo Restante', 'value': context.get('time_remaining', 'N/A'), 'short': True}
                    ]
                },
                'sla_breach': {
                    'text': f'🚨 VIOLAÇÃO DE SLA',
                    'color': 'danger',
                    'fields': [
                        {'title': 'Ticket', 'value': f'#{ticket.numero}', 'short': True},
                        {'title': 'Tempo Excedido', 'value': context.get('time_exceeded', 'N/A'), 'short': True}
                    ]
                }
            }
            
            message_config = slack_messages.get(event_type)
            if not message_config:
                return
            
            payload = {
                'channel': self.slack_config.get('CHANNEL', '#atendimento'),
                'username': 'iConnect Bot',
                'icon_emoji': ':robot_face:',
                'attachments': [{
                    'color': message_config['color'],
                    'text': message_config['text'],
                    'fields': message_config['fields'],
                    'footer': 'Sistema iConnect',
                    'ts': int(ticket.criado_em.timestamp())
                }]
            }
            
            response = requests.post(
                self.slack_config['WEBHOOK_URL'],
                data=json.dumps(payload),
                headers={'Content-Type': 'application/json'},
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"Mensagem Slack enviada: {event_type}")
            else:
                logger.error(f"Erro ao enviar Slack: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Erro ao enviar notificação Slack: {str(e)}")
    
    def _send_whatsapp_notification(self, phone, event_type, context):
        """Envia notificação via WhatsApp Business API"""
        try:
            ticket = context['ticket']
            
            # Limpar o número de telefone
            clean_phone = ''.join(filter(str.isdigit, phone))
            if not clean_phone.startswith('55'):
                clean_phone = '55' + clean_phone
            
            whatsapp_messages = {
                'ticket_created': {
                    'template': 'ticket_created',
                    'parameters': [ticket.numero, ticket.titulo]
                },
                'ticket_updated': {
                    'template': 'ticket_updated',
                    'parameters': [ticket.numero, ticket.status.upper()]
                },
                'ticket_resolved': {
                    'template': 'ticket_resolved',
                    'parameters': [ticket.numero]
                }
            }
            
            message_config = whatsapp_messages.get(event_type)
            if not message_config:
                return
            
            url = f"{self.whatsapp_config['BASE_URL']}/{self.whatsapp_config['PHONE_NUMBER_ID']}/messages"
            
            headers = {
                'Authorization': f"Bearer {self.whatsapp_config['ACCESS_TOKEN']}",
                'Content-Type': 'application/json'
            }
            
            payload = {
                'messaging_product': 'whatsapp',
                'to': clean_phone,
                'type': 'template',
                'template': {
                    'name': message_config['template'],
                    'language': {'code': 'pt_BR'},
                    'components': [{
                        'type': 'body',
                        'parameters': [{'type': 'text', 'text': param} for param in message_config['parameters']]
                    }]
                }
            }
            
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
            
            if response.status_code == 200:
                logger.info(f"WhatsApp enviado para {clean_phone}: {event_type}")
            else:
                logger.error(f"Erro WhatsApp: {response.status_code} - {response.text}")
                
        except Exception as e:
            logger.error(f"Erro ao enviar WhatsApp: {str(e)}")


# Instância global do serviço de notificações
notification_service = NotificationService()
