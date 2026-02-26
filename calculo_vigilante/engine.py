"""
Motor de Cálculo de Implantação de Vigilante
=============================================
Módulo independente (sem dependência do Django) para calcular valores
de implantação de postos de vigilância com base em empresa, UF e jornada.

Dependências externas: pandas, unidecode

Uso standalone (sem Django):
    from calculo_vigilante.engine import calcular_valor_implantacao
    import pandas as pd

    df = pd.read_excel("planilha.xlsx")
    df = calcular_valor_implantacao(df)
    df.to_excel("resultado.xlsx", index=False)
"""
import re
import logging

import pandas as pd
from unidecode import unidecode
from datetime import timedelta, time

logger = logging.getLogger(__name__)

# ╔══════════════════════════════════════════════════════════════════╗
# ║                  CONSTANTES DE JORNADA                          ║
# ╚══════════════════════════════════════════════════════════════════╝
JORNADA_8H48_MINUTOS = 508.8       # 8 horas e 48 minutos
JORNADA_24H_MINUTOS = 1440         # 24 horas
TOLERANCIA_MINUTOS = 10

# Períodos noturnos (22:00 – 04:59)
HORA_INICIO_NOTURNO_1 = time(22, 0)
HORA_FIM_NOTURNO_1 = time(23, 59, 59)
HORA_INICIO_NOTURNO_2 = time(0, 0)
HORA_FIM_NOTURNO_2 = time(4, 59, 59)


