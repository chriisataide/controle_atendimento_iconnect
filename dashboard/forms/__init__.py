# =============================================================================
# Dashboard Forms Package
# =============================================================================
# Re-exporta todos os formulários para manter compatibilidade com
# imports existentes: `from dashboard.forms import TicketForm`, etc.
# =============================================================================

from .base import (  # noqa: F401
    DashboardUserCreationForm,
    DashboardUserChangeForm,
    CustomLoginForm,
    QuickTicketForm,
    MobileCommentForm,
    TicketForm,
    TicketCreateForm,
    ClienteForm,
)

from .simple import (  # noqa: F401
    CustomLoginForm as SimpleLoginForm,
    QuickTicketForm as SimpleQuickTicketForm,
    MobileCommentForm as SimpleMobileCommentForm,
    TicketForm as SimpleTicketForm,
    ClienteForm as SimpleClienteForm,
)

from .whatsapp import (  # noqa: F401
    WhatsAppAccountForm,
    WhatsAppTemplateForm,
    WhatsAppAutoResponseForm,
    WhatsAppContactForm,
    WhatsAppMessageForm,
    WhatsAppBulkMessageForm,
    WhatsAppAnalyticsFilterForm,
)
