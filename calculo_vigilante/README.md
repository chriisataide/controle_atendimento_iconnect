# Cálculo de Implantação de Vigilante — App Django

App Django isolado e reutilizável para calcular valores de implantação de postos de vigilância.

## Estrutura

```
calculo_vigilante/
├── __init__.py
├── apps.py
├── engine.py          ← Motor de cálculo (100% independente do Django)
├── views.py           ← Views (página + processamento AJAX)
├── urls.py            ← URLs do app
├── migrations/
│   └── __init__.py
├── exemplos/          ← Planilhas de exemplo para teste
│   ├── Acumulado_Pronta Resposta_Implantação.xlsx
│   ├── Acumulado_Pronta Resposta_Implantação (1).xlsx
│   └── Empresas de Vigilante - Implantacao.xlsx
└── templates/
    └── calculo_vigilante/
        └── calculo.html   ← Template da página (herda base.html)
```

## Instalação no seu projeto (3 passos)

### 1. Copie a pasta

Copie a pasta `calculo_vigilante/` para a raiz do seu projeto Django (ao lado do `manage.py`).

### 2. Registre no settings.py

```python
INSTALLED_APPS = [
    # ... seus apps ...
    'calculo_vigilante',
]
```

**Opcional** — configurar diretórios de upload/saída:

```python
# Se não definir, usa BASE_DIR/uploads_calculo e BASE_DIR/processados_calculo
CALCULO_VIGILANTE_UPLOAD_DIR = os.path.join(BASE_DIR, 'uploads_calculo')
CALCULO_VIGILANTE_OUTPUT_DIR = os.path.join(BASE_DIR, 'processados_calculo')
```

### 3. Adicione a URL no urls.py do projeto

```python
from django.urls import path, include

urlpatterns = [
    # ... suas URLs ...
    path('calculo-vigilante/', include('calculo_vigilante.urls')),
]
```

**Pronto!** Acesse `http://seusite/calculo-vigilante/` para usar.

## Adicionar no sidebar

No seu `base.html`, adicione um item de menu apontando para:

```html
<a href="{% url 'calculo_vigilante:pagina' %}">
    <i class="material-icons-round">attach_money</i>
    <span>Cálculo de Implantação</span>
</a>
```

## Dependências Python

Adicione ao seu `requirements.txt` (se ainda não tiver):

```
pandas
openpyxl
unidecode
```

## Uso programático (sem interface web)

O `engine.py` funciona 100% standalone, sem precisar do Django:

```python
from calculo_vigilante.engine import calcular_valor_implantacao
import pandas as pd

df = pd.read_excel("minha_planilha.xlsx")
df = calcular_valor_implantacao(df)
df.to_excel("resultado.xlsx", index=False)

print(df[['empresa', 'uf', 'DURACAO_MINUTOS', 'VALOR_TOTAL']])
```

## Formato esperado da planilha

| Coluna | Variações aceitas |
|--------|-------------------|
| **empresa** | "Empresa", "EMPRESA", "Empresa Vigilante", "Vigilante" (aceita nome completo como "INTERFORT SEGURANCA DE VALORES LTDA - PE") |
| **uf** | "UF", "Estado", "Sigla Estado" (opcional — se ausente, tenta extrair do nome da empresa) |
| **Entrada** | "Entrada", "Chegada", "Data Chegada", "Data Entrada" + "Hora Entrada" |
| **Saída** | "Saída", "Partida", "Data Saída", "Data Partida" + "Hora Saída" |

## Empresas/UFs cadastradas (38 combinações)

AZUL (RJ, SP), BELFORT (SP, RJ), CAMPSEG (MG, SP), DFA SEG (BA), EPAVI (SP, PR, SC, RS),
FORT KNOX (SP), SEGURPRO (RR, PI, MT, MS, ES, AC, AL, AM, AP, BA, SE, TO),
GLOBAL SEG (DF), GOIAS F (GO, MG), GUARDED PLACE (SP, RS), INTERFORT (PE, PB, RN),
LISERVE (PE), RG SEG (MA), CEARA SEGUR (CE), FIEL VIG (PA, RO), SUNSET (RJ)

## Lógica de cálculo

1. **Normaliza** colunas de data/hora → `ENTRADA` e `SAIDA`
2. **Calcula** duração em minutos
3. Para cada linha:
   - Consome jornadas completas de **24h** (valor fixo por empresa/UF)
   - Restante ≥ 8h48: aplica valor **diurno** ou **noturno** (baseado nos minutos noturnos 22h–05h)
   - Restante residual: **hora extra** proporcional
4. Gera `VALOR_NUM` (float) e `VALOR_TOTAL` (formatado R$)
