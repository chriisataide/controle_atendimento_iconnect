"""
Views de Banking Features — Knowledge Base, Macros, Time Tracking, Ticket Merge.
"""
import json
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from ..utils.rbac import role_required
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

    # Parse tags string into list
    tags_list = [t.strip() for t in artigo.tags.split(',') if t.strip()] if artigo.tags else []

    return render(request, 'dashboard/knowledge/article_detail.html', {
        'artigo': artigo,
        'relacionados': relacionados,
        'tags_list': tags_list,
    })


@login_required
def knowledge_vote(request, pk):
    """Vota se artigo foi útil ou não."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    # Support both form POST and JSON body
    vote = request.POST.get('vote')
    if not vote and request.content_type and 'json' in request.content_type:
        try:
            body = json.loads(request.body)
            vote = body.get('vote')
        except (json.JSONDecodeError, ValueError):
            pass

    artigo = get_object_or_404(ArtigoConhecimento, pk=pk)

    if vote == 'yes':
        ArtigoConhecimento.objects.filter(pk=pk).update(util_sim=F('util_sim') + 1)
    elif vote == 'no':
        ArtigoConhecimento.objects.filter(pk=pk).update(util_nao=F('util_nao') + 1)

    artigo.refresh_from_db()
    return JsonResponse({
        'success': True,
        'util_sim': artigo.util_sim,
        'util_nao': artigo.util_nao,
        'taxa': round(artigo.taxa_utilidade(), 1),
    })


# ========== CRUD — ARTIGOS ==========

@login_required
@role_required('admin', 'gerente', 'supervisor')
def knowledge_create(request):
    """Criar novo artigo na base de conhecimento."""
    categorias = CategoriaConhecimento.objects.filter(ativo=True).order_by('ordem', 'nome')

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        resumo = request.POST.get('resumo', '').strip()
        categoria_id = request.POST.get('categoria')
        tags = request.POST.get('tags', '').strip()
        publico = request.POST.get('publico') == 'on'
        destaque = request.POST.get('destaque') == 'on'

        errors = []
        if not titulo:
            errors.append('O título é obrigatório.')
        if not conteudo:
            errors.append('O conteúdo é obrigatório.')
        if not categoria_id:
            errors.append('Selecione uma categoria.')

        if errors:
            return render(request, 'dashboard/knowledge/article_form.html', {
                'categorias': categorias,
                'errors': errors,
                'form_data': request.POST,
                'editing': False,
            })

        categoria = get_object_or_404(CategoriaConhecimento, pk=categoria_id)
        artigo = ArtigoConhecimento.objects.create(
            titulo=titulo,
            conteudo=conteudo,
            resumo=resumo,
            categoria=categoria,
            autor=request.user,
            tags=tags,
            publico=publico,
            destaque=destaque,
            slug=slugify(titulo)[:220],
        )
        messages.success(request, f'Artigo "{titulo}" criado com sucesso.')
        return redirect('dashboard:knowledge_article', pk=artigo.pk)

    return render(request, 'dashboard/knowledge/article_form.html', {
        'categorias': categorias,
        'editing': False,
    })


@login_required
@role_required('admin', 'gerente', 'supervisor')
def knowledge_edit(request, pk):
    """Editar artigo existente."""
    artigo = get_object_or_404(ArtigoConhecimento, pk=pk)
    categorias = CategoriaConhecimento.objects.filter(ativo=True).order_by('ordem', 'nome')

    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        conteudo = request.POST.get('conteudo', '').strip()
        resumo = request.POST.get('resumo', '').strip()
        categoria_id = request.POST.get('categoria')
        tags = request.POST.get('tags', '').strip()
        publico = request.POST.get('publico') == 'on'
        destaque = request.POST.get('destaque') == 'on'

        errors = []
        if not titulo:
            errors.append('O título é obrigatório.')
        if not conteudo:
            errors.append('O conteúdo é obrigatório.')
        if not categoria_id:
            errors.append('Selecione uma categoria.')

        if errors:
            return render(request, 'dashboard/knowledge/article_form.html', {
                'categorias': categorias,
                'artigo': artigo,
                'errors': errors,
                'form_data': request.POST,
                'editing': True,
            })

        categoria = get_object_or_404(CategoriaConhecimento, pk=categoria_id)
        artigo.titulo = titulo
        artigo.conteudo = conteudo
        artigo.resumo = resumo
        artigo.categoria = categoria
        artigo.tags = tags
        artigo.publico = publico
        artigo.destaque = destaque
        artigo.slug = slugify(titulo)[:220]
        artigo.save()

        messages.success(request, f'Artigo "{titulo}" atualizado com sucesso.')
        return redirect('dashboard:knowledge_article', pk=artigo.pk)

    return render(request, 'dashboard/knowledge/article_form.html', {
        'categorias': categorias,
        'artigo': artigo,
        'editing': True,
    })


@login_required
@role_required('admin', 'gerente', 'supervisor')
def knowledge_delete(request, pk):
    """Excluir artigo da base de conhecimento."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    artigo = get_object_or_404(ArtigoConhecimento, pk=pk)
    titulo = artigo.titulo
    artigo.delete()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': True, 'message': f'Artigo "{titulo}" excluído.'})

    messages.success(request, f'Artigo "{titulo}" excluído com sucesso.')
    return redirect('dashboard:knowledge_base')


