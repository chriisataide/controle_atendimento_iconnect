"""
Exemplo de configuração para integrações externas (Slack, WhatsApp, Webhook, CRM, ERP).
Copie e adapte para uso real em settings_base.py ou settings_prod.py.
"""
import os

WHATSAPP_CONFIG = {
    'BASE_URL': os.environ.get('WHATSAPP_API_URL', ''),
    'ACCESS_TOKEN': os.environ.get('WHATSAPP_ACCESS_TOKEN', ''),
    'PHONE_NUMBER_ID': os.environ.get('WHATSAPP_PHONE_NUMBER_ID', ''),
    'WEBHOOK_VERIFY_TOKEN': os.environ.get('WHATSAPP_WEBHOOK_TOKEN', ''),
}

SLACK_CONFIG = {
    'WEBHOOK_URL': os.environ.get('SLACK_WEBHOOK_URL', ''),
    'BOT_TOKEN': os.environ.get('SLACK_BOT_TOKEN', ''),
    'CHANNEL': os.environ.get('SLACK_CHANNEL', '#atendimento'),
}

# Exemplo de integração com CRM/ERP (HubSpot, Pipedrive, Salesforce, RD Station, TOTVS, Blip)
CRM_CONFIG = {
    'HUBSPOT_API_KEY': os.environ.get('HUBSPOT_API_KEY', ''),
    'PIPEDRIVE_API_TOKEN': os.environ.get('PIPEDRIVE_API_TOKEN', ''),
    'SALESFORCE_CLIENT_ID': os.environ.get('SALESFORCE_CLIENT_ID', ''),
    'SALESFORCE_CLIENT_SECRET': os.environ.get('SALESFORCE_CLIENT_SECRET', ''),
    'RDSTATION_TOKEN': os.environ.get('RDSTATION_TOKEN', ''),
    'TOTVS_API_URL': os.environ.get('TOTVS_API_URL', ''),
    'BLIP_AUTH_TOKEN': os.environ.get('BLIP_AUTH_TOKEN', ''),
}

# Webhook genérico para integrações customizadas
WEBHOOKS = {
    'TICKET_CREATED': os.environ.get('WEBHOOK_TICKET_CREATED', ''),
    'TICKET_UPDATED': os.environ.get('WEBHOOK_TICKET_UPDATED', ''),
    'CLIENTE_CREATED': os.environ.get('WEBHOOK_CLIENTE_CREATED', ''),
}
