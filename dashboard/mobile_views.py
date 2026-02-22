
from django.template.loader import render_to_string
from django.core.paginator import Paginator
# API AJAX para scroll infinito/paginação mobile
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required

@login_required
@require_GET
def mobile_tickets_ajax(request):
    """Retorna tickets paginados para scroll infinito (AJAX)"""
    page = int(request.GET.get('page', 1))
    per_page = int(request.GET.get('per_page', 20))
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    search = request.GET.get('search')

    user_agent = None
    try:
        user_agent = PerfilAgente.objects.get(user=request.user)
    except PerfilAgente.DoesNotExist:
        pass

    if user_agent or request.user.is_staff:
        tickets = Ticket.objects.filter(agente=request.user)
    else:
        customer = None
        try:
            customer = Cliente.objects.get(email=request.user.email)
            tickets = Ticket.objects.filter(cliente=customer)
        except Cliente.DoesNotExist:
            tickets = Ticket.objects.none()

    if status_filter:
        tickets = tickets.filter(status=status_filter)
    if priority_filter:
        tickets = tickets.filter(prioridade=priority_filter)
    if search:
        tickets = tickets.filter(
            Q(titulo__icontains=search) |
            Q(descricao__icontains=search) |
            Q(numero__icontains=search)
        )
    tickets = tickets.order_by('-criado_em')

    paginator = Paginator(tickets, per_page)
    page_obj = paginator.get_page(page)
    html = render_to_string('mobile/_ticket_list_items.html', {
        'tickets': page_obj.object_list,
        'is_agent': bool(user_agent or request.user.is_staff),
        'is_mobile': True
    })
    return JsonResponse({
        'html': html,
        'has_next': page_obj.has_next(),
        'has_previous': page_obj.has_previous(),
        'num_pages': paginator.num_pages,
        'total': paginator.count,
        'page': page_obj.number,
        'per_page': per_page
    })
