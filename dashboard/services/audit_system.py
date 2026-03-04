"""
Sistema de Auditoria do iConnect
Implementa logging e monitoramento de ações do sistema
"""

import logging
from datetime import datetime
from functools import wraps

from django.contrib.auth import get_user_model
from django.utils import timezone


def get_client_ip(request):
    """Obtém o IP do cliente considerando proxies"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


User = get_user_model()
logger = logging.getLogger("audit")

# ========== DECORADORES DE AUDITORIA ==========


def audit_action(
    action=None, action_type=None, description=None, severity="LOW", module="system", resource_type="unknown"
):
    """
    Decorator para auditar ações do usuário

    Args:
        action: Tipo da ação (para compatibilidade com views existentes)
        action_type: Tipo da ação (create, update, delete, view, etc.)
        description: Descrição personalizada da ação
        severity: Nível de severidade (LOW, MEDIUM, HIGH, CRITICAL)
        module: Módulo/componente onde a ação ocorre
        resource_type: Tipo do recurso (ticket, user, etc.)
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Executar função original
            result = view_func(request, *args, **kwargs)

            try:
                # Usar action ou action_type (prioridade para action se fornecido)
                final_action = action or action_type or "unknown"
                final_description = description or f"{final_action} in {view_func.__name__}"

                # Coletar dados da auditoria
                audit_data = {
                    "user_id": request.user.id if request.user.is_authenticated else None,
                    "username": request.user.username if request.user.is_authenticated else "Anonymous",
                    "action_type": final_action,
                    "description": final_description,
                    "severity": severity,
                    "module": module,
                    "resource_type": resource_type,
                    "timestamp": timezone.now().isoformat(),
                    "ip_address": get_client_ip(request),
                    "user_agent": request.META.get("HTTP_USER_AGENT", "Unknown"),
                    "path": request.path,
                    "method": request.method,
                    "args": str(args),
                    "kwargs": str(kwargs),
                }

                # Log da auditoria
                logger.info(f"Action: {action_type} on {resource_type}", extra=audit_data)

            except Exception as e:
                logger.error(f"Error in audit logging: {e}")

            return result

        return wrapper

    return decorator


def audit_model_changes(model_class):
    """
    Decorator para auditar mudanças em modelos

    Args:
        model_class: Classe do modelo a ser auditado
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Capturar estado antes (se for update)
            before_state = None
            if "pk" in kwargs:
                try:
                    instance = model_class.objects.get(pk=kwargs["pk"])
                    before_state = model_to_dict(instance)
                except model_class.DoesNotExist:
                    before_state = None

            # Executar função original
            result = view_func(request, *args, **kwargs)

            try:
                # Capturar estado depois
                after_state = None
                if "pk" in kwargs:
                    try:
                        instance = model_class.objects.get(pk=kwargs["pk"])
                        after_state = model_to_dict(instance)
                    except model_class.DoesNotExist:
                        after_state = None

                # Log das mudanças
                if before_state != after_state:
                    audit_data = {
                        "user_id": request.user.id if request.user.is_authenticated else None,
                        "model": model_class.__name__,
                        "object_id": kwargs.get("pk"),
                        "before": before_state,
                        "after": after_state,
                        "timestamp": timezone.now().isoformat(),
                    }

                    logger.info(f"Model changed: {model_class.__name__}", extra=audit_data)

            except Exception as e:
                logger.error(f"Error in model audit logging: {e}")

            return result

        return wrapper

    return decorator


def audit_sensitive_data_access(data_type="sensitive_data"):
    """
    Decorator para auditar acesso a dados sensíveis

    Args:
        data_type: Tipo de dados sensíveis acessados
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Log do acesso
            try:
                audit_data = {
                    "user_id": request.user.id if request.user.is_authenticated else None,
                    "username": request.user.username if request.user.is_authenticated else "Anonymous",
                    "data_type": data_type,
                    "access_type": "read",
                    "timestamp": timezone.now().isoformat(),
                    "ip_address": get_client_ip(request),
                    "path": request.path,
                }

                logger.warning(f"Sensitive data access: {data_type}", extra=audit_data)

            except Exception as e:
                logger.error(f"Error in sensitive data audit: {e}")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# ========== UTILITÁRIOS ==========


