#!/usr/bin/env python
"""
Script para testar o sistema de cache Redis
"""
import os
import sys
import django

# Setup Django
sys.path.append('/Users/chrisataide/Documents/controle_atendimento_iconnect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django.setup()

from django.core.cache import cache
from dashboard.services.cache_service import cache_service

def test_cache():
    print("🧪 Testando sistema de cache Redis...\n")
    
    # Teste básico do Django cache
    print("1. Teste básico do cache Django:")
    cache.set('test_key', 'test_value', 30)
    result = cache.get('test_key')
    print(f"   Cache set/get: {'✅ OK' if result == 'test_value' else '❌ FALHOU'}")
    
    # Teste do health check
    print("\n2. Health check do cache service:")
    health = cache_service.health_check()
    print(f"   Status: {health['status']}")
    print(f"   Backend: {health['backend']}")
    
    # Teste de cache de dashboard
    print("\n3. Teste de cache de dashboard:")
    test_stats = {'total_tickets': 100, 'resolved': 80, 'pending': 20}
    cache_service.cache_dashboard_stats(1, test_stats)
    cached_stats = cache_service.get_dashboard_stats(1)
    print(f"   Dashboard cache: {'✅ OK' if cached_stats == test_stats else '❌ FALHOU'}")
    
    # Teste de invalidação
    print("\n4. Teste de invalidação:")
    cache_service.invalidate_user_cache(1)
    after_invalidation = cache_service.get_dashboard_stats(1)
    print(f"   Invalidação: {'✅ OK' if after_invalidation is None else '❌ FALHOU'}")
    
    print("\n🎉 Testes de cache concluídos!")

if __name__ == "__main__":
    test_cache()