"""
Integrações externas para WhatsApp Business API e Slack.
"""
import hmac
import hashlib
import logging
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.shortcuts import get_object_or_404
from .models import Ticket, Cliente, InteracaoTicket
from .automation import chatbot_service
from .notifications import notification_service

logger = logging.getLogger(__name__)


def _verify_whatsapp_signature(request):
    """
    Verifica a assinatura HMAC-SHA256 do webhook do WhatsApp Business API.
    Retorna True se a assinatura é válida ou se a verificação está desabilitada.
    """
    whatsapp_config = getattr(settings, 'WHATSAPP_CONFIG', {})
    app_secret = whatsapp_config.get('APP_SECRET', '')

    if not app_secret:
        # Se APP_SECRET não configurado, logar warning e permitir (dev mode)
        logger.warning("WHATSAPP_CONFIG.APP_SECRET não configurado — assinatura de webhook não verificada")
        return True

    signature_header = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
    if not signature_header or not signature_header.startswith('sha256='):
        logger.warning("Webhook WhatsApp recebido sem assinatura X-Hub-Signature-256")
        return False

    expected_signature = signature_header[7:]  # Remove 'sha256=' prefix
    computed_signature = hmac.new(
        app_secret.encode('utf-8'),
        request.body,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected_signature, computed_signature)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """Webhook para receber mensagens do WhatsApp Business API"""
    whatsapp_config = getattr(settings, 'WHATSAPP_CONFIG', {})
    verify_token = whatsapp_config.get('WEBHOOK_VERIFY_TOKEN', '')

    if request.method == 'GET':
        # Verificação do webhook
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == verify_token:
            logger.info("WhatsApp webhook verificado com sucesso")
            return HttpResponse(challenge)
        else:
            logger.error("Falha na verificação do webhook WhatsApp")
            return HttpResponse('Verification failed', status=403)

    elif request.method == 'POST':
        # Verificar assinatura HMAC antes de processar
        if not _verify_whatsapp_signature(request):
            logger.warning("Webhook WhatsApp rejeitado: assinatura inválida")
            return JsonResponse({'error': 'Invalid signature'}, status=403)

        try:
            body = json.loads(request.body)
            return _process_whatsapp_message(body)
        except json.JSONDecodeError:
            logger.error("Webhook WhatsApp: payload JSON inválido")
            return JsonResponse({'error': 'Invalid payload'}, status=400)
        except Exception as e:
            logger.error(f"Erro ao processar mensagem WhatsApp: {str(e)}")
            return JsonResponse({'error': 'Processing failed'}, status=500)


def _process_whatsapp_message(webhook_data):
    """Processa mensagem recebida via WhatsApp"""
    try:
        entry = webhook_data.get('entry', [{}])[0]
        changes = entry.get('changes', [{}])[0]
        value = changes.get('value', {})
        
        if 'messages' not in value:
            return JsonResponse({'status': 'no_messages'})
        
        messages = value['messages']
        for message in messages:
            from_number = message['from']
            message_body = message.get('text', {}).get('body', '')
            
            if not message_body:
                continue
            
            # Buscar cliente pelo telefone
            clean_phone = ''.join(filter(str.isdigit, from_number))
            cliente = Cliente.objects.filter(telefone__icontains=clean_phone[-10:]).first()
            
            if not cliente:
                # Criar cliente temporário
                cliente = Cliente.objects.create(
                    nome=f"Cliente WhatsApp {clean_phone[-4:]}",
                    telefone=from_number,
                    email=f"whatsapp_{clean_phone}@temp.com"
                )
            
            # Buscar ou criar ticket ativo
            ticket = Ticket.objects.filter(
                cliente=cliente,
                status__in=['aberto', 'em_andamento', 'aguardando_cliente']
            ).first()
            
            if not ticket:
                # Criar novo ticket
                ticket = Ticket.objects.create(
                    cliente=cliente,
                    titulo=f"Atendimento WhatsApp - {message_body[:50]}...",
                    descricao=message_body,
                    origem='whatsapp',
                    status='aberto',
                    prioridade='media'
                )
                
                # Tentar resposta do chatbot
                bot_response = chatbot_service.get_bot_response(message_body, ticket)
                if bot_response:
                    InteracaoTicket.objects.create(
                        ticket=ticket,
                        usuario=None,
                        tipo='sistema',
                        conteudo=bot_response,
                        publico=True
                    )
                    
                    # Enviar resposta via WhatsApp
                    _send_whatsapp_message(from_number, bot_response)
            else:
                # Adicionar interação ao ticket existente
                InteracaoTicket.objects.create(
                    ticket=ticket,
                    usuario=None,
                    tipo='cliente',
                    conteudo=message_body,
                    publico=True
                )
                
                # Atualizar status se estava aguardando cliente
                if ticket.status == 'aguardando_cliente':
                    ticket.status = 'em_andamento'
                    ticket.save()
            
            logger.info(f"Mensagem WhatsApp processada para ticket #{ticket.numero}")
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Erro ao processar webhook WhatsApp: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)