# ╔══════════════════════════════════════════════════════════════════╗
# ║              TABELA DE VALORES DE IMPLANTAÇÃO                   ║
# ╚══════════════════════════════════════════════════════════════════╝
VALORES_IMPLANTACAO = [
    {"empresa": "AZUL",           "uf": "RJ", "hora_extra": 43.04, "8h48_diurno": 269.00, "8h48_noturno": 312.83, "24h": 793.89},
    {"empresa": "AZUL",           "uf": "SP", "hora_extra": 46.10, "8h48_diurno": 288.82, "8h48_noturno": 317.43, "24h": 828.39},
    {"empresa": "BELFORT",        "uf": "SP", "hora_extra": 46.30, "8h48_diurno": 289.38, "8h48_noturno": 319.01, "24h": 839.11},
    {"empresa": "BELFORT",        "uf": "RJ", "hora_extra": 44.26, "8h48_diurno": 276.63, "8h48_noturno": 357.32, "24h": 848.89},
    {"empresa": "CAMPSEG",        "uf": "MG", "hora_extra": 50.94, "8h48_diurno": 318.35, "8h48_noturno": 366.82, "24h": 1058.64},
    {"empresa": "CAMPSEG",        "uf": "SP", "hora_extra": 47.64, "8h48_diurno": 297.77, "8h48_noturno": 365.19, "24h": 1026.29},
    {"empresa": "DFA SEG",        "uf": "BA", "hora_extra": 39.05, "8h48_diurno": 244.04, "8h48_noturno": 323.51, "24h": 791.94},
    {"empresa": "EPAVI",          "uf": "SP", "hora_extra": 45.74, "8h48_diurno": 285.91, "8h48_noturno": 330.39, "24h": 853.70},
    {"empresa": "EPAVI",          "uf": "PR", "hora_extra": 48.55, "8h48_diurno": 303.43, "8h48_noturno": 353.98, "24h": 967.55},
    {"empresa": "EPAVI",          "uf": "SC", "hora_extra": 39.99, "8h48_diurno": 249.94, "8h48_noturno": 309.10, "24h": 837.83},
    {"empresa": "EPAVI",          "uf": "RS", "hora_extra": 40.42, "8h48_diurno": 252.62, "8h48_noturno": 311.76, "24h": 844.66},
    {"empresa": "FORT KNOX",      "uf": "SP", "hora_extra": 47.01, "8h48_diurno": 293.77, "8h48_noturno": 334.98, "24h": 937.71},
    {"empresa": "SEGURPRO",       "uf": "RR", "hora_extra": 33.33, "8h48_diurno": 208.36, "8h48_noturno": 261.28, "24h": 622.81},
    {"empresa": "SEGURPRO",       "uf": "PI", "hora_extra": 39.55, "8h48_diurno": 247.19, "8h48_noturno": 309.32, "24h": 758.90},
    {"empresa": "SEGURPRO",       "uf": "MT", "hora_extra": 38.35, "8h48_diurno": 251.37, "8h48_noturno": 287.24, "24h": 732.59},
    {"empresa": "SEGURPRO",       "uf": "MS", "hora_extra": 42.09, "8h48_diurno": 263.03, "8h48_noturno": 324.91, "24h": 789.04},
    {"empresa": "SEGURPRO",       "uf": "ES", "hora_extra": 45.51, "8h48_diurno": 284.43, "8h48_noturno": 353.95, "24h": 867.75},
    {"empresa": "SEGURPRO",       "uf": "AC", "hora_extra": 44.25, "8h48_diurno": 276.61, "8h48_noturno": 341.45, "24h": 827.55},
    {"empresa": "SEGURPRO",       "uf": "AL", "hora_extra": 37.54, "8h48_diurno": 234.61, "8h48_noturno": 274.87, "24h": 715.55},
    {"empresa": "SEGURPRO",       "uf": "AM", "hora_extra": 40.79, "8h48_diurno": 254.90, "8h48_noturno": 330.29, "24h": 806.02},
    {"empresa": "SEGURPRO",       "uf": "AP", "hora_extra": 48.79, "8h48_diurno": 304.21, "8h48_noturno": 379.33, "24h": 920.34},
    {"empresa": "SEGURPRO",       "uf": "BA", "hora_extra": 33.16, "8h48_diurno": 207.20, "8h48_noturno": 270.15, "24h": 645.77},
    {"empresa": "SEGURPRO",       "uf": "SE", "hora_extra": 35.00, "8h48_diurno": 218.73, "8h48_noturno": 276.02, "24h": 671.42},
    {"empresa": "SEGURPRO",       "uf": "TO", "hora_extra": 44.23, "8h48_diurno": 276.47, "8h48_noturno": 341.34, "24h": 832.54},
    {"empresa": "GLOBAL SEG",     "uf": "DF", "hora_extra": 66.11, "8h48_diurno": 413.20, "8h48_noturno": 461.65, "24h": 1234.89},
    {"empresa": "GOIAS F",        "uf": "GO", "hora_extra": 41.59, "8h48_diurno": 259.91, "8h48_noturno": 295.55, "24h": 868.92},
    {"empresa": "GOIAS F",        "uf": "MG", "hora_extra": 50.94, "8h48_diurno": 318.36, "8h48_noturno": 366.82, "24h": 1058.64},
    {"empresa": "GUARDED PLACE",  "uf": "SP", "hora_extra": 47.91, "8h48_diurno": 299.47, "8h48_noturno": 325.51, "24h": 950.14},
    {"empresa": "GUARDED PLACE",  "uf": "RS", "hora_extra": 42.04, "8h48_diurno": 262.73, "8h48_noturno": 324.23, "24h": 878.45},
    {"empresa": "INTERFORT",      "uf": "PE", "hora_extra": 38.50, "8h48_diurno": 240.66, "8h48_noturno": 280.03, "24h": 700.67},
    {"empresa": "INTERFORT",      "uf": "PB", "hora_extra": 33.04, "8h48_diurno": 206.47, "8h48_noturno": 243.43, "24h": 624.19},
    {"empresa": "INTERFORT",      "uf": "RN", "hora_extra": 40.77, "8h48_diurno": 254.83, "8h48_noturno": 300.90, "24h": 764.72},
    {"empresa": "LISERVE",        "uf": "PE", "hora_extra": 928.70, "8h48_diurno": 0.0,    "8h48_noturno": 6463.56, "24h": 88707.08},
    {"empresa": "RG SEG",         "uf": "MA", "hora_extra": 37.81, "8h48_diurno": 236.33, "8h48_noturno": 292.01, "24h": 687.71},
    {"empresa": "CEARA SEGUR",    "uf": "CE", "hora_extra": 39.87, "8h48_diurno": 249.18, "8h48_noturno": 293.41, "24h": 679.34},
    {"empresa": "FIEL VIG",       "uf": "PA", "hora_extra": 42.79, "8h48_diurno": 267.43, "8h48_noturno": 361.02, "24h": 852.20},
    {"empresa": "FIEL VIG",       "uf": "RO", "hora_extra": 42.80, "8h48_diurno": 267.47, "8h48_noturno": 331.20, "24h": 820.29},
    {"empresa": "SUNSET",         "uf": "RJ", "hora_extra": 47.46, "8h48_diurno": 296.58, "8h48_noturno": 355.39, "24h": 902.57},
]

