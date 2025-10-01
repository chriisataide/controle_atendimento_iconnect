"""
Cache Service - Centralized caching logic
"""
from django.core.cache import cache
from django.conf import settings
from typing import Any, Optional, Dict, List
import json
import logging

logger = logging.getLogger(__name__)


class CacheService:
    """Service para gerenciar cache do sistema"""
    
    # Timeouts em segundos
    TIMEOUTS = {
        'dashboard_stats': 300,      # 5 minutos
        'ticket_list': 120,          # 2 minutos
        'user_permissions': 1800,    # 30 minutos
        'ml_predictions': 600,       # 10 minutos
        'analytics': 900,            # 15 minutos
        'reports': 3600,             # 1 hora
    }
    
    def __init__(self):
        self.key_prefix = getattr(settings, 'CACHE_KEYS', {}).get('prefix', 'iconnect')
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obter valor do cache
        """
        try:
            full_key = self._build_key(key)
            return cache.get(full_key, default)
        except Exception as e:
            logger.warning(f"Cache get error for key {key}: {str(e)}")
            return default
    
    def set(self, key: str, value: Any, timeout: Optional[int] = None, cache_type: str = 'default') -> bool:
        """
        Definir valor no cache
        """
        try:
            full_key = self._build_key(key)
            if timeout is None:
                timeout = self.TIMEOUTS.get(cache_type, 300)
            
            cache.set(full_key, value, timeout)
            return True
        except Exception as e:
            logger.warning(f"Cache set error for key {key}: {str(e)}")
            return False
    
    def delete(self, key: str) -> bool:
        """
        Deletar chave do cache
        """
        try:
            full_key = self._build_key(key)
            cache.delete(full_key)
            return True
        except Exception as e:
            logger.warning(f"Cache delete error for key {key}: {str(e)}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Deletar chaves que combinam com padrão
        """
        try:
            full_pattern = self._build_key(pattern)
            return cache.delete_many(cache.keys(full_pattern))
        except Exception as e:
            logger.warning(f"Cache delete pattern error for {pattern}: {str(e)}")
            return 0
    
    def get_or_set(self, key: str, callable_func, timeout: Optional[int] = None, cache_type: str = 'default') -> Any:
        """
        Obter do cache ou executar função e cachear resultado
        """
        try:
            full_key = self._build_key(key)
            if timeout is None:
                timeout = self.TIMEOUTS.get(cache_type, 300)
            
            return cache.get_or_set(full_key, callable_func, timeout)
        except Exception as e:
            logger.warning(f"Cache get_or_set error for key {key}: {str(e)}")
            # Fallback: executar função diretamente
            return callable_func()
    
    # Métodos específicos para diferentes tipos de cache
    
    def cache_dashboard_stats(self, user_id: int, stats: Dict) -> bool:
        """Cache de estatísticas do dashboard"""
        key = f"dashboard_stats:user:{user_id}"
        return self.set(key, stats, cache_type='dashboard_stats')
    
    def get_dashboard_stats(self, user_id: int) -> Optional[Dict]:
        """Obter estatísticas do dashboard do cache"""
        key = f"dashboard_stats:user:{user_id}"
        return self.get(key)
    
    def cache_ticket_list(self, filters: Dict, tickets: List) -> bool:
        """Cache de lista de tickets"""
        # Criar chave baseada nos filtros
        filter_key = self._create_filter_key(filters)
        key = f"ticket_list:{filter_key}"
        return self.set(key, tickets, cache_type='ticket_list')
    
    def get_cached_ticket_list(self, filters: Dict) -> Optional[List]:
        """Obter lista de tickets do cache"""
        filter_key = self._create_filter_key(filters)
        key = f"ticket_list:{filter_key}"
        return self.get(key)
    
    def cache_user_permissions(self, user_id: int, permissions: Dict) -> bool:
        """Cache de permissões do usuário"""
        key = f"user_permissions:{user_id}"
        return self.set(key, permissions, cache_type='user_permissions')
    
    def get_user_permissions(self, user_id: int) -> Optional[Dict]:
        """Obter permissões do usuário do cache"""
        key = f"user_permissions:{user_id}"
        return self.get(key)
    
    def cache_ml_prediction(self, input_hash: str, prediction: Dict) -> bool:
        """Cache de predições ML"""
        key = f"ml_prediction:{input_hash}"
        return self.set(key, prediction, cache_type='ml_predictions')
    
    def get_ml_prediction(self, input_hash: str) -> Optional[Dict]:
        """Obter predição ML do cache"""
        key = f"ml_prediction:{input_hash}"
        return self.get(key)
    
    def cache_analytics_report(self, report_type: str, params: Dict, data: Dict) -> bool:
        """Cache de relatórios analytics"""
        params_key = self._create_filter_key(params)
        key = f"analytics:{report_type}:{params_key}"
        return self.set(key, data, cache_type='analytics')
    
    def get_analytics_report(self, report_type: str, params: Dict) -> Optional[Dict]:
        """Obter relatório analytics do cache"""
        params_key = self._create_filter_key(params)
        key = f"analytics:{report_type}:{params_key}"
        return self.get(key)
    
    # Métodos de invalidação
    
    def invalidate_user_cache(self, user_id: int):
        """Invalidar todo cache relacionado a um usuário"""
        patterns = [
            f"dashboard_stats:user:{user_id}",
            f"user_permissions:{user_id}",
        ]
        
        for pattern in patterns:
            self.delete(pattern)
    
    def invalidate_ticket_cache(self, ticket_id: Optional[int] = None):
        """Invalidar cache de tickets"""
        # Invalidar listas de tickets
        self.delete_pattern("ticket_list:*")
        
        # Invalidar estatísticas que dependem de tickets
        self.delete_pattern("dashboard_stats:*")
        self.delete_pattern("analytics:*")
        
        if ticket_id:
            self.delete(f"ticket:{ticket_id}")
    
    def invalidate_analytics_cache(self):
        """Invalidar todo cache de analytics"""
        self.delete_pattern("analytics:*")
        self.delete_pattern("dashboard_stats:*")
    
    # Métodos auxiliares
    
    def _build_key(self, key: str) -> str:
        """Construir chave completa com prefixo"""
        return f"{self.key_prefix}:{key}"
    
    def _create_filter_key(self, filters: Dict) -> str:
        """Criar chave baseada em filtros"""
        try:
            # Ordenar filtros para garantir consistência
            sorted_filters = dict(sorted(filters.items()))
            return json.dumps(sorted_filters, sort_keys=True).encode('utf-8').hex()[:32]
        except Exception:
            return "default"
    
    # Health check
    
    def health_check(self) -> Dict:
        """Verificar saúde do sistema de cache"""
        try:
            test_key = "health_check"
            test_value = "ok"
            
            # Teste de escrita
            write_success = self.set(test_key, test_value, timeout=10)
            
            # Teste de leitura
            read_value = self.get(test_key)
            read_success = read_value == test_value
            
            # Limpeza
            self.delete(test_key)
            
            return {
                'status': 'healthy' if (write_success and read_success) else 'unhealthy',
                'write_test': write_success,
                'read_test': read_success,
                'backend': cache.__class__.__name__
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e),
                'backend': cache.__class__.__name__
            }


# Instância global do service
cache_service = CacheService()