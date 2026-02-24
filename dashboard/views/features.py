"""
Views de funcionalidades diversas: relatórios, busca, PWA, chatbot, comunicação e exportação.
"""
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model
from django.db.models import Q, Avg, F
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import timedelta
import json
import logging

from ..models import Ticket, Cliente, StatusTicket, PrioridadeTicket
from ..chatbot_service import ChatbotService

logger = logging.getLogger('dashboard')


# ========== CHATBOT ==========

@login_required
def chatbot_interface(request):
    """Interface do Chatbot AI"""
    return render(request, 'dashboard/chatbot/interface.html', {
        'title': 'Chatbot AI - iConnect',
        'current_page': 'chatbot'
    })


@login_required
def chatbot_api(request):
    """API do Chatbot"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            message = data.get('message', '')

            chatbot = ChatbotService()
            response = chatbot.process_message(request.user.id, message)

            return JsonResponse({
                'response': response.message,
                'suggestions': response.suggestions,
                'type': response.response_type
            })
        except Exception as e:
            logger.error(f'Erro no chatbot_api: {e}', exc_info=True)
            return JsonResponse({'error': 'Erro interno.'}, status=500)

    return JsonResponse({'error': 'Método não permitido'}, status=405)


@login_required
def chat_interface(request):
    """Interface de Chat em Tempo Real"""
    return render(request, 'dashboard/chat/interface.html', {
        'title': 'Chat - iConnect',
        'current_page': 'chat'
    })


# ========== RELATÓRIOS ==========

@login_required
def reports_dashboard(request):
    """Dashboard de Relatórios Avançados"""
    from ..models import RelatorioFinanceiro

    total_reports = RelatorioFinanceiro.objects.count()
    relatorios_recentes = RelatorioFinanceiro.objects.order_by('-gerado_em')[:10]

    return render(request, 'dashboard/reports/advanced.html', {
        'title': 'Relatórios Avançados',
        'current_page': 'reports',
        'total_reports': total_reports,
        'scheduled_reports': 0,
        'avg_generation_time': 0,
        'data_sources': 0,
        'relatorios_recentes': relatorios_recentes,
    })


@login_required
def generate_report(request):
    """Gerar Relatório Customizado"""
    if request.method == 'POST':
        return JsonResponse({'status': 'success', 'report_id': 'temp_123'})

    return render(request, 'dashboard/reports/generate.html', {
        'title': 'Gerar Relatório',
        'current_page': 'reports'
    })


@login_required
def download_report(request, report_id):
    """Download de Relatório"""
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="relatorio_{report_id}.pdf"'
    response.write(b'%PDF-1.4 placeholder')
    return response


@login_required
def custom_reports(request):
    """Relatórios Customizados"""
    return render(request, 'dashboard/reports/custom.html', {
        'title': 'Relatórios Customizados',
        'current_page': 'reports'
    })


# ========== BUSCA AVANÇADA ==========

@login_required
def advanced_search(request):
    """Busca Avançada com filtros"""
    query = request.GET.get('q', '')
    filter_type = request.GET.get('type', 'all')  # all, tickets, clientes
    filter_status = request.GET.get('status', '')
    filter_priority = request.GET.get('priority', '')
    tickets = []
    clientes = []

    if query:
        # Buscar tickets
        if filter_type in ('all', 'tickets'):
            qs = Ticket.objects.select_related(
                'cliente', 'agente', 'categoria'
            ).filter(
                Q(titulo__icontains=query) |
                Q(descricao__icontains=query) |
                Q(numero__icontains=query) |
                Q(tags__icontains=query)
            )
            if filter_status:
                qs = qs.filter(status=filter_status)
            if filter_priority:
                qs = qs.filter(prioridade=filter_priority)
            tickets = qs.order_by('-criado_em')[:30]

        # Buscar clientes
        if filter_type in ('all', 'clientes'):
            clientes = Cliente.objects.filter(
                Q(nome__icontains=query) |
                Q(email__icontains=query) |
                Q(empresa__icontains=query)
            ).order_by('nome')[:20]

    total = len(tickets) + len(clientes)

    return render(request, 'dashboard/search/advanced.html', {
        'title': 'Busca Avançada',
        'query': query,
        'tickets': tickets,
        'clientes': clientes,
        'total': total,
        'filter_type': filter_type,
        'filter_status': filter_status,
        'filter_priority': filter_priority,
        'status_choices': StatusTicket.choices,
        'priority_choices': PrioridadeTicket.choices,
        'current_page': 'search'
    })


def search_suggestions(request):
    """Sugestões de Busca — retorna tickets + clientes para live search (sem @login_required para evitar 302 no fetch)"""
    query = request.GET.get('q', '').strip()
    results = []

    # Checar auth manualmente (retorna JSON vazio em vez de redirect)
    if not request.user.is_authenticated:
        return JsonResponse({'results': [], 'query': query})

    if len(query) >= 2:
        # Buscar tickets por numero, titulo
        tickets = Ticket.objects.filter(
            Q(titulo__icontains=query) | Q(numero__icontains=query)
        ).select_related('cliente').order_by('-criado_em')[:5]

        status_colors = {
            'aberto': '#06b6d4', 'em_andamento': '#f59e0b',
            'aguardando_cliente': '#8b5cf6', 'resolvido': '#22c55e', 'fechado': '#94a3b8'
        }
        for t in tickets:
            results.append({
                'type': 'ticket',
                'icon': 'confirmation_number',
                'title': f'#{t.numero} — {t.titulo[:60]}',
                'subtitle': f'{t.get_status_display()} · {t.cliente.nome}',
                'url': f'/dashboard/tickets/{t.id}/',
                'color': status_colors.get(t.status, '#64748b'),
            })

        # Buscar clientes por nome ou empresa
        clientes = Cliente.objects.filter(
            Q(nome__icontains=query) | Q(empresa__icontains=query)
        ).order_by('nome')[:3]

        for c in clientes:
            results.append({
                'type': 'cliente',
                'icon': 'person',
                'title': c.nome,
                'subtitle': c.empresa or c.email,
                'url': f'/dashboard/clientes/{c.id}/',
                'color': '#22c55e',
            })

    return JsonResponse({'results': results, 'query': query})


# ========== PWA ==========

@login_required
def pwa_info(request):
    """Informações sobre PWA"""
    return render(request, 'dashboard/pwa/info.html', {
        'title': 'App Progressivo - PWA',
        'current_page': 'pwa'
    })


@login_required
def pwa_install_guide(request):
    """Guia de Instalação PWA"""
    return render(request, 'dashboard/pwa/install.html', {
        'title': 'Como Instalar o App',
        'current_page': 'pwa'
    })


def manifest(request):
    """Manifest do PWA"""
    manifest_data = {
        "name": "iConnect - Sistema de Atendimento",
        "short_name": "iConnect",
        "description": "Sistema completo de atendimento ao cliente",
        "start_url": "/dashboard/",
        "display": "standalone",
        "theme_color": "#334155",
        "background_color": "#f8fafc",
        "icons": [
            {
                "src": "/static/img/icon-192x192.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/img/icon-512x512.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return JsonResponse(manifest_data)


def service_worker(request):
    """Service Worker do PWA"""
    sw_content = """