# ╔══════════════════════════════════════════════════════════════════╗
# ║                   LOOKUP PRÉ-COMPILADO                          ║
# ╚══════════════════════════════════════════════════════════════════╝
VALORES_LOOKUP = {}
for _row in VALORES_IMPLANTACAO:
    _empresa = unidecode(_row['empresa']).strip().upper()
    _uf = unidecode(_row['uf']).strip().upper()
    for _tipo in ['hora_extra', '8h48_diurno', '8h48_noturno', '24h']:
        VALORES_LOOKUP[(_empresa, _uf, _tipo)] = _row[_tipo]

logger.info(f"Lookup de valores criado com {len(VALORES_LOOKUP)} entradas.")


# ╔══════════════════════════════════════════════════════════════════╗
# ║    MAPEAMENTO NOME COMPLETO → SIGLA (para planilhas variadas)   ║
# ╚══════════════════════════════════════════════════════════════════╝

# Mapeia fragmentos do nome completo da empresa para a sigla usada na tabela.
# Basta que o nome completo CONTENHA o fragmento para fazer match.
EMPRESA_NOME_PARA_SIGLA = {
    "AZUL":           "AZUL",
    "BELFORT":        "BELFORT",
    "CAMPSEG":        "CAMPSEG",
    "DFA SEG":        "DFA SEG",
    "DFA":            "DFA SEG",
    "EPAVI":          "EPAVI",
    "FORT KNOX":      "FORT KNOX",
    "SEGURPRO":       "SEGURPRO",
    "GLOBAL SEG":     "GLOBAL SEG",
    "GOIAS F":        "GOIAS F",
    "GUARDED PLACE":  "GUARDED PLACE",
    "INTERFORT":      "INTERFORT",
    "LISERVE":        "LISERVE",
    "RG SEG":         "RG SEG",
    "CEARA SEGUR":    "CEARA SEGUR",
    "FIEL VIG":       "FIEL VIG",
    "SUNSET":         "SUNSET",
}

# Siglas de UF válidas para extração do nome da empresa
UFS_VALIDAS = {
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS",
    "MT", "PA", "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC",
    "SE", "SP", "TO",
}


def normalizar_nome_empresa(nome_completo):
    """
    Converte nome completo da empresa (ex: 'INTERFORT SEGURANCA DE VALORES LTDA - PE')
    para a sigla usada na tabela de valores (ex: 'INTERFORT').
    Retorna (sigla_empresa, uf_extraida_ou_None).
    """
    if pd.isna(nome_completo):
        return "", None

    nome = unidecode(str(nome_completo)).strip().upper()
    uf_extraida = None

    # Tentar extrair UF do final: "... - PE" ou "... -PE" ou ".../ SP"
    match_uf = re.search(r'[-/]\s*([A-Z]{2})\s*$', nome)
    if match_uf:
        candidata = match_uf.group(1)
        if candidata in UFS_VALIDAS:
            uf_extraida = candidata

    # Tentar encontrar a sigla da empresa
    for fragmento, sigla in sorted(EMPRESA_NOME_PARA_SIGLA.items(), key=lambda x: -len(x[0])):
        if unidecode(fragmento).upper() in nome:
            return sigla, uf_extraida

    # Se não encontrou no mapeamento, retornar nome limpo
    # Remove sufixos comuns: LTDA, S/A, S.A., EIRELI, etc.
    nome_limpo = re.sub(r'\s*(LTDA|S/?A\.?|EIRELI|ME|EPP|SEGURANCA.*|VIGILANCIA.*|DE VALORES.*)\s*', ' ', nome)
    nome_limpo = re.sub(r'\s*[-/]\s*[A-Z]{2}\s*$', '', nome_limpo).strip()
    return nome_limpo, uf_extraida


def extrair_dias(indisponibilidade):
    """Extrai o número de dias de uma string de indisponibilidade."""
    if pd.isna(indisponibilidade):
        return 0
    match = re.search(r"(\d+)\s*dias", str(indisponibilidade), flags=re.IGNORECASE)
    return int(match.group(1)) if match else 0


