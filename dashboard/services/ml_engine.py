# Sistema de Machine Learning para iConnect
import logging
import os
from datetime import timedelta

import joblib
import pandas as pd
from django.conf import settings
from django.db.models import Count
from django.utils import timezone
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.preprocessing import LabelEncoder
from textblob import TextBlob

from ..models import Ticket

logger = logging.getLogger(__name__)

# Stop words em português para o TfidfVectorizer
# Fonte: NLTK + palavras comuns em tickets de suporte
PORTUGUESE_STOP_WORDS = [
    "a",
    "ao",
    "aos",
    "aquela",
    "aquelas",
    "aquele",
    "aqueles",
    "aquilo",
    "as",
    "até",
    "com",
    "como",
    "da",
    "das",
    "de",
    "dela",
    "delas",
    "dele",
    "deles",
    "depois",
    "do",
    "dos",
    "e",
    "ela",
    "elas",
    "ele",
    "eles",
    "em",
    "entre",
    "era",
    "eram",
    "essa",
    "essas",
    "esse",
    "esses",
    "esta",
    "estas",
    "este",
    "estes",
    "eu",
    "foi",
    "for",
    "foram",
    "fosse",
    "fossem",
    "há",
    "isso",
    "isto",
    "já",
    "lhe",
    "lhes",
    "lo",
    "mais",
    "mas",
    "me",
    "mesmo",
    "meu",
    "meus",
    "minha",
    "minhas",
    "muito",
    "na",
    "nas",
    "nem",
    "no",
    "nos",
    "nós",
    "nossa",
    "nossas",
    "nosso",
    "nossos",
    "num",
    "numa",
    "não",
    "o",
    "onde",
    "os",
    "ou",
    "para",
    "pela",
    "pelas",
    "pelo",
    "pelos",
    "por",
    "qual",
    "quando",
    "que",
    "quem",
    "se",
    "sem",
    "ser",
    "será",
    "seu",
    "seus",
    "sido",
    "sob",
    "sobre",
    "sua",
    "suas",
    "são",
    "só",
    "também",
    "te",
    "tem",
    "tendo",
    "ter",
    "teu",
    "teus",
    "ti",
    "tinha",
    "tinham",
    "toda",
    "todas",
    "todo",
    "todos",
    "tu",
    "tua",
    "tuas",
    "tudo",
    "um",
    "uma",
    "umas",
    "uns",
    "vai",
    "vos",
    "à",
    "às",
    "é",
]


# Análise de sentimento simplificada para português
# TextBlob usa modelo em inglês — inadequado para tickets em pt-BR
_PALAVRAS_POSITIVAS = {
    "obrigado",
    "obrigada",
    "agradeço",
    "excelente",
    "ótimo",
    "otimo",
    "bom",
    "boa",
    "maravilhoso",
    "parabéns",
    "parabens",
    "perfeito",
    "satisfeito",
    "satisfeita",
    "resolvido",
    "funciona",
    "funcionando",
    "rápido",
    "rapido",
    "eficiente",
    "incrível",
    "incrivel",
    "sucesso",
    "adorei",
    "gostei",
    "recomendo",
    "atencioso",
    "ajudou",
    "fantástico",
}

_PALAVRAS_NEGATIVAS = {
    "problema",
    "erro",
    "bug",
    "falha",
    "quebrado",
    "lento",
    "demora",
    "péssimo",
    "pessimo",
    "horrível",
    "horrivel",
    "ruim",
    "insatisfeito",
    "insatisfeita",
    "reclamação",
    "reclamacao",
    "urgente",
    "crítico",
    "critico",
    "grave",
    "inaceitável",
    "inaceitavel",
    "absurdo",
    "pior",
    "travando",
    "trava",
    "caiu",
    "fora",
    "indisponível",
    "indisponivel",
    "não funciona",
    "nao funciona",
    "frustrado",
    "frustrada",
    "raiva",
    "decepcionado",
    "decepcionada",
    "cancelar",
    "desistir",
}


def analisar_sentimento_pt(texto: str) -> float:
    """Análise de sentimento simples para português.

    Retorna valor entre -1.0 (muito negativo) e 1.0 (muito positivo).
    Usa contagem de palavras-chave com fallback para TextBlob.
    """
    texto_lower = texto.lower()
    palavras = set(texto_lower.split())

    score_pos = len(palavras & _PALAVRAS_POSITIVAS)
    score_neg = len(palavras & _PALAVRAS_NEGATIVAS)

    total = score_pos + score_neg
    if total == 0:
        # Fallback: usar TextBlob (melhor que nada para palavras universais)
        return TextBlob(texto).sentiment.polarity

    return (score_pos - score_neg) / total


