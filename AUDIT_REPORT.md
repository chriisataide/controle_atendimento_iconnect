# 🔍 RELATÓRIO DE AUDITORIA FORENSE — iConnect

**Projeto:** controle_atendimento_iconnect  
**Stack:** Django 5.2.6 · Python 3.11 · PostgreSQL 15 · Redis 7 · Celery 5.3.4  
**Data:** Junho 2025  
**Auditor:** Análise automatizada de código  

---

## SUMÁRIO EXECUTIVO

| Severidade | Quantidade |
|------------|-----------|
| 🔴 CRITICAL | 8 |
| 🟠 HIGH | 14 |
| 🟡 MEDIUM | 22 |
| **Total** | **44** |

---

## 🔴 VULNERABILIDADES CRÍTICAS

### C-01 · Recursão Infinita em `_safe_group_send()` — CRASH EM PRODUÇÃO

**Arquivo:** `dashboard/signals.py` linha 26  
**Tipo:** Bug / DoS  

```python
def _safe_group_send(group, message):
    if channel_layer is not None:
        try:
            _safe_group_send(group, message)  # ← CHAMA A SI MESMA!
        except Exception:
            logger.debug("Channel layer send failed")
```

**Impacto:** Toda vez que um ticket é criado/atualizado, essa função é chamada e entra em recursão infinita até `RecursionError` — derrubando o request e potencialmente o worker.

**Correção:**
```python
def _safe_group_send(group, message):
    if channel_layer is not None:
        try:
            async_to_sync(channel_layer.group_send)(group, message)
        except Exception:
            logger.debug("Channel layer send failed (no backend?)")
```

---

### C-02 · Webhook WhatsApp sem Verificação de Assinatura

**Arquivo:** `dashboard/integrations.py` linhas 18-19  
**Arquivo:** `dashboard/whatsapp_views.py` linhas 293-330  
**Tipo:** Segurança / Spoofing  

```python
@csrf_exempt  # ← sem CSRF
def whatsapp_webhook(request):
    # Não verifica X-Hub-Signature-256 do Meta
```

**Impacto:** Qualquer atacante pode enviar payloads forjados ao endpoint `/whatsapp/webhook/`, criando tickets falsos, injetando dados e manipulando o sistema.

**Correção:** Validar o header `X-Hub-Signature-256` com HMAC-SHA256 usando o `app_secret` da Meta.

---

### C-03 · Webhook Slack sem Verificação de Assinatura

**Arquivo:** `dashboard/integrations.py` linha 155  
**Tipo:** Segurança / Spoofing  

```python
@csrf_exempt
def slack_webhook(request):
    # Não verifica X-Slack-Signature
```

**Impacto:** Idêntico ao C-02 — comandos Slack podem ser forjados para criar/manipular tickets.

**Correção:** Implementar verificação de `X-Slack-Signature` + `X-Slack-Request-Timestamp` conforme documentação Slack.

---

### C-04 · `settings_prod.py` com Definições Duplicadas/Conflitantes

**Arquivo:** `controle_atendimento/settings_prod.py`  
**Tipo:** Configuração / Comportamento Indefinido  

O arquivo importa `from .settings_base import *` **duas vezes** (linhas ~9 e ~72), e redefine `DATABASES`, `CACHES`, `STATICFILES_STORAGE` e settings de segurança com abordagens conflitantes (`decouple.config()` vs `os.environ.get()`). As definições do segundo bloco sobrescrevem silenciosamente o primeiro.

**Impacto:** Comportamento imprevisível em produção — settings de segurança podem não estar realmente ativos.

**Correção:** Remover a duplicação. Manter apenas um bloco coerente usando `decouple.config()`.

---

### C-05 · API Key de IA Armazenada em Texto Puro no Banco

**Arquivo:** `dashboard/models.py` linhas 1380-1394 (modelo `AIConfiguration`)  
**Tipo:** Segurança / Vazamento de Credenciais  

```python
class AIConfiguration(models.Model):
    api_key = models.CharField(max_length=255)  # ← texto puro!
```

