# =============================================================================
# Dashboard Forms Package
# =============================================================================
# Re-exporta todos os formulários para manter compatibilidade com
# imports existentes: `from dashboard.forms import TicketForm`, etc.
# =============================================================================

from .base import (  # noqa: F401
    ClienteForm,
    CustomLoginForm,
    DashboardUserChangeForm,
    DashboardUserCreationForm,
    MobileCommentForm,
    QuickTicketForm,
    TicketCreateForm,
    TicketForm,
)
from .simple import ClienteForm as SimpleClienteForm
from .simple import CustomLoginForm as SimpleLoginForm  # noqa: F401
from .simple import MobileCommentForm as SimpleMobileCommentForm
from .simple import QuickTicketForm as SimpleQuickTicketForm
from .simple import TicketForm as SimpleTicketForm
from .whatsapp import (  # noqa: F401
    WhatsAppAccountForm,
    WhatsAppAnalyticsFilterForm,
    WhatsAppAutoResponseForm,
    WhatsAppBulkMessageForm,
    WhatsAppContactForm,
    WhatsAppMessageForm,
    WhatsAppTemplateForm,
)
