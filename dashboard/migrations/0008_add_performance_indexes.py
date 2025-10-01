"""
Migração para adicionar índices de performance
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0007_alter_slapolicy_unique_together_slapolicy_end_hour_and_more'),
    ]

    operations = [
        # Índices para modelo Ticket
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ticket_status_priority_idx ON dashboard_ticket (status, prioridade);",
            reverse_sql="DROP INDEX IF EXISTS ticket_status_priority_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ticket_created_agent_idx ON dashboard_ticket (criado_em, agente_id);",
            reverse_sql="DROP INDEX IF EXISTS ticket_created_agent_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ticket_client_status_idx ON dashboard_ticket (cliente_id, status);",
            reverse_sql="DROP INDEX IF EXISTS ticket_client_status_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS ticket_sla_deadline_idx ON dashboard_ticket (sla_deadline);",
            reverse_sql="DROP INDEX IF EXISTS ticket_sla_deadline_idx;"
        ),
        
        # Índices para modelo Cliente
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS client_email_idx ON dashboard_cliente (email);",
            reverse_sql="DROP INDEX IF EXISTS client_email_idx;"
        ),
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS client_phone_idx ON dashboard_cliente (telefone);",
            reverse_sql="DROP INDEX IF EXISTS client_phone_idx;"
        ),
        
        # Índices para modelo InteracaoTicket
        migrations.RunSQL(
            "CREATE INDEX IF NOT EXISTS interaction_ticket_created_idx ON dashboard_interacaoticket (ticket_id, criado_em);",
            reverse_sql="DROP INDEX IF EXISTS interaction_ticket_created_idx;"
        ),
    ]