"""
Views do app Cálculo de Implantação de Vigilante.
Inclui: página principal, processamento, preview AJAX, download template, histórico.
"""

import io
import json
import logging
import os
import traceback

import pandas as pd
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET, require_POST

from .engine import calcular_valor_implantacao, get_empresas_disponiveis
from .models import ProcessamentoHistorico

logger = logging.getLogger(__name__)

# Diretórios de trabalho
UPLOAD_DIR = getattr(settings, "CALCULO_VIGILANTE_UPLOAD_DIR", os.path.join(settings.BASE_DIR, "uploads_calculo"))
OUTPUT_DIR = getattr(settings, "CALCULO_VIGILANTE_OUTPUT_DIR", os.path.join(settings.BASE_DIR, "processados_calculo"))

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


@login_required
def pagina_calculo(request):
    """Renderiza a página do cálculo de implantação."""
    empresas = get_empresas_disponiveis()
    empresas_unicas = set(e["empresa"] for e in empresas)
    ufs_unicas = set(e["uf"] for e in empresas)

    # Últimos 5 processamentos do usuário
    historico = ProcessamentoHistorico.objects.filter(usuario=request.user).order_by("-criado_em")[:5]

    historico_json = json.dumps(
        [
            {
                "id": h.id,
                "arquivo": h.arquivo_nome,
                "tamanho": h.arquivo_tamanho,
                "linhas_total": h.linhas_total,
                "linhas_processadas": h.linhas_processadas,
                "linhas_com_valor": h.linhas_com_valor,
                "linhas_sem_match": h.linhas_sem_match,
                "valor_total": str(h.valor_total),
                "status": h.status,
                "erro": h.erro_mensagem,
                "data": h.criado_em.strftime("%d/%m/%Y %H:%M"),
            }
            for h in historico
        ]
    )

    return render(
        request,
        "calculo_vigilante/calculo.html",
        {
            "active_page": "calculo_vigilante",
            "empresas": empresas,
            "total_empresas": len(empresas_unicas),
            "total_ufs": len(ufs_unicas),
            "total_combinacoes": len(empresas),
            "historico_json": historico_json,
        },
    )


@login_required
@require_POST
def preview_planilha(request):
    """
    Recebe planilha via AJAX e retorna preview:
    colunas detectadas, nº de linhas, amostra dos dados.
    """
    if "file" not in request.FILES:
        return JsonResponse({"erro": "Nenhum arquivo enviado."}, status=400)

    arquivo = request.FILES["file"]
    nome = arquivo.name

    if not nome.lower().endswith((".xlsx", ".xls")):
        return JsonResponse({"erro": "Formato inválido. Envie .xlsx ou .xls"}, status=400)

    try:
        df = pd.read_excel(arquivo)
        colunas = list(df.columns)
        total_linhas = len(df)

        # Verificar colunas mapeáveis
        from unidecode import unidecode

        cols_norm = {unidecode(c.lower().replace(" ", "")): c for c in colunas}

        detectadas = {
            "empresa": None,
            "uf": None,
            "entrada": None,
            "saida": None,
        }

        emp_keys = ["empresa", "empresavigilante", "vigilante", "nomeempresa"]
        uf_keys = ["uf", "estado", "siglaestado", "sigla"]
        entrada_keys = ["entrada", "chegada", "datachegada", "dataentrada", "inicio"]
        saida_keys = ["saida", "partida", "datasaida", "datapartida", "fim"]

        for norm, orig in cols_norm.items():
            if any(k in norm for k in emp_keys) and not detectadas["empresa"]:
                detectadas["empresa"] = orig
            if any(k in norm for k in uf_keys) and not detectadas["uf"]:
                detectadas["uf"] = orig
            if any(k in norm for k in entrada_keys) and not detectadas["entrada"]:
                detectadas["entrada"] = orig
            if any(k in norm for k in saida_keys) and not detectadas["saida"]:
                detectadas["saida"] = orig

        # Amostra dos primeiros 5 registros
        amostra = df.head(5).fillna("").astype(str).to_dict(orient="records")

        # Salvar arquivo temporariamente
        caminho_upload = os.path.join(UPLOAD_DIR, nome)
        arquivo.seek(0)
        with open(caminho_upload, "wb+") as dest:
            for chunk in arquivo.chunks():
                dest.write(chunk)

        return JsonResponse(
            {
                "sucesso": True,
                "arquivo": nome,
                "total_linhas": total_linhas,
                "colunas": colunas,
                "detectadas": detectadas,
                "amostra": amostra,
            }
        )

    except Exception as e:
        logger.error(f"[calculo_vigilante] Erro no preview: {e}")
        return JsonResponse({"erro": f"Erro ao ler planilha: {str(e)}"}, status=400)


