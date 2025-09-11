"""
Sistema Mobile-Friendly para iConnect
Interface otimizada para dispositivos móveis
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Count
import json

from .models import Ticket, Cliente, PerfilAgente
from django.contrib.auth.models import User
from .forms import QuickTicketForm

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
        else:
            my_tickets = []
        
        context = {
            'my_tickets': my_tickets,
            'customer': customer,
            'is_agent': False,
            'is_mobile': True
        }
    
    return render(request, 'mobile/dashboard.html', context)

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q
import json

from .models import Ticket, Cliente, PerfilAgente
from django.contrib.auth.models import User
from .forms import QuickTicketForm, MobileCommentForm

@login_required
def mobile_dashboard(request):
    """Dashboard otimizado para mobile"""
    
    # Estatísticas rápidas
    user_agent = None
    try:
        user_agent = PerfilAgente.objects.get(user=request.user)
    except PerfilAgente.DoesNotExist:
        pass
    
    if user_agent:
        # Dashboard para agentes
        my_tickets = Ticket.objects.filter(agente=request.user).order_by('-criado_em')[:10]
        pending_count = my_tickets.filter(status__in=['NOVO', 'ABERTO', 'EM_ANDAMENTO']).count()
        today_resolved = my_tickets.filter(
            status='FECHADO',
            resolved_at__date=timezone.now().date()
        ).count()
        
        context = {
            'is_agent': True,
            'my_tickets': my_tickets,
            'pending_count': pending_count,
            'today_resolved': today_resolved,
            'is_mobile': True
        }
    else:
        # Dashboard para clientes
        try:
            customer = Customer.objects.get(email=request.user.email)
            my_tickets = Ticket.objects.filter(customer=customer).order_by('-created_at')[:10]
        except Customer.DoesNotExist:
            my_tickets = []
        
        context = {
            'is_agent': False,
            'my_tickets': my_tickets,
            'ticket_count': len(my_tickets),
            'is_mobile': True
        }
    
    return render(request, 'mobile/dashboard.html', context)

@login_required
def mobile_ticket_list(request):
    """Lista de tickets otimizada para mobile"""
    
    user_agent = None
    try:
        user_agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        pass
    
    # Filtros
    status_filter = request.GET.get('status', 'all')
    priority_filter = request.GET.get('priority', 'all')
    search_query = request.GET.get('q', '')
    
    if user_agent:
        # Tickets do agente
        tickets = Ticket.objects.filter(assigned_to=user_agent)
    else:
        # Tickets do cliente
        try:
            customer = Customer.objects.get(email=request.user.email)
            tickets = Ticket.objects.filter(customer=customer)
        except Customer.DoesNotExist:
            tickets = Ticket.objects.none()
    
    # Aplicar filtros
    if status_filter != 'all':
        tickets = tickets.filter(status=status_filter)
    
    if priority_filter != 'all':
        tickets = tickets.filter(priority=priority_filter)
    
    if search_query:
        tickets = tickets.filter(
            Q(title__icontains=search_query) |
            Q(ticket_number__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    tickets = tickets.order_by('-created_at')[:50]  # Limitar para performance
    
    context = {
        'tickets': tickets,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_query': search_query,
        'is_agent': bool(user_agent),
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
        user_agent = Agent.objects.get(user=request.user)
        has_access = (ticket.assigned_to == user_agent) or user_agent.is_supervisor
    except Agent.DoesNotExist:
        # Cliente
        try:
            customer = Customer.objects.get(email=request.user.email)
            has_access = ticket.customer == customer
        except Customer.DoesNotExist:
            has_access = False
    
    if not has_access:
        return redirect('mobile_dashboard')
    
    # Processar ações rápidas
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'change_status' and user_agent:
            new_status = request.POST.get('status')
            if new_status in ['ABERTO', 'EM_ANDAMENTO', 'RESOLVIDO', 'FECHADO']:
                ticket.status = new_status
                if new_status == 'FECHADO':
                    ticket.resolved_at = timezone.now()
                ticket.save()
                
                return JsonResponse({'success': True, 'new_status': new_status})
        
        elif action == 'change_priority' and user_agent:
            new_priority = request.POST.get('priority')
            if new_priority in ['BAIXA', 'MEDIA', 'ALTA', 'CRITICA']:
                ticket.priority = new_priority
                ticket.save()
                
                return JsonResponse({'success': True, 'new_priority': new_priority})
        
        elif action == 'add_comment':
            comment_text = request.POST.get('comment', '').strip()
            if comment_text:
                # Adicionar comentário (implementar modelo de comentários)
                # Por enquanto, adicionar à descrição
                timestamp = timezone.now().strftime('%d/%m/%Y %H:%M')
                user_name = request.user.get_full_name() or request.user.username
                
                new_comment = f"\n\n--- {user_name} ({timestamp}) ---\n{comment_text}"
                ticket.description += new_comment
                ticket.updated_at = timezone.now()
                ticket.save()
                
                return JsonResponse({'success': True, 'message': 'Comentário adicionado'})
    
    # Status e prioridades disponíveis
    status_choices = [
        ('NOVO', 'Novo'),
        ('ABERTO', 'Aberto'),
        ('EM_ANDAMENTO', 'Em Andamento'),
        ('RESOLVIDO', 'Resolvido'),
        ('FECHADO', 'Fechado')
    ]
    
    priority_choices = [
        ('BAIXA', 'Baixa'),
        ('MEDIA', 'Média'),
        ('ALTA', 'Alta'),
        ('CRITICA', 'Crítica')
    ]
    
    context = {
        'ticket': ticket,
        'is_agent': bool(user_agent),
        'status_choices': status_choices,
        'priority_choices': priority_choices,
        'is_mobile': True
    }
    
    return render(request, 'mobile/ticket_detail.html', context)

@login_required
def mobile_create_ticket(request):
    """Criação rápida de ticket no mobile"""
    
    if request.method == 'POST':
        form = QuickTicketForm(request.POST)
        
        if form.is_valid():
            # Buscar ou criar customer
            customer, created = Customer.objects.get_or_create(
                email=request.user.email,
                defaults={
                    'name': request.user.get_full_name() or request.user.username,
                    'phone': ''
                }
            )
            
            # Criar ticket
            ticket = Ticket.objects.create(
                customer=customer,
                title=form.cleaned_data['title'],
                description=form.cleaned_data['description'],
                priority=form.cleaned_data['priority'],
                status='NOVO',
                source='MOBILE'
            )
            
            return JsonResponse({
                'success': True, 
                'ticket_id': ticket.id,
                'ticket_number': ticket.ticket_number,
                'message': 'Ticket criado com sucesso!'
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    form = QuickTicketForm()
    
    context = {
        'form': form,
        'is_mobile': True
    }
    
    return render(request, 'mobile/create_ticket.html', context)

@login_required
@csrf_exempt
def mobile_quick_actions(request):
    """Ações rápidas via AJAX para mobile"""
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Método não permitido'})
    
    try:
        data = json.loads(request.body)
        action = data.get('action')
        ticket_id = data.get('ticket_id')
        
        ticket = get_object_or_404(Ticket, id=ticket_id)
        
        # Verificar permissões
        user_agent = None
        try:
            user_agent = Agent.objects.get(user=request.user)
            has_access = (ticket.assigned_to == user_agent) or user_agent.is_supervisor
        except Agent.DoesNotExist:
            has_access = False
        
        if not has_access:
            return JsonResponse({'success': False, 'error': 'Sem permissão'})
        
        if action == 'take_ticket':
            if not ticket.assigned_to:
                ticket.assigned_to = user_agent
                ticket.status = 'ABERTO'
                ticket.save()
                
                return JsonResponse({
                    'success': True, 
                    'message': 'Ticket assumido com sucesso'
                })
        
        elif action == 'escalate':
            ticket.escalated = True
            ticket.escalation_level = 'supervisor'
            ticket.escalated_at = timezone.now()
            ticket.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Ticket escalado para supervisor'
            })
        
        elif action == 'close':
            ticket.status = 'FECHADO'
            ticket.resolved_at = timezone.now()
            ticket.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Ticket fechado com sucesso'
            })
        
        return JsonResponse({'success': False, 'error': 'Ação não reconhecida'})
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'JSON inválido'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def mobile_search(request):
    """Busca otimizada para mobile"""
    
    query = request.GET.get('q', '').strip()
    
    if not query or len(query) < 2:
        return JsonResponse({'results': []})
    
    user_agent = None
    try:
        user_agent = Agent.objects.get(user=request.user)
    except Agent.DoesNotExist:
        pass
    
    if user_agent:
        # Buscar tickets do agente
        tickets = Ticket.objects.filter(
            Q(assigned_to=user_agent) |
            (Q(assigned_to__isnull=True) if user_agent.is_supervisor else Q())
        ).filter(
            Q(title__icontains=query) |
            Q(ticket_number__icontains=query) |
            Q(customer__name__icontains=query)
        )[:10]
    else:
        # Buscar tickets do cliente
        try:
            customer = Customer.objects.get(email=request.user.email)
            tickets = Ticket.objects.filter(
                customer=customer
            ).filter(
                Q(title__icontains=query) |
                Q(ticket_number__icontains=query)
            )[:10]
        except Customer.DoesNotExist:
            tickets = []
    
    results = []
    for ticket in tickets:
        results.append({
            'id': ticket.id,
            'ticket_number': ticket.ticket_number,
            'title': ticket.title,
            'status': ticket.status,
            'priority': ticket.priority,
            'created_at': ticket.created_at.strftime('%d/%m/%Y'),
            'customer_name': ticket.customer.name if ticket.customer else 'N/A'
        })
    
    return JsonResponse({'results': results})

@login_required
def mobile_notifications(request):
    """Notificações mobile"""
    
    # Buscar notificações não lidas (implementar quando modelo estiver disponível)
    notifications = []
    
    context = {
        'notifications': notifications,
        'is_mobile': True
    }
    
    return render(request, 'mobile/notifications.html', context)

def mobile_offline(request):
    """Página offline para PWA"""
    return render(request, 'mobile/offline.html', {'is_mobile': True})
