# Dashboard Executivo - Modelos para KPIs Avançados
from django.db import models
from django.db.models import Q
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import datetime, timedelta
import json

class ExecutiveDashboardKPI(models.Model):
    """KPIs personalizáveis para o dashboard executivo"""
    
    KPI_TYPES = [
        ('tickets_volume', 'Volume de Tickets'),
        ('sla_compliance', 'Compliance SLA'),
        ('customer_satisfaction', 'Satisfação do Cliente'),
        ('agent_productivity', 'Produtividade dos Agentes'),
        ('resolution_time', 'Tempo de Resolução'),
        ('first_contact_resolution', 'Resolução no Primeiro Contato'),
        ('cost_per_ticket', 'Custo por Ticket'),
        ('revenue_impact', 'Impacto na Receita'),
    ]
    
    name = models.CharField(max_length=100, verbose_name="Nome do KPI")
    kpi_type = models.CharField(max_length=50, choices=KPI_TYPES, verbose_name="Tipo de KPI")
    target_value = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Meta")
    current_value = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Valor Atual")
    department = models.CharField(max_length=50, blank=True, verbose_name="Departamento")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "KPI Executivo"
        verbose_name_plural = "KPIs Executivos"
    
    def __str__(self):
        return f"{self.name} - {self.current_value}/{self.target_value}"
    
    @property
    def performance_percentage(self):
        """Calcula o percentual de performance"""
        if self.target_value == 0:
            return 0
        return (self.current_value / self.target_value) * 100
    
    @property
    def status(self):
        """Status do KPI baseado na performance"""
        perf = self.performance_percentage
        if perf >= 100:
            return 'excellent'
        elif perf >= 80:
            return 'good'
        elif perf >= 60:
            return 'warning'
        else:
            return 'critical'

class DashboardWidget(models.Model):
    """Widgets configuráveis para o dashboard"""
    
    WIDGET_TYPES = [
        ('chart_line', 'Gráfico de Linha'),
        ('chart_bar', 'Gráfico de Barras'),
        ('chart_pie', 'Gráfico de Pizza'),
        ('metric_card', 'Card de Métrica'),
        ('table', 'Tabela'),
        ('progress_bar', 'Barra de Progresso'),
        ('heat_map', 'Mapa de Calor'),
    ]
    
    title = models.CharField(max_length=100, verbose_name="Título")
    widget_type = models.CharField(max_length=20, choices=WIDGET_TYPES, verbose_name="Tipo")
    data_source = models.CharField(max_length=100, verbose_name="Fonte de Dados")
    config = models.JSONField(default=dict, verbose_name="Configuração")
    position_x = models.IntegerField(default=0, verbose_name="Posição X")
    position_y = models.IntegerField(default=0, verbose_name="Posição Y")
    width = models.IntegerField(default=4, verbose_name="Largura")
    height = models.IntegerField(default=3, verbose_name="Altura")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Criado por")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Widget do Dashboard"
        verbose_name_plural = "Widgets do Dashboard"
        ordering = ['position_y', 'position_x']
    
    def __str__(self):
        return f"{self.title} ({self.widget_type})"

class MetricaTempoReal(models.Model):
    """Métricas calculadas em tempo real"""
    
    metric_name = models.CharField(max_length=50, verbose_name="Nome da Métrica")
    value = models.JSONField(verbose_name="Valor")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Timestamp")
    category = models.CharField(max_length=30, verbose_name="Categoria")
    
    class Meta:
        verbose_name = "Métrica Tempo Real"
        verbose_name_plural = "Métricas Tempo Real"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['metric_name', 'timestamp']),
            models.Index(fields=['category', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.metric_name} - {self.timestamp}"

class AlertaKPI(models.Model):
    """Sistema de alertas para KPIs"""
    
    ALERT_TYPES = [
        ('threshold', 'Limite'),
        ('trend', 'Tendência'),
        ('anomaly', 'Anomalia'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Baixa'),
        ('medium', 'Média'),
        ('high', 'Alta'),
        ('critical', 'Crítica'),
    ]
    
    kpi = models.ForeignKey(ExecutiveDashboardKPI, on_delete=models.CASCADE, verbose_name="KPI")
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES, verbose_name="Tipo de Alerta")
    severity = models.CharField(max_length=20, choices=SEVERITY_LEVELS, verbose_name="Severidade")
    message = models.TextField(verbose_name="Mensagem")
    threshold_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, verbose_name="Valor Limite")
    is_resolved = models.BooleanField(default=False, verbose_name="Resolvido")
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True, verbose_name="Resolvido em")
    
    class Meta:
        verbose_name = "Alerta KPI"
        verbose_name_plural = "Alertas KPI"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Alerta {self.kpi.name} - {self.severity}"