# Integrações externas (Slack, WhatsApp, CRM, ERP, Webhooks)

O sistema já possui endpoints e estrutura para integrações:
- **WhatsApp Business API**: Recebe e envia mensagens, cria tickets automaticamente.
- **Slack**: Webhook para comandos e notificações, integração pronta para tickets e status.
- **Webhooks**: Serializer pronto para criação de tickets via API externa.
- **CRM/ERP**: Exemplo de settings para HubSpot, Pipedrive, Salesforce, RD Station, TOTVS, Blip.

## Como ativar
1. Copie `config/integrations_settings_example.py` para `settings_base.py` ou `settings_prod.py` e preencha as variáveis de ambiente.
2. Os endpoints já estão disponíveis em `dashboard/urls.py`:
   - `/dashboard/webhooks/whatsapp/`
   - `/dashboard/webhooks/slack/`
3. Para webhooks customizados, utilize o serializer `WebhookTicketSerializer`.

## Próximos passos sugeridos
- Implementar integração real com CRM/ERP desejado (usar tokens/URLs do settings).
- Documentar payloads e exemplos de uso para cada integração.
- Adicionar testes automatizados para webhooks e integrações.

## Referências
- [Django REST Framework - Webhooks](https://www.django-rest-framework.org/api-guide/views/)
- [API WhatsApp Business](https://developers.facebook.com/docs/whatsapp/)
- [Slack API](https://api.slack.com/)
- [HubSpot API](https://developers.hubspot.com/docs/api/overview)
- [Pipedrive API](https://developers.pipedrive.com/docs/api/v1/)
- [Salesforce API](https://developer.salesforce.com/docs/atlas.en-us.api.meta/api/)
- [RD Station API](https://developers.rdstation.com/pt-BR/)
- [TOTVS API](https://developers.totvs.com.br/)
- [Blip API](https://docs.blip.ai/)
