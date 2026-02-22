"""
Migração para aplicar os novos índices de performance e modelos de auditoria
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0008_add_performance_indexes'),
    ]

    operations = [
        # No-op: índices já aplicados na migração 0008
        migrations.RunSQL(
            migrations.RunSQL.noop,
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]