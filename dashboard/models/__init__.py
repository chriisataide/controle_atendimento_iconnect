# =============================================================================
# Dashboard Models Package
# =============================================================================
# Todos os modelos são re-exportados aqui para manter compatibilidade com
# imports existentes: `from dashboard.models import Ticket`, etc.
# =============================================================================

# Modelos principais (base)
from .base import *  # noqa: F401,F403

# Modelos de Chat
from .chat import (  # noqa: F401
    ChatRoom, ChatParticipant, ChatMessage, ChatMessageReadReceipt,
    ChatReaction, ChatSettings, ChatBot
)

# Modelos LGPD
from .lgpd import (  # noqa: F401
    LGPDConsent, LGPDDataRequest, LGPDAccessLog
)

# Modelos Chatbot AI
from .chatbot_ai import (  # noqa: F401
    ChatbotKnowledgeBase, ChatbotConversation, ChatbotMessage,
    ChatbotAnalytics, ChatbotTraining, ChatbotConfiguration
)

# Modelos Executive Dashboard
from .executive import (  # noqa: F401
    ExecutiveDashboardKPI, DashboardWidget, MetricaTempoReal, AlertaKPI
)

# Modelos Push Notifications
from .push import (  # noqa: F401
    PushSubscription, NotificationPreference, PushNotificationLog
)

# Modelos Satisfação
from .satisfacao import (  # noqa: F401
    AvaliacaoSatisfacao, PesquisaSatisfacao, PerguntaPesquisa
)

# Modelos WhatsApp
from .whatsapp import (  # noqa: F401
    WhatsAppBusinessAccount, WhatsAppContact, WhatsAppConversation,
    WhatsAppMessage, WhatsAppTemplate, WhatsAppAutoResponse,
    WhatsAppAnalytics, WhatsAppWebhookLog
)

# Modelos Knowledge Base
from .knowledge import (  # noqa: F401
    CategoriaConhecimento, ArtigoConhecimento
)

# Modelos Auto-atribuição
from .auto_assignment import (  # noqa: F401
    SkillAgent, RegraAtribuicao, CargoTrabalho
)

# Modelos Equipamentos
from .equipamento import (  # noqa: F401
    Equipamento, HistoricoEquipamento, AlertaEquipamento,
    ConfiguracaoAlertaEquipamento
)

# Modelos Estoque (já importado via base.py)
from .estoque import (  # noqa: F401
    CategoriaEstoque, UnidadeMedida, Fornecedor, Produto,
    MovimentacaoEstoque, EstoqueAlerta
)

# Modelos Auditoria
from .audit import (  # noqa: F401
    AuditEvent, SecurityAlert, ComplianceReport, DataAccessLog
)
