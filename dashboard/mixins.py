"""
Mixins reutilizáveis para modelos do dashboard.
Padrão BACEN/Compliance — Soft Delete para modelos financeiros.
"""

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class SoftDeleteQuerySet(models.QuerySet):
    """QuerySet que filtra registros soft-deleted por padrão."""

    def delete(self):
        """Override de delete em massa para soft delete."""
        return self.update(is_deleted=True, deleted_at=timezone.now())

    def hard_delete(self):
        """Exclusão real — usar somente em migrations ou admin."""
        return super().delete()

    def alive(self):
        """Retorna apenas registros não excluídos."""
        return self.filter(is_deleted=False)

    def dead(self):
        """Retorna apenas registros excluídos (lixeira)."""
        return self.filter(is_deleted=True)


class SoftDeleteManager(models.Manager):
    """Manager padrão que exclui registros soft-deleted."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db).alive()


class SoftDeleteAllManager(models.Manager):
    """Manager que inclui TODOS os registros, inclusive soft-deleted."""

    def get_queryset(self):
        return SoftDeleteQuerySet(self.model, using=self._db)


class SoftDeleteModel(models.Model):
    """
    Mixin abstrato para soft delete em modelos financeiros.

    Uso:
        class Contrato(SoftDeleteModel):
            ...

    - objects = SoftDeleteManager() → filtra deletados
    - all_objects = SoftDeleteAllManager() → inclui deletados
    - .soft_delete(user) → marca como deletado
    - .restore() → restaura registro
    """

    is_deleted = models.BooleanField(
        default=False,
        db_index=True,
        verbose_name="Excluído",
        help_text="Soft delete — registro não é removido do banco",
    )
    deleted_at = models.DateTimeField(null=True, blank=True, verbose_name="Excluído em")
    deleted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(class)s_deleted",
        verbose_name="Excluído por",
    )

    objects = SoftDeleteManager()
    all_objects = SoftDeleteAllManager()

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        """Marca o registro como excluído (soft delete)."""
        self.is_deleted = True
        self.deleted_at = timezone.now()
        self.deleted_by = user
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def restore(self):
        """Restaura um registro soft-deleted."""
        self.is_deleted = False
        self.deleted_at = None
        self.deleted_by = None
        self.save(update_fields=["is_deleted", "deleted_at", "deleted_by"])

    def hard_delete(self):
        """Exclusão real — somente para admin/migrations."""
        super().delete()
