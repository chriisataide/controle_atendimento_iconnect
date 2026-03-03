import os

import django

os.environ["DJANGO_SETTINGS_MODULE"] = "controle_atendimento.settings"
import sys

sys.path.insert(0, "/app")
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from dashboard.views import TicketCreateView

User = get_user_model()
u = User.objects.filter(is_superuser=True).first()
factory = RequestFactory()
request = factory.get("/dashboard/tickets/novo/")
request.user = u
request.session = SessionStore()
setattr(request, "_messages", FallbackStorage(request))
response = TicketCreateView.as_view()(request)
response.render()
html = response.content.decode()

checks = {
    "tk-page-header": "Page Header",
    "tk-stepper": "Stepper",
    "uniorgSearch": "UNIORG input",
    "tk-suggestions": "Suggestions container",
    "tk-editor-content": "Rich Editor",
    "tk-priority-options": "Priority selector",
    "produtoSearch": "Product search",
    "uploadArea": "File upload",
    "previewCard": "Preview sidebar",
    "tk-shortcuts": "Shortcuts card",
    "searchUniorg": "UNIORG JS function",
    "selectPdv": "SelectPdv JS function",
    "updatePreview": "Preview JS function",
}
ok = 0
for key, label in checks.items():
    found = key in html
    if found:
        ok += 1
    print(f"{'OK' if found else 'FALHOU'}: {label}")
print(f"\n{ok}/{len(checks)} componentes verificados")
