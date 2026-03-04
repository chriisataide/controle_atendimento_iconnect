# =============================================================================
# Dashboard Models Package
# =============================================================================
# Todos os modelos são re-exportados aqui para manter compatibilidade com
# imports existentes: `from dashboard.models import Ticket`, etc.
# =============================================================================

# Modelos Auditoria
from .audit import AuditEvent, ComplianceReport, DataAccessLog, SecurityAlert  # noqa: F401

# Modelos Auto-atribuição
from .auto_assignment import CargoTrabalho, RegraAtribuicao, SkillAgent  # noqa: F401

# Modelos principais (base)
from .base import *  # noqa: F401,F403

# Modelos de Chat
from .chat import (  # noqa: F401
    ChatBot,
    ChatMessage,
    ChatMessageReadReceipt,
    ChatParticipant,
    ChatReaction,
    ChatRoom,
    ChatSettings,
)

# Modelos Chatbot AI
from .chatbot_ai import (  # noqa: F401
    ChatbotAnalytics,
    ChatbotConfiguration,
    ChatbotConversation,
    ChatbotKnowledgeBase,
    ChatbotMessage,
    ChatbotTraining,
)

# Modelos Equipamentos
from .equipamento import (  # noqa: F401
    AlertaEquipamento,
    ConfiguracaoAlertaEquipamento,
    Equipamento,
    HistoricoEquipamento,
)

# Modelos Estoque (já importado via base.py)
from .estoque import (  # noqa: F401
    CategoriaEstoque,
    EstoqueAlerta,
    Fornecedor,
    MovimentacaoEstoque,
    Produto,
    UnidadeMedida,
)

# Modelos Executive Dashboard
from .executive import AlertaKPI, DashboardWidget, ExecutiveDashboardKPI, MetricaTempoReal  # noqa: F401

# Modelos Knowledge Base
from .knowledge import ArtigoConhecimento, CategoriaConhecimento  # noqa: F401

# Modelos LGPD
from .lgpd import LGPDAccessLog, LGPDConsent, LGPDDataRequest  # noqa: F401

# Modelos Push Notifications
from .push import NotificationPreference, PushNotificationLog, PushSubscription  # noqa: F401

# Modelos Satisfação
from .satisfacao import AvaliacaoSatisfacao, PerguntaPesquisa, PesquisaSatisfacao  # noqa: F401

# Modelos WhatsApp
from .whatsapp import (  # noqa: F401
    WhatsAppAnalytics,
    WhatsAppAutoResponse,
    WhatsAppBusinessAccount,
    WhatsAppContact,
    WhatsAppConversation,
    WhatsAppMessage,
    WhatsAppTemplate,
    WhatsAppWebhookLog,
)