class TicketPredictor:
    """Sistema de ML para previsão de tickets"""

    def __init__(self):
        self.models_path = os.path.join(settings.BASE_DIR, "ml_models")
        os.makedirs(self.models_path, exist_ok=True)

        # Modelos
        self.priority_model = None
        self.category_model = None
        self.resolution_time_model = None
        self.satisfaction_model = None

        # Encoders e Vectorizers
        self.priority_encoder = LabelEncoder()
        self.category_encoder = LabelEncoder()
        self.text_vectorizer = TfidfVectorizer(max_features=1000, stop_words=PORTUGUESE_STOP_WORDS)

    def prepare_data(self):
        """Prepara dados para treinamento"""
        logger.info("🤖 Preparando dados para treinamento ML...")

        # Buscar tickets com dados completos
        tickets = Ticket.objects.filter(criado_em__gte=timezone.now() - timedelta(days=365)).select_related(
            "cliente", "agente"
        )

        if tickets.count() < 100:
            logger.warning("⚠️ Poucos dados para treinamento ML (mínimo 100 tickets)")
            return None

        # Criar DataFrame
        data = []
        for ticket in tickets:
            # Calcular tempo de resolução em horas
            if ticket.resolvido_em:
                resolution_time = (ticket.resolvido_em - ticket.criado_em).total_seconds() / 3600
            else:
                resolution_time = None

            # Texto combinado para análise
            text = f"{ticket.titulo} {ticket.descricao}"

            # Análise de sentimento (português)
            sentiment = analisar_sentimento_pt(text)

            # Horário de criação
            hour = ticket.criado_em.hour
            weekday = ticket.criado_em.weekday()

            # Histórico do cliente
            cliente_tickets = Ticket.objects.filter(cliente=ticket.cliente).count()

            data.append(
                {
                    "titulo": ticket.titulo,
                    "descricao": ticket.descricao,
                    "texto_completo": text,
                    "categoria": ticket.categoria or "Geral",
                    "prioridade": ticket.prioridade,
                    "origem": ticket.origem,
                    "hora_criacao": hour,
                    "dia_semana": weekday,
                    "sentiment": sentiment,
                    "cliente_historico": cliente_tickets,
                    "resolution_time": resolution_time,
                    "satisfacao": self._get_satisfaction(ticket),
                }
            )

        df = pd.DataFrame(data)
        logger.info(f"✅ Dados preparados: {len(df)} tickets")
        return df

    def train_models(self):
        """Treina todos os modelos ML"""
        logger.info("🎓 Iniciando treinamento dos modelos ML...")

        df = self.prepare_data()
        if df is None:
            return False

        try:
            # 1. Modelo de Prioridade
            self._train_priority_model(df)

            # 2. Modelo de Categoria
            self._train_category_model(df)

            # 3. Modelo de Tempo de Resolução
            self._train_resolution_time_model(df)

            # 4. Modelo de Satisfação
            self._train_satisfaction_model(df)

            # Salvar modelos
            self._save_models()

            logger.info("🎉 Todos os modelos treinados com sucesso!")
            return True

        except Exception as e:
            logger.error(f"❌ Erro no treinamento: {str(e)}")
            return False

    def _train_priority_model(self, df):
        """Treina modelo de predição de prioridade"""
        logger.info("📊 Treinando modelo de prioridade...")

        # Preparar features
        features = df[["hora_criacao", "dia_semana", "sentiment", "cliente_historico"]]

        # Vetorizar texto
        text_features = self.text_vectorizer.fit_transform(df["texto_completo"])
        text_df = pd.DataFrame(text_features.toarray())

        # Combinar features
        X = pd.concat([features.reset_index(drop=True), text_df], axis=1)
        y = self.priority_encoder.fit_transform(df["prioridade"])

        # Treinar modelo
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.priority_model = RandomForestClassifier(n_estimators=100, random_state=42)
        self.priority_model.fit(X_train, y_train)

        # Avaliar
        y_pred = self.priority_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"✅ Modelo de Prioridade - Acurácia: {accuracy:.2f}")

    def _train_category_model(self, df):
        """Treina modelo de predição de categoria"""
        logger.info("📁 Treinando modelo de categoria...")

        # Usar apenas texto para categoria
        X = self.text_vectorizer.transform(df["texto_completo"])
        y = self.category_encoder.fit_transform(df["categoria"])

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.category_model = MultinomialNB()
        self.category_model.fit(X_train, y_train)

        y_pred = self.category_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"✅ Modelo de Categoria - Acurácia: {accuracy:.2f}")

    def _train_resolution_time_model(self, df):
        """Treina modelo de predição de tempo de resolução"""
        logger.info("⏱️ Treinando modelo de tempo de resolução...")

        # Filtrar apenas tickets resolvidos
        df_resolved = df.dropna(subset=["resolution_time"])

        if len(df_resolved) < 50:
            logger.warning("⚠️ Poucos dados para modelo de tempo de resolução")
            return

        # Features
        features = df_resolved[["hora_criacao", "dia_semana", "sentiment", "cliente_historico"]]

        # Adicionar prioridade encoded
        priority_encoded = self.priority_encoder.transform(df_resolved["prioridade"])
        features = features.copy()
        features["prioridade_encoded"] = priority_encoded

        X = features
        y = df_resolved["resolution_time"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.resolution_time_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.resolution_time_model.fit(X_train, y_train)

        score = self.resolution_time_model.score(X_test, y_test)
        logger.info(f"✅ Modelo de Tempo - R²: {score:.2f}")

    def _train_satisfaction_model(self, df):
        """Treina modelo de predição de satisfação"""
        logger.info("⭐ Treinando modelo de satisfação...")

        # Filtrar apenas tickets com satisfação
        df_satisfaction = df.dropna(subset=["satisfacao"])

        if len(df_satisfaction) < 50:
            logger.warning("⚠️ Poucos dados para modelo de satisfação")
            return

        features = df_satisfaction[["hora_criacao", "dia_semana", "sentiment", "resolution_time"]]
        X = features.dropna()
        y = df_satisfaction.loc[X.index, "satisfacao"]

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

        self.satisfaction_model = RandomForestRegressor(n_estimators=100, random_state=42)
        self.satisfaction_model.fit(X_train, y_train)

        score = self.satisfaction_model.score(X_test, y_test)
        logger.info(f"✅ Modelo de Satisfação - R²: {score:.2f}")

    def predict_ticket_properties(self, titulo, descricao, cliente_id=None):
        """Prediz propriedades de um novo ticket"""
        self._load_models()

        if not self.priority_model:
            return None

        # Preparar features
        texto_completo = f"{titulo} {descricao}"
        sentiment = analisar_sentimento_pt(texto_completo)

        now = timezone.now()
        hora_criacao = now.hour
        dia_semana = now.weekday()

        # Histórico do cliente
        cliente_historico = 1
        if cliente_id:
            cliente_historico = Ticket.objects.filter(cliente_id=cliente_id).count()

        # Features numéricas
        features = pd.DataFrame(
            {
                "hora_criacao": [hora_criacao],
                "dia_semana": [dia_semana],
                "sentiment": [sentiment],
                "cliente_historico": [cliente_historico],
            }
        )

        # Features de texto
        text_features = self.text_vectorizer.transform([texto_completo])
        text_df = pd.DataFrame(text_features.toarray())

        # Combinar features
        X = pd.concat([features.reset_index(drop=True), text_df], axis=1)

        predictions = {}

        # Predição de prioridade
        if self.priority_model:
            priority_pred = self.priority_model.predict(X)[0]
            priority_proba = self.priority_model.predict_proba(X)[0]
            predictions["prioridade"] = self.priority_encoder.inverse_transform([priority_pred])[0]
            predictions["prioridade_confianca"] = max(priority_proba)

        # Predição de categoria
        if self.category_model:
            category_pred = self.category_model.predict(text_features)[0]
            category_proba = self.category_model.predict_proba(text_features)[0]
            predictions["categoria"] = self.category_encoder.inverse_transform([category_pred])[0]
            predictions["categoria_confianca"] = max(category_proba)

        # Predição de tempo de resolução
        if self.resolution_time_model:
            # Adicionar prioridade para features
            priority_encoded = self.priority_encoder.transform([predictions.get("prioridade", "media")])[0]
            time_features = features.copy()
            time_features["prioridade_encoded"] = [priority_encoded]

            resolution_time = self.resolution_time_model.predict(time_features)[0]
            predictions["tempo_estimado_horas"] = max(1, round(resolution_time, 1))

        return predictions

    def get_insights(self):
        """Gera insights baseados nos modelos treinados"""
        insights = {
            "total_tickets_analyzed": 0,
            "priority_distribution": {},
            "category_distribution": {},
            "resolution_time_avg": 0,
            "satisfaction_avg": 0,
            "peak_hours": [],
            "peak_days": [],
            "sentiment_analysis": {"positive": 0, "neutral": 0, "negative": 0},
        }

        # Análise dos últimos 30 dias
        last_month = timezone.now() - timedelta(days=30)
        tickets = Ticket.objects.filter(criado_em__gte=last_month)

        insights["total_tickets_analyzed"] = tickets.count()

        # Distribuição de prioridades
        priorities = tickets.values("prioridade").annotate(count=Count("id"))
        insights["priority_distribution"] = {p["prioridade"]: p["count"] for p in priorities}

        # Horários de pico (análise por hora)
        hourly_data = {}
        for ticket in tickets:
            hour = ticket.criado_em.hour
            hourly_data[hour] = hourly_data.get(hour, 0) + 1

        insights["peak_hours"] = sorted(hourly_data.items(), key=lambda x: x[1], reverse=True)[:3]

        return insights

    def _save_models(self):
        """Salva modelos treinados"""
        if self.priority_model:
            joblib.dump(self.priority_model, os.path.join(self.models_path, "priority_model.pkl"))
            joblib.dump(self.priority_encoder, os.path.join(self.models_path, "priority_encoder.pkl"))

        if self.category_model:
            joblib.dump(self.category_model, os.path.join(self.models_path, "category_model.pkl"))
            joblib.dump(self.category_encoder, os.path.join(self.models_path, "category_encoder.pkl"))

        if self.text_vectorizer:
            joblib.dump(self.text_vectorizer, os.path.join(self.models_path, "text_vectorizer.pkl"))

        if self.resolution_time_model:
            joblib.dump(self.resolution_time_model, os.path.join(self.models_path, "resolution_time_model.pkl"))

        if self.satisfaction_model:
            joblib.dump(self.satisfaction_model, os.path.join(self.models_path, "satisfaction_model.pkl"))

    def _load_models(self):
        """Carrega modelos salvos"""
        try:
            if os.path.exists(os.path.join(self.models_path, "priority_model.pkl")):
                self.priority_model = joblib.load(os.path.join(self.models_path, "priority_model.pkl"))
                self.priority_encoder = joblib.load(os.path.join(self.models_path, "priority_encoder.pkl"))

            if os.path.exists(os.path.join(self.models_path, "category_model.pkl")):
                self.category_model = joblib.load(os.path.join(self.models_path, "category_model.pkl"))
                self.category_encoder = joblib.load(os.path.join(self.models_path, "category_encoder.pkl"))

            if os.path.exists(os.path.join(self.models_path, "text_vectorizer.pkl")):
                self.text_vectorizer = joblib.load(os.path.join(self.models_path, "text_vectorizer.pkl"))

            if os.path.exists(os.path.join(self.models_path, "resolution_time_model.pkl")):
                self.resolution_time_model = joblib.load(os.path.join(self.models_path, "resolution_time_model.pkl"))

            if os.path.exists(os.path.join(self.models_path, "satisfaction_model.pkl")):
                self.satisfaction_model = joblib.load(os.path.join(self.models_path, "satisfaction_model.pkl"))

        except Exception as e:
            logger.error(f"❌ Erro ao carregar modelos: {str(e)}")

    def _get_satisfaction(self, ticket):
        """Obtém satisfação do ticket"""
        try:
            # Buscar avaliação de satisfação relacionada ao ticket
            from ..models import AvaliacaoSatisfacao

            avaliacao = AvaliacaoSatisfacao.objects.filter(ticket=ticket).first()

            if avaliacao:
                return avaliacao.nota

            # Se não há avaliação, tentar inferir baseado no tempo de resolução e escalações
            if ticket.resolvido_em and ticket.criado_em:
                (ticket.resolvido_em - ticket.criado_em).total_seconds() / 3600

                # Inferir satisfação baseado em métricas de qualidade
                satisfaction_score = 5.0  # Começa com nota máxima

                # Penalizar por tempo de resolução longo
                if hasattr(ticket, "sla_deadline") and ticket.sla_deadline:
                    if ticket.resolvido_em > ticket.sla_deadline:
                        satisfaction_score -= 2.0  # SLA violado

                # Penalizar por escalações
                if ticket.is_escalated:
                    satisfaction_score -= 1.0

                # Penalizar por muitas interações (pode indicar problema complexo)
                interaction_count = ticket.interacoes.count() if hasattr(ticket, "interacoes") else 0
                if interaction_count > 10:
                    satisfaction_score -= 0.5

                # Garantir que está entre 1 e 5
                satisfaction_score = max(1.0, min(5.0, satisfaction_score))
                return satisfaction_score

        except Exception as e:
            logger.warning(f"Erro ao obter satisfação do ticket {ticket.id}: {str(e)}")

        return None


# Instância global
ml_predictor = TicketPredictor()