**Impacto:** Qualquer acesso ao banco de dados (SQL injection, backup vazado, admin Django) expõe chaves de API da OpenAI/Anthropic/Google.

**Correção:** Usar `django-encrypted-model-fields` ou similar e nunca expor o valor no Admin/API.

---

### C-06 · Senha de Email Armazenada em Texto Puro no Banco

**Arquivo:** `dashboard/models.py` linhas 1490-1510 (modelo `EmailAccount`)  
**Tipo:** Segurança / Vazamento de Credenciais  

```python
class EmailAccount(models.Model):
    password = models.CharField(max_length=255)  # ← texto puro!
```

**Impacto:** Idêntico ao C-05 — credenciais IMAP/POP3 expostas.

---

### C-07 · Token de Webhook Hardcoded

**Arquivo:** `controle_atendimento/settings.py` linhas 29-31  
**Tipo:** Segurança / Credencial Exposta  

```python
WHATSAPP_WEBHOOK_VERIFY_TOKEN = config(
    'WHATSAPP_WEBHOOK_VERIFY_TOKEN',
    default='controle_atendimento_webhook_2024'  # ← hardcoded no código-fonte
)
```

**Impacto:** O token padrão está no código-fonte (e potencialmente no Git). Se `.env` não definir a variável, o sistema usará o valor previsível.

---

### C-08 · SECRET_KEY Insegura por Padrão

**Arquivo:** `controle_atendimento/settings_base.py` linha 15  
**Tipo:** Segurança / Criptografia  

```python
SECRET_KEY = config('SECRET_KEY', default='django-insecure-MUDE-ESTA-CHAVE-EM-PRODUCAO')
```

**Impacto:** Se `.env` não existir, todas as sessões, cookies e tokens CSRF usarão uma chave previsível.

---

## 🟠 VULNERABILIDADES HIGH

### H-01 · IDOR em APIs REST — Sem Verificação de Propriedade

**Arquivo:** `dashboard/api_views.py`  
**Tipo:** Segurança / Broken Access Control  

```python
class CannedResponseDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = CannedResponse.objects.all()  # ← qualquer autenticado pode editar/deletar

class WebhookDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    queryset = WebhookEndpoint.objects.all()  # ← idem
```

Também em `TicketDetailAPIView` — qualquer usuário autenticado pode acessar/modificar qualquer ticket, sem verificação de `criado_por` ou role.

**Correção:** Filtrar querysets por `criado_por=request.user` ou implementar `get_queryset()` com check de permissão.

---

### H-02 · Mass Assignment em `PontoDeVendaForm`

**Arquivo:** `dashboard/views.py` linha 30  
**Tipo:** Segurança / Mass Assignment  

```python
class PontoDeVendaForm(forms.ModelForm):
    class Meta:
        model = PontoDeVenda
        fields = '__all__'  # ← expõe TODOS os campos
```

**Correção:** Listar campos explicitamente.

---

### H-03 · `ProfileView.post()` Sem Validação de Formulário

**Arquivo:** `dashboard/views.py` linhas ~1500-1540  
**Tipo:** Segurança / Mass Assignment  

```python
def post(self, request):
    user = request.user
    user.first_name = request.POST.get('first_name', user.first_name)
    user.last_name = request.POST.get('last_name', user.last_name)
    user.email = request.POST.get('email', user.email)
    user.save()
```

**Impacto:** Aceita dados POST diretamente sem form validation. Se algum campo adicional do User model for incluído inadvertidamente, pode ser explorado.

**Correção:** Usar um `ModelForm` com campos explícitos.

---

### H-04 · Upload de Arquivo Sem Validação de Tipo/Conteúdo

**Arquivo:** `dashboard/views.py` linhas ~920-935 (`TicketCreateView`)  
**Tipo:** Segurança / Upload de Arquivo Malicioso  

A view só valida tamanho (10MB), mas não chama `security.validate_file_upload()` que existe no projeto e faz validação de extensão + conteúdo.