def classificar_falhas(df):
    """
    Classifica as falhas em 'Crítica' ou 'Alerta'.
    Requer colunas: Evento, Status, Indisponibilidade.
    """
    if not all(c in df.columns for c in ["Evento", "Status", "Indisponibilidade"]):
        logger.warning("Colunas Evento/Status/Indisponibilidade não encontradas. Pulando classificação.")
        return df

    df["Dias Indisponível"] = df["Indisponibilidade"].apply(extrair_dias)
    df["Classificação"] = "Alerta - Atendimento em até 4 dias"

    criticas = (
        ((df["Evento"] == "CONEXAO") & (df["Status"] == "OFFLINE")) |
        ((df["Evento"].isin([
            "PORTA ACESSIBILIDADE", "SENSOR DE PORTA", "SENSOR SISMICO",
            "SENSOR QUEBRA-VIDRO", "SENSOR DE PRESENÇA"
        ]) & df["Status"].isin(["MANUTENÇÃO", "AUSÊNCIA"]) & (df["Dias Indisponível"] > 3))) |
        ((df["Evento"] == "FALHA DE AC") & (df["Status"] == "ALARME"))
    )
    df.loc[criticas, "Classificação"] = "Crítica - Atendimento em 1 dia útil"
    logger.info(f"Falhas classificadas: {criticas.sum()} críticas, {len(df) - criticas.sum()} alertas")
    return df


# ╔══════════════════════════════════════════════════════════════════╗
# ║                    FUNÇÕES AUXILIARES                            ║
# ╚══════════════════════════════════════════════════════════════════╝

def limpar_valor(valor_str):
    """Converte string monetária ('R$ 1.234,56') para float."""
    if pd.isna(valor_str):
        return None
    texto = str(valor_str).strip()
    texto = texto.replace('R$', '').replace(' ', '').replace('.', '').replace(',', '.')
    try:
        return float(texto)
    except (ValueError, Exception) as e:
        logger.warning(f"Erro ao converter '{valor_str}': {e}")
        return None


def formatar_valor_real(valor):
    """Formata float para 'R$ 1.234,56'."""
    try:
        if pd.isna(valor):
            return "R$ 0,00"
        return f"R$ {valor:,.2f}".replace('.', 'X').replace(',', '.').replace('X', ',')
    except Exception:
        return "R$ 0,00"


def calcular_minutos_noturnos(entrada, saida):
    """Calcula minutos no período noturno (22:00–04:59) entre dois datetimes."""
    if pd.isna(entrada) or pd.isna(saida):
        return 0

    total = 0
    current = entrada
    while current < saida:
        h = current.time()
        if h >= HORA_INICIO_NOTURNO_1 or (h >= HORA_INICIO_NOTURNO_2 and h <= HORA_FIM_NOTURNO_2):
            total += 1
        current += timedelta(minutes=1)
        if (current - entrada).total_seconds() / 60 > JORNADA_24H_MINUTOS * 10:
            break
    return total


def obter_tipo_jornada_8h48(entrada, saida):
    """Determina se jornada 8h48 é diurna ou noturna."""
    noturnos = calcular_minutos_noturnos(entrada, saida)
    return '8h48_noturno' if noturnos >= (JORNADA_8H48_MINUTOS / 2) else '8h48_diurno'


def normalizar_colunas_tempo(df):
    """
    Identifica e normaliza colunas de data/hora da planilha
    para colunas padronizadas 'ENTRADA' e 'SAIDA' (datetime).
    """
    colunas_map = {
        'entrada':      ['entrada', 'chegada', 'datachegada', 'dataentrada'],
        'hora_entrada': ['horaentrada', 'horachegada', 'hr_entrada', 'hr_chegada'],
        'saida':        ['saida', 'partida', 'datasaida', 'datapartida'],
        'hora_saida':   ['horasaida', 'horapartida', 'hr_saida', 'hr_partida'],
    }

    df_cols = {unidecode(c.lower().replace(" ", "")): c for c in df.columns}

    entrada_data_col = entrada_hora_col = saida_data_col = saida_hora_col = None

    for norm, orig in df_cols.items():
        if any(k in norm for k in colunas_map['entrada']) and not entrada_data_col:
            entrada_data_col = orig
        if any(k in norm for k in colunas_map['hora_entrada']) and not entrada_hora_col:
            entrada_hora_col = orig
        if any(k in norm for k in colunas_map['saida']) and not saida_data_col:
            saida_data_col = orig
        if any(k in norm for k in colunas_map['hora_saida']) and not saida_hora_col:
            saida_hora_col = orig

    try:
        if entrada_data_col and entrada_hora_col:
            df["ENTRADA"] = pd.to_datetime(
                df[entrada_data_col].astype(str) + " " + df[entrada_hora_col].astype(str), errors='coerce')
        elif entrada_data_col:
            df["ENTRADA"] = pd.to_datetime(df[entrada_data_col], errors='coerce')
        else:
            df["ENTRADA"] = pd.NaT

        if saida_data_col and saida_hora_col:
            df["SAIDA"] = pd.to_datetime(
                df[saida_data_col].astype(str) + " " + df[saida_hora_col].astype(str), errors='coerce')
        elif saida_data_col:
            df["SAIDA"] = pd.to_datetime(df[saida_data_col], errors='coerce')
        else:
            df["SAIDA"] = pd.NaT
    except Exception as e:
        logger.warning(f"Erro ao normalizar datas: {e}")
        df["ENTRADA"] = pd.NaT
        df["SAIDA"] = pd.NaT

    return df


