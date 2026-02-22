# 🔴 RELATÓRIO DE AUDITORIA DE SEGURANÇA OFENSIVA (RED TEAM)

**Projeto:** Controle de Atendimento iConnect  
**Data:** 22 de Fevereiro de 2026  
**Classificação:** CONFIDENCIAL  
**Auditor:** Red Team Security Specialist  

---

## RESUMO EXECUTIVO

| Severidade | Quantidade |
|------------|------------|
| 🔴 CRÍTICA | 7 |
| 🟠 ALTA    | 12 |
| 🟡 MÉDIA   | 11 |
| 🔵 BAIXA   | 5 |
| **TOTAL**  | **35** |

---

## 1. AUTENTICAÇÃO & SEGURANÇA DE SESSÃO

### VULN-001: SECRET_KEY insegura com fallback hardcoded
- **Severidade:** 🔴 CRÍTICA
- **Arquivo:** `controle_atendimento/settings_base.py`, Linha 15
- **Código vulnerável:**
```python
SECRET_KEY = config('SECRET_KEY', default='django-insecure-MUDE-ESTA-CHAVE-EM-PRODUCAO')
```
- **Cenário de ataque:** Se a variável de ambiente `SECRET_KEY` não for definida (deploy incorreto, container sem `.env`), o sistema usa uma chave previsível. Um atacante pode forjar cookies de sessão, tokens CSRF e tokens JWT, obtendo acesso como qualquer usuário, incluindo superusuário.
- **Correção:**
```python
SECRET_KEY = config('SECRET_KEY')  # Sem default — falha se não configurada
```

---

### VULN-002: SECURE_SSL_REDIRECT desabilitado em produção por padrão
- **Severidade:** 🟠 ALTA
- **Arquivo:** `controle_atendimento/settings_prod.py`, Linha 40
- **Código vulnerável:**
```python
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=False, cast=bool)  # Disabled for local dev
```
- **Cenário de ataque:** Tráfego HTTP não criptografado permite interceptação MiTM de credenciais, tokens de sessão e dados financeiros de clientes (CNPJ, CPF). O comentário "Disabled for local dev" indica confusão — isto é o arquivo de **produção**.
- **Correção:**
```python
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
```

---

### VULN-003: Arquivo settings_prod.py duplicado e contraditório
- **Severidade:** 🟠 ALTA
- **Arquivo:** `controle_atendimento/settings_prod.py`, Linhas 65-155
- **Código vulnerável:** O arquivo contém **duas definições** com `from .settings_base import *` na linha 8 e novamente na linha 65. A segunda sobrescreve a primeira, e a segunda seção define `SECURE_SSL_REDIRECT = True` (linha 96), mas a primeira define `default=False` (linha 40). Como Python executa sequencialmente, a segunda redefinição vence, mas isso gera confusão e bugs de configuração.
- **Cenário de ataque:** Manutenção futura pode acidentalmente remover a segunda seção, revertendo para defaults inseguros.
- **Correção:** Remover a definição duplicada e consolidar em um único bloco de configuração.

---

### VULN-004: Sessão sem cookies seguros no settings_base.py
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `controle_atendimento/settings_base.py`, Linhas 175-178
- **Código vulnerável:**
```python
SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
SESSION_CACHE_ALIAS = 'default'
SESSION_COOKIE_AGE = 3600
SESSION_SAVE_EVERY_REQUEST = True
```
- **Cenário de ataque:** `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_SECURE` e `CSRF_COOKIE_HTTPONLY` **não estão definidos** no settings_base. Embora settings_prod os defina, qualquer ambiente que use settings_base diretamente (ou dev em Docker) fica sem proteção de cookies. Em dev, cookies podem ser roubados via scripts XSS.
- **Correção:** Adicionar ao `settings_base.py`:
```python
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
```

---

## 2. SEGURANÇA DE API

### VULN-005: Health check expõe informações do sistema sem autenticação
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/api_views.py`, Linhas 275-295
- **Código vulnerável:**
```python
@api_view(["GET"])
@permission_classes([])
def health_check(request):
    ...
    checks["tickets_total"] = Ticket.objects.count()
