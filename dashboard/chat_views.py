"""
Views para Sistema de Chat Integrado Avançado
iConnect - Sistema de Atendimento Competitivo
"""
import json
import uuid
from datetime import datetime, timedelta
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Max, Prefetch, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages

from .models import (
    Ticket, Cliente,
    ChatRoom, ChatMessage, ChatParticipant, ChatSettings, ChatBot
)


@login_required
def chat_dashboard(request):
    """Dashboard principal do sistema de chat"""
    user = request.user
    
    # Salas ativas do usuário
    active_rooms = ChatRoom.objects.filter(
        participants__user=user,
        participants__is_active=True,
        status='active'
    ).annotate(
        last_message_time=Max('messages__created_at'),
        unread_count=Count('messages', filter=Q(
            messages__created_at__gt=F('participants__last_read_message__created_at')
        ) & ~Q(messages__sender=user))
    ).order_by('-last_activity')[:10]
    
    # Estatísticas
    stats = {
        'total_rooms': ChatRoom.objects.filter(participants__user=user).count(),
        'active_conversations': active_rooms.filter(status='active').count(),
        'unread_messages': sum(room.unread_count or 0 for room in active_rooms),
        'today_messages': ChatMessage.objects.filter(
            room__participants__user=user,
            created_at__date=timezone.now().date()
        ).count()
    }
    
    # Configurações do usuário
    chat_settings, created = ChatSettings.objects.get_or_create(user=user)
    
    context = {
        'title': 'Chat Dashboard',
        'active_rooms': active_rooms,
        'stats': stats,
        'chat_settings': chat_settings,
        'user_id': user.id,
    }
    
    return render(request, 'dashboard/chat/dashboard.html', context)


@login_required
def chat_room(request, room_id):
    """Interface da sala de chat"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    # Verificar se usuário tem acesso
    participant = ChatParticipant.objects.filter(
        room=room, user=request.user, is_active=True
    ).first()
    
    if not participant and not request.user.is_staff:
        messages.error(request, "Você não tem acesso a esta sala de chat.")
        return redirect('dashboard:chat_dashboard')
    
    # Criar participante se não existir (para staff)
    if not participant and request.user.is_staff:
        participant = ChatParticipant.objects.create(
            room=room,
            user=request.user,
            role='admin'
        )
    
    # Mensagens recentes (últimas 50)
    messages_queryset = room.messages.select_related('sender', 'reply_to').filter(
        is_deleted=False
    ).order_by('-created_at')[:50]
    
    messages_list = list(reversed(messages_queryset))
    
    # Participantes ativos
    participants = room.participants.filter(is_active=True).select_related('user')
    
    # Marcar mensagens como lidas
    unread_messages = room.messages.exclude(sender=request.user).exclude(
        read_receipts__user=request.user
    )
    
    for message in unread_messages:
        message.mark_as_read_by(request.user)
    
    # Atualizar last_seen do participante
    participant.last_seen = timezone.now()
    participant.save(update_fields=['last_seen'])
    
    context = {
        'title': f'Chat - {room.name}',
        'room': room,
        'messages': messages_list,
        'participants': participants,
        'participant': participant,
        'user_id': request.user.id,
        'room_json': json.dumps({
            'id': str(room.id),
            'name': room.name,
            'type': room.room_type,
            'participants_count': room.participant_count,
        })
    }
    
    return render(request, 'dashboard/chat/room.html', context)


@login_required
def create_chat_room(request):
    """Criar nova sala de chat"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        room_type = request.POST.get('room_type', 'private')
        ticket_id = request.POST.get('ticket_id')
        participants_ids = request.POST.getlist('participants')
        
        if not name:
            messages.error(request, "Nome da sala é obrigatório.")
            return redirect('dashboard:chat_dashboard')
        
        # Criar sala
        room = ChatRoom.objects.create(
            name=name,
            room_type=room_type,
            created_by=request.user,
            ticket_id=ticket_id if ticket_id else None
        )
        
        # Adicionar criador como admin
        ChatParticipant.objects.create(
            room=room,
            user=request.user,
            role='admin'
        )
        
        # Adicionar outros participantes
        for user_id in participants_ids:
            try:
                user = User.objects.get(id=user_id)
                ChatParticipant.objects.create(
                    room=room,
                    user=user,
                    role='client' if not user.is_staff else 'agent'
                )
            except User.DoesNotExist:
                continue
        
        # Atualizar contador de participantes
        room.participant_count = room.participants.filter(is_active=True).count()
        room.save(update_fields=['participant_count'])
        
        messages.success(request, f"Sala '{name}' criada com sucesso!")
        return redirect('dashboard:chat_room', room_id=room.id)
    
    # GET: Mostrar formulário
    users = User.objects.filter(is_active=True).exclude(id=request.user.id)
    tickets = Ticket.objects.filter(status__in=['aberto', 'em_andamento'])
    
    context = {
        'title': 'Criar Sala de Chat',
        'users': users,
        'tickets': tickets,
        'room_types': ChatRoom.ROOM_TYPES,
    }
    
    return render(request, 'dashboard/chat/create_room.html', context)