# ╔══════════════════════════════════════════════════════════════════╗
# ║                CÁLCULO PRINCIPAL POR LINHA                      ║
# ╚══════════════════════════════════════════════════════════════════╝

def _resolver_uf_empresa(empresa, uf):
    """
    Se a UF está vazia/desconhecida mas a empresa só tem UMA UF na tabela, usa essa.
    Retorna a UF resolvida (ou a original se já era válida).
    """
    if uf and VALORES_LOOKUP.get((empresa, uf, 'hora_extra')) is not None:
        return uf  # UF válida, retornar como está

    # UF vazia ou não encontrada no lookup — buscar UFs disponíveis para essa empresa
    ufs_disponiveis = set()
    for (emp, u, _) in VALORES_LOOKUP:
        if emp == empresa:
            ufs_disponiveis.add(u)

    if len(ufs_disponiveis) == 1:
        uf_resolvida = ufs_disponiveis.pop()
        logger.info(f"UF auto-atribuída para {empresa}: {uf_resolvida}")
        return uf_resolvida
    elif len(ufs_disponiveis) > 1:
        logger.warning(f"Empresa '{empresa}' tem múltiplas UFs ({ufs_disponiveis}) e UF '{uf}' não identificada.")
    return uf


def calcular_valor_linha(row):
    """Calcula o valor total de implantação para uma linha do DataFrame."""
    empresa = unidecode(str(row.get('empresa', ''))).strip().upper()
    uf = unidecode(str(row.get('uf', ''))).strip().upper()
    entrada = row.get("ENTRADA")
    saida = row.get("SAIDA")
    duracao = row.get('DURACAO_MINUTOS')

    if not empresa or pd.isna(duracao):
        return 0

    # Resolver UF se estiver vazia ou inválida
    uf = _resolver_uf_empresa(empresa, uf)
    if not uf:
        logger.warning(f"UF não resolvida para empresa '{empresa}'")
        return 0

    # Buscar valores no lookup
    he  = VALORES_LOOKUP.get((empresa, uf, 'hora_extra'))
    d88 = VALORES_LOOKUP.get((empresa, uf, '8h48_diurno'))
    n88 = VALORES_LOOKUP.get((empresa, uf, '8h48_noturno'))
    v24 = VALORES_LOOKUP.get((empresa, uf, '24h'))

    if any(v is None for v in [he, d88, n88, v24]):
        logger.warning(f"Valores não encontrados para ({empresa}, {uf})")
        return 0

    total = 0
    restante = duracao

    # Jornadas completas de 24h
    while restante >= JORNADA_24H_MINUTOS - TOLERANCIA_MINUTOS:
        total += v24
        restante -= JORNADA_24H_MINUTOS

    # Jornada de 8h48
    if restante > TOLERANCIA_MINUTOS:
        if restante >= JORNADA_8H48_MINUTOS - TOLERANCIA_MINUTOS:
            tipo = obter_tipo_jornada_8h48(entrada, saida)
            total += n88 if tipo == '8h48_noturno' else d88
            restante -= JORNADA_8H48_MINUTOS

        # Hora extra residual
        if restante > TOLERANCIA_MINUTOS:
            total += (restante / 60) * he

    return total


# ╔══════════════════════════════════════════════════════════════════╗
# ║              FUNÇÃO PRINCIPAL — PONTO DE ENTRADA                ║
# ╚══════════════════════════════════════════════════════════════════╝