```
- **Cenário de ataque:** O endpoint `/api/health/` é público (sem autenticação, `permission_classes=[]`). Expõe: status do banco de dados, status do cache Redis, e **contagem total de tickets** — informação de negócio. Atacante pode usar isto para reconhecimento e monitorar a atividade da plataforma.
- **Correção:**
```python
@api_view(["GET"])
@permission_classes([])
def health_check(request):
    checks = {"status": "healthy", "timestamp": timezone.now().isoformat()}
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"
        checks["status"] = "unhealthy"
    # Remover: checks["tickets_total"] — dados de negócio
    http_status = 200 if checks["status"] == "healthy" else 503
    return Response(checks, status=http_status)
```

---

### VULN-006: Dashboard compartilhado público sem autenticação vaza dados
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/api_views.py`, Linhas 780-812
- **Código vulnerável:**
```python
@api_view(["GET"])
@permission_classes([])
def shared_dashboard_view(request, token):
    ...
    return Response({
        "nome": dash.nome,
        "data": {
            "total_tickets": tickets.count(),
            "by_status": ...,
            "by_priority": ...,
        },
    })
```
- **Cenário de ataque:** Qualquer pessoa com o token (que é UUIDv4, mas pode ser brute-forced ou leakado em logs/referrer headers) acessa KPIs e métricas de negócio em tempo real **sem autenticação**. Exposição de dados financeiros/governamentais.
- **Correção:** Adicionar rate limit agressivo, IP whitelist, ou exigir autenticação básica no endpoint.

---

### VULN-007: Bulk action sem verificação de permissão granular
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/api_views.py`, Linhas 400-421
- **Código vulnerável:**
```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_action_tickets(request):
    ticket_ids = request.data.get("ticket_ids", [])
    action = request.data.get("action")
    value = request.data.get("value")
    ...
    tickets = Ticket.objects.filter(id__in=ticket_ids)
    if action == "close":
        tickets.update(status="fechado", fechado_em=timezone.now())
    elif action == "assign":
        tickets.update(agente_id=value)
```
- **Cenário de ataque:** Qualquer usuário autenticado (incluindo clientes) pode fechar, reatribuir ou mudar prioridade de **qualquer ticket do sistema** em massa. Não há verificação se o usuário é staff, agente ou tem permissão sobre os tickets. Um agente junior pode reatribuir tickets de outros agentes.
- **Correção:**
```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bulk_action_tickets(request):
    if not request.user.is_staff:
        return Response({"error": "Permissão negada"}, status=403)
    # ... validar que os ticket_ids existem e aplicar RBAC
```

---

### VULN-008: Webhook trigger externo com autenticação insuficiente
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/api_views.py`, Linhas 497-505
- **Código vulnerável:**
```python
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def webhook_external_trigger(request):
    event = request.data.get("event")
    payload = request.data.get("data", {})
    ...
    webhook_service.trigger_event(event, payload)
```
- **Cenário de ataque:** Qualquer usuário autenticado pode disparar **qualquer evento de workflow** no sistema, incluindo escalações, mudanças de status e envio de notificações. Não há restrição de role (deveria ser admin-only).
- **Correção:** Adicionar `if not request.user.is_staff` check.

---

## 3. IDOR & CONTROLE DE ACESSO

### VULN-009: TicketDetailAPIView sem verificação de propriedade — IDOR
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/api_views.py`, Linhas 63-67
- **Código vulnerável:**
```python
class TicketDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    queryset = Ticket.objects.select_related("cliente", "agente", "categoria")
```
- **Cenário de ataque:** Um agente pode ler, **modificar ou deletar** qualquer ticket de qualquer outro agente ou cliente via `GET/PUT/PATCH/DELETE /api/tickets/<pk>/`. Enumeração de IDs sequenciais trivial. Dados financeiros e PII de clientes expostos.
- **Correção:**
```python
class TicketDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Ticket.objects.select_related("cliente", "agente", "categoria")
        return Ticket.objects.filter(
            Q(agente=user) | Q(cliente__user=user)
        ).select_related("cliente", "agente", "categoria")
