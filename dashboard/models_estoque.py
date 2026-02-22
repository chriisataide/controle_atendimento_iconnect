"""
Modelos para Sistema de Controle de Estoque
Integrado ao Sistema iConnect
"""
from django.db import models, transaction
from django.db.models import F
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator
import uuid
import logging

logger = logging.getLogger('dashboard')


class CategoriaEstoque(models.Model):
    """Categorias de produtos/serviços"""
    nome = models.CharField(max_length=100, unique=True)
    descricao = models.TextField(blank=True)
    cor = models.CharField(max_length=7, default='#007bff', help_text="Cor em hexadecimal")
    icone = models.CharField(max_length=50, default='inventory', help_text="Ícone Material Design")
    ativo = models.BooleanField(default=True)
    
    # Configurações específicas
    controla_estoque = models.BooleanField(default=True, help_text="Se deve controlar estoque para esta categoria")
    permite_estoque_negativo = models.BooleanField(default=False)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Categoria de Estoque"
        verbose_name_plural = "Categorias de Estoque"
        ordering = ['nome']
    
    def __str__(self):
        return self.nome


class UnidadeMedida(models.Model):
    """Unidades de medida para produtos"""
    TIPOS_UNIDADE = [
        ('peso', 'Peso'),
        ('volume', 'Volume'),
        ('comprimento', 'Comprimento'),
        ('area', 'Área'),
        ('unidade', 'Unidade'),
        ('tempo', 'Tempo'),
        ('outros', 'Outros'),
    ]
    
    nome = models.CharField(max_length=50)
    sigla = models.CharField(max_length=10, unique=True)
    tipo = models.CharField(max_length=20, choices=TIPOS_UNIDADE)
    ativo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Unidade de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ['nome']
    
    def __str__(self):
        return f"{self.nome} ({self.sigla})"


