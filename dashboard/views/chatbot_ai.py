import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from ..models import Ticket
from ..models.chatbot_ai import ChatbotConfiguration, ChatbotConversation, ChatbotKnowledgeBase, ChatbotMessage
from ..services.chatbot_ai_engine import chatbot_engine
from ..utils.rbac import role_required

logger = logging.getLogger(__name__)


def chatbot_interface(request):
    """Interface do chatbot para usuários"""
    return render(request, "dashboard/chatbot_interface.html")


@require_http_methods(["POST"])
@login_required
def chatbot_api(request):
    """API principal do chatbot"""
    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()
        session_id = data.get("session_id", "")

        if not message:
            return JsonResponse({"success": False, "error": "Mensagem não pode estar vazia"})

        if not session_id:
            return JsonResponse({"success": False, "error": "Session ID é obrigatório"})

        # Processar mensagem
        user = request.user if request.user.is_authenticated else None
        response = chatbot_engine.process_message(message, session_id, user)

        return JsonResponse(response)

    except json.JSONDecodeError:
        return JsonResponse({"success": False, "error": "JSON inválido"})
    except Exception as e:
        logger.error(f"Erro na API do chatbot: {e}")
        return JsonResponse({"success": False, "error": "Erro interno do servidor"})


@require_http_methods(["POST"])
@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def chatbot_feedback(request):
    """API para feedback do chatbot"""
    try:
        data = json.loads(request.body)
        conversation_id = data.get("conversation_id")
        data.get("message_id")
        positive = data.get("positive", True)
        comment = data.get("comment", "")

        if conversation_id:
            conversation = get_object_or_404(ChatbotConversation, uuid=conversation_id)

            # Buscar última interação para treinar
            last_user_msg = conversation.mensagens.filter(tipo="user").last()
            last_bot_msg = conversation.mensagens.filter(tipo="bot").last()

            if last_user_msg and last_bot_msg:
                chatbot_engine.add_training_data(
                    question=last_user_msg.conteudo,
                    bot_response=last_bot_msg.conteudo,
                    expected_response=comment if comment and not positive else None,
                    positive_feedback=positive,
                    user=request.user if request.user.is_authenticated else None,
                )

        return JsonResponse({"success": True})

    except Exception as e:
        logger.error(f"Erro no feedback do chatbot: {e}")
        return JsonResponse({"success": False, "error": "Erro ao processar feedback"})


@login_required
@role_required('admin', 'gerente', 'supervisor')
def chatbot_dashboard(request):
    """Dashboard administrativo do chatbot"""
    if not request.user.is_staff:
        return render(request, "403.html")

    # Analytics gerais
    analytics = chatbot_engine.get_analytics(30)

    # Conversas recentes
    recent_conversations = ChatbotConversation.objects.select_related("usuario").order_by("-iniciada_em")[:10]

    # Perguntas não respondidas (baixa confiança)
    low_confidence_messages = (
        ChatbotMessage.objects.filter(tipo="bot", confianca__lt=0.7)
        .select_related("conversa")
        .order_by("-timestamp")[:10]
    )

    # Base de conhecimento
    kb_count = ChatbotKnowledgeBase.objects.filter(ativo=True).count()

    context = {
        "analytics": analytics,
        "recent_conversations": recent_conversations,
        "low_confidence_messages": low_confidence_messages,
        "kb_count": kb_count,
    }

    return render(request, "dashboard/chatbot_dashboard.html", context)


@login_required
@role_required('admin', 'gerente', 'supervisor')
def chatbot_knowledge_base(request):
    """Gerenciamento da base de conhecimento"""
    if not request.user.is_staff:
        return render(request, "403.html")

    knowledge_items = ChatbotKnowledgeBase.objects.all().order_by("-criado_em")

    # Paginação
    paginator = Paginator(knowledge_items, 20)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "total_items": knowledge_items.count(),
    }

    return render(request, "dashboard/chatbot_knowledge_base.html", context)


@require_http_methods(["POST"])
@login_required
@role_required('admin', 'gerente', 'supervisor')
def chatbot_add_knowledge(request):
    """Adicionar item à base de conhecimento"""
    if not request.user.is_staff:
        return JsonResponse({"success": False, "error": "Permissão negada"})

    try:
        data = json.loads(request.body)

        item = ChatbotKnowledgeBase.objects.create(
            categoria=data["categoria"],
            pergunta=data["pergunta"],
            resposta=data["resposta"],
            tags=data.get("tags", ""),
            confianca=data.get("confianca", 1.0),
        )

        return JsonResponse(
            {
                "success": True,
                "item": {
                    "id": item.id,
                    "categoria": item.categoria,
                    "pergunta": item.pergunta,
                    "resposta": item.resposta,
                    "tags": item.tags,
                    "confianca": item.confianca,
                },
            }
        )

    except Exception as e:
        logger.error(f"Erro ao adicionar conhecimento: {e}")
        return JsonResponse({"success": False, "error": "Erro ao adicionar item"})