**Correção:** Chamar `validate_file_upload()` de `security.py` antes de salvar o arquivo.

---

### H-05 · `@csrf_exempt` em Endpoints Autenticados

**Arquivo:** `dashboard/chat_views.py` linha ~308 (`api_send_message`)  
**Arquivo:** `dashboard/sla_views.py` linhas ~400, 430, 460  
**Arquivo:** `dashboard/executive_views.py` linha ~335  
**Tipo:** Segurança / CSRF  

```python
@login_required
@require_http_methods(["POST"])
@csrf_exempt  # ← por que?
def api_send_message(request):
```

Múltiplas views que exigem `@login_required` também usam `@csrf_exempt`, anulando a proteção CSRF do Django.

**Correção:** Remover `@csrf_exempt` e usar CSRF token no frontend, ou usar DRF com JWT para endpoints API.

---

### H-06 · Bulk Actions sem Verificação de Permissão

**Arquivo:** `dashboard/api_views.py` linhas ~400-420  
**Tipo:** Segurança / Privilege Escalation  

```python
tickets = Ticket.objects.filter(id__in=ticket_ids)
if action == "close":
    tickets.update(status="fechado", fechado_em=timezone.now())
elif action == "assign":
    tickets.update(agente_id=value)
```

Qualquer usuário autenticado pode fechar tickets em massa ou reatribuí-los. Não há verificação de role.

---

### H-07 · Dashboard SLA Público Sem Autenticação

**Arquivo:** `dashboard/sla_views.py` linhas 30-50  
**Tipo:** Segurança / Information Disclosure  

```python
def sla_dashboard_public(request):
    """Dashboard SLA público temporário para demonstração"""
    dashboard_data = sla_monitor.get_sla_dashboard_data()
```

Expõe dados de SLA, métricas e tickets sem nenhuma autenticação.

---

### H-08 · `sla_test()` Endpoint de Debug em Produção

**Arquivo:** `dashboard/sla_views.py` linhas 23-29  
**Tipo:** Segurança / Information Disclosure  

```python
def sla_test(request):
    """Teste SLA sem autenticação"""
    return JsonResponse({
        'sla_policies_count': SLAPolicy.objects.count(),
        'sla_alerts_count': SLAAlert.objects.count()
    })
```

---

### H-09 · Informação Sensível Exposta em Respostas de Erro

**Arquivo:** `dashboard/api_views.py` (múltiplas views)  
**Arquivo:** `dashboard/whatsapp_views.py`  
**Tipo:** Segurança / Information Disclosure  

```python
except Exception as e:
    return Response({"error": str(e)}, status=500)
```

Stack traces e mensagens de erro internas são retornadas diretamente na resposta JSON.

**Correção:** Retornar mensagens genéricas e logar o erro internamente.

---

### H-10 · `access_token` do WhatsApp em Texto Puro

**Arquivo:** `dashboard/models_whatsapp.py` linha 13  
**Tipo:** Segurança / Vazamento de Credenciais  

```python
access_token = models.TextField(verbose_name='Access Token')  # ← texto puro
```

---

### H-11 · Shared Dashboard Público com Token Previsível

**Arquivo:** `dashboard/api_views.py` linhas ~770-810  
**Tipo:** Segurança / Information Disclosure  

```python
@api_view(["GET"])
@permission_classes([])  # ← SEM autenticação!
def shared_dashboard_view(request, token):
    dash.view_count += 1
    dash.save(update_fields=["view_count"])
    # Retorna dados de tickets em tempo real
```

Dados de negócio são expostos publicamente. O `view_count` increment é vulnerável a race conditions.

---

### H-12 · Race Condition na Geração de Número de Ticket

**Arquivo:** `dashboard/models.py` (método `Ticket.save()`)  
**Tipo:** Integridade de Dados  

A geração de número usa `Max('id')` sem `select_for_update()`, criando possibilidade de números duplicados em concorrência.

---

### H-13 · `InteracaoTicket` Criada com `usuario=None`