```

---

### VULN-010: ClienteDetailAPIView permite CRUD de qualquer cliente
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/api_views.py`, Linhas 93-96
- **Código vulnerável:**
```python
class ClienteDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = ClienteSerializer
    permission_classes = [IsAuthenticated]
    queryset = Cliente.objects.all()
```
- **Cenário de ataque:** Qualquer usuário autenticado pode **deletar** clientes ou **modificar** seus dados (email, telefone, empresa) via API. Manipulação de dados cadastrais de clientes.
- **Correção:** Restringir a `IsAdminUser` ou custom permission para staff.

---

### VULN-011: CannedResponseDetailAPIView sem owner check
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/api_views.py`, Linhas 316-319
- **Código vulnerável:**
```python
class CannedResponseDetailAPIView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CannedResponseSerializer
    permission_classes = [IsAuthenticated]
    queryset = CannedResponse.objects.all()
```
- **Cenário de ataque:** Qualquer usuário pode editar ou deletar respostas prontas de outros agentes via ID sequencial.

---

### VULN-012: Views financeiras sem restrição de staff
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/financeiro_views.py`, Linhas 19-122
- **Código vulnerável:**
```python
@login_required
def dashboard_financeiro(request):
    ...
    receita_chamados_mes = ...
    
@login_required
def contratos_lista(request):
    ...
    
@login_required
def faturas_lista(request):
    ...

@login_required
def movimentacoes_lista(request):
    ...
```
- **Cenário de ataque:** Todas as views financeiras usam apenas `@login_required`. Qualquer usuário logado (incluindo clientes com portal de acesso) pode acessar: dados de receita, contratos, faturas, movimentações financeiras — **dados financeiros sigilosos**.
- **Correção:** Adicionar `@staff_member_required` a todas as views financeiras.

---

### VULN-013: Views de estoque sem restrição de role
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/estoque_views.py`, Linhas 28-300
- **Código vulnerável:** Todas as views (`estoque_dashboard`, `ProdutoListView`, `ProdutoDetailView`, `ProdutoCreateView`, `ProdutoUpdateView`, `MovimentacaoListView`) usam apenas `@login_required`.
- **Cenário de ataque:** Um cliente com acesso ao portal pode visualizar dados de estoque, preços de custo, margens e criar/editar produtos.
- **Correção:** Adicionar verificação `is_staff` em todas as views de estoque.

---

### VULN-014: SLA Dashboard público sem qualquer autenticação
- **Severidade:** 🔴 CRÍTICA
- **Arquivo:** `dashboard/sla_views.py`, Linhas 22-51
- **Código vulnerável:**
```python
def sla_test(request):
    """Teste SLA sem autenticação"""
    return JsonResponse({
        'status': 'success',
        ...
        'sla_policies_count': SLAPolicy.objects.count(),
        'sla_alerts_count': SLAAlert.objects.count()
    })

def sla_dashboard_public(request):
    """Dashboard SLA público temporário para demonstração"""
    ...
    dashboard_data = sla_monitor.get_sla_dashboard_data()
```
- **Cenário de ataque:** Dois endpoints (`sla_test` e `sla_dashboard_public`) são **completamente públicos**. Expõem métricas de SLA, número de políticas, alertas ativos e dados de compliance — informações que revelam a saúde operacional da organização. Comentário diz "TEMPORÁRIO" mas está em produção.
- **Correção:** Remover estes endpoints ou adicionar `@login_required` + `@staff_member_required`.

---

## 4. ATAQUES DE INJEÇÃO

### VULN-015: Exceção retornando str(e) em API endpoints (Information Disclosure)
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/api_views.py`, Linha 160; `dashboard/views.py`, múltiplas linhas; `dashboard/chat_views.py`, Linha 355; `dashboard/sla_views.py`, Linha 48
- **Código vulnerável (exemplo):**
```python
except Exception as e:
    return Response({"error": str(e)}, status=500)
```
```python
return JsonResponse({'error': str(e)}, status=500)
```
- **Cenário de ataque:** Stack traces e mensagens de erro internas são retornados aos clientes. Podem revelar: estrutura de banco de dados, nomes de tabelas, paths do sistema de arquivos, versões de bibliotecas. Em `sla_views.py` linha 48, a exceção do dashboard público expõe erros do ORM diretamente.
- **Correção:** Em produção, retornar mensagens genéricas:
```python
except Exception as e:
    logger.error("Erro interno: %s", e, exc_info=True)
    return Response({"error": "Erro interno do servidor"}, status=500)
```

