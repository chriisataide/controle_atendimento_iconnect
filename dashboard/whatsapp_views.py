from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.models import User
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db.models import Q, Count, Avg, Sum
from django.contrib import messages
from django.core.paginator import Paginator
from django.views import View
from django.conf import settings
import json
import logging

from .models_whatsapp import (
    WhatsAppBusinessAccount, WhatsAppContact, WhatsAppConversation,
    WhatsAppMessage, WhatsAppTemplate, WhatsAppAutoResponse,
    WhatsAppAnalytics, WhatsAppWebhookLog
)
from .whatsapp_service import WhatsAppMessageProcessor, WhatsAppAnalyticsService, WhatsAppBusinessAPI
from .whatsapp_forms import WhatsAppAccountForm, WhatsAppTemplateForm, WhatsAppAutoResponseForm

logger = logging.getLogger(__name__)


@login_required
@staff_member_required
def whatsapp_dashboard(request):
    """Dashboard principal do WhatsApp"""
    accounts = WhatsAppBusinessAccount.objects.filter(ativo=True)
    
    # Métricas gerais
    total_conversas = WhatsAppConversation.objects.count()
    conversas_ativas = WhatsAppConversation.objects.filter(estado='ativa').count()
    mensagens_hoje = WhatsAppMessage.objects.filter(
        timestamp__date=timezone.now().date()
    ).count()
    
    # Analytics dos últimos 7 dias
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=7)
    
    analytics_data = []
    for account in accounts:
        analytics = WhatsAppAnalytics.objects.filter(
            account=account,
            data__gte=start_date,
            data__lte=end_date
        )
        
        account_data = {
            'account': account,
            'mensagens_enviadas': sum(a.mensagens_enviadas for a in analytics),
            'mensagens_recebidas': sum(a.mensagens_recebidas for a in analytics),
            'conversas_iniciadas': sum(a.conversas_iniciadas for a in analytics),
            'tickets_criados': sum(a.tickets_criados for a in analytics)
        }
        analytics_data.append(account_data)
    
    context = {
        'accounts': accounts,
        'total_conversas': total_conversas,
        'conversas_ativas': conversas_ativas,
        'mensagens_hoje': mensagens_hoje,
        'analytics_data': analytics_data,
    }
    
    return render(request, 'dashboard/whatsapp/dashboard.html', context)


@login_required
@staff_member_required
def whatsapp_conversations(request):
    """Lista de conversas do WhatsApp"""
    conversations = WhatsAppConversation.objects.select_related(
        'account', 'contact', 'agente', 'ticket'
    ).order_by('-iniciada_em')
    
    # Filtros
    account_id = request.GET.get('account')
    estado = request.GET.get('estado')
    agente_id = request.GET.get('agente')
    
    if account_id:
        conversations = conversations.filter(account_id=account_id)
    if estado:
        conversations = conversations.filter(estado=estado)
    if agente_id:
        conversations = conversations.filter(agente_id=agente_id)
    
    # Paginação
    paginator = Paginator(conversations, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'accounts': WhatsAppBusinessAccount.objects.filter(ativo=True),
        'agentes': User.objects.filter(is_staff=True),
        'current_filters': {
            'account': account_id,
            'estado': estado,
            'agente': agente_id,
        }
    }
    
    return render(request, 'dashboard/whatsapp/conversations.html', context)