class Fornecedor(models.Model):
    """Fornecedores de produtos"""
    TIPOS_PESSOA = [
        ('fisica', 'Pessoa Física'),
        ('juridica', 'Pessoa Jurídica'),
    ]
    
    codigo = models.CharField(max_length=20, unique=True, help_text="Código interno do fornecedor")
    nome = models.CharField(max_length=200)
    nome_fantasia = models.CharField(max_length=200, blank=True)
    tipo_pessoa = models.CharField(max_length=10, choices=TIPOS_PESSOA, default='juridica')
    
    # Documentos
    cnpj_cpf = models.CharField(max_length=18, unique=True)
    inscricao_estadual = models.CharField(max_length=30, blank=True)
    inscricao_municipal = models.CharField(max_length=30, blank=True)
    
    # Contato
    email = models.EmailField(blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    celular = models.CharField(max_length=20, blank=True)
    
    # Endereço
    cep = models.CharField(max_length=9, blank=True)
    logradouro = models.CharField(max_length=200, blank=True)
    numero = models.CharField(max_length=10, blank=True)
    complemento = models.CharField(max_length=50, blank=True)
    bairro = models.CharField(max_length=100, blank=True)
    cidade = models.CharField(max_length=100, blank=True)
    estado = models.CharField(max_length=2, blank=True)
    
    # Status e observações
    ativo = models.BooleanField(default=True)
    observacoes = models.TextField(blank=True)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Fornecedor"
        verbose_name_plural = "Fornecedores"
        ordering = ['nome']
    
    def __str__(self):
        return self.nome


class Produto(models.Model):
    """Produtos e Serviços"""
    TIPOS_PRODUTO = [
        ('produto', 'Produto Físico'),
        ('servico', 'Serviço'),
        ('kit', 'Kit/Combo'),
    ]
    
    STATUS_CHOICES = [
        ('ativo', 'Ativo'),
        ('inativo', 'Inativo'),
        ('descontinuado', 'Descontinuado'),
    ]
    
    # Identificação
    codigo = models.CharField(max_length=50, unique=True, help_text="SKU/Código do produto")
    codigo_barras = models.CharField(max_length=50, blank=True, unique=True, null=True)
    nome = models.CharField(max_length=200)
    descricao = models.TextField(blank=True)
    tipo = models.CharField(max_length=10, choices=TIPOS_PRODUTO, default='produto')
    
    # Categorização
    categoria = models.ForeignKey(CategoriaEstoque, on_delete=models.PROTECT)
    fornecedor_principal = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True)
    unidade_medida = models.ForeignKey(UnidadeMedida, on_delete=models.PROTECT)
    
    # Preços
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    preco_venda = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal('0'))])
    margem_lucro = models.DecimalField(max_digits=5, decimal_places=2, default=0, help_text="Percentual de margem")
    
    # Controle de Estoque
    controla_estoque = models.BooleanField(default=True)
    estoque_atual = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    estoque_minimo = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    estoque_maximo = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    
    # Localização
    localizacao = models.CharField(max_length=100, blank=True, help_text="Endereço no estoque")
    
    # Status e configurações
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='ativo')
    permite_venda_sem_estoque = models.BooleanField(default=False)
    
    # Dimensões e peso
    peso = models.DecimalField(max_digits=8, decimal_places=3, default=0, help_text="Peso em Kg")
    altura = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Altura em cm")
    largura = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Largura em cm")
    profundidade = models.DecimalField(max_digits=8, decimal_places=2, default=0, help_text="Profundidade em cm")
    
    # Observações
    observacoes = models.TextField(blank=True)
    
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)
    criado_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        verbose_name = "Produto"
        verbose_name_plural = "Produtos"
        ordering = ['nome']
        indexes = [
            models.Index(fields=['codigo']),
            models.Index(fields=['codigo_barras']),
            models.Index(fields=['categoria']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.codigo} - {self.nome}"
    
    @property
    def estoque_critico(self):
        """Verifica se estoque está crítico"""
        return self.estoque_atual <= self.estoque_minimo
    
    @property
    def valor_estoque(self):
        """Valor total do estoque atual"""
        return self.estoque_atual * self.preco_custo
    
    @property
    def percentual_estoque(self):
        """Percentual do estoque atual em relação ao máximo"""
        if self.estoque_maximo > 0:
            return (float(self.estoque_atual) / float(self.estoque_maximo)) * 100
        return 0
    
    @property
    def status_estoque_css(self):
        """Classe CSS baseada no status do estoque"""
        percentual = self.percentual_estoque
        if percentual <= 20:
            return 'text-danger'
        elif percentual <= 50:
            return 'text-warning'
        else:
            return 'text-success'
    
    @property
    def estoque_baixo(self):
        """Verifica se estoque está baixo (30% do máximo)"""
        if self.estoque_maximo > 0:
            return self.estoque_atual <= (self.estoque_maximo * Decimal('0.3'))
        return False
    
    def calcular_margem_automatica(self):
        """Calcula margem de lucro baseada nos preços"""
        if self.preco_custo > 0 and self.preco_venda > 0:
            self.margem_lucro = ((self.preco_venda - self.preco_custo) / self.preco_custo) * 100
    
    def save(self, *args, **kwargs):
        with transaction.atomic():
            if not self.codigo:
                # Gerar código automático com retry para evitar race condition
                for attempt in range(5):
                    ultimo_codigo = Produto.objects.filter(
                        categoria=self.categoria
                    ).select_for_update().count() + 1
                    codigo_candidato = f"{self.categoria.nome[:3].upper()}{ultimo_codigo:04d}"
                    if not Produto.objects.filter(codigo=codigo_candidato).exists():
                        self.codigo = codigo_candidato
                        break
                    ultimo_codigo += 1
                    self.codigo = f"{self.categoria.nome[:3].upper()}{ultimo_codigo:04d}"
            
            # Calcular margem automaticamente
            self.calcular_margem_automatica()
            
            super().save(*args, **kwargs)


class TipoMovimentacao(models.Model):
    """Tipos de movimentação de estoque"""
    TIPOS_OPERACAO = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
        ('ajuste', 'Ajuste'),
        ('transferencia', 'Transferência'),
    ]
    
    nome = models.CharField(max_length=100, unique=True)
    tipo_operacao = models.CharField(max_length=15, choices=TIPOS_OPERACAO)
    descricao = models.TextField(blank=True)
    automatico = models.BooleanField(default=False, help_text="Criado automaticamente pelo sistema")
    ativo = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Tipo de Movimentação"
        verbose_name_plural = "Tipos de Movimentação"
        ordering = ['nome']
    
    def __str__(self):
        return f"{self.nome} ({self.get_tipo_operacao_display()})"