---

## 5. SEGURANÇA DE UPLOAD DE ARQUIVOS

### VULN-016: Upload de avatar sem validação de tipo de arquivo
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/views.py`, Linhas 1548-1550 (ProfileView.post)
- **Código vulnerável:**
```python
# Processa upload de avatar
if 'avatar' in request.FILES:
    perfil.avatar = request.FILES['avatar']
```
- **Cenário de ataque:** O upload de avatar na ProfileView **não valida** tipo de arquivo, tamanho ou conteúdo. Um atacante pode:
  1. Fazer upload de arquivo `.php`, `.py`, `.html` ou `.svg` com scripts maliciosos
  2. Fazer upload de arquivos de tamanho ilimitado (DoS)
  3. Explorar path traversal em `upload_to='avatars/'`
  4. Se o media serve sem `Content-Disposition`, executar XSS via SVG malicioso

  Note que `dashboard/security.py` tem a função `validate_file_upload()` (linhas 213-239) mas **ela não é usada** no ProfileView.
- **Correção:**
```python
if 'avatar' in request.FILES:
    from .security import validate_file_upload
    is_valid, error_msg = validate_file_upload(request.FILES['avatar'])
    if is_valid:
        perfil.avatar = request.FILES['avatar']
    else:
        messages.error(request, error_msg)
```

---

### VULN-017: Upload de anexos de ticket com validação parcial
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/views.py`, Linhas 919-926 (TicketCreateView.form_valid)
- **Código vulnerável:**
```python
if 'anexos' in self.request.FILES:
    anexos = self.request.FILES.getlist('anexos')
    for anexo in anexos:
        if anexo.size <= 10 * 1024 * 1024:
            TicketAnexo.objects.create(
                ticket=self.object,
                arquivo=anexo,
                nome_original=anexo.name,
                ...
            )
```
- **Cenário de ataque:** Apenas o tamanho é validado. Não há validação de tipo MIME, extensão, ou conteúdo malicioso. Arquivos executáveis, scripts ou binários podem ser armazenados e potencialmente servidos. O `FileField(upload_to='tickets/anexos/%Y/%m/')` no model não impõe restrição de tipo.
- **Correção:** Usar `validate_file_upload()` de `security.py` para cada anexo.

---

## 6. CSRF BYPASS

### VULN-018: Múltiplos endpoints com @csrf_exempt desnecessário
- **Severidade:** 🟠 ALTA
- **Arquivos e linhas:**
  - `dashboard/chat_views.py`, Linha 291: `api_send_message` — endpoint de chat com `@csrf_exempt` + `@login_required`
  - `dashboard/push_views.py`, Linhas 30, 83, 108, 141: subscribe_push, unsubscribe_push, update_preferences, test_notification
  - `dashboard/mobile_views.py`, Linhas 344, 391, 467: mobile_ticket_status_update, mobile_ticket_comment, mobile_ticket_upload_photo
  - `dashboard/chatbot_ai_views.py`, Linhas 31, 71: chatbot_api, chatbot_feedback
  - `dashboard/executive_views.py`, Linha 323
  - `dashboard/integrations.py`, Linhas 18, 163: whatsapp_webhook, slack_webhook
  
