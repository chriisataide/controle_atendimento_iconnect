# Exemplos de uso da API

## Autenticação
A maioria dos endpoints exige autenticação via token ou sessão. Consulte a documentação Swagger/Redoc para detalhes.

## Criar ticket via Webhook
```json
POST /dashboard/api/tickets/webhook/
{
  "titulo": "Problema no sistema",
  "descricao": "O sistema está apresentando erro ao salvar.",
  "cliente_email": "cliente@exemplo.com",
  "cliente_nome": "Cliente Exemplo",
  "cliente_telefone": "11999999999",
  "categoria": "Suporte",
  "prioridade": "alta"
}
```

## Consultar tickets (exemplo DRF)
```http
GET /dashboard/api/tickets/?status=aberto
Authorization: Token <seu_token>
```

## Enviar mensagem via WhatsApp (integração)
```json
POST /dashboard/webhooks/whatsapp/
{
  "messages": [
    {"from": "5511999999999", "text": {"body": "Olá, preciso de ajuda!"}}
  ]
}
```

## Sugestão automática de prioridade/categoria (IA)
```json
POST /dashboard/api/ml/suggest-ticket/
{
  "titulo": "Erro ao acessar sistema",
  "descricao": "Não consigo fazer login, aparece mensagem de falha."
}

// Resposta:
{
  "prioridade": "alta",
  "prioridade_confianca": 0.92,
  "categoria": "TECNICO",
  "categoria_confianca": 0.88,
  "tempo_estimado_horas": 4
}
```

## Comandos Slack
- `/ticket` — lista tickets ativos
- `/ticket <numero>` — detalhes do ticket
- `/status` — status geral do sistema

Consulte `/swagger/` ou `/redoc/` para todos os endpoints e payloads.