const CACHE_NAME = 'iconnect-v1.0.0';
const OFFLINE_URL = '/mobile/offline/';

const urlsToCache = [
    '/dashboard/',
    '/static/css/material-dashboard.min.css',
    '/static/js/material-dashboard.min.js',
    OFFLINE_URL
];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(urlsToCache))
    );
});

self.addEventListener('fetch', event => {
    if (event.request.mode === 'navigate') {
        event.respondWith(
            fetch(event.request)
                .catch(() => caches.match(OFFLINE_URL))
        );
    }
});
"""
    return HttpResponse(sw_content, content_type='application/javascript')


# ========== EXPORTAÇÃO ==========

@login_required
def export_tickets(request):
    """View para exportar dados dos tickets (somente staff)."""
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Sem permissão para exportar dados.')
    import csv
    from django.utils import timezone as tz

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="tickets_{tz.now().strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Número', 'Cliente', 'Status', 'Data Criação', 'Categoria'])

    tickets = Ticket.objects.select_related('cliente', 'categoria').only(
        'id', 'numero', 'cliente__nome', 'status', 'criado_em', 'categoria__nome'
    )[:1000]

    for ticket in tickets:
        writer.writerow([
            ticket.id,
            ticket.numero,
            ticket.cliente.nome if ticket.cliente else 'N/A',
            ticket.get_status_display() if hasattr(ticket, 'get_status_display') else ticket.status,
            ticket.criado_em.strftime('%d/%m/%Y %H:%M'),
            ticket.categoria.nome if ticket.categoria else 'N/A',
        ])

    return response


# ========== CENTRAL DE COMUNICAÇÃO ==========

@login_required
def communication_center(request):
    """Central de Comunicação Unificada"""
    from django.db import models

    try:
        from ..models_chat import ChatRoom, ChatMessage, ChatBot
    except ImportError:
        ChatRoom = ChatMessage = ChatBot = None

    try:
        from ..models_chatbot_ai import ChatbotConversation, ChatbotKnowledge
    except ImportError:
        ChatbotConversation = None
        ChatbotKnowledge = None

    recent_conversations = []
    total_conversations = 0
    active_conversations = 0

    if ChatRoom:
        try:
            recent_conversations = ChatRoom.objects.filter(
                participants__user=request.user
            ).annotate(
                last_message_time=models.Max('messages__created_at')
            ).order_by('-last_message_time')[:5]

            total_conversations = ChatRoom.objects.filter(
                participants__user=request.user,
                created_at__date=timezone.now().date()
            ).count()

            active_conversations = ChatRoom.objects.filter(
                participants__user=request.user,
                status='active'
            ).count()
        except Exception as e:
            logger.error("Erro ao carregar dados do chat: %s", e, exc_info=True)

    chatbot = None
    if ChatBot:
        try:
            chatbot = ChatBot.objects.first()
        except Exception:
            pass

    recent_knowledge = []
    if ChatbotKnowledge:
        try:
            recent_knowledge = ChatbotKnowledge.objects.order_by('-created_at')[:3]
        except Exception:
            pass

    total_messages_today = 0
    if ChatMessage:
        try:
            total_messages_today = ChatMessage.objects.filter(
                created_at__date=timezone.now().date()
            ).count()
        except Exception:
            pass

    avg_response_time_val = 0
    if ChatMessage:
        try:
            avg_rt = ChatMessage.objects.filter(
                created_at__date=timezone.now().date(),
                reply_to__isnull=False,
            ).annotate(
                response_delta=F('created_at') - F('reply_to__created_at')
            ).aggregate(avg=Avg('response_delta'))['avg']
            if avg_rt:
                avg_response_time_val = round(avg_rt.total_seconds() / 60, 1)
        except Exception:
            pass

    satisfaction_rate_val = 0
    try:
        from ..models_satisfacao import AvaliacaoSatisfacao
        avaliacoes = AvaliacaoSatisfacao.objects.filter(
            criado_em__date=timezone.now().date()
        )
        total_aval = avaliacoes.count()
        if total_aval > 0:
            from django.db.models import Avg as AvgAval
            media = avaliacoes.aggregate(m=AvgAval('nota'))['m'] or 0
            satisfaction_rate_val = round(media / 5 * 100)
    except Exception:
        pass

    analytics_data = {
        'total_messages': total_messages_today,
        'active_conversations': active_conversations,
        'avg_response_time': avg_response_time_val,
        'satisfaction_rate': satisfaction_rate_val,
    }

    team_users = []
    try:
        team_users = get_user_model().objects.filter(
            is_active=True,
            groups__name__in=['Agentes', 'Supervisores', 'Gerentes']
        ).distinct()
    except Exception:
        team_users = get_user_model().objects.filter(is_active=True)[:10]

    context = {
        'title': 'Central de Comunicação',
        'recent_conversations': recent_conversations,
        'total_conversations': total_conversations,
        'active_conversations': active_conversations,
        'avg_response_time': f"{avg_response_time_val}m" if avg_response_time_val else "0m",
        'chatbot': chatbot,
        'recent_knowledge': recent_knowledge,
        'analytics': analytics_data,
        'team_users': team_users,
    }

    return render(request, 'dashboard/communication_center.html', context)