- **Código vulnerável (exemplo em chat_views.py):**
```python
@login_required
@require_http_methods(["POST"])
@csrf_exempt
def api_send_message(request):
```
- **Cenário de ataque:** Endpoints com `@csrf_exempt` e `@login_required` são vulneráveis a Cross-Site Request Forgery. Um site malicioso pode enviar mensagens de chat, alterar status de tickets, fazer upload de fotos ou enviar notificações push em nome do usuário logado. Os webhooks de WhatsApp/Slack são legítimos para `@csrf_exempt`, mas os endpoints internos não.
- **Correção:** Remover `@csrf_exempt` de todos os endpoints internos que usam `@login_required`. Para AJAX, usar o header `X-CSRFToken`. Para APIs mobile, usar token authentication em vez de cookies.

---

### VULN-019: Chatbot API público sem autenticação E sem CSRF
- **Severidade:** 🔴 CRÍTICA
- **Arquivo:** `dashboard/chatbot_ai_views.py`, Linhas 28-68
- **Código vulnerável:**
```python
def chatbot_interface(request):
    """Interface do chatbot para usuários"""
    return render(request, 'dashboard/chatbot_interface.html')

@csrf_exempt
@require_http_methods(["POST"])
def chatbot_api(request):
    """API principal do chatbot"""
    ...
    response = chatbot_engine.process_message(message, session_id, user)
```
- **Cenário de ataque:** O endpoint do chatbot API é **completamente público** (sem `@login_required`) e sem CSRF. Pode ser abusado para:
  1. DoS via mensagens em massa
  2. Extração de dados da base de conhecimento
  3. Prompt injection se usa LLM
  4. Criação automatizada de tickets
- **Correção:** Adicionar rate limiting agressivo e, se possível, autenticação.

---

## 7. SEGURANÇA DE WEBSOCKET

### VULN-020: WebSocket routing com regex permissivo (ReDoS potencial)
- **Severidade:** 🔵 BAIXA
- **Arquivo:** `dashboard/routing.py`, Linha 13
- **Código vulnerável:**
```python
re_path(r'ws/tickets/(?P<ticket_id>\w+)/$', consumers.TicketChatConsumer.as_asgi()),
```
- **Cenário de ataque:** O `\w+` aceita strings de qualquer tamanho como ticket_id. Embora o consumer valide no `connect()`, patterns regex permissivos em URLs de WebSocket podem causar comportamento inesperado.
- **Correção:**
```python
re_path(r'ws/tickets/(?P<ticket_id>\d+)/$', consumers.TicketChatConsumer.as_asgi()),
```

---

### VULN-021: Exception genérica em TicketChatConsumer suprime erros de acesso
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/consumers.py`, Linhas 461-474
- **Código vulnerável:**
```python
try:
    ticket = await database_sync_to_async(Ticket.objects.get)(id=self.ticket_id)
    ...
except:
    await self.close()
    return