**Arquivo:** `dashboard/integrations.py` linha ~100  
**Arquivo:** `dashboard/workflows.py` (múltiplas linhas)  
**Arquivo:** `dashboard/automation.py` linha ~285  
**Tipo:** Bug / Integridade  

```python
InteracaoTicket.objects.create(usuario=None, ...)
```

Se o campo `usuario` não aceita `NULL`, isso causa `IntegrityError`. Se aceita, perde rastreabilidade.

---

### H-14 · `TicketChatConsumer.connect()` com `except:` Genérico

**Arquivo:** `dashboard/consumers.py` linha ~455  
**Tipo:** Segurança / Supressão de Erros  

```python
try:
    ticket = await database_sync_to_async(Ticket.objects.get)(id=self.ticket_id)
    ...
except:  # ← BARE EXCEPT
    await self.close()
    return
```

Qualquer exceção (inclusive `KeyboardInterrupt`, `SystemExit`) é silenciosamente engolida.

---

## 🟡 PROBLEMAS MEDIUM

### M-01 · God File: `views.py` com 2925 Linhas

**Arquivo:** `dashboard/views.py`  
**Tipo:** Qualidade / Manutenibilidade  

Um único arquivo com 2925 linhas contém dashboard, tickets, clientes, automação, relatórios, PWA, chat, busca, notificações e estoque. Viola completamente o SRP (Single Responsibility Principle).

**Correção:** Separar em módulos: `views/dashboard.py`, `views/tickets.py`, `views/clients.py`, etc.

---

### M-02 · God Method: `DashboardView.get_context_data()` com ~250 Linhas

**Arquivo:** `dashboard/views.py` linhas ~370-600  
**Tipo:** Complexidade / Performance  

Um único método faz ~20 queries ao banco de dados, calcula métricas, monta gráficos e prepara contexto. Complexidade ciclomática extremamente alta.

**Correção:** Extrair para `DashboardService` com métodos separados para cada bloco de métricas.

---

### M-03 · N+1 Queries no Dashboard Financeiro

**Arquivo:** `dashboard/financeiro_views.py` linhas 1-180  
**Tipo:** Performance  

O dashboard faz múltiplas queries separadas com `Sum`, `Count`, `Avg` quando poderia consolidar com `aggregate()` e annotations.

---

### M-04 · SLA Reports com Loop de Queries

**Arquivo:** `dashboard/sla_views.py` linhas ~170-260  
**Tipo:** Performance / N+1  

```python
for sla_history in sla_histories:
    metrics = sla_calculator.calculate_sla_metrics(sla_history)
```

Itera sobre `sla_histories` e para cada um calcula métricas individualmente em vez de usar queries em batch.

---

### M-05 · `executive_kpis_api` com Loop Python no Banco

**Arquivo:** `dashboard/executive_views.py` linhas ~118-130  
**Tipo:** Performance  

```python
total_time = sum([
    (ticket.resolvido_em - ticket.criado_em).total_seconds() / 3600
    for ticket in resolved_tickets
])
```

Carrega TODOS os tickets resolvidos na memória em vez de usar `Avg(F('resolvido_em') - F('criado_em'))`.

---

### M-06 · Duplicação de Lógica entre 3 Engines de Automação

**Arquivos:**
- `dashboard/automation.py` (`AutoAssignmentEngine`, `WorkflowAutomation`)
- `dashboard/automation_service.py` (`AutomationEngine`)
- `dashboard/workflows.py` (`WorkflowEngine`)

**Tipo:** Arquitetura / DRY Violation  

Três módulos separados implementam lógica similar de auto-assignment, escalação e automação de workflows com abordagens incompatíveis. `automation_service.py` importa `from .models import Agent, Customer` que não existem (os modelos se chamam `PerfilAgente` e `Cliente`).

**Correção:** Unificar em um único `AutomationService`.

---

### M-07 · Imports de Modelos Inexistentes

**Arquivo:** `dashboard/automation_service.py` linha 18  
**Arquivo:** `dashboard/chatbot_service.py` linha 18  
**Tipo:** Bug / Import Error  