class MovimentacaoEstoque(models.Model):
    """Movimentações de entrada e saída de estoque"""
    TIPOS_OPERACAO = [
        ('entrada', 'Entrada'),
        ('saida', 'Saída'),
        ('ajuste', 'Ajuste'),
        ('transferencia', 'Transferência'),
    ]
    
    # Identificação
    numero = models.CharField(max_length=20, unique=True, editable=False)
    tipo_movimentacao = models.ForeignKey(TipoMovimentacao, on_delete=models.PROTECT)
    tipo_operacao = models.CharField(max_length=15, choices=TIPOS_OPERACAO)
    
    # Produto e quantidade
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    quantidade = models.DecimalField(max_digits=10, decimal_places=3, validators=[MinValueValidator(Decimal('0.001'))])
    valor_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    valor_total = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    
    # Estoque antes e depois
    estoque_anterior = models.DecimalField(max_digits=10, decimal_places=3, editable=False, default=0)
    estoque_apos_movimentacao = models.DecimalField(max_digits=10, decimal_places=3, editable=False, default=0)
    
    # Relacionamentos externos
    fornecedor = models.ForeignKey(Fornecedor, on_delete=models.SET_NULL, null=True, blank=True)
    ticket_relacionado = models.ForeignKey('Ticket', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Documentos
    numero_documento = models.CharField(max_length=50, blank=True, help_text="Número da NF, pedido, etc.")
    data_documento = models.DateField(null=True, blank=True)
    
    # Observações
    observacoes = models.TextField(blank=True)
    justificativa = models.TextField(blank=True, help_text="Justificativa para ajustes")
    
    # Controle
    data_movimentacao = models.DateTimeField(default=timezone.now)
    usuario = models.ForeignKey(User, on_delete=models.PROTECT)
    criado_em = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Movimentação de Estoque"
        verbose_name_plural = "Movimentações de Estoque"
        ordering = ['-data_movimentacao']
        indexes = [
            models.Index(fields=['numero']),
            models.Index(fields=['produto', '-data_movimentacao']),
            models.Index(fields=['tipo_operacao', '-data_movimentacao']),
        ]
    
    def __str__(self):
        return f"{self.numero} - {self.produto.nome} ({self.quantidade})"
    
    def save(self, *args, **kwargs):
        with transaction.atomic():
            # Gerar número automático com proteção contra race condition
            if not self.numero:
                from datetime import datetime
                ano_mes = datetime.now().strftime('%Y%m')
                for attempt in range(10):
                    ultimo_numero = MovimentacaoEstoque.objects.filter(
                        numero__startswith=f"MOV{ano_mes}"
                    ).select_for_update().count() + 1
                    numero_candidato = f"MOV{ano_mes}{ultimo_numero:04d}"
                    if not MovimentacaoEstoque.objects.filter(numero=numero_candidato).exists():
                        self.numero = numero_candidato
                        break
                    ultimo_numero += 1
                    self.numero = f"MOV{ano_mes}{ultimo_numero:04d}"
            
            # Calcular valor total
            self.valor_total = self.quantidade * self.valor_unitario
            
            # Lock do produto para evitar race condition no estoque
            produto = Produto.objects.select_for_update().get(pk=self.produto_id)
            
            # Salvar estoque anterior
            if not self.pk:  # Apenas na criação
                self.estoque_anterior = produto.estoque_atual
            
            # Aplicar movimentação no estoque usando F() para atomicidade
            if self.tipo_operacao == 'entrada':
                Produto.objects.filter(pk=produto.pk).update(
                    estoque_atual=F('estoque_atual') + self.quantidade
                )
                self.estoque_apos_movimentacao = produto.estoque_atual + self.quantidade
            elif self.tipo_operacao == 'saida':
                # Validar estoque suficiente
                if produto.estoque_atual < self.quantidade and not produto.categoria.permite_estoque_negativo:
                    raise ValueError(
                        f'Estoque insuficiente para {produto.nome}. '
                        f'Disponível: {produto.estoque_atual}, Solicitado: {self.quantidade}'
                    )
                Produto.objects.filter(pk=produto.pk).update(
                    estoque_atual=F('estoque_atual') - self.quantidade
                )
                self.estoque_apos_movimentacao = produto.estoque_atual - self.quantidade
            elif self.tipo_operacao == 'ajuste':
                Produto.objects.filter(pk=produto.pk).update(
                    estoque_atual=self.quantidade
                )
                self.estoque_apos_movimentacao = self.quantidade
            
            super().save(*args, **kwargs)


class EstoqueAlerta(models.Model):
    """Alertas de estoque crítico"""
    TIPOS_ALERTA = [
        ('estoque_baixo', 'Estoque Baixo'),
        ('estoque_critico', 'Estoque Crítico'),
        ('estoque_zerado', 'Estoque Zerado'),
        ('produto_inativo', 'Produto Inativo'),
    ]
    
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    tipo_alerta = models.CharField(max_length=20, choices=TIPOS_ALERTA)
    mensagem = models.TextField()
    resolvido = models.BooleanField(default=False)
    data_alerta = models.DateTimeField(auto_now_add=True)
    data_resolucao = models.DateTimeField(null=True, blank=True)
    resolvido_por = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = "Alerta de Estoque"
        verbose_name_plural = "Alertas de Estoque"
        ordering = ['-data_alerta']
    
    def __str__(self):
        return f"{self.produto.nome} - {self.get_tipo_alerta_display()}"