"""
Sistema Mobile-Friendly para iConnect
Interface otimizada para dispositivos móveis
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q, Count
from django.contrib import messages
import json

from .models import Ticket, Cliente, PerfilAgente, CategoriaTicket, InteracaoTicket
from django.contrib.auth.models import User

@login_required
def mobile_dashboard(request):
    """Dashboard otimizado para mobile"""
    
    # Estatísticas rápidas
    user_agent = None
    try:
        user_agent = PerfilAgente.objects.get(user=request.user)
    except PerfilAgente.DoesNotExist:
        pass
    
    if user_agent or request.user.is_staff:
        # Dashboard para agentes
        my_tickets = Ticket.objects.filter(agente=request.user).order_by('-criado_em')[:10]
        
        context = {
            'my_tickets': my_tickets,
            'total_tickets': Ticket.objects.count(),
            'open_tickets': Ticket.objects.filter(status='aberto').count(),
            'in_progress_tickets': Ticket.objects.filter(status='em_andamento').count(),
            'resolved_tickets': Ticket.objects.filter(status='resolvido').count(),
            'is_agent': True,
            'is_mobile': True
        }
    else:
        # Dashboard para clientes
        customer = None
        try:
            customer = Cliente.objects.get(email=request.user.email)
        except Cliente.DoesNotExist:
            pass
        
        if customer:
            my_tickets = Ticket.objects.filter(cliente=customer).order_by('-criado_em')[:10]
            customer_tickets = Ticket.objects.filter(cliente=customer)
        else:
            my_tickets = []
            customer_tickets = Ticket.objects.none()
        
        context = {
            'my_tickets': my_tickets,
            'customer': customer,
            'total_tickets': customer_tickets.count(),
            'open_tickets': customer_tickets.filter(status='aberto').count(),
            'in_progress_tickets': customer_tickets.filter(status='em_andamento').count(),
            'resolved_tickets': customer_tickets.filter(status='resolvido').count(),
            'is_agent': False,
            'is_mobile': True
        }
    
    return render(request, 'mobile/dashboard.html', context)

@login_required
def mobile_ticket_list(request):
    """Lista de tickets otimizada para mobile"""
    
    # Filtros
    status_filter = request.GET.get('status')
    priority_filter = request.GET.get('priority')
    search = request.GET.get('search')
    
    user_agent = None
    try:
        user_agent = PerfilAgente.objects.get(user=request.user)
    except PerfilAgente.DoesNotExist:
        pass
    
    if user_agent or request.user.is_staff:
        # Tickets do agente
        tickets = Ticket.objects.filter(agente=request.user)
    else:
        # Tickets do cliente
        customer = None
        try:
            customer = Cliente.objects.get(email=request.user.email)
            tickets = Ticket.objects.filter(cliente=customer)
        except Cliente.DoesNotExist:
            tickets = Ticket.objects.none()
    
    # Aplicar filtros
    if status_filter:
        tickets = tickets.filter(status=status_filter)
    
    if priority_filter:
        tickets = tickets.filter(prioridade=priority_filter)
    
    if search:
        tickets = tickets.filter(
            Q(titulo__icontains=search) |
            Q(descricao__icontains=search) |
            Q(numero__icontains=search)
        )
    
    tickets = tickets.order_by('-criado_em')[:50]
    
    context = {
        'tickets': tickets,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search': search,
        'is_agent': bool(user_agent or request.user.is_staff),
        'is_mobile': True
    }
    
    return render(request, 'mobile/ticket_list.html', context)

@login_required
def mobile_ticket_detail(request, ticket_id):
    """Detalhes do ticket otimizados para mobile"""
    
    ticket = get_object_or_404(Ticket, id=ticket_id)
    
    # Verificar permissões
    user_agent = None
    try:
        user_agent = PerfilAgente.objects.get(user=request.user)
    except PerfilAgente.DoesNotExist:
        pass
    
    if not (user_agent or request.user.is_staff):
        # Se não é agente, verificar se é o cliente do ticket
        try:
            customer = Cliente.objects.get(email=request.user.email)
            if ticket.cliente != customer:
                messages.error(request, 'Você não tem permissão para ver este ticket.')
                return redirect('mobile:mobile_dashboard')
        except Cliente.DoesNotExist:
            messages.error(request, 'Você não tem permissão para ver este ticket.')
            return redirect('mobile:mobile_dashboard')
    
    # Adicionar comentário
    if request.method == 'POST' and 'comment' in request.POST:
        comment_text = request.POST.get('comment')
        if comment_text:
            InteracaoTicket.objects.create(
                ticket=ticket,
                usuario=request.user,
                conteudo=comment_text,
                tipo='comentario'
            )
            messages.success(request, 'Comentário adicionado com sucesso!')
            return redirect('mobile:ticket_detail', ticket_id=ticket.id)
    
    # Atualizar status
    if request.method == 'POST' and 'status' in request.POST:
        new_status = request.POST.get('status')
        if new_status and (user_agent or request.user.is_staff):
            ticket.status = new_status
            ticket.save()
            
            # Adicionar interacao sobre mudança de status
            InteracaoTicket.objects.create(
                ticket=ticket,
                usuario=request.user,
                conteudo=f'Status alterado para: {ticket.get_status_display()}',
                tipo='sistema'
            )
            
            messages.success(request, 'Status atualizado com sucesso!')
            return redirect('mobile:ticket_detail', ticket_id=ticket.id)
    
    # Buscar interações
    comments = InteracaoTicket.objects.filter(ticket=ticket).order_by('criado_em')
    
    context = {
        'ticket': ticket,
        'comments': comments,
        'can_edit': bool(user_agent or request.user.is_staff),
        'is_agent': bool(user_agent or request.user.is_staff),
        'is_mobile': True
    }
    
    return render(request, 'mobile/ticket_detail.html', context)

@login_required
def mobile_create_ticket(request):
    """Criação rápida de ticket no mobile"""
    
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        descricao = request.POST.get('descricao')
        prioridade = request.POST.get('prioridade', 'media')
        categoria_id = request.POST.get('categoria')
        latitude = request.POST.get('latitude')
        longitude = request.POST.get('longitude')
        
        if titulo and descricao:
            # Buscar ou criar cliente
            customer = None
            try:
                customer = Cliente.objects.get(email=request.user.email)
            except Cliente.DoesNotExist:
                customer = Cliente.objects.create(
                    nome=request.user.get_full_name() or request.user.username,
                    email=request.user.email
                )
            
            # Buscar categoria
            categoria = None
            if categoria_id:
                try:
                    categoria = CategoriaTicket.objects.get(id=categoria_id)
                except CategoriaTicket.DoesNotExist:
                    pass
            
            # Criar ticket
            ticket = Ticket.objects.create(
                titulo=titulo,
                descricao=descricao,
                cliente=customer,
                categoria=categoria,
                prioridade=prioridade,
                status='aberto',
                origem='mobile'
            )
            
            # Adicionar localização se fornecida
            if latitude and longitude:
                InteracaoTicket.objects.create(
                    ticket=ticket,
                    usuario=request.user,
                    conteudo=f'Localização registrada: Lat {latitude}, Lng {longitude}',
                    tipo='sistema'
                )
            
            # Resposta para AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'ticket_id': ticket.id,
                    'ticket_number': ticket.numero,
                    'redirect_url': f'/mobile/ticket/{ticket.id}/'
                })
            
            messages.success(request, f'Ticket #{ticket.numero} criado com sucesso!')
            return redirect('mobile:ticket_detail', ticket_id=ticket.id)
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Título e descrição são obrigatórios.'
                })
            messages.error(request, 'Título e descrição são obrigatórios.')
    
    # Buscar categorias para o formulário
    categorias = CategoriaTicket.objects.all()
    
    context = {
        'categorias': categorias,
        'is_mobile': True
    }
    
    return render(request, 'mobile/create_ticket.html', context)

# Aliases para compatibilidade com URLs antigas
mobile_tickets = mobile_ticket_list
mobile_ticket_create = mobile_create_ticket

# Views adicionais que podem ser necessárias
@login_required
def mobile_chat(request):
    """Chat mobile (placeholder)"""
    return render(request, 'mobile/chat.html', {'is_mobile': True})

@login_required
def mobile_ticket_status_update(request, ticket_id):
    """Atualizar status do ticket via AJAX"""
    if request.method == 'POST':
        try:
            ticket = get_object_or_404(Ticket, id=ticket_id)
            
            # Verificar permissões
            user_agent = None
            try:
                user_agent = PerfilAgente.objects.get(user=request.user)
            except PerfilAgente.DoesNotExist:
                pass
            
            if not (user_agent or request.user.is_staff):
                return JsonResponse({'success': False, 'error': 'Sem permissão'})
            
            # Obter novo status
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                new_status = data.get('status')
            else:
                new_status = request.POST.get('status')
            
            if new_status and new_status in [choice[0] for choice in Ticket._meta.get_field('status').choices]:
                old_status = ticket.status
                ticket.status = new_status
                ticket.save()
                
                # Adicionar interação
                InteracaoTicket.objects.create(
                    ticket=ticket,
                    usuario=request.user,
                    conteudo=f'Status alterado de "{old_status}" para "{new_status}"',
                    tipo='sistema'
                )
                
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Status inválido'})
                
        except Exception:
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def mobile_ticket_comment(request, ticket_id):
    """Adicionar comentário ao ticket via AJAX"""
    if request.method == 'POST':
        try:
            ticket = get_object_or_404(Ticket, id=ticket_id)
            
            # Obter comentário
            if request.content_type == 'application/json':
                data = json.loads(request.body)
                comment_text = data.get('comment')
            else:
                comment_text = request.POST.get('comment')
            
            if comment_text:
                InteracaoTicket.objects.create(
                    ticket=ticket,
                    usuario=request.user,
                    conteudo=comment_text,
                    tipo='comentario'
                )
                
                return JsonResponse({'success': True})
            else:
                return JsonResponse({'success': False, 'error': 'Comentário vazio'})
                
        except Exception:
            return JsonResponse({'success': False, 'error': 'Erro interno do servidor'})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def mobile_tickets_check_updates(request):
    """Verificar se há atualizações nos tickets"""
    try:
        # Obter timestamp da última verificação
        last_check = request.GET.get('last_check')
        if last_check:
            last_check = timezone.datetime.fromtimestamp(float(last_check), tz=timezone.get_current_timezone())
        else:
            last_check = timezone.now() - timezone.timedelta(minutes=5)
        
        # Verificar por tickets atualizados
        user_agent = None
        try:
            user_agent = PerfilAgente.objects.get(user=request.user)
        except PerfilAgente.DoesNotExist:
            pass
        
        if user_agent or request.user.is_staff:
            # Tickets do agente
            updated_tickets = Ticket.objects.filter(
                agente=request.user,
                atualizado_em__gt=last_check
            ).exists()
        else:
            # Tickets do cliente
            customer = None
            try:
                customer = Cliente.objects.get(email=request.user.email)
                updated_tickets = Ticket.objects.filter(
                    cliente=customer,
                    atualizado_em__gt=last_check
                ).exists()
            except Cliente.DoesNotExist:
                updated_tickets = False
        
        return JsonResponse({
            'hasUpdates': updated_tickets,
            'timestamp': timezone.now().timestamp()
        })
        
    except Exception:
        return JsonResponse({'hasUpdates': False, 'error': 'Erro interno'})

@login_required
def mobile_ticket_upload_photo(request, ticket_id):
    """Upload de foto para o ticket"""
    if request.method == 'POST':
        try:
            ticket = get_object_or_404(Ticket, id=ticket_id)
            
            # Verificar se há arquivo
            if 'photo' not in request.FILES:
                return JsonResponse({'success': False, 'error': 'Nenhuma foto enviada'})
            
            photo = request.FILES['photo']
            
            # Validações básicas
            if photo.size > 10 * 1024 * 1024:  # 10MB
                return JsonResponse({'success': False, 'error': 'Arquivo muito grande'})
            
            if not photo.content_type.startswith('image/'):
                return JsonResponse({'success': False, 'error': 'Apenas imagens são permitidas'})
            
            # Por enquanto, apenas registrar que a foto foi enviada
            # Em uma implementação real, você salvaria o arquivo e criaria um TicketAnexo
            InteracaoTicket.objects.create(
                ticket=ticket,
                usuario=request.user,
                conteudo=f'Foto enviada: {photo.name} ({photo.size} bytes)',
                tipo='sistema'
            )
            
            return JsonResponse({'success': True, 'message': 'Foto enviada com sucesso'})
            
        except Exception:
            return JsonResponse({'success': False, 'error': 'Erro ao processar upload'})
    
    return JsonResponse({'success': False, 'error': 'Método não permitido'})

@login_required
def mobile_chat_ticket(request, ticket_id):
    """Chat específico do ticket (placeholder)"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, 'mobile/chat_ticket.html', {
        'ticket': ticket,
        'is_mobile': True
    })

@login_required
def mobile_offline(request):
    """Página offline para PWA"""
    context = {
        'is_mobile': True,
        'offline_message': 'Você está offline. Algumas funcionalidades podem estar limitadas.'
    }
    return render(request, 'mobile/offline.html', context)

@login_required
def mobile_notifications(request):
    """Notificações mobile"""
    notifications = []
    try:
        from .models import Notification
        
        # Marcar todas como lidas via POST
        if request.method == 'POST':
            Notification.objects.filter(user=request.user, read=False).update(
                read=True, read_at=timezone.now()
            )
            return JsonResponse({'success': True})
        
        notifications = Notification.objects.filter(
            user=request.user
        ).order_by('-created_at')[:50]
    except Exception:
        pass
    
    context = {
        'is_mobile': True,
        'notifications': notifications,
    }
    return render(request, 'mobile/notifications.html', context)
