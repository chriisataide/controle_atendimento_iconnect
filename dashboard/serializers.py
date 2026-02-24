# Serializers para API REST
from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Ticket, Cliente

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            'id', 'nome', 'nome_fantasia', 'cnpj', 'inscricao_estadual',
            'segmento', 'empresa', 'email', 'telefone', 'celular', 'website',
            'cep', 'logradouro', 'numero', 'complemento', 'bairro', 'cidade', 'estado',
            'responsavel_nome', 'responsavel_cargo', 'responsavel_telefone', 'responsavel_email',
            'observacoes', 'ativo', 'criado_em', 'atualizado_em'
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em']

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'email']
        read_only_fields = ['id', 'username']

class TicketSerializer(serializers.ModelSerializer):
    cliente_nome = serializers.CharField(source='cliente.nome', read_only=True)
    agente_nome = serializers.CharField(source='agente.get_full_name', read_only=True)
    tempo_resolucao_horas = serializers.SerializerMethodField()
    
    class Meta:
        model = Ticket
        fields = [
            'id', 'titulo', 'descricao', 'status', 'prioridade', 
            'categoria', 'origem', 'cliente', 'cliente_nome',
            'agente', 'agente_nome', 'criado_em', 'atualizado_em',
            'resolvido_em', 'tempo_resolucao_horas'
        ]
        read_only_fields = ['id', 'criado_em', 'atualizado_em']
    
    def get_tempo_resolucao_horas(self, obj):
        if obj.resolvido_em and obj.criado_em:
            delta = obj.resolvido_em - obj.criado_em
            return round(delta.total_seconds() / 3600, 1)
        return None

class TicketCreateSerializer(serializers.ModelSerializer):
    """Serializer específico para criação de tickets via API"""
    cliente_email = serializers.EmailField(write_only=True)
    cliente_nome = serializers.CharField(write_only=True, required=False)
    cliente_telefone = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = Ticket
        fields = [
            'titulo', 'descricao', 'categoria', 'prioridade', 'origem',
            'cliente_email', 'cliente_nome', 'cliente_telefone'
        ]
    
    def create(self, validated_data):
        # Extrair dados do cliente
        cliente_email = validated_data.pop('cliente_email')
        cliente_nome = validated_data.pop('cliente_nome', cliente_email)
        cliente_telefone = validated_data.pop('cliente_telefone', '')
        
        # Buscar ou criar cliente
        cliente, created = Cliente.objects.get_or_create(
            email=cliente_email,
            defaults={
                'nome': cliente_nome,
                'telefone': cliente_telefone,
            }
        )
        
        # Criar ticket
        validated_data['cliente'] = cliente
        return super().create(validated_data)

class ChatbotInteractionSerializer(serializers.Serializer):
    """Serializer para interações do chatbot"""
    message = serializers.CharField(max_length=1000)
    session_id = serializers.CharField(max_length=100, required=False)
    user_id = serializers.CharField(max_length=100, required=False)
    
    def validate_message(self, value):
        if not value.strip():
            raise serializers.ValidationError("Mensagem não pode estar vazia")
        return value.strip()

class SatisfactionSerializer(serializers.Serializer):
    """Serializer para avaliações de satisfação"""
    ticket_id = serializers.IntegerField()
    nota_atendimento = serializers.IntegerField(min_value=1, max_value=5)
    nota_resolucao = serializers.IntegerField(min_value=1, max_value=5)
    nota_tempo = serializers.IntegerField(min_value=1, max_value=5)
    comentario = serializers.CharField(max_length=1000, required=False, allow_blank=True)
    
    def validate_ticket_id(self, value):
        try:
            ticket = Ticket.objects.get(id=value)
            if ticket.status not in ['resolvido', 'fechado']:
                raise serializers.ValidationError("Só é possível avaliar tickets resolvidos ou fechados")
            return value
        except Ticket.DoesNotExist:
            raise serializers.ValidationError("Ticket não encontrado")

class WebhookTicketSerializer(serializers.Serializer):
    """Serializer para criação de tickets via webhook"""
    titulo = serializers.CharField(max_length=200)
    descricao = serializers.CharField()
    cliente_email = serializers.EmailField()
    cliente_nome = serializers.CharField(max_length=100, required=False)
    cliente_telefone = serializers.CharField(max_length=20, required=False)
    categoria = serializers.CharField(max_length=100, required=False, default='Geral')
    prioridade = serializers.ChoiceField(
        choices=['baixa', 'media', 'alta', 'critica'],
        default='media'
    )
    origem = serializers.CharField(max_length=50, default='webhook')
    
    def validate_titulo(self, value):
        if len(value.strip()) < 5:
            raise serializers.ValidationError("Título deve ter pelo menos 5 caracteres")
        return value.strip()
    
    def validate_descricao(self, value):
        if len(value.strip()) < 10:
            raise serializers.ValidationError("Descrição deve ter pelo menos 10 caracteres")
        return value.strip()