@login_required
def chat_history(request, room_id):
    """Histórico completo de mensagens"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    # Verificar acesso
    if not ChatParticipant.objects.filter(room=room, user=request.user, is_active=True).exists():
        if not request.user.is_staff:
            messages.error(request, "Acesso negado.")
            return redirect('dashboard:chat_dashboard')
    
    # Filtros
    date_from = request.GET.get('from')
    date_to = request.GET.get('to')
    sender_id = request.GET.get('sender')
    message_type = request.GET.get('type')
    
    messages_qs = room.messages.select_related('sender').filter(is_deleted=False)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            messages_qs = messages_qs.filter(created_at__date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            messages_qs = messages_qs.filter(created_at__date__lte=date_to)
        except ValueError:
            pass
    
    if sender_id:
        messages_qs = messages_qs.filter(sender_id=sender_id)
    
    if message_type:
        messages_qs = messages_qs.filter(message_type=message_type)
    
    # Paginação
    paginator = Paginator(messages_qs.order_by('-created_at'), 50)
    page_number = request.GET.get('page')
    messages_page = paginator.get_page(page_number)
    
    # Participantes para filtro
    participants = room.participants.select_related('user').filter(is_active=True)
    
    context = {
        'title': f'Histórico - {room.name}',
        'room': room,
        'messages': messages_page,
        'participants': participants,
        'filters': {
            'from': date_from.strftime('%Y-%m-%d') if date_from else '',
            'to': date_to.strftime('%Y-%m-%d') if date_to else '',
            'sender': sender_id,
            'type': message_type,
        }
    }
    
    return render(request, 'dashboard/chat/history.html', context)


@login_required
def chat_settings_view(request):
    """Configurações de chat do usuário"""
    settings, created = ChatSettings.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Atualizar configurações
        settings.notifications_enabled = request.POST.get('notifications_enabled') == 'on'
        settings.sound_notifications = request.POST.get('sound_notifications') == 'on'
        settings.desktop_notifications = request.POST.get('desktop_notifications') == 'on'
        settings.email_notifications = request.POST.get('email_notifications') == 'on'
        settings.theme = request.POST.get('theme', 'light')
        settings.font_size = request.POST.get('font_size', 'medium')
        settings.show_online_status = request.POST.get('show_online_status') == 'on'
        settings.show_typing_indicator = request.POST.get('show_typing_indicator') == 'on'
        settings.show_read_receipts = request.POST.get('show_read_receipts') == 'on'
        settings.auto_response_enabled = request.POST.get('auto_response_enabled') == 'on'
        settings.auto_response_message = request.POST.get('auto_response_message', '')
        
        settings.save()
        messages.success(request, "Configurações salvas com sucesso!")
        return redirect('dashboard:chat_settings')
    
    context = {
        'title': 'Configurações de Chat',
        'settings': settings,
    }
    
    return render(request, 'dashboard/chat/settings.html', context)


# ========== APIs AJAX ==========

@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_send_message(request):
    """API para enviar mensagem via AJAX"""
    try:
        data = json.loads(request.body)
        room_id = data.get('room_id')
        content = data.get('content', '').strip()
        message_type = data.get('message_type', 'text')
        reply_to_id = data.get('reply_to')
        
        if not room_id or not content:
            return JsonResponse({'error': 'Dados incompletos'}, status=400)
        
        room = get_object_or_404(ChatRoom, id=room_id)
        
        # Verificar participação
        if not ChatParticipant.objects.filter(room=room, user=request.user, is_active=True).exists():
            return JsonResponse({'error': 'Acesso negado'}, status=403)
        
        # Criar mensagem
        reply_to = None
        if reply_to_id:
            try:
                reply_to = ChatMessage.objects.get(id=reply_to_id, room=room)
            except ChatMessage.DoesNotExist:
                pass
        
        message = ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content=content,
            message_type=message_type,
            reply_to=reply_to
        )
        
        # Atualizar estatísticas da sala
        room.message_count += 1
        room.last_activity = timezone.now()
        room.save(update_fields=['message_count', 'last_activity'])
        
        return JsonResponse({
            'success': True,
            'message': {
                'id': str(message.id),
                'content': message.content,
                'sender_name': message.sender.get_full_name() or message.sender.username,
                'timestamp': message.created_at.isoformat(),
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def api_room_participants(request, room_id):
    """API para listar participantes da sala"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if not ChatParticipant.objects.filter(room=room, user=request.user, is_active=True).exists():
        return JsonResponse({'error': 'Acesso negado'}, status=403)
    
    participants = room.participants.filter(is_active=True).select_related('user')
    
    data = [{
        'id': p.user.id,
        'username': p.user.username,
        'full_name': p.user.get_full_name(),
        'role': p.role,
        'is_online': p.is_online,
        'is_typing': p.is_typing,
        'last_seen': p.last_seen.isoformat() if p.last_seen else None,
        'avatar_url': f"https://ui-avatars.com/api/?name={p.user.get_full_name() or p.user.username}&background=667eea&color=fff"
    } for p in participants]
    
    return JsonResponse({'participants': data})


