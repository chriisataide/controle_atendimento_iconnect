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
        else:
            my_tickets = []
        
        context = {
            'my_tickets': my_tickets,
            'customer': customer,
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
                return redirect('mobile:dashboard')
        except Cliente.DoesNotExist:
            messages.error(request, 'Você não tem permissão para ver este ticket.')
            return redirect('mobile:dashboard')
    
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
            
            messages.success(request, f'Ticket #{ticket.numero} criado com sucesso!')
            return redirect('mobile:ticket_detail', ticket_id=ticket.id)
        else:
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
def mobile_chat_ticket(request, ticket_id):
    """Chat específico do ticket (placeholder)"""
    ticket = get_object_or_404(Ticket, id=ticket_id)
    return render(request, 'mobile/chat_ticket.html', {
        'ticket': ticket,
        'is_mobile': True
    })
