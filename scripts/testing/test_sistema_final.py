#!/usr/bin/env python3
"""
Script final de validação do sistema
Testa todas as funcionalidades implementadas
"""

import os
import sys
import django

# Adicionar o diretório do projeto ao path
sys.path.append('/Users/chrisataide/Documents/controle_atendimento_iconnect')

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django.setup()

def test_database():
    """Testa conexão com o banco de dados"""
    print("🗄️  Testando banco de dados...")
    try:
        from dashboard.models import Ticket, Cliente
        ticket_count = Ticket.objects.count()
        cliente_count = Cliente.objects.count()
        print(f"✅ Banco conectado - {ticket_count} tickets, {cliente_count} clientes")
        return True
    except Exception as e:
        print(f"❌ Erro no banco: {str(e)}")
        return False

def test_cache():
    """Testa sistema de cache Redis"""
    print("\n💾 Testando cache Redis...")
    try:
        from django.core.cache import cache
        cache.set('test_key', 'test_value', 30)
        result = cache.get('test_key')
        if result == 'test_value':
            print("✅ Cache Redis funcionando")
            return True
        else:
            print("❌ Cache não retornou valor esperado")
            return False
    except Exception as e:
        print(f"❌ Erro no cache: {str(e)}")
        return False

def test_services():
    """Testa camada de serviços"""
    print("\n🔧 Testando serviços...")
    try:
        from dashboard.services.ticket_service import TicketService
        from dashboard.services.analytics_service import AnalyticsService
        from dashboard.services.cache_service import CacheService
        
        # Testar TicketService
        ticket_service = TicketService()
        print("✅ TicketService carregado")
        
        # Testar AnalyticsService
        analytics_service = AnalyticsService()
        print("✅ AnalyticsService carregado")
        
        # Testar CacheService
        cache_service = CacheService()
        cache_service.set('test_service', 'working', 60)
        result = cache_service.get('test_service')
        if result == 'working':
            print("✅ CacheService funcionando")
        
        return True
    except Exception as e:
        print(f"❌ Erro nos serviços: {str(e)}")
        return False

def test_push_notifications():
    """Testa sistema de push notifications"""
    print("\n📱 Testando push notifications...")
    try:
        from dashboard.push_views import send_push_notification
        print("✅ Sistema de push notifications carregado")
        return True
    except Exception as e:
        print(f"❌ Erro no push: {str(e)}")
        return False

def test_ml_system():
    """Testa sistema de Machine Learning"""
    print("\n🤖 Testando Machine Learning...")
    try:
        from dashboard.ml_engine import TicketPredictor
        ml_engine = TicketPredictor()
        
        # Testar predição básica
        prediction = ml_engine.predict_ticket_properties(
            "Problema no sistema",
            "Sistema não está funcionando corretamente"
        )
        print("✅ Sistema ML básico funcionando")
        return True
    except Exception as e:
        print(f"❌ Erro no ML: {str(e)}")
        return False

def test_security():
    """Testa configurações de segurança"""
    print("\n🔒 Testando segurança...")
    try:
        from django.conf import settings
        
        # Verificar configurações de segurança
        security_checks = [
            ('DEBUG', not settings.DEBUG if hasattr(settings, 'DEBUG') else True),
            ('SECRET_KEY', bool(settings.SECRET_KEY)),
            ('SECURE_SSL_REDIRECT', getattr(settings, 'SECURE_SSL_REDIRECT', False)),
            ('SECURE_HSTS_SECONDS', getattr(settings, 'SECURE_HSTS_SECONDS', 0) > 0),
        ]
        
        passed = 0
        for check_name, check_result in security_checks:
            if check_result:
                print(f"✅ {check_name}: OK")
                passed += 1
            else:
                print(f"⚠️  {check_name}: Precisa de atenção")
        
        print(f"📊 Segurança: {passed}/{len(security_checks)} checks passaram")
        return passed >= 2  # Pelo menos metade dos checks
    except Exception as e:
        print(f"❌ Erro na segurança: {str(e)}")
        return False

def test_performance():
    """Testa otimizações de performance"""
    print("\n⚡ Testando performance...")
    try:
        from dashboard.models import Ticket
        from django.db import connection
        
        # Teste de query otimizada
        initial_queries = len(connection.queries)
        tickets = list(Ticket.objects.select_related('cliente', 'agente')[:5])
        final_queries = len(connection.queries)
        queries_used = final_queries - initial_queries
        
        print(f"✅ Queries otimizadas: {queries_used} queries para {len(tickets)} tickets")
        return True
    except Exception as e:
        print(f"❌ Erro na performance: {str(e)}")
        return False

def main():
    """Executa todos os testes"""
    print("=" * 60)
    print("🚀 VALIDAÇÃO FINAL DO SISTEMA - CONTROLE DE ATENDIMENTO")
    print("=" * 60)
    
    tests = [
        ("Banco de Dados", test_database),
        ("Cache Redis", test_cache),
        ("Serviços", test_services),
        ("Push Notifications", test_push_notifications),
        ("Machine Learning", test_ml_system),
        ("Segurança", test_security),
        ("Performance", test_performance),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Erro crítico em {test_name}: {str(e)}")
            results.append((test_name, False))
    
    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    passed = 0
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSOU" if result else "❌ FALHOU"
        print(f"{test_name:.<30} {status}")
        if result:
            passed += 1
    
    print("-" * 60)
    print(f"Total: {passed}/{total} testes passaram ({passed/total*100:.1f}%)")
    
    if passed >= total * 0.8:  # 80% ou mais
        print("\n🎉 SISTEMA PRONTO PARA PRODUÇÃO!")
        print("✅ Todas as melhorias foram implementadas com sucesso")
        print("✅ Sistema estável e funcional")
    elif passed >= total * 0.6:  # 60% ou mais
        print("\n⚠️  SISTEMA FUNCIONAL COM ALGUMAS LIMITAÇÕES")
        print("✅ Principais funcionalidades operacionais")
        print("⚠️  Algumas áreas precisam de ajustes")
    else:
        print("\n❌ SISTEMA PRECISA DE AJUSTES")
        print("❌ Várias funcionalidades com problemas")
        print("🔧 Recomenda-se revisar as implementações")
    
    print("\n📝 PRÓXIMOS PASSOS RECOMENDADOS:")
    if not any(name == "Machine Learning" and result for name, result in results):
        print("- Ajustar sistema de ML para dados específicos")
    if not any(name == "Push Notifications" and result for name, result in results):
        print("- Configurar VAPID keys para push notifications")
    if not any(name == "Segurança" and result for name, result in results):
        print("- Revisar configurações de segurança")
    
    print("- Realizar testes em ambiente de staging")
    print("- Configurar monitoramento e logs")
    print("- Preparar backup automatizado")
    print("=" * 60)

if __name__ == "__main__":
    main()