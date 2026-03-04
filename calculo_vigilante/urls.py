"""
URLs do app Cálculo de Implantação de Vigilante.

No urls.py do seu projeto, adicione:
    path('calculo-vigilante/', include('calculo_vigilante.urls')),
"""

from django.urls import path

from . import views

app_name = "calculo_vigilante"

urlpatterns = [
    path("", views.pagina_calculo, name="pagina"),
    path("preview/", views.preview_planilha, name="preview"),
    path("processar/", views.processar_planilha, name="processar"),
    path("download/", views.download_resultado, name="download"),
    path("template/", views.download_template, name="template"),
]