```python
from .models import Ticket, Agent, Customer, Notification
```

Os modelos `Agent` e `Customer` não existem — são `PerfilAgente` e `Cliente`. Isso causa `ImportError` ao usar esses módulos.

---

### M-08 · Duplicação de `ChatbotService`

**Arquivos:**
- `dashboard/automation.py` — `ChatbotService` (simples, com knowledge_base dict)
- `dashboard/chatbot_service.py` — `ChatbotService` (avançado, com intent classification)

**Tipo:** Arquitetura / DRY  

Dois `ChatbotService` com mesmo nome mas implementações diferentes. Instâncias globais em ambos os arquivos.

---

### M-09 · Múltiplos `bare except:` no Codebase

**Arquivos:** `dashboard/integrations.py`, `dashboard/monitoring.py`, `dashboard/consumers.py`, `dashboard/views.py`  
**Tipo:** Qualidade / Debugging  

```python
except:
    # swallowed silently
```

Encontrados em pelo menos 8 locais. Suprimem erros legítimos e dificultam debugging.

**Correção:** Usar `except Exception as e:` e logar o erro.

---

### M-10 · Mismatch de Prioridades entre Form e Model

**Arquivo:** `dashboard/forms.py` (`QuickTicketForm`)  
**Tipo:** Bug / Data Integrity  

```python
PRIORITY_CHOICES = [('BAIXA', 'Baixa'), ('MEDIA', 'Média'), ...]
```

O form usa uppercase (`'BAIXA'`, `'MEDIA'`), mas o model `PrioridadeTicket` usa lowercase (`'baixa'`, `'media'`). Tickets criados pelo QuickTicketForm podem ter prioridade inválida.

---

### M-11 · Código Morto / Stub — `download_report()`

**Arquivo:** `dashboard/views.py` linha ~2070  
**Tipo:** Qualidade / Dead Code  

```python
def download_report(request, report_type):
    # Returns placeholder PDF
```

Retorna um PDF placeholder em vez de implementação real.

---

### M-12 · Modelo `KnowledgeBase` Marcado como DEPRECADO Mas Ainda Existe

**Arquivo:** `dashboard/models.py`  
**Tipo:** Qualidade / Dead Code  

Ainda referenciado em imports e admin, sem migração de remoção.

---

### M-13 · Instâncias Globais de Serviços (Singletons)

**Arquivos:** `dashboard/automation.py`, `dashboard/automation_service.py`, `dashboard/chatbot_service.py`, `dashboard/workflows.py`, `dashboard/notifications.py`, `dashboard/sla.py`, `dashboard/ml_engine.py`  
**Tipo:** Arquitetura / Testing  

```python
# No final de cada arquivo:
automation_engine = AutomationEngine()
chatbot_service = ChatbotService()
sla_manager = SLAManager()
ml_predictor = TicketPredictor()
```

Padrão de singleton via módulo em 7+ arquivos. Dificulta testes unitários, não permite configuração dinâmica e cria acoplamento forte.

---

### M-14 · `whatsapp_conversation_detail` — Shadowing de `messages`

**Arquivo:** `dashboard/whatsapp_views.py` linhas ~115-150  
**Tipo:** Bug  

```python
messages = conversation.mensagens.order_by('timestamp')
# ...
messages.success(request, 'Agente atribuído com sucesso!')  # ← QUERYSET, não django.contrib.messages!
```

A variável `messages` é sobrescrita pelo queryset, então `messages.success()` falhará com `AttributeError`.

---

### M-15 · `channel_layer` Carregado em Tempo de Import

**Arquivo:** `dashboard/signals.py` linha 22  
**Tipo:** Arquitetura / Reliability  

```python
channel_layer = get_channel_layer()  # ← executado no import
```

Se Redis estiver indisponível no momento do import, `channel_layer` será `None` permanentemente, mesmo que Redis volte depois.

---

### M-16 · Business Logic em Views

