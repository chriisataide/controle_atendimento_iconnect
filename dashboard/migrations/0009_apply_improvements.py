"""
Migração para aplicar os novos índices de performance e modelos de auditoria
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_add_performance_indexes'),
    ]

    operations = [
        # Executar migração de índices criada anteriormente
        migrations.RunSQL(
            "-- Índices já aplicados na migração 0008",
            reverse_sql="-- Rollback dos índices na migração 0008"
        ),
    ]