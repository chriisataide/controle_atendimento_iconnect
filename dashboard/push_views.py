from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils import timezone
from pywebpush import webpush, WebPushException

import json
import logging
from .models_push import PushSubscription

logger = logging.getLogger(__name__)

# VAPID keys - configure in settings
VAPID_PUBLIC_KEY = getattr(settings, 'VAPID_PUBLIC_KEY', 'BEl62iUYgUivxIkv69yViEuiBIa40HI0u2Zd43v_rYgL6-xfEkUNECDqJf0pv8VFJdw4aBQQ1hvGsq-cDdfqjgI')
VAPID_PRIVATE_KEY = getattr(settings, 'VAPID_PRIVATE_KEY', '')
VAPID_CLAIMS = getattr(settings, 'VAPID_CLAIMS', {"sub": "mailto:admin@iconnect.com"})

@login_required
@require_http_methods(["GET"])
def get_public_key(request):
    """Retorna a chave pública VAPID para o cliente"""
    return JsonResponse({
        'public_key': VAPID_PUBLIC_KEY,
        'status': 'active'
    })

@login_required  
@require_http_methods(["POST"])
def subscribe_push(request):
    """Inscreve o usuário para notificações push"""
    try:
        data = json.loads(request.body)
        subscription_info = data.get('subscription')
        
        if not subscription_info:
            return JsonResponse({'success': False, 'error': 'Subscription data missing'})
        
        # Criar ou atualizar subscription
        subscription, created = PushSubscription.objects.update_or_create(
            user=request.user,
            defaults={
                'endpoint': subscription_info.get('endpoint'),
                'p256dh': subscription_info.get('keys', {}).get('p256dh'),
                'auth': subscription_info.get('keys', {}).get('auth'),
                'is_active': True
            }
        )
        
        logger.info(f"Push subscription {'created' if created else 'updated'} for user {request.user.username}")
        
        return JsonResponse({
            'success': True,
            'message': 'Subscription successful',
            'subscription_id': subscription.id
        })
        
    except Exception as e:
        logger.error(f"Error in push subscription: {str(e)}")
        return JsonResponse({'success': False, 'error': 'Subscription failed'})
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