@login_required
@require_POST
def processar_planilha(request):
    """
    Recebe planilha .xlsx via upload, calcula valores de implantação
    e retorna JSON com estatísticas + sinaliza download disponível.
    """
    if "file" not in request.FILES:
        return JsonResponse({"erro": "Nenhum arquivo enviado."}, status=400)

    arquivo = request.FILES["file"]
    nome = arquivo.name

    if not nome.lower().endswith((".xlsx", ".xls")):
        return JsonResponse({"erro": "Formato inválido. Envie um arquivo .xlsx"}, status=400)

    caminho_upload = os.path.join(UPLOAD_DIR, nome)
    with open(caminho_upload, "wb+") as dest:
        for chunk in arquivo.chunks():
            dest.write(chunk)

    logger.info(f"[calculo_vigilante] Arquivo recebido: {nome}")

    try:
        df = pd.read_excel(caminho_upload)
        total_linhas = len(df)

        df = calcular_valor_implantacao(df)

        linhas_com_valor = int((df["VALOR_NUM"] > 0).sum())
        linhas_sem_match = total_linhas - linhas_com_valor
        valor_total = float(df["VALOR_NUM"].sum())

        caminho_saida = os.path.join(OUTPUT_DIR, "relatorio_implantacao.xlsx")
        df.to_excel(caminho_saida, index=False)

        logger.info(f"[calculo_vigilante] Relatório gerado: {caminho_saida}")

        # Salvar histórico
        ProcessamentoHistorico.objects.create(
            usuario=request.user,
            arquivo_nome=nome,
            arquivo_tamanho=arquivo.size,
            linhas_total=total_linhas,
            linhas_processadas=total_linhas,
            linhas_com_valor=linhas_com_valor,
            linhas_sem_match=linhas_sem_match,
            valor_total=valor_total,
            status="sucesso",
        )

        return JsonResponse(
            {
                "sucesso": True,
                "stats": {
                    "linhas_total": total_linhas,
                    "linhas_processadas": total_linhas,
                    "linhas_com_valor": linhas_com_valor,
                    "linhas_sem_match": linhas_sem_match,
                    "valor_total": f"R$ {valor_total:,.2f}".replace(".", "X").replace(",", ".").replace("X", ","),
                    "valor_total_num": valor_total,
                },
            }
        )

    except Exception as e:
        logger.error(f"[calculo_vigilante] Erro: {e}")
        logger.error(traceback.format_exc())

        ProcessamentoHistorico.objects.create(
            usuario=request.user,
            arquivo_nome=nome,
            arquivo_tamanho=arquivo.size,
            status="erro",
            erro_mensagem=str(e),
        )

        return JsonResponse({"erro": f"Erro ao processar: {str(e)}"}, status=500)


@login_required
@require_GET
def download_resultado(request):
    """Baixa o último relatório processado."""
    caminho_saida = os.path.join(OUTPUT_DIR, "relatorio_implantacao.xlsx")
    if not os.path.exists(caminho_saida):
        return JsonResponse({"erro": "Nenhum relatório disponível."}, status=404)

    return FileResponse(
        open(caminho_saida, "rb"),
        as_attachment=True,
        filename="relatorio_implantacao.xlsx",
    )


@login_required
@require_GET
def download_template(request):
    """Gera e retorna uma planilha modelo com as colunas necessárias."""
    df = pd.DataFrame(
        {
            "Empresa": [
                "SEGURPRO SEGURANCA LTDA - BA",
                "INTERFORT SEGURANCA DE VALORES LTDA - PE",
                "EPAVI VIGILANCIA LTDA",
                "AZUL SEGURANCA",
            ],
            "UF": ["BA", "PE", "SP", "RJ"],
            "Entrada": [
                "2026-01-15 08:00:00",
                "2026-01-15 22:00:00",
                "2026-01-16 07:00:00",
                "2026-01-16 08:00:00",
            ],
            "Saída": [
                "2026-01-15 16:48:00",
                "2026-01-16 06:48:00",
                "2026-01-17 07:00:00",
                "2026-01-16 16:48:00",
            ],
        }
    )

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Dados")
        ws = writer.sheets["Dados"]
        ws.column_dimensions["A"].width = 45
        ws.column_dimensions["B"].width = 8
        ws.column_dimensions["C"].width = 22
        ws.column_dimensions["D"].width = 22

    buffer.seek(0)
    response = HttpResponse(
        buffer.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="template_calculo_vigilante.xlsx"'
    return response