def _send_whatsapp_message(to_number, message_text):
    """Envia mensagem via WhatsApp Business API"""
    import requests
    
    try:
        whatsapp_config = getattr(settings, 'WHATSAPP_CONFIG', {})
        
        url = f"{whatsapp_config['BASE_URL']}/{whatsapp_config['PHONE_NUMBER_ID']}/messages"
        
        headers = {
            'Authorization': f"Bearer {whatsapp_config['ACCESS_TOKEN']}",
            'Content-Type': 'application/json'
        }
        
        payload = {
            'messaging_product': 'whatsapp',
            'to': to_number,
            'type': 'text',
            'text': {'body': message_text}
        }
        
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=10)
        
        if response.status_code == 200:
            logger.info(f"Mensagem WhatsApp enviada para {to_number}")
        else:
            logger.error(f"Erro ao enviar WhatsApp: {response.status_code}")
            
    except Exception as e:
        logger.error(f"Erro ao enviar mensagem WhatsApp: {str(e)}")


def _verify_slack_signature(request):
    """
    Verifica a assinatura do Slack usando Signing Secret.
    https://api.slack.com/authentication/verifying-requests-from-slack
    """
    slack_config = getattr(settings, 'SLACK_CONFIG', {})
    signing_secret = slack_config.get('SIGNING_SECRET', '')

    if not signing_secret:
        logger.warning("SLACK_CONFIG.SIGNING_SECRET não configurado — assinatura não verificada")
        return True

    timestamp = request.META.get('HTTP_X_SLACK_REQUEST_TIMESTAMP', '')
    signature = request.META.get('HTTP_X_SLACK_SIGNATURE', '')

    if not timestamp or not signature:
        return False

    # Proteger contra replay attacks (5 minutos)
    import time
    if abs(time.time() - int(timestamp)) > 300:
        return False

    sig_basestring = f"v0:{timestamp}:{request.body.decode('utf-8')}"
    computed = 'v0=' + hmac.new(
        signing_secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(computed, signature)


@csrf_exempt
@require_http_methods(["POST"])
def slack_webhook(request):
    """Webhook para receber comandos do Slack"""
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else dict(request.POST.items())

        # Verificação do URL do Slack (não precisa de assinatura)
        if data.get('type') == 'url_verification':
            return JsonResponse({'challenge': data.get('challenge')})

        # Verificar assinatura do Slack
        if not _verify_slack_signature(request):
            logger.warning("Webhook Slack rejeitado: assinatura inválida")
            return JsonResponse({'error': 'Invalid signature'}, status=403)

        # Processar comando
        if data.get('command'):
            return _process_slack_command(data)

        return JsonResponse({'status': 'ok'})

    except Exception as e:
        logger.error(f"Erro ao processar webhook Slack: {str(e)}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


def _process_slack_command(command_data):
    """Processa comandos recebidos do Slack"""
    try:
        command = command_data.get('command')
        text = command_data.get('text', '').strip()
        
        if command == '/ticket':
            return _handle_slack_ticket_command(text)
        elif command == '/status':
            return _handle_slack_status_command()
        
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': 'Comando não reconhecido. Use /ticket [numero] ou /status'
        })
        
    except Exception as e:
        logger.error(f"Erro ao processar comando Slack: {str(e)}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': 'Erro interno do servidor.'
        })