# ========== CRUD — CATEGORIAS ==========

@login_required
@role_required('admin', 'gerente', 'supervisor')
def knowledge_category_create(request):
    """Criar nova categoria de conhecimento via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    nome = request.POST.get('nome', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    icone = request.POST.get('icone', 'help').strip()
    cor = request.POST.get('cor', '#e91e63').strip()

    if not nome:
        return JsonResponse({'error': 'O nome é obrigatório.'}, status=400)

    if CategoriaConhecimento.objects.filter(nome__iexact=nome).exists():
        return JsonResponse({'error': 'Já existe uma categoria com esse nome.'}, status=400)

    cat = CategoriaConhecimento.objects.create(
        nome=nome,
        descricao=descricao,
        icone=icone,
        cor=cor,
    )
    return JsonResponse({
        'success': True,
        'id': cat.pk,
        'nome': cat.nome,
        'icone': cat.icone,
        'cor': cat.cor,
        'message': f'Categoria "{nome}" criada.',
    })


@login_required
def knowledge_category_list(request):
    """Lista categorias via AJAX."""
    categorias = CategoriaConhecimento.objects.filter(ativo=True).annotate(
        total_artigos=Count('artigos', filter=Q(artigos__publico=True))
    ).order_by('ordem', 'nome')
    data = [{
        'id': c.pk,
        'nome': c.nome,
        'descricao': c.descricao,
        'icone': c.icone,
        'cor': c.cor,
        'total_artigos': c.total_artigos,
    } for c in categorias]
    return JsonResponse({'categorias': data})


@login_required
@role_required('admin', 'gerente', 'supervisor')
def knowledge_category_delete(request, pk):
    """Excluir categoria via AJAX (só se sem artigos)."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    cat = get_object_or_404(CategoriaConhecimento, pk=pk)
    if cat.artigos.filter(publico=True).exists():
        return JsonResponse(
            {'error': 'Não é possível excluir: existem artigos vinculados a esta categoria.'},
            status=400,
        )
    nome = cat.nome
    cat.delete()
    return JsonResponse({'success': True, 'message': f'Categoria "{nome}" excluída.'})


# ========== MACROS / RESPOSTAS RÁPIDAS ==========

@login_required
@role_required('admin', 'gerente', 'supervisor', 'agente')
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
@role_required('admin', 'gerente', 'supervisor', 'agente')
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
@role_required('admin', 'gerente', 'supervisor', 'agente')
def macro_delete(request, pk):
    """Exclui macro via AJAX."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    macro = get_object_or_404(CannedResponse, pk=pk)
    macro.delete()
    return JsonResponse({'status': 'deleted', 'message': 'Macro excluída.'})


# ========== TIME TRACKING ==========

@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
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