@login_required
@staff_member_required
def whatsapp_conversation_detail(request, uuid):
    """Detalhes de uma conversa"""
    conversation = get_object_or_404(WhatsAppConversation, uuid=uuid)
    messages = conversation.mensagens.order_by('timestamp')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'assign_agent':
            agente_id = request.POST.get('agente_id')
            if agente_id:
                conversation.agente_id = agente_id
                conversation.save()
                messages.success(request, 'Agente atribuído com sucesso!')
        
        elif action == 'change_status':
            new_status = request.POST.get('status')
            if new_status in ['ativa', 'pausada', 'encerrada']:
                conversation.estado = new_status
                if new_status == 'encerrada':
                    conversation.encerrada_em = timezone.now()
                conversation.save()
                messages.success(request, 'Status alterado com sucesso!')
        
        elif action == 'send_message':
            message_text = request.POST.get('message')
            if message_text:
                try:
                    api = WhatsAppBusinessAPI(conversation.account)
                    result = api.send_text_message(
                        to=conversation.contact.whatsapp_id,
                        text=message_text
                    )
                    
                    # Salva mensagem enviada
                    WhatsAppMessage.objects.create(
                        whatsapp_message_id=result.get('messages', [{}])[0].get('id', ''),
                        conversation=conversation,
                        contact=conversation.contact,
                        agente=request.user,
                        direcao='outbound',
                        tipo='text',
                        conteudo=message_text,
                        timestamp=timezone.now(),
                        processada=True
                    )
                    
                    messages.success(request, 'Mensagem enviada com sucesso!')
                    
                except Exception as e:
                    messages.error(request, f'Erro ao enviar mensagem: {e}')
        
        return redirect('whatsapp_conversation_detail', uuid=uuid)
    
    context = {
        'conversation': conversation,
        'messages': messages,
        'agentes': User.objects.filter(is_staff=True),
    }
    
    return render(request, 'dashboard/whatsapp/conversation_detail.html', context)


@login_required
@staff_member_required
def whatsapp_contacts(request):
    """Lista de contatos do WhatsApp"""
    contacts = WhatsAppContact.objects.order_by('-ultimo_contato')
    
    # Busca
    search = request.GET.get('search')
    if search:
        contacts = contacts.filter(
            Q(nome__icontains=search) |
            Q(profile_name__icontains=search) |
            Q(phone_number__icontains=search)
        )
    
    # Paginação
    paginator = Paginator(contacts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
    }
    
    return render(request, 'dashboard/whatsapp/contacts.html', context)


@login_required
@staff_member_required
def whatsapp_templates(request):
    """Gerenciamento de templates"""
    templates = WhatsAppTemplate.objects.order_by('-criado_em')
    
    if request.method == 'POST':
        form = WhatsAppTemplateForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Template criado com sucesso!')
            return redirect('whatsapp_templates')
    else:
        form = WhatsAppTemplateForm()
    
    context = {
        'templates': templates,
        'form': form,
    }
    
    return render(request, 'dashboard/whatsapp/templates.html', context)


@login_required
@staff_member_required
def whatsapp_auto_responses(request):
    """Gerenciamento de respostas automáticas"""
    auto_responses = WhatsAppAutoResponse.objects.order_by('-criado_em')
    
    if request.method == 'POST':
        form = WhatsAppAutoResponseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Resposta automática criada com sucesso!')
            return redirect('whatsapp_auto_responses')
    else:
        form = WhatsAppAutoResponseForm()
    
    context = {
        'auto_responses': auto_responses,
        'form': form,
    }
    
    return render(request, 'dashboard/whatsapp/auto_responses.html', context)


