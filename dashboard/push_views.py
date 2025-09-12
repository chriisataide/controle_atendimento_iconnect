from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
# Versão temporária simplificada das Push Views
# TODO: Instalar pywebpush e ativar modelos completos

import json
import logging

logger = logging.getLogger(__name__)

@login_required
@require_http_methods(["GET"])
def get_public_key(request):
    """Retorna a chave pública VAPID para o cliente"""
    return JsonResponse({
        'public_key': 'BEl62iUYgUivxIkv69yViEuiBIa40HI0u2Zd43v_rYgL6-xfEkUNECDqJf0pv8VFJdw4aBQQ1hvGsq-cDdfqjgI',
        'status': 'mock'
    })

@login_required  
@csrf_exempt
@require_http_methods(["POST"])
def subscribe_push(request):
    """Inscreve o usuário para notificações push - versão mock"""
    try:
        data = json.loads(request.body)
        logger.info(f"Mock push subscription for user {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'created': True,
            'subscription_id': 1,
            'status': 'mock'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Dados JSON inválidos'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao inscrever usuário {request.user.id}: {str(e)}")
        return JsonResponse({
            'error': 'Erro interno do servidor'
        }, status=500)

@login_required
@csrf_exempt  
@require_http_methods(["POST"])
def unsubscribe_push(request):
    """Remove inscrição do usuário para notificações push - versão mock"""
    try:
        data = json.loads(request.body)
        logger.info(f"Mock push unsubscription for user {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'deleted': True,
            'status': 'mock'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Dados JSON inválidos'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao desinscrever usuário {request.user.id}: {str(e)}")
        return JsonResponse({
            'error': 'Erro interno do servidor'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def update_preferences(request):
    """Atualiza preferências de notificação do usuário - versão mock"""
    try:
        data = json.loads(request.body)
        preferences = data.get('preferences', {})
        logger.info(f"Mock preferences update for user {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'preferences': {
                'tickets': preferences.get('tickets', True),
                'chat': preferences.get('chat', True),
                'system': preferences.get('system', True),
                'quiet_hours': preferences.get('quiet_hours', False),
                'quiet_start': preferences.get('quiet_start', '22:00'),
                'quiet_end': preferences.get('quiet_end', '08:00'),
            },
            'status': 'mock'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'error': 'Dados JSON inválidos'
        }, status=400)
    except Exception as e:
        logger.error(f"Erro ao atualizar preferências do usuário {request.user.id}: {str(e)}")
        return JsonResponse({
            'error': 'Erro interno do servidor'
        }, status=500)

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def test_notification(request):
    """Envia uma notificação de teste para o usuário - versão mock"""
    try:
        logger.info(f"Mock test notification for user {request.user.id}")
        
        return JsonResponse({
            'success': True,
            'sent': 1,
            'failed': 0,
            'status': 'mock'
        })
        
    except Exception as e:
        logger.error(f"Erro ao enviar notificação de teste para usuário {request.user.id}: {str(e)}")
        return JsonResponse({
            'error': 'Erro interno do servidor'
        }, status=500)