```
- **Cenário de ataque:** O `except:` bare suprime todas as exceções incluindo `PermissionError` ou erros de lógica. Um bug de permissão seria silenciosamente ignorado. Log should be added.
- **Correção:** Usar `except Exception as e:` com logging e fechar com código de erro específico.

---

## 8. SEGREDOS & CONFIGURAÇÃO

### VULN-022: Chaves VAPID em arquivo versionado
- **Severidade:** 🔴 CRÍTICA
- **Arquivo:** `vapid_keys.txt`, Linhas 1-4
- **Código vulnerável:**
```
VAPID_PUBLIC_KEY=BC2pDJ8z6ylnYee0JT_ARw7o3-__lhCm6bnrH-jsaWxJ1SfB0CIgM1gk_aULAUTyf-J8UbruCRhqRXXiGgLtjrs
VAPID_PRIVATE_KEY=cDwnvkISqlUsY9K9udefIHHexhILAsBod_dyBdreIk4
VAPID_CLAIMS_EMAIL=admin@seudominio.com
```
- **Cenário de ataque:** Chave **privada** VAPID commitada no repositório. Qualquer pessoa com acesso ao repo (inclui forks, clones, CI/CD logs) pode:
  1. Enviar push notifications falsas em nome do sistema
  2. Interceptar notificações se combinado com endpoint subscribe
- **Correção:** 
  1. Mover para variáveis de ambiente
  2. Adicionar `vapid_keys.txt` ao `.gitignore`
  3. Rotacionar as chaves comprometidas imediatamente

---

### VULN-023: Chave VAPID hardcoded em push_views.py
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/push_views.py`, Linhas 13-15
- **Código vulnerável:**
```python
VAPID_PUBLIC_KEY = getattr(settings, 'VAPID_PUBLIC_KEY', 'BEl62iUYgUivxIkv69yViEuiBIa40HI0u2Zd43v_rYgL6-xfEkUNECDqJf0pv8VFJdw4aBQQ1hvGsq-cDdfqjgI')
VAPID_PRIVATE_KEY = getattr(settings, 'VAPID_PRIVATE_KEY', '')
VAPID_CLAIMS = getattr(settings, 'VAPID_CLAIMS', {"sub": "mailto:admin@iconnect.com"})
```
- **Cenário de ataque:** Mesmo que settings defina chaves corretas, o fallback hardcoded da chave pública é uma chave real. Se settings não define, usa fallback. Além disso, email de claims revela domínio interno.
- **Correção:** Usar `config('VAPID_PUBLIC_KEY')` sem default ou com erro explícito.

---

### VULN-024: WHATSAPP_WEBHOOK_VERIFY_TOKEN hardcoded
- **Severidade:** 🟠 ALTA
- **Arquivo:** `controle_atendimento/settings.py`, Linhas 31-34
- **Código vulnerável:**
```python
WHATSAPP_WEBHOOK_VERIFY_TOKEN = config(
    'WHATSAPP_WEBHOOK_VERIFY_TOKEN',
    default='controle_atendimento_webhook_2024'
)
```
- **Cenário de ataque:** O token de verificação de webhook do WhatsApp é previsível. Um atacante pode registrar seu próprio webhook endpoint fingindo ser o WhatsApp e injetar mensagens falsas no sistema, criando tickets fraudulentos.
- **Correção:** Remover o default e exigir envvar.

---

### VULN-025: CORS com origens de desenvolvimento
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `controle_atendimento/settings_base.py`, Linhas 338-343
- **Código vulnerável:**
```python
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://localhost:8001',
    'http://127.0.0.1:3000',
    'http://127.0.0.1:8001',
]
CORS_ALLOW_CREDENTIALS = True
```
- **Cenário de ataque:** Origens de desenvolvimento estão no settings_base (compartilhado com produção). Com `CORS_ALLOW_CREDENTIALS = True`, um atacante rodando um servidor em `localhost:3000` na rede do usuário pode fazer requests cross-origin autenticados.
- **Correção:** Mover CORS_ALLOWED_ORIGINS para settings_dev e settings_prod separadamente, com origens de produção reais.

---

### VULN-026: CSP desabilitado em modo DEBUG
- **Severidade:** 🟡 MÉDIA  
- **Arquivo:** `dashboard/security.py`, Linhas 175-188
- **Código vulnerável:**
```python
if not settings.DEBUG:
    response['Content-Security-Policy'] = (...)
```
- **Cenário de ataque:** Em desenvolvimento (DEBUG=True), CSP não é aplicado. Se DEBUG=True vazar para produção (VULN-002), não há proteção contra XSS via CSP.
- **Correção:** Aplicar CSP sempre, com política mais permissiva para DEBUG:
```python
csp = "default-src 'self'; ..."
if settings.DEBUG:
    csp += " script-src 'unsafe-eval';"
response['Content-Security-Policy'] = csp
```

---

## 9. EXPOSIÇÃO DE DADOS SENSÍVEIS