def get_client_ip(request):
    """Obtém o IP real do cliente"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def model_to_dict(instance):
    """Converte instância do modelo para dicionário"""
    try:
        from django.forms.models import model_to_dict as django_model_to_dict

        return django_model_to_dict(instance)
    except Exception:
        # Fallback manual
        data = {}
        for field in instance._meta.fields:
            value = getattr(instance, field.name)
            if isinstance(value, datetime):
                value = value.isoformat()
            elif hasattr(value, "pk"):
                value = value.pk
            data[field.name] = value
        return data


# ========== LOGGER DE AUDITORIA ==========


class AuditLogger:
    """Classe para logging estruturado de auditoria"""

    @staticmethod
    def log_user_action(user, action, resource=None, details=None):
        """
        Log de ação do usuário

        Args:
            user: Usuário que executou a ação
            action: Ação executada
            resource: Recurso afetado (opcional)
            details: Detalhes adicionais (opcional)
        """
        try:
            audit_data = {
                "user_id": user.id if user and user.is_authenticated else None,
                "username": user.username if user and user.is_authenticated else "System",
                "action": action,
                "resource": str(resource) if resource else None,
                "details": details or {},
                "timestamp": timezone.now().isoformat(),
            }

            logger.info(f"User action: {action}", extra=audit_data)

        except Exception as e:
            logger.error(f"Error logging user action: {e}")

    @staticmethod
    def log_system_event(event_type, message, details=None):
        """
        Log de evento do sistema

        Args:
            event_type: Tipo do evento
            message: Mensagem do evento
            details: Detalhes adicionais
        """
        try:
            event_data = {
                "event_type": event_type,
                "message": message,
                "details": details or {},
                "timestamp": timezone.now().isoformat(),
            }

            logger.info(f"System event: {event_type}", extra=event_data)

        except Exception as e:
            logger.error(f"Error logging system event: {e}")

    @staticmethod
    def log_security_event(event_type, user, ip_address, details=None):
        """
        Log de evento de segurança

        Args:
            event_type: Tipo do evento de segurança
            user: Usuário relacionado (se houver)
            ip_address: Endereço IP
            details: Detalhes adicionais
        """
        try:
            security_data = {
                "event_type": event_type,
                "user_id": user.id if user and user.is_authenticated else None,
                "username": user.username if user and user.is_authenticated else "Anonymous",
                "ip_address": ip_address,
                "details": details or {},
                "timestamp": timezone.now().isoformat(),
            }

            logger.warning(f"Security event: {event_type}", extra=security_data)

        except Exception as e:
            logger.error(f"Error logging security event: {e}")


# ========== MIDDLEWARE DE AUDITORIA ==========


class AuditMiddleware:
    """Middleware para auditoria automática de requests"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Log do request
        start_time = timezone.now()

        response = self.get_response(request)

        # Log da resposta
        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()

        try:
            audit_data = {
                "user_id": request.user.id if request.user.is_authenticated else None,
                "path": request.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration": duration,
                "ip_address": get_client_ip(request),
                "user_agent": request.META.get("HTTP_USER_AGENT", "Unknown"),
                "timestamp": start_time.isoformat(),
            }

            # Log apenas requests importantes (não assets)
            if not request.path.startswith("/static/") and not request.path.startswith("/media/"):
                logger.info(f"Request: {request.method} {request.path}", extra=audit_data)

        except Exception as e:
            logger.error(f"Error in audit middleware: {e}")

        return response


# ========== CONFIGURAÇÕES ==========

AUDIT_SETTINGS = {
    "LOG_ALL_REQUESTS": False,
    "LOG_SENSITIVE_DATA": True,
    "LOG_MODEL_CHANGES": True,
    "LOG_USER_ACTIONS": True,
    "RETENTION_DAYS": 90,
}

# ========== RELATÓRIOS DE AUDITORIA ==========


def generate_audit_report(start_date=None, end_date=None, user=None):
    """
    Gera relatório de auditoria

    Args:
        start_date: Data de início
        end_date: Data de fim
        user: Usuário específico (opcional)

    Returns:
        dict: Dados do relatório
    """
    try:
        # Aqui você implementaria a lógica para gerar relatórios
        # baseado nos logs de auditoria armazenados

        report_data = {
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            "user": user.username if user else "All users",
            "generated_at": timezone.now().isoformat(),
            "total_events": 0,  # Implementar contagem real
            "events_by_type": {},  # Implementar agrupamento
            "security_events": 0,  # Implementar contagem
        }

        return report_data

    except Exception as e:
        logger.error(f"Error generating audit report: {e}")
        return {"error": str(e)}
