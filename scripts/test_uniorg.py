#!/usr/bin/env python
import os

import django

os.environ["DJANGO_SETTINGS_MODULE"] = "controle_atendimento.settings"
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

User = get_user_model()
u = User.objects.filter(is_superuser=True).first()

from dashboard.views import TicketCreateView

factory = RequestFactory()
request = factory.get("/dashboard/tickets/novo/")
request.user = u
request.session = SessionStore()
setattr(request, "_messages", FallbackStorage(request))

response = TicketCreateView.as_view()(request)
response.render()
html = response.content.decode()

checks = [
    ("uniorgSearch", "Campo UNIORG input"),
    ("uniorg-suggestions", "Suggestions container"),
    ("searchUniorg", "JavaScript UNIORG function"),
    ("pdvInfo", "PdV info badge"),
    ("uniorg-search-wrapper", "UNIORG wrapper CSS class"),
]
for key, label in checks:
    status = "OK" if key in html else "FALHOU"
    print(f"{status}: {label}")
