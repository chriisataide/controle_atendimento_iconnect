"""
Views de Banking Features — Knowledge Base, Macros, Time Tracking, Ticket Merge.
"""
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.db.models import Q, Sum, Count, F

from dashboard.models.knowledge import ArtigoConhecimento, CategoriaConhecimento
from dashboard.models.base import Ticket, CannedResponse


# ========== BASE DE CONHECIMENTO ==========

@method_decorator(login_required, name='dispatch')
class KnowledgeBaseView(ListView):
    """Base de conhecimento com busca e categorias."""
    model = ArtigoConhecimento
    template_name = 'dashboard/knowledge/knowledge_base.html'
    context_object_name = 'artigos'
    paginate_by = 12

    def get_queryset(self):
        qs = ArtigoConhecimento.objects.filter(publico=True).select_related('categoria', 'autor')

        search = self.request.GET.get('q')
        cat = self.request.GET.get('cat')

        if search:
            qs = qs.filter(
                Q(titulo__icontains=search) |
                Q(conteudo__icontains=search) |
                Q(tags__icontains=search) |
                Q(resumo__icontains=search)
            )
        if cat:
            qs = qs.filter(categoria_id=cat)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categorias'] = CategoriaConhecimento.objects.filter(ativo=True).annotate(
            total_artigos=Count('artigos', filter=Q(artigos__publico=True))
        )
        ctx['destaques'] = ArtigoConhecimento.objects.filter(publico=True, destaque=True)[:4]
        ctx['mais_vistos'] = ArtigoConhecimento.objects.filter(publico=True).order_by('-visualizacoes')[:5]
        return ctx


@login_required
def knowledge_article_detail(request, pk):
    """Detalhe de artigo com incremento de visualizações."""
    artigo = get_object_or_404(ArtigoConhecimento, pk=pk, publico=True)
    # Incrementa views
    ArtigoConhecimento.objects.filter(pk=pk).update(visualizacoes=F('visualizacoes') + 1)
    artigo.refresh_from_db()

    # Artigos relacionados (mesma categoria)
    relacionados = ArtigoConhecimento.objects.filter(
        categoria=artigo.categoria, publico=True
    ).exclude(pk=pk).order_by('-visualizacoes')[:4]

    return render(request, 'dashboard/knowledge/article_detail.html', {
        'artigo': artigo,
        'relacionados': relacionados,
    })


@login_required
def knowledge_vote(request, pk):
    """Vota se artigo foi útil ou não."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    vote = request.POST.get('vote')  # 'yes' or 'no'
    artigo = get_object_or_404(ArtigoConhecimento, pk=pk)

    if vote == 'yes':
        ArtigoConhecimento.objects.filter(pk=pk).update(util_sim=F('util_sim') + 1)
    elif vote == 'no':
        ArtigoConhecimento.objects.filter(pk=pk).update(util_nao=F('util_nao') + 1)

    artigo.refresh_from_db()
    return JsonResponse({
        'util_sim': artigo.util_sim,
        'util_nao': artigo.util_nao,
        'taxa': round(artigo.taxa_utilidade(), 1),
    })


# ========== MACROS / RESPOSTAS RÁPIDAS ==========

@login_required
def macros_list(request):
    """Lista de macros/respostas rápidas."""
    macros = CannedResponse.objects.all()

    search = request.GET.get('q')
    if search:
        macros = macros.filter(
            Q(titulo__icontains=search) |
            Q(corpo__icontains=search) |
            Q(atalho__icontains=search)
        )

    categoria = request.GET.get('category')
    if categoria:
        macros = macros.filter(categoria=categoria)

    # Pegar categorias únicas
    categories = CannedResponse.objects.values_list('categoria', flat=True).distinct().order_by('categoria')

    return render(request, 'dashboard/macros/macros_list.html', {
        'macros': macros,
        'categories': [c for c in categories if c],
    })


@login_required
def macro_create(request):
    """Cria nova macro via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    titulo = request.POST.get('titulo', '').strip()
    corpo = request.POST.get('corpo', '').strip()
    atalho = request.POST.get('atalho', '').strip()
    categoria = request.POST.get('categoria', '').strip()

    if not titulo or not corpo:
        return JsonResponse({'error': 'Título e conteúdo são obrigatórios.'}, status=400)

    macro = CannedResponse.objects.create(
        titulo=titulo,
        corpo=corpo,
        atalho=atalho or '',
        categoria=categoria or 'geral',
        criado_por=request.user,
    )
    return JsonResponse({
        'status': 'created',
        'id': macro.pk,
        'message': f'Macro "{titulo}" criada com sucesso.',
    })


@login_required
def macro_delete(request, pk):
    """Exclui macro via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    macro = get_object_or_404(CannedResponse, pk=pk)
    macro.delete()
    return JsonResponse({'status': 'deleted', 'message': 'Macro excluída.'})


# ========== TIME TRACKING ==========

@login_required
def ticket_timetrack(request, pk):
    """Registra tempo de trabalho em ticket via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    ticket = get_object_or_404(Ticket, pk=pk)

    try:
        minutes = int(request.POST.get('minutes', 0))
    except (ValueError, TypeError):
        return JsonResponse({'error': 'Valor inválido de minutos.'}, status=400)

    if minutes <= 0:
        return JsonResponse({'error': 'Informe um valor positivo.'}, status=400)

    descricao = request.POST.get('descricao', '').strip()

    # Registra como interação com tipo 'timetrack'
    from dashboard.models.base import InteracaoTicket
    InteracaoTicket.objects.create(
        ticket=ticket,
        usuario=request.user,
        tipo='nota_interna',
        mensagem=f'⏱ Tempo registrado: {minutes} min — {descricao}' if descricao else f'⏱ Tempo registrado: {minutes} min',
    )

    return JsonResponse({
        'status': 'ok',
        'minutes': minutes,
        'message': f'{minutes} minutos registrados com sucesso.',
    })