def _handle_slack_ticket_command(text):
    """Manipula comando /ticket do Slack"""
    try:
        if not text:
            # Listar tickets recentes
            tickets_recentes = Ticket.objects.filter(
                status__in=['aberto', 'em_andamento']
            ).order_by('-criado_em')[:5]
            
            if not tickets_recentes:
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': 'Nenhum ticket ativo encontrado.'
                })
            
            attachments = []
            for ticket in tickets_recentes:
                attachments.append({
                    'color': 'good' if ticket.status == 'aberto' else 'warning',
                    'fields': [
                        {'title': 'Número', 'value': ticket.numero, 'short': True},
                        {'title': 'Cliente', 'value': ticket.cliente.nome, 'short': True},
                        {'title': 'Status', 'value': ticket.status.upper(), 'short': True},
                        {'title': 'Prioridade', 'value': ticket.prioridade.upper(), 'short': True}
                    ]
                })
            
            return JsonResponse({
                'response_type': 'in_channel',
                'text': 'Tickets Ativos:',
                'attachments': attachments
            })
        
        else:
            # Buscar ticket específico
            try:
                ticket = get_object_or_404(Ticket, numero=text.upper())
                
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': f'Ticket #{ticket.numero}',
                    'attachments': [{
                        'color': 'good',
                        'fields': [
                            {'title': 'Cliente', 'value': ticket.cliente.nome, 'short': True},
                            {'title': 'Status', 'value': ticket.status.upper(), 'short': True},
                            {'title': 'Prioridade', 'value': ticket.prioridade.upper(), 'short': True},
                            {'title': 'Agente', 'value': ticket.agente.username if ticket.agente else 'Não atribuído', 'short': True},
                            {'title': 'Título', 'value': ticket.titulo, 'short': False}
                        ]
                    }]
                })
                
            except:
                return JsonResponse({
                    'response_type': 'ephemeral',
                    'text': f'Ticket {text.upper()} não encontrado.'
                })
    
    except Exception as e:
        logger.error(f"Erro no comando ticket Slack: {str(e)}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': 'Erro interno do servidor.'
        })


def _handle_slack_status_command():
    """Manipula comando /status do Slack"""
    try:
        # Estatísticas do sistema
        total_tickets = Ticket.objects.count()
        tickets_abertos = Ticket.objects.filter(status='aberto').count()
        tickets_em_andamento = Ticket.objects.filter(status='em_andamento').count()
        tickets_hoje = Ticket.objects.filter(criado_em__date=timezone.now().date()).count()
        
        return JsonResponse({
            'response_type': 'in_channel',
            'text': 'Status do Sistema iConnect',
            'attachments': [{
                'color': 'good',
                'fields': [
                    {'title': 'Total de Tickets', 'value': str(total_tickets), 'short': True},
                    {'title': 'Tickets Abertos', 'value': str(tickets_abertos), 'short': True},
                    {'title': 'Em Andamento', 'value': str(tickets_em_andamento), 'short': True},
                    {'title': 'Criados Hoje', 'value': str(tickets_hoje), 'short': True}
                ]
            }]
        })
        
    except Exception as e:
        logger.error(f"Erro no comando status Slack: {str(e)}")
        return JsonResponse({
            'response_type': 'ephemeral',
            'text': 'Erro ao obter status do sistema.'
        })
