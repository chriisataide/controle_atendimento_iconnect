"""
Sistema de Versionamento de API do iConnect
Implementa versionamento automático e transformação de respostas
"""

import json
from functools import wraps
from datetime import datetime
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone

# ========== CONSTANTES DE VERSÃO ==========

SUPPORTED_VERSIONS = ['v1', 'v2', 'v3']
DEFAULT_VERSION = 'v1'

def _is_valid_version(version):
    """Valida se a versão está na lista de versões suportadas"""
    return version in SUPPORTED_VERSIONS

# ========== CONFIGURAÇÕES DE VERSÃO ==========

API_VERSIONS = {
    'v1': {
        'version': '1.0.0',
        'released': '2025-01-01',
        'deprecated': False,
        'end_of_life': None,
    },
    'v2': {
        'version': '2.0.0', 
        'released': '2025-09-15',
        'deprecated': False,
        'end_of_life': None,
    }
}

DEFAULT_VERSION = 'v2'

# ========== DECORADOR DE VERSIONAMENTO ==========

def api_version(version='v1', supported_versions=None):
    """
    Decorator para versionamento de API
    
    Args:
        version (str): Versão padrão da API (default: 'v1')
        supported_versions (list): Lista de versões suportadas pela view
    
    Usage:
        @api_version('v2')
        def my_api_view(request):
            pass
            
        @api_version(supported_versions=['v1', 'v2'])
        def my_multi_version_view(request):
            pass
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Obter versão solicitada do header ou query param
            requested_version = (
                request.META.get('HTTP_API_VERSION') or 
                request.GET.get('version') or 
                version  # usar versão padrão se não especificada
            )
            
            # Usar versões suportadas específicas ou globais
            valid_versions = supported_versions or SUPPORTED_VERSIONS
            
            # Validar versão
            if not _is_valid_version(requested_version) or requested_version not in valid_versions:
                return JsonResponse({
                    'error': f'Unsupported API version: {requested_version}',
                    'supported_versions': valid_versions
                }, status=400)
            
            # Adicionar versão ao request para uso na view
            request.api_version = requested_version
            
            # Executar view
            response = view_func(request, *args, **kwargs)
            
            # Transformar resposta se necessário
            if hasattr(response, 'content') and response.get('Content-Type', '').startswith('application/json'):
                transformer = APIResponseTransformer(requested_version)
                response = transformer.transform_response(response)
            
            # Adicionar header de versão na resposta
            if hasattr(response, '__setitem__'):
                response['API-Version'] = requested_version
            
            return response
        
        # Marcar função como versionada
        wrapper._api_versioned = True
        wrapper._api_version = version
        wrapper._supported_versions = supported_versions or SUPPORTED_VERSIONS
        return wrapper
    return decorator

# ========== TRANSFORMADOR DE RESPOSTAS ==========

class APIResponseTransformer:
    """Classe para transformar respostas da API baseado na versão"""
    
    @staticmethod
    def transform_response(data, version='v2'):
        """
        Transforma dados baseado na versão da API
        
        Args:
            data: Dados a serem transformados
            version: Versão da API
        
        Returns:
            dict: Dados transformados
        """
        if version == 'v1':
            return APIResponseTransformer._transform_v1(data)
        elif version == 'v2':
            return APIResponseTransformer._transform_v2(data)
        else:
            return data
    
    @staticmethod
    def _transform_v1(data):
        """Transformação para API v1 (formato legado)"""
        if isinstance(data, dict):
            # Formato v1: campos em snake_case
            transformed = {}
            for key, value in data.items():
                # Converter camelCase para snake_case
                snake_key = APIResponseTransformer._camel_to_snake(key)
                transformed[snake_key] = value
            return transformed
        return data
    
    @staticmethod
    def _transform_v2(data):
        """Transformação para API v2 (formato atual)"""
        if isinstance(data, dict):
            # Adicionar metadados da API v2
            if '_metadata' not in data:
                data['_metadata'] = {
                    'version': '2.0.0',
                    'timestamp': timezone.now().isoformat(),
                    'server': 'iConnect API'
                }
        return data
    
    @staticmethod
    def _camel_to_snake(name):
        """Converte camelCase para snake_case"""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

# ========== UTILITÁRIOS ==========

def get_api_info():
    """Retorna informações sobre todas as versões da API"""
    return {
        'versions': API_VERSIONS,
        'default_version': DEFAULT_VERSION,
        'current_time': timezone.now().isoformat()
    }

def create_versioned_response(data, request=None, status=200):
    """
    Cria resposta JSON com versionamento automático
    
    Args:
        data: Dados da resposta
        request: Request object (opcional)
        status: Código de status HTTP
    
    Returns:
        JsonResponse: Resposta formatada
    """
    version = DEFAULT_VERSION
    if request:
        version = getattr(request, 'api_version', DEFAULT_VERSION)
    
    # Transformar dados baseado na versão
    transformed_data = APIResponseTransformer.transform_response(data, version)
    
    response = JsonResponse(transformed_data, status=status)
    
    # Adicionar headers de versão
    response['API-Version'] = version
    response['API-Version-Info'] = API_VERSIONS[version]['version']
    
    return response

def validate_api_request(request):
    """
    Valida request da API
    
    Args:
        request: Django request object
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Verificar Content-Type para POST/PUT
    if request.method in ['POST', 'PUT', 'PATCH']:
        content_type = request.headers.get('Content-Type', '')
        if not content_type.startswith('application/json'):
            return False, "Content-Type must be application/json"
    
    # Verificar se versão é suportada
    version = (
        request.headers.get('API-Version') or 
        request.GET.get('version') or 
        DEFAULT_VERSION
    )
    
    if version not in API_VERSIONS:
        return False, f"API version {version} not supported"
    
    # Verificar se versão não está no fim da vida
    version_info = API_VERSIONS[version]
    if version_info.get('end_of_life'):
        eol_date = datetime.fromisoformat(version_info['end_of_life'])
        if timezone.now() > eol_date:
            return False, f"API version {version} has reached end of life"
    
    return True, ""

# ========== MIDDLEWARE DE VERSIONAMENTO ==========

class APIVersioningMiddleware:
    """Middleware para adicionar versionamento automático"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Adicionar informações de versão ao request
        if request.path.startswith('/api/'):
            version = (
                request.headers.get('API-Version') or
                request.GET.get('version') or
                DEFAULT_VERSION
            )
            request.api_version = version
            request.api_version_info = API_VERSIONS.get(version, API_VERSIONS[DEFAULT_VERSION])
        
        response = self.get_response(request)
        
        # Adicionar headers de versão para responses da API
        if hasattr(request, 'api_version') and response.get('Content-Type', '').startswith('application/json'):
            response['API-Version'] = request.api_version
            response['API-Supported-Versions'] = ','.join(API_VERSIONS.keys())
        
        return response

# ========== COMPATIBILIDADE ==========

def ensure_backward_compatibility(data, from_version, to_version):
    """
    Garante compatibilidade entre versões
    
    Args:
        data: Dados a serem convertidos
        from_version: Versão origem
        to_version: Versão destino
    
    Returns:
        dict: Dados compatíveis
    """
    if from_version == to_version:
        return data
    
    # Implementar regras de conversão específicas
    if from_version == 'v1' and to_version == 'v2':
        # Converter de v1 para v2
        return APIResponseTransformer._transform_v2(data)
    elif from_version == 'v2' and to_version == 'v1':
        # Converter de v2 para v1
        return APIResponseTransformer._transform_v1(data)
    
    return data