@login_required
@staff_member_required
def whatsapp_analytics(request):
    """Analytics do WhatsApp"""
    accounts = WhatsAppBusinessAccount.objects.filter(ativo=True)
    
    # Período
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timezone.timedelta(days=days)
    
    analytics_data = []
    for account in accounts:
        metrics = WhatsAppAnalyticsService.get_account_metrics(account, days)
        analytics_data.append({
            'account': account,
            'metrics': metrics
        })
    
    # Dados para gráficos
    chart_data = []
    for i in range(days):
        date = start_date + timezone.timedelta(days=i)
        day_data = {
            'date': date.strftime('%d/%m'),
            'mensagens_enviadas': 0,
            'mensagens_recebidas': 0,
            'conversas_iniciadas': 0,
        }
        
        for account in accounts:
            analytics = WhatsAppAnalytics.objects.filter(
                account=account,
                data=date
            ).first()
            
            if analytics:
                day_data['mensagens_enviadas'] += analytics.mensagens_enviadas
                day_data['mensagens_recebidas'] += analytics.mensagens_recebidas
                day_data['conversas_iniciadas'] += analytics.conversas_iniciadas
        
        chart_data.append(day_data)
    
    context = {
        'accounts': accounts,
        'analytics_data': analytics_data,
        'chart_data': chart_data,
        'days': days,
    }
    
    return render(request, 'dashboard/whatsapp/analytics.html', context)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    """Webhook do WhatsApp Business API"""
    if request.method == 'GET':
        # Verificação do webhook
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        # Verifica token (deve estar nas settings)
        verify_token = getattr(settings, 'WHATSAPP_WEBHOOK_VERIFY_TOKEN', 'your_verify_token')
        
        if mode == 'subscribe' and token == verify_token:
            return HttpResponse(challenge)
        else:
            return HttpResponse('Failed validation', status=403)
    
    elif request.method == 'POST':
        try:
            # Log do webhook
            webhook_data = json.loads(request.body)
            
            WhatsAppWebhookLog.objects.create(
                tipo_evento='message',
                payload=webhook_data,
                ip_origem=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            # Processa webhook
            processor = WhatsAppMessageProcessor()
            result = processor.process_webhook(webhook_data)
            
            if result['status'] == 'success':
                return JsonResponse({'status': 'ok'})
            else:
                logger.error(f"Erro no webhook: {result}")
                return JsonResponse({'error': result['message']}, status=400)
                
        except Exception as e:
            logger.error(f"Erro no webhook do WhatsApp: {e}")
            return JsonResponse({'error': 'Internal server error'}, status=500)


# API Views para AJAX
@login_required
@staff_member_required
def whatsapp_api_send_message(request):
    """API para enviar mensagem"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            conversation_uuid = data.get('conversation_uuid')
            message_text = data.get('message')
            
            conversation = get_object_or_404(WhatsAppConversation, uuid=conversation_uuid)
            
            api = WhatsAppBusinessAPI(conversation.account)
            result = api.send_text_message(
                to=conversation.contact.whatsapp_id,
                text=message_text
            )
            
            # Salva mensagem enviada
            message = WhatsAppMessage.objects.create(
                whatsapp_message_id=result.get('messages', [{}])[0].get('id', ''),
                conversation=conversation,
                contact=conversation.contact,
                agente=request.user,
                direcao='outbound',
                tipo='text',
                conteudo=message_text,
                timestamp=timezone.now(),
                processada=True
            )
            
            return JsonResponse({
                'status': 'success',
                'message_id': message.id
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@login_required
@staff_member_required
def whatsapp_api_conversation_messages(request, uuid):
    """API para obter mensagens de uma conversa"""
    conversation = get_object_or_404(WhatsAppConversation, uuid=uuid)
    
    # Últimas mensagens
    last_message_id = request.GET.get('last_message_id')
    messages = conversation.mensagens.order_by('timestamp')
    
    if last_message_id:
        messages = messages.filter(id__gt=last_message_id)
    
    messages_data = []
    for message in messages:
        messages_data.append({
            'id': message.id,
            'content': message.conteudo,
            'direction': message.direcao,
            'type': message.tipo,
            'timestamp': message.timestamp.isoformat(),
            'agent': message.agente.get_full_name() if message.agente else None,
            'status': message.status,
        })
    
    return JsonResponse({
        'messages': messages_data,
        'conversation_status': conversation.estado
    })


@login_required
@staff_member_required
def whatsapp_api_stats(request):
    """API para estatísticas em tempo real"""
    today = timezone.now().date()
    
    stats = {
        'mensagens_hoje': WhatsAppMessage.objects.filter(
            timestamp__date=today
        ).count(),
        'conversas_ativas': WhatsAppConversation.objects.filter(
            estado='ativa'
        ).count(),
        'tickets_criados_hoje': WhatsAppConversation.objects.filter(
            ticket__criado_em__date=today
        ).count(),
        'agentes_online': User.objects.filter(
            is_staff=True,
            last_login__gte=timezone.now() - timezone.timedelta(minutes=15)
        ).count(),
    }
    
    return JsonResponse(stats)