@login_required
@role_required('admin', 'gerente', 'supervisor')
def chatbot_conversations(request):
    """Lista de conversas do chatbot"""
    if not request.user.is_staff:
        return render(request, "403.html")

    conversations = ChatbotConversation.objects.select_related("usuario").order_by("-iniciada_em")

    # Filtros
    search = request.GET.get("search")
    if search:
        conversations = conversations.filter(
            Q(session_id__icontains=search)
            | Q(usuario__username__icontains=search)
            | Q(usuario__email__icontains=search)
        )

    # Paginação
    paginator = Paginator(conversations, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "search": search,
    }

    return render(request, "dashboard/chatbot_conversations.html", context)


@login_required
@role_required('admin', 'gerente', 'supervisor')
def chatbot_conversation_detail(request, conversation_id):
    """Detalhes de uma conversa específica"""
    if not request.user.is_staff:
        return render(request, "403.html")

    conversation = get_object_or_404(ChatbotConversation, uuid=conversation_id)
    messages = conversation.mensagens.all().order_by("timestamp")

    context = {
        "conversation": conversation,
        "messages": messages,
    }

    return render(request, "dashboard/chatbot_conversation_detail.html", context)


@require_http_methods(["POST"])
@login_required
@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')
def chatbot_create_ticket_from_conversation(request):
    """Criar ticket a partir de uma conversa do chatbot"""
    try:
        data = json.loads(request.body)
        conversation_id = data.get("conversation_id")

        conversation = get_object_or_404(ChatbotConversation, uuid=conversation_id)

        if not conversation.usuario:
            return JsonResponse({"success": False, "error": "Usuário não identificado na conversa"})

        # Buscar mensagens do usuário para criar descrição
        user_messages = conversation.mensagens.filter(tipo="user").order_by("timestamp")
        description = "\n".join([msg.conteudo for msg in user_messages])

        # Criar ticket
        ticket = Ticket.objects.create(
            titulo=f"Suporte via Chatbot - {conversation.session_id[:8]}",
            descricao=description,
            cliente=conversation.usuario.cliente if hasattr(conversation.usuario, "cliente") else None,
            prioridade="media",
            status="aberto",
            categoria="suporte",
        )

        # Atualizar contexto da conversa
        conversation.contexto["ticket_created"] = ticket.id
        conversation.save()

        return JsonResponse({"success": True, "ticket_id": ticket.id, "ticket_url": f"/dashboard/tickets/{ticket.id}/"})

    except Exception as e:
        logger.error(f"Erro ao criar ticket da conversa: {e}")
        return JsonResponse({"success": False, "error": "Erro ao criar ticket"})


@login_required
@role_required('admin', 'gerente', 'supervisor')
def chatbot_analytics_api(request):
    """API para analytics do chatbot"""
    if not request.user.is_staff:
        return JsonResponse({"error": "Permissão negada"}, status=403)

    try:
        days = int(request.GET.get("days", 30))
        analytics = chatbot_engine.get_analytics(days)

        # Adicionar dados específicos para gráficos
        from datetime import timedelta

        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)

        # Conversas por dia
        daily_conversations = []
        for i in range(days):
            date = start_date + timedelta(days=i)
            count = ChatbotConversation.objects.filter(iniciada_em__date=date).count()
            daily_conversations.append({"date": date.strftime("%Y-%m-%d"), "count": count})

        analytics["daily_conversations"] = daily_conversations

        return JsonResponse(analytics)

    except Exception as e:
        logger.error(f"Erro na API de analytics: {e}")
        return JsonResponse({"error": "Erro interno"}, status=500)


@login_required
@role_required('admin', 'gerente', 'supervisor')
def chatbot_settings(request):
    """Configurações do chatbot"""
    if not request.user.is_staff:
        return render(request, "403.html")

    if request.method == "POST":
        try:
            # Atualizar configurações
            configs = [
                ("confidence_threshold", request.POST.get("confidence_threshold", "0.7"), "float"),
                ("max_suggestions", request.POST.get("max_suggestions", "3"), "integer"),
                ("enable_training", request.POST.get("enable_training", "false"), "boolean"),
                ("welcome_message", request.POST.get("welcome_message", ""), "string"),
            ]

            for name, value, tipo in configs:
                config, created = ChatbotConfiguration.objects.get_or_create(
                    nome=name, defaults={"valor": value, "tipo": tipo}
                )
                if not created:
                    config.valor = value
                    config.save()

            # Recarregar configurações no engine
            chatbot_engine.load_configurations()

            return JsonResponse({"success": True})

        except Exception as e:
            logger.error(f"Erro ao salvar configurações: {e}")
            return JsonResponse({"success": False, "error": "Erro ao salvar"})

    # Carregar configurações atuais
    configs = {}
    for config in ChatbotConfiguration.objects.filter(ativo=True):
        configs[config.nome] = config.get_value()

    context = {
        "configs": configs,
    }

    return render(request, "dashboard/chatbot_settings.html", context)