### VULN-027: PII sem criptografia at-rest
- **Severidade:** 🟠 ALTA
- **Arquivo:** `dashboard/models.py`, Linhas 14-68 (PontoDeVenda) e Linhas 59-68 (Cliente)
- **Dados expostos em plaintext:**
  - `PontoDeVenda`: CNPJ, Inscrição Estadual/Municipal, CPF do responsável, emails
  - `Cliente`: email, telefone, celular
  - `PerfilUsuario` (linhas 434-470): telefone, endereço, cidade, estado, CEP
- **Cenário de ataque:** Em caso de breach do banco de dados (SQL injection, backup vazado, acesso interno malicioso), todos os dados PII estão em texto claro. Para um sistema financeiro/governamental, CPF e CNPJ em plaintext violam LGPD.
- **Correção:** Implementar criptografia a nível de campo com `django-encrypted-model-fields` ou `django-fernet-fields` para campos sensíveis.

---

### VULN-028: API de notificações expõe str(e) com stack trace potencial
- **Severidade:** 🔵 BAIXA
- **Arquivo:** `dashboard/views.py`, Linhas 2424, 2440, 2460, 2475
- **Código vulnerável:**
```python
except Exception as e:
    return JsonResponse({
        'success': False,
        'error': str(e)
    }, status=500)
```
- **Cenário de ataque:** Mensagens de erro de banco de dados ou ORM podem vazar nomes de tabelas, campos e estrutura do banco.

---

### VULN-029: analytics_satisfaction expõe exceção completa
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/api_views.py`, Linhas 154-162
- **Código vulnerável:**
```python
except Exception as e:
    return Response({"error": str(e)}, status=500)
```
- **Cenário de ataque:** Se o model `AvaliacaoSatisfacao` não existir ou tiver migration pendente, o traceback completo incluindo paths do servidor é retornado.

---

## 10. DENIAL OF SERVICE (DoS)

### VULN-030: Exportação de tickets sem limite de dados
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/api_views.py`, Linhas 330-370 (`export_tickets_excel`)
- **Código vulnerável:**
```python
tickets = Ticket.objects.filter(criado_em__gte=since).select_related(...)
```
- **Cenário de ataque:** O parâmetro `days` aceita qualquer valor inteiro via query string. Um atacante pode enviar `?days=999999`, forçando o sistema a carregar **todos os tickets** na memória para gerar o Excel. Com milhões de registros, isso causa OOM (Out of Memory).
- **Correção:**
```python
period = min(int(request.query_params.get("days", 30)), 365)
```

---

### VULN-031: Parâmetros inteiros sem sanitização em analytics
- **Severidade:** 🔵 BAIXA
- **Arquivo:** `dashboard/api_views.py`, Linhas 109, 130, 159, 168
- **Código vulnerável:**
```python
period = int(request.query_params.get("days", 30))
```
- **Cenário de ataque:** Sem try/except, enviar `?days=abc` causa crash 500. Sem limite máximo, `?days=999999` causa queries pesadas.
- **Correção:**
```python
try:
    period = min(max(int(request.query_params.get("days", 30)), 1), 365)
except (ValueError, TypeError):
    period = 30
```

---

## 11. WEBHOOK & INTEGRAÇÕES

### VULN-032: WhatsApp webhook sem validação de assinatura
- **Severidade:** 🔴 CRÍTICA
- **Arquivo:** `dashboard/integrations.py`, Linhas 18-50
- **Código vulnerável:**
```python
@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_webhook(request):
    ...
    elif request.method == 'POST':
        try:
            body = json.loads(request.body)
            return _process_whatsapp_message(body)
```
- **Cenário de ataque:** O webhook `POST` não valida a assinatura `X-Hub-Signature-256` que o Facebook/Meta envia. Qualquer pessoa pode enviar webhooks falsos para:
  1. Criar tickets fraudulentos em nome de qualquer número de telefone
  2. Injetar conteúdo malicioso nas conversas
  3. Criar clientes falsos com emails temporários (`whatsapp_*@temp.com`)
  4. Automatizar spam de tickets