@login_required
def api_recent_rooms(request):
    """API para salas recentes do usuário"""
    rooms = ChatRoom.objects.filter(
        participants__user=request.user,
        participants__is_active=True
    ).annotate(
        last_message_time=Max('messages__created_at'),
        unread_count=Count('messages', filter=Q(
            messages__created_at__gt=F('participants__last_read_message__created_at')
        ) & ~Q(messages__sender=request.user))
    ).order_by('-last_activity')[:20]
    
    data = [{
        'id': str(room.id),
        'name': room.name,
        'type': room.room_type,
        'participant_count': room.participant_count,
        'unread_count': room.unread_count or 0,
        'last_activity': room.last_activity.isoformat() if room.last_activity else None,
        'status': room.status,
    } for room in rooms]
    
    return JsonResponse({'rooms': data})


@login_required 
@require_http_methods(["POST"])
def api_create_ticket_from_chat(request, room_id):
    """Criar ticket a partir de conversa de chat"""
    room = get_object_or_404(ChatRoom, id=room_id)
    
    if not ChatParticipant.objects.filter(room=room, user=request.user, is_active=True).exists():
        return JsonResponse({'error': 'Acesso negado'}, status=403)
    
    try:
        data = json.loads(request.body)
        title = data.get('title', f'Chat: {room.name}')
        description = data.get('description', '')
        priority = data.get('priority', 'media')
        
        # Buscar cliente participante
        client_participant = room.participants.filter(
            role='client', is_active=True
        ).select_related('user').first()
        
        if not client_participant:
            return JsonResponse({'error': 'Nenhum cliente encontrado na conversa'}, status=400)
        
        # Criar cliente se não existir
        cliente, created = Cliente.objects.get_or_create(
            email=client_participant.user.email,
            defaults={
                'nome': client_participant.user.get_full_name() or client_participant.user.username,
                'telefone': '',
            }
        )
        
        # Criar ticket
        ticket = Ticket.objects.create(
            titulo=title,
            descricao=description,
            cliente=cliente,
            prioridade=priority,
            created_by=request.user
        )
        
        # Vincular sala ao ticket
        room.ticket = ticket
        room.save(update_fields=['ticket'])
        
        # Criar mensagem de sistema
        ChatMessage.objects.create(
            room=room,
            sender=request.user,
            content=f"Ticket #{ticket.id} criado a partir desta conversa.",
            message_type='system'
        )
        
        return JsonResponse({
            'success': True,
            'ticket_id': ticket.id,
            'ticket_url': f'/dashboard/tickets/{ticket.id}/'
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def chatbot_settings(request):
    """Configurações do ChatBot"""
    if not request.user.is_staff:
        messages.error(request, "Acesso negado.")
        return redirect('dashboard:chat_dashboard')
    
    chatbot, created = ChatBot.objects.get_or_create(id=1)
    
    if request.method == 'POST':
        chatbot.name = request.POST.get('name', chatbot.name)
        chatbot.is_active = request.POST.get('is_active') == 'on'
        chatbot.greeting_message = request.POST.get('greeting_message', chatbot.greeting_message)
        chatbot.fallback_message = request.POST.get('fallback_message', chatbot.fallback_message)
        chatbot.handoff_keywords = request.POST.get('handoff_keywords', chatbot.handoff_keywords)
        chatbot.max_tokens = int(request.POST.get('max_tokens', chatbot.max_tokens))
        chatbot.temperature = float(request.POST.get('temperature', chatbot.temperature))
        chatbot.weekend_active = request.POST.get('weekend_active') == 'on'
        
        chatbot.save()
        messages.success(request, "Configurações do ChatBot salvas!")
        return redirect('dashboard:chatbot_settings')
    
    context = {
        'title': 'Configurações do ChatBot',
        'chatbot': chatbot,
    }
    
    return render(request, 'dashboard/chat/chatbot_settings.html', context)
