"""
Sistema de Monitoramento e Health Checks - iConnect
Middleware e views para monitoramento de saúde da aplicação
"""
import time
import logging
from django.http import JsonResponse
from django.views import View
from django.db import connections
from django.core.cache import cache
from django.conf import settings
from django.utils import timezone
from datetime import datetime, timedelta

logger = logging.getLogger('dashboard')

class HealthCheckView(View):
    """
    Endpoint para verificação de saúde da aplicação
    GET /health/
    """
    
    def get(self, request):
        """
        Verifica a saúde de todos os componentes críticos
        """
        health_data = {
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'version': getattr(settings, 'VERSION', '1.0.0'),
            'environment': getattr(settings, 'ENVIRONMENT', 'unknown'),
            'checks': {}
        }
        
        # Check Database
        try:
            db_conn = connections['default']
            db_conn.cursor()
            health_data['checks']['database'] = {
                'status': 'healthy',
                'response_time': self._measure_db_response_time()
            }
        except Exception as e:
            health_data['checks']['database'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # Check Cache/Redis
        try:
            cache_key = f'health_check_{int(time.time())}'
            cache.set(cache_key, 'test', 60)
            cached_value = cache.get(cache_key)
            
            if cached_value == 'test':
                health_data['checks']['cache'] = {'status': 'healthy'}
            else:
                raise Exception("Cache test failed")
        except Exception as e:
            health_data['checks']['cache'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
            health_data['status'] = 'unhealthy'
        
        # Check Disk Space
        import shutil
        try:
            usage = shutil.disk_usage('/')
            free_percent = (usage.free / usage.total) * 100
            
            health_data['checks']['disk'] = {
                'status': 'healthy' if free_percent > 10 else 'warning',
                'free_percent': round(free_percent, 2),
                'free_gb': round(usage.free / (1024**3), 2)
            }
            
            if free_percent < 5:
                health_data['status'] = 'unhealthy'
        except Exception as e:
            health_data['checks']['disk'] = {
                'status': 'unhealthy',
                'error': str(e)
            }
        
        # Determinar status code HTTP
        status_code = 200 if health_data['status'] == 'healthy' else 503
        
        return JsonResponse(health_data, status=status_code)
    
    def _measure_db_response_time(self):
        """Mede o tempo de resposta do banco de dados"""
        start_time = time.time()
        db_conn = connections['default']
        cursor = db_conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        end_time = time.time()
        return round((end_time - start_time) * 1000, 2)  # ms


class MetricsView(View):
    """
    Endpoint para métricas da aplicação
    GET /metrics/
    """
    
    def get(self, request):
        """
        Retorna métricas detalhadas da aplicação
        """
        from dashboard.models import Ticket, Cliente, PerfilAgente
        from django.contrib.auth.models import User
        
        # Métricas básicas
        now = timezone.now()
        today = now.date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        metrics = {
            'timestamp': now.isoformat(),
            'application': {
                'name': 'iConnect Sistema de Atendimento',
                'version': getattr(settings, 'VERSION', '1.0.0'),
                'uptime_seconds': self._get_uptime()
            },
            'business_metrics': {
                'tickets': {
                    'total': Ticket.objects.count(),
                    'open': Ticket.objects.filter(status__in=['aberto', 'em_andamento']).count(),
                    'closed_today': Ticket.objects.filter(
                        status='fechado',
                        atualizado_em__date=today
                    ).count(),
                    'created_this_week': Ticket.objects.filter(
                        criado_em__date__gte=week_ago
                    ).count()
                },
                'users': {
                    'total_clients': Cliente.objects.count(),
                    'active_agents': PerfilAgente.objects.filter(status='disponivel').count(),
                    'total_users': User.objects.count(),
                    'new_users_this_month': User.objects.filter(
                        date_joined__date__gte=month_ago
                    ).count()
                }
            },
            'system_metrics': self._get_system_metrics()
        }
        
        return JsonResponse(metrics)
    
    def _get_uptime(self):
        """Calcula o uptime da aplicação"""
        try:
            import psutil
            boot_time = psutil.boot_time()
            return int(time.time() - boot_time)
        except:
            return 0
    
    def _get_system_metrics(self):
        """Coleta métricas do sistema"""
        try:
            import psutil
            
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory': {
                    'total_gb': round(memory.total / (1024**3), 2),
                    'used_gb': round(memory.used / (1024**3), 2),
                    'percent': memory.percent
                },
                'disk': {
                    'total_gb': round(disk.total / (1024**3), 2),
                    'used_gb': round(disk.used / (1024**3), 2),
                    'free_gb': round(disk.free / (1024**3), 2),
                    'percent': round((disk.used / disk.total) * 100, 2)
                },
                'load_average': psutil.getloadavg()
            }
        except ImportError:
            return {'error': 'psutil not installed'}


class MonitoringMiddleware:
    """
    Middleware para coleta de métricas de request/response
    """
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Marca o início da request
        start_time = time.time()
        
        # Processa a request
        response = self.get_response(request)
        
        # Calcula o tempo de resposta
        duration = time.time() - start_time
        
        # Log de métricas
        logger.info(
            f"REQUEST: {request.method} {request.path} "
            f"| Status: {response.status_code} "
            f"| Duration: {duration:.3f}s "
            f"| User: {getattr(request.user, 'username', 'anonymous')} "
            f"| IP: {self._get_client_ip(request)}"
        )
        
        # Headers de resposta para debugging
        if settings.DEBUG:
            response['X-Response-Time'] = f"{duration:.3f}s"
            response['X-Process-Time'] = str(int(duration * 1000))
        
        return response

    def _get_client_ip(self, request):
        """Obtém o IP real do cliente"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def process_exception(self, request, exception):
        """Log de exceções"""
        logger.error(
            f"EXCEPTION: {request.method} {request.path} "
            f"| Exception: {type(exception).__name__}: {str(exception)} "
            f"| User: {getattr(request.user, 'username', 'anonymous')} "
            f"| IP: {self._get_client_ip(request)}",
            exc_info=True
        )
        return None