- **Correção:** Validar `X-Hub-Signature-256` com HMAC-SHA256 usando o App Secret:
```python
import hmac, hashlib
signature = request.META.get('HTTP_X_HUB_SIGNATURE_256', '')
expected = 'sha256=' + hmac.new(
    settings.WHATSAPP_APP_SECRET.encode(),
    request.body, hashlib.sha256
).hexdigest()
if not hmac.compare_digest(signature, expected):
    return HttpResponse('Invalid signature', status=403)
```

---

### VULN-033: Slack webhook sem verificação de signing secret
- **Severidade:** 🔴 CRÍTICA
- **Arquivo:** `dashboard/integrations.py`, Linhas 163-183
- **Código vulnerável:**
```python
@csrf_exempt
@require_http_methods(["POST"])
def slack_webhook(request):
    try:
        data = json.loads(request.body) if request.content_type == 'application/json' else dict(request.POST.items())
        if data.get('type') == 'url_verification':
            return JsonResponse({'challenge': data.get('challenge')})
        if data.get('command'):
            return _process_slack_command(data)
```
- **Cenário de ataque:** Sem verificação do Slack Signing Secret, qualquer pessoa pode:
  1. Verificar o URL (endpoint responde ao `url_verification` challenge)
  2. Enviar comandos falsos como `/ticket` ou `/status`
  3. Exfiltrar dados de tickets via respostas do processamento de comandos
- **Correção:** Verificar `X-Slack-Signature` e `X-Slack-Request-Timestamp`.

---

## 12. MOBILE & PUSH

### VULN-034: Mobile views com @csrf_exempt permitem CSRF attacks
- **Severidade:** 🟡 MÉDIA
- **Arquivo:** `dashboard/mobile_views.py`, Linhas 344-500
- **Código vulnerável:**
```python
@login_required
@csrf_exempt
def mobile_ticket_status_update(request, ticket_id):
    ...

@login_required
@csrf_exempt
def mobile_ticket_comment(request, ticket_id):
    ...
    
@login_required
@csrf_exempt  
def mobile_ticket_upload_photo(request, ticket_id):
    ...
```
- **Cenário de ataque:** Se um agente visita um site malicioso enquanto logado no app mobile (webview), o site pode alterar status de tickets, adicionar comentários falsos e fazer upload de arquivos.
- **Correção:** Para app mobile, usar Token Authentication em vez de session cookies + CSRF exempt. Se usar webview, manter CSRF.

---

### VULN-035: db.sqlite3 no repositório
- **Severidade:** 🔵 BAIXA
- **Arquivo:** `db.sqlite3` (raiz do projeto)
- **Cenário de ataque:** Banco de dados SQLite versionado pode conter credenciais de desenvolvimento, dados de teste com IDs reais e histórico de senhas.
- **Correção:** Adicionar `db.sqlite3` ao `.gitignore` e remover do histórico Git.

---

## RECOMENDAÇÕES PRIORITÁRIAS

### Ação Imediata (24-48h):
1. **VULN-022**: Rotacionar chaves VAPID e mover para envvars
2. **VULN-032/033**: Adicionar validação de assinatura nos webhooks
3. **VULN-014/019**: Remover endpoints públicos de SLA e chatbot
4. **VULN-001**: Remover default da SECRET_KEY

### Curto Prazo (1-2 semanas):
5. **VULN-009/010/007**: Implementar controle de acesso granular nas APIs
6. **VULN-012/013**: Adicionar `@staff_member_required` às views financeiras e estoque
7. **VULN-016/017**: Aplicar `validate_file_upload()` em todos os uploads
8. **VULN-018**: Remover `@csrf_exempt` de endpoints internos

### Médio Prazo (1-2 meses):
9. **VULN-027**: Implementar criptografia de PII (LGPD compliance)
10. **VULN-003**: Consolidar settings_prod duplicado
11. **VULN-025**: Separar CORS por ambiente
12. **VULN-015**: Sanitizar mensagens de erro em produção

---

*Fim do relatório. Este documento deve ser tratado como CONFIDENCIAL e distribuído apenas para a equipe de desenvolvimento e segurança.*