**Arquivo:** `dashboard/views.py` (múltiplas views)  
**Tipo:** Arquitetura / SRP  

Views como `DashboardView`, `automation_dashboard`, `reports_dashboard`, `generate_report` contêm cálculos de negócio, queries complexas e lógica de automação diretamente no código da view.

**Correção:** Mover para service layer (`dashboard/services/`).

---

### M-17 · Controle de Acesso Inconsistente

**Tipo:** Segurança / Arquitetura  

O sistema RBAC (`rbac.py`) define roles e o decorator `@role_required`, mas quase nenhuma view o utiliza. Em vez disso, views checam `is_staff` ou `is_superuser` diretamente, ignorando o modelo de roles.

---

### M-18 · `validate_file_upload()` — Validação Bypassável

**Arquivo:** `dashboard/security.py` linhas ~235-255  
**Tipo:** Segurança  

```python
file_extension = uploaded_file.name.lower().split('.')[-1]
```

Valida apenas por extensão do nome do arquivo, e não pelo MIME type real. Um arquivo `malware.exe.jpg` passaria pela validação.

**Correção:** Usar `python-magic` para detectar MIME type real.

---

### M-19 · CSP com `'unsafe-inline'` para Scripts

**Arquivo:** `dashboard/security.py` linhas ~210-225  
**Arquivo:** `nginx.conf`  
**Tipo:** Segurança / XSS  

```python
"script-src 'self' 'unsafe-inline' ..."
```

`'unsafe-inline'` anula grande parte da proteção CSP contra XSS.

---

### M-20 · `WhatsAppAnalyticsService` Iterando Analytics em Python

**Arquivo:** `dashboard/whatsapp_service.py` linhas ~430-460  
**Tipo:** Performance  

```python
return {
    'total_mensagens_enviadas': sum(a.mensagens_enviadas for a in analytics),
    ...
}
```

Carrega todos os registros em memória e soma em Python em vez de usar `aggregate(Sum(...))`.

---

### M-21 · Múltiplos `post_save` Signals no Mesmo Modelo

**Arquivo:** `dashboard/signals.py` (linhas 36, 308, 360, 530)  
**Tipo:** Performance / Complexidade  

4 signals `post_save` registrados para `Ticket`, cada um fazendo queries e operações separadas. Ordem de execução não é garantida.

**Correção:** Consolidar em um único handler com clara separação de responsabilidades.

---

### M-22 · Docker — Código Mont	ado como Volume em Produção

**Arquivo:** `docker-compose.yml`  
**Tipo:** Segurança / DevOps  

```yaml
volumes:
  - .:/app
```

O código-fonte local é montado diretamente no container. Em produção, deveria usar apenas a imagem Docker construída.

---

## RESUMO DE AÇÕES PRIORITÁRIAS

### Imediato (próximas 24h)
1. **Corrigir C-01** — `_safe_group_send()` recursão infinita
2. **Corrigir C-02/C-03** — Adicionar verificação de assinatura nos webhooks
3. **Corrigir C-04** — Remover duplicação em `settings_prod.py`
4. **Remover H-07/H-08** — Endpoints de debug/demo sem autenticação

### Curto Prazo (1 semana)
5. **Corrigir H-01/H-06** — Adicionar checks de permissão em todas as APIs
6. **Corrigir C-05/C-06/H-10** — Encriptar credenciais no banco
7. **Corrigir H-05** — Remover `@csrf_exempt` desnecessários
8. **Corrigir M-07** — Imports de modelos inexistentes
9. **Corrigir M-14** — Shadowing de `messages` no WhatsApp views

### Médio Prazo (1 mês)
10. **Refatorar M-01/M-02** — Dividir `views.py` em módulos
11. **Unificar M-06** — Consolidar engines de automação
12. **Implementar M-17** — Usar RBAC consistentemente
13. **Corrigir M-03/M-04/M-05** — Otimizar queries N+1
14. **Corrigir M-18** — Validação de upload por MIME type

---

*Fim do relatório de auditoria.*