def normalizar_colunas_empresa_uf(df):
    """
    Normaliza as colunas de empresa e UF do DataFrame.
    Lida com os seguintes cenários:
      1. Colunas 'empresa' e 'uf' já existem (planilha simples)
      2. Coluna 'EMPRESA' com nome completo e sem 'uf' → extrai sigla + UF do nome
      3. Variações de nome como 'Empresa Vigilante', 'Vigilante', 'Estado' etc.
    """
    df.columns = df.columns.str.strip()
    col_map = {unidecode(c.lower().replace(" ", "")): c for c in df.columns}

    # Mapear variações de nome da coluna empresa
    emp_keys = ["empresa", "empresavigilante", "vigilante"]
    emp_col = None
    for k in emp_keys:
        if k in col_map:
            emp_col = col_map[k]
            break

    # Mapear variações de nome da coluna UF
    uf_keys = ["uf", "estado", "siglaestado"]
    uf_col = None
    for k in uf_keys:
        if k in col_map:
            uf_col = col_map[k]
            break

    if emp_col and emp_col != "empresa":
        df.rename(columns={emp_col: "empresa"}, inplace=True)
    if uf_col and uf_col != "uf":
        df.rename(columns={uf_col: "uf"}, inplace=True)

    # Se temos empresa mas NÃO temos UF, ou se os nomes são longos:
    # Tentar normalizar nomes completos → sigla + UF
    if "empresa" in df.columns:
        tem_uf = "uf" in df.columns and df["uf"].notna().any()

        # Detectar se os nomes são longos (nome completo vs sigla)
        amostra = df["empresa"].dropna().head(5).tolist()
        nomes_longos = any(len(str(n)) > 20 for n in amostra)

        if nomes_longos or not tem_uf:
            # Normalizar cada empresa
            resultados = df["empresa"].apply(lambda x: normalizar_nome_empresa(x))
            df["empresa"] = resultados.apply(lambda x: x[0])

            if not tem_uf:
                df["uf"] = resultados.apply(lambda x: x[1] if x[1] else "")
                logger.info("UF extraída do nome da empresa.")

    # Auto-resolver UF vazia para empresas com uma única UF na tabela
    if "empresa" in df.columns and "uf" in df.columns:
        mask_uf_vazia = df["uf"].isna() | (df["uf"].astype(str).str.strip() == "")
        if mask_uf_vazia.any():
            for idx in df[mask_uf_vazia].index:
                emp = unidecode(str(df.at[idx, "empresa"])).strip().upper()
                uf_resolvida = _resolver_uf_empresa(emp, "")
                if uf_resolvida:
                    df.at[idx, "uf"] = uf_resolvida
    
    return df


def calcular_valor_implantacao(df):
    """
    Recebe um DataFrame com colunas de empresa, UF, entrada e saída.
    Retorna o mesmo DataFrame com colunas adicionais:
      - ENTRADA / SAIDA (datetime normalizado)
      - DURACAO_MINUTOS (float)
      - VALOR_NUM (float — valor calculado)
      - VALOR_TOTAL (string — 'R$ 1.234,56')

    Colunas esperadas na planilha (aceita variações de nome):
      - empresa (ou "Empresa Vigilante", "Vigilante", "EMPRESA" — pode ser nome completo)
      - uf (ou "Estado", "Sigla Estado", "UF" — opcional se UF estiver no nome da empresa)
      - Data/hora de entrada e saída (diversas variações aceitas)
    """
    df = normalizar_colunas_empresa_uf(df)
    df = normalizar_colunas_tempo(df)
    df['DURACAO_MINUTOS'] = (df['SAIDA'] - df['ENTRADA']).dt.total_seconds() / 60
    df['DURACAO_MINUTOS'] = df['DURACAO_MINUTOS'].apply(lambda x: abs(x) if pd.notna(x) else x)
    df['VALOR_NUM'] = df.apply(calcular_valor_linha, axis=1)
    df['VALOR_TOTAL'] = df['VALOR_NUM'].apply(formatar_valor_real)
    return df


def get_empresas_disponiveis():
    """Retorna lista de empresas/UFs disponíveis na tabela (útil para o frontend)."""
    return [
        {
            "empresa": r["empresa"],
            "uf": r["uf"],
            "hora_extra": f"{r['hora_extra']:.2f}",
            "diurno_8h48": f"{r['8h48_diurno']:.2f}",
            "noturno_8h48": f"{r['8h48_noturno']:.2f}",
            "valor_24h": f"{r['24h']:.2f}",
        }
        for r in VALORES_IMPLANTACAO
    ]
