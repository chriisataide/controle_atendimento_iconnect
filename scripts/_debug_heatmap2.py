import os, sys, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "controle_atendimento.settings")
sys.path.insert(0, "/app")
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from dashboard.views.dashboard import DashboardView

User = get_user_model()
user = User.objects.filter(is_superuser=True).first()
print(f"User: {user}")

factory = RequestFactory()
request = factory.get("/dashboard/")
request.user = user

view = DashboardView()
view.request = request
view.kwargs = {}
view.args = ()

ctx = view.get_context_data()
heatmap = ctx.get("heatmap_data", "NOT FOUND")
print(f"heatmap_data type: {type(heatmap)}")
print(f"heatmap_data value: {heatmap}")
