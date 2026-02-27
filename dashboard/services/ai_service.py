"""
AI Service — Integracao com LLMs (OpenAI, Anthropic, Google)
Funcionalidades: auto-categorizacao, sugestao de resposta, resumo, sentimento,
deteccao de duplicatas, auto-triagem, chatbot RAG
"""
import hashlib
import json
import logging
import time
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Q, Count
from django.utils import timezone

logger = logging.getLogger(__name__)


class AIService:
    """Servico unificado de IA para o helpdesk"""

    def __init__(self):
        self._client = None
        self._provider = None
        self._model = None

    def _get_config(self):
        """Obter configuracao ativa de IA"""
        from dashboard.models import AIConfiguration
        try:
            config = AIConfiguration.objects.filter(is_active=True).first()
            if config:
                return config
        except Exception:
            pass
        return None

    def _get_client(self):
        """Inicializa cliente de IA baseado no provedor configurado"""
        config = self._get_config()
        if not config:
            return None, None, None

        self._provider = config.provider
        self._model = config.model_name

        try:
            if config.provider == 'openai':
                import openai
                client = openai.OpenAI(api_key=config.api_key)
                return client, config.provider, config
            elif config.provider == 'anthropic':
                import anthropic
                client = anthropic.Anthropic(api_key=config.api_key)
                return client, config.provider, config
        except ImportError:
            logger.warning(f"Pacote {config.provider} nao instalado")
        except Exception as e:
            logger.error(f"Erro ao inicializar cliente IA: {e}")

        return None, None, None

    def _call_llm(self, system_prompt: str, user_prompt: str, max_tokens: int = 500) -> Optional[str]:
        """Chamada unificada ao LLM"""
        client, provider, config = self._get_client()
        if not client:
            return None

        try:
            if provider == 'openai':
                response = client.chat.completions.create(
                    model=config.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=config.temperature,
                    max_tokens=max_tokens,
                )
                return response.choices[0].message.content

            elif provider == 'anthropic':
                response = client.messages.create(
                    model=config.model_name,
                    max_tokens=max_tokens,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return response.content[0].text

        except Exception as e:
            logger.error(f"Erro na chamada LLM ({provider}): {e}")
            return None

    def _log_interaction(self, tipo, ticket, input_text, output_text,
                         confidence=None, tokens=0, ms=0):
        """Registrar interacao de IA no banco"""
        try:
            from dashboard.models import AIInteraction
            AIInteraction.objects.create(
                tipo=tipo,
                ticket=ticket,
                input_text=input_text[:2000],
                output_text=output_text[:2000],
                confidence=confidence,
                provider=self._provider or '',
                model_used=self._model or '',
                tokens_used=tokens,
                processing_time_ms=ms,
            )
        except Exception as e:
            logger.error(f"Erro ao logar interacao IA: {e}")

    # -----------------------------------------------------------------------
    # Auto-categorizacao
    # -----------------------------------------------------------------------
    def auto_categorize(self, titulo: str, descricao: str) -> dict:
        """Classificar ticket automaticamente"""
        from dashboard.models import CategoriaTicket
        categories = list(CategoriaTicket.objects.values_list('nome', flat=True))
        if not categories:
            return {"category": "Geral", "confidence": 0.5, "source": "fallback"}

        start = time.time()

        # Tentar LLM primeiro
        system_prompt = (
            "Voce e um classificador de tickets de suporte. "
            "Classifique o ticket na categoria mais adequada. "
            "Responda APENAS com um JSON: {\"category\": \"...\", \"confidence\": 0.X}"
        )
        user_prompt = (
            f"Categorias disponiveis: {', '.join(categories)}\n\n"
            f"Titulo: {titulo}\nDescricao: {descricao}"
        )

        result = self._call_llm(system_prompt, user_prompt, max_tokens=100)
        ms = int((time.time() - start) * 1000)

        if result:
            try:
                data = json.loads(result)
                self._log_interaction('categorization', None, user_prompt, result,
                                      confidence=data.get('confidence'), ms=ms)
                return {**data, "source": "llm"}
            except json.JSONDecodeError:
                pass

        # Fallback heurístico
        text = f"{titulo} {descricao}".lower()
        best, best_score = categories[0], 0
        for cat in categories:
            score = sum(1 for w in cat.lower().split() if w in text)
            if score > best_score:
                best_score = score
                best = cat

        confidence = min(0.5 + best_score * 0.15, 0.9)
        return {"category": best, "confidence": confidence, "source": "heuristic"}

    # -----------------------------------------------------------------------
    # Predicao de prioridade
    # -----------------------------------------------------------------------
    def predict_priority(self, titulo: str, descricao: str) -> dict:
        """Predizer prioridade baseado no texto"""
        start = time.time()
        text = f"{titulo} {descricao}".lower()

        # Heurística como fallback rápido
        urgency_words = ["urgente", "critico", "emergencia", "parado", "fora do ar",
                         "nao funciona", "caiu", "down", "produção parada"]
        high_words = ["erro", "bug", "falha", "problema grave", "impacto", "lento",
                      "instavel", "intermitente"]

        if any(w in text for w in urgency_words):
            priority, confidence = "critica", 0.85
        elif any(w in text for w in high_words):
            priority, confidence = "alta", 0.75
        else:
            priority, confidence = "media", 0.60

        # Tentar LLM para melhor precisão
        system_prompt = (
            "Voce classifica a prioridade de tickets de suporte. "
            "Prioridades: critica, alta, media, baixa. "
            "Responda APENAS com JSON: {\"priority\": \"...\", \"confidence\": 0.X, \"reason\": \"...\"}"
        )
        result = self._call_llm(system_prompt, f"Titulo: {titulo}\nDescricao: {descricao}", 150)
        ms = int((time.time() - start) * 1000)

        if result:
            try:
                data = json.loads(result)
                self._log_interaction('priority', None, text[:500], result,
                                      confidence=data.get('confidence'), ms=ms)
                return {**data, "source": "llm"}
            except json.JSONDecodeError:
                pass

        return {"priority": priority, "confidence": confidence, "source": "heuristic"}

    # -----------------------------------------------------------------------
    # Sugestao de resposta
    # -----------------------------------------------------------------------
    def suggest_response(self, ticket) -> dict:
        """Sugerir resposta baseada em KB + historico"""
        start = time.time()

        # Buscar artigos relevantes da KB
        kb_context = self._get_kb_context(ticket.titulo, ticket.descricao)

        # Buscar respostas de tickets similares
        similar_responses = self._get_similar_responses(ticket)

        system_prompt = (
            "Voce e um agente de suporte tecnico profissional. "
            "Sugira uma resposta para o ticket do cliente, baseando-se no contexto fornecido. "
            "Responda de forma profissional, empatica e objetiva em portugues."
        )
        user_prompt = (
            f"TICKET:\nTitulo: {ticket.titulo}\nDescricao: {ticket.descricao}\n\n"
            f"ARTIGOS DA BASE DE CONHECIMENTO:\n{kb_context}\n\n"
            f"RESPOSTAS SIMILARES ANTERIORES:\n{similar_responses}\n\n"
            "Sugira uma resposta para o cliente:"
        )

        result = self._call_llm(system_prompt, user_prompt, max_tokens=800)
        ms = int((time.time() - start) * 1000)

        if result:
            self._log_interaction('response', ticket, user_prompt[:1000], result, ms=ms)
            return {"suggestion": result, "source": "llm", "kb_articles_used": kb_context[:200]}

        # Fallback: resposta padrão
        return {
            "suggestion": (
                f"Olá {ticket.cliente.nome if ticket.cliente else 'cliente'},\n\n"
                f"Recebemos seu ticket #{ticket.numero} sobre \"{ticket.titulo}\". "
                "Nossa equipe está analisando o caso e retornaremos em breve.\n\n"
                "Atenciosamente,\nEquipe de Suporte"
            ),
            "source": "template",
        }

    # -----------------------------------------------------------------------
    # Resumo de conversa
    # -----------------------------------------------------------------------
    def summarize_conversation(self, ticket) -> dict:
        """Resumir todas as interacoes de um ticket"""
        from dashboard.models import InteracaoTicket
        interactions = InteracaoTicket.objects.filter(ticket=ticket).order_by('criado_em')

        if not interactions.exists():
            return {"summary": "Nenhuma interação registrada.", "source": "empty"}

        conversation = "\n".join([
            f"[{i.criado_em.strftime('%d/%m %H:%M')}] {i.usuario.get_full_name() if i.usuario else 'Sistema'}: {i.mensagem}"
            for i in interactions[:50]
        ])

        system_prompt = (
            "Resuma a conversa do ticket de suporte em 2-3 frases objetivas. "
            "Destaque: problema, acoes tomadas, status atual."
        )

        result = self._call_llm(system_prompt, conversation, 300)
        if result:
            self._log_interaction('summary', ticket, conversation[:1000], result)
            return {"summary": result, "source": "llm"}

        # Fallback: últimas 3 interações
        last3 = list(interactions.order_by('-criado_em')[:3])
        summary = " | ".join([f"{i.mensagem[:100]}" for i in last3])
        return {"summary": summary, "source": "fallback"}

    # -----------------------------------------------------------------------
    # Análise de sentimento
    # -----------------------------------------------------------------------
    def analyze_sentiment(self, text: str) -> dict:
        """Analisar sentimento do texto do cliente"""
        start = time.time()

        # Heurística rápida
        negative_words = ["frustrado", "irritado", "absurdo", "ridiculo", "pessimo",
                          "horrivel", "nunca", "sempre", "problema", "raiva",
                          "insatisfeito", "inaceitavel", "vergonha", "demora"]
        positive_words = ["obrigado", "excelente", "otimo", "parabens", "satisfeito",
                          "rapido", "eficiente", "agradeço", "perfeito", "bom"]

        text_lower = text.lower()
        neg_count = sum(1 for w in negative_words if w in text_lower)
        pos_count = sum(1 for w in positive_words if w in text_lower)

        if neg_count > pos_count + 1:
            sentiment, confidence = "negative", min(0.6 + neg_count * 0.1, 0.95)
        elif pos_count > neg_count:
            sentiment, confidence = "positive", min(0.6 + pos_count * 0.1, 0.95)
        else:
            sentiment, confidence = "neutral", 0.6

        # Tentar LLM
        system_prompt = (
            "Analise o sentimento do texto. Responda com JSON: "
            "{\"sentiment\": \"positive|neutral|negative\", \"confidence\": 0.X, \"emoji\": \"...\", \"reason\": \"...\"}"
        )
        result = self._call_llm(system_prompt, text[:500], 150)
        ms = int((time.time() - start) * 1000)

        if result:
            try:
                data = json.loads(result)
                return {**data, "source": "llm"}
            except json.JSONDecodeError:
                pass

        emoji_map = {"positive": "😊", "neutral": "😐", "negative": "😠"}
        return {
            "sentiment": sentiment,
            "confidence": confidence,
            "emoji": emoji_map.get(sentiment, "😐"),
            "source": "heuristic"
        }

    # -----------------------------------------------------------------------
    # Deteccao de duplicatas
    # -----------------------------------------------------------------------
    def find_duplicates(self, titulo: str, descricao: str, limit: int = 5) -> list:
        """Encontrar tickets similares"""
        from dashboard.models import Ticket
        text = f"{titulo} {descricao}".lower()
        words = set(text.split())

        # Buscar tickets dos últimos 90 dias
        since = timezone.now() - timedelta(days=90)
        recent_tickets = Ticket.objects.filter(
            criado_em__gte=since
        ).exclude(
            status='fechado'
        ).values('id', 'numero', 'titulo', 'descricao', 'status')[:200]

        scored = []
        for t in recent_tickets:
            t_text = f"{t['titulo']} {t['descricao']}".lower()
            t_words = set(t_text.split())
            if not words or not t_words:
                continue
            # Jaccard similarity
            intersection = words & t_words
            union = words | t_words
            similarity = len(intersection) / len(union) if union else 0
            if similarity > 0.15:
                scored.append({
                    "id": t['id'],
                    "numero": t['numero'],
                    "titulo": t['titulo'],
                    "status": t['status'],
                    "similarity": round(similarity, 3),
                })

        scored.sort(key=lambda x: x['similarity'], reverse=True)
        return scored[:limit]

    # -----------------------------------------------------------------------
    # Auto-triagem completa
    # -----------------------------------------------------------------------
    def auto_triage(self, titulo: str, descricao: str) -> dict:
        """Pipeline completo: categorizar + priorizar + sugerir KB"""
        category_result = self.auto_categorize(titulo, descricao)
        priority_result = self.predict_priority(titulo, descricao)
        duplicates = self.find_duplicates(titulo, descricao, limit=3)
        sentiment = self.analyze_sentiment(descricao)
        kb_suggestions = self._get_kb_articles(titulo, descricao)

        return {
            "category": category_result,
            "priority": priority_result,
            "duplicates": duplicates,
            "sentiment": sentiment,
            "kb_suggestions": kb_suggestions,
        }

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------
    def _get_kb_context(self, titulo: str, descricao: str, limit: int = 3) -> str:
        """Buscar artigos relevantes na base de conhecimento"""
        articles = self._get_kb_articles(titulo, descricao, limit)
        if not articles:
            return "Nenhum artigo relevante encontrado."
        return "\n---\n".join([f"[{a['titulo']}]: {a['resumo']}" for a in articles])

    def _get_kb_articles(self, titulo: str, descricao: str, limit: int = 5) -> list:
        """Buscar artigos da KB por similaridade de texto"""
        try:
            from dashboard.models import ArtigoConhecimento
            text = f"{titulo} {descricao}".lower()
            words = [w for w in text.split() if len(w) > 3]

            q = Q()
            for word in words[:10]:
                q |= Q(titulo__icontains=word) | Q(conteudo__icontains=word)

            articles = ArtigoConhecimento.objects.filter(q, publicado=True)[:limit]
            return [
                {"id": a.id, "titulo": a.titulo, "resumo": a.conteudo[:200]}
                for a in articles
            ]
        except Exception:
            pass

        try:
            from dashboard.models import KnowledgeBase
            text = f"{titulo} {descricao}".lower()
            words = [w for w in text.split() if len(w) > 3]
            q = Q()
            for word in words[:10]:
                q |= Q(title__icontains=word) | Q(content__icontains=word)
            articles = KnowledgeBase.objects.filter(q)[:limit]
            return [
                {"id": a.id, "titulo": a.title, "resumo": a.content[:200]}
                for a in articles
            ]
        except Exception:
            return []

    def _get_similar_responses(self, ticket, limit: int = 3) -> str:
        """Buscar respostas de tickets similares"""
        from dashboard.models import InteracaoTicket, Ticket

        words = ticket.titulo.lower().split()
        q = Q()
        for w in words[:5]:
            if len(w) > 3:
                q |= Q(titulo__icontains=w)

        similar = Ticket.objects.filter(
            q, status__in=['resolvido', 'fechado']
        ).exclude(id=ticket.id).order_by('-criado_em')[:limit]

        responses = []
        for t in similar:
            last_response = InteracaoTicket.objects.filter(
                ticket=t, tipo='resposta'
            ).order_by('-criado_em').first()
            if last_response:
                responses.append(f"[Ticket #{t.numero}]: {last_response.mensagem[:300]}")

        return "\n---\n".join(responses) if responses else "Nenhuma resposta similar encontrada."


# Singleton
ai_service = AIService()
