"""
Sistema de Segurança do iConnect
Implementa funcionalidades de rate limiting, auditoria e proteção
"""

import hashlib
import logging
import time
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone

User = get_user_model()
logger = logging.getLogger(__name__)

# ========== RATE LIMITING ==========


def get_client_ip(request):
    """Obtém o IP real do cliente"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


def rate_limit(max_requests=60, window_seconds=60, key_func=None):
    """
    Decorator para rate limiting

    Args:
        max_requests: Número máximo de requests
        window_seconds: Janela de tempo em segundos
        key_func: Função personalizada para gerar chave do cache
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Gerar chave do cache
            if key_func:
                cache_key = key_func(request)
            else:
                ip = get_client_ip(request)
                cache_key = f"rate_limit:{view_func.__name__}:{ip}"

            # Verificar rate limit
            current_requests = cache.get(cache_key, 0)

            if current_requests >= max_requests:
                # Log da tentativa bloqueada
                log_suspicious_activity_func(
                    request, f"Rate limit exceeded for {view_func.__name__}", "rate_limit_exceeded"
                )

                if request.headers.get("Accept", "").startswith("application/json"):
                    return JsonResponse(
                        {
                            "error": "Too many requests",
                            "detail": f"Rate limit exceeded. Try again in {window_seconds} seconds.",
                        },
                        status=429,
                    )
                else:
                    return HttpResponse("Too many requests. Please try again later.", status=429)

            # Incrementar contador
            cache.set(cache_key, current_requests + 1, window_seconds)

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


# ========== LOGGING DE ATIVIDADES SUSPEITAS ==========


def log_suspicious_activity_func(request, description, activity_type="suspicious"):
    """
    Registra atividade suspeita no sistema

    Args:
        request: Request object do Django
        description: Descrição da atividade
        activity_type: Tipo da atividade (suspicious, rate_limit, etc.)
    """
    try:
        ip = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")
        user = request.user if request.user.is_authenticated else None

        # Dados da atividade suspeita
        log_data = {
            "ip": ip,
            "user_agent": user_agent,
            "user_id": user.id if user else None,
            "username": user.username if user else "Anonymous",
            "description": description,
            "activity_type": activity_type,
            "timestamp": timezone.now().isoformat(),
            "path": request.path,
            "method": request.method,
        }

        # Log no sistema de logging
        logger.warning(f"Suspicious Activity: {description}", extra=log_data)

        # Salvar em cache para análise posterior
        cache_key = f"suspicious_activity:{int(time.time())}"
        cache.set(cache_key, log_data, 3600)  # 1 hora

        # Se for muito suspeito, alertar admins
        if activity_type in ["rate_limit_exceeded", "multiple_login_failures"]:
            alert_administrators(log_data)

    except Exception as e:
        logger.error(f"Error logging suspicious activity: {e}")


def log_suspicious_activity(description="Suspicious activity detected"):
    """
    Decorator para log automático de atividades suspeitas

    Args:
        description: Descrição da atividade suspeita
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                # Executar a view
                response = view_func(request, *args, **kwargs)

                # Log apenas de respostas com erro (status >= 400)
                if hasattr(response, "status_code") and response.status_code >= 400:
                    log_suspicious_activity_func(request, f"{description} - {view_func.__name__} [HTTP {response.status_code}]")

                return response
            except Exception as e:
                # Log do erro como atividade suspeita
                log_suspicious_activity_func(request, f"Error in {view_func.__name__}: {str(e)}", "error")
                raise

        return wrapper

    return decorator


def alert_administrators(log_data):
    """Alerta administradores sobre atividade crítica via email e log"""
    try:
        from django.core.mail import mail_admins

        logger.critical(f"SECURITY ALERT: {log_data['description']}", extra=log_data)

        # Cache para evitar spam de alertas
        alert_key = f"alert_sent:{log_data['ip']}:{log_data['activity_type']}"
        if not cache.get(alert_key):
            cache.set(alert_key, True, 300)  # 5 minutos de cooldown

            # Enviar email para administradores (ADMINS no settings)
            subject = (
                f"[iConnect Security] {log_data['activity_type']}: {log_data.get('description', 'Atividade suspeita')}"
            )
            message = (
                f"Descri\u00e7\u00e3o: {log_data.get('description', 'N/A')}\n"
                f"IP: {log_data.get('ip', 'N/A')}\n"
                f"Usu\u00e1rio: {log_data.get('username', 'An\u00f4nimo')}\n"
                f"Path: {log_data.get('path', 'N/A')}\n"
                f"M\u00e9todo: {log_data.get('method', 'N/A')}\n"
                f"User-Agent: {log_data.get('user_agent', 'N/A')}\n"
                f"Hor\u00e1rio: {log_data.get('timestamp', 'N/A')}\n"
            )
            try:
                mail_admins(subject, message, fail_silently=True)
            except Exception:
                pass  # Se email falhar, n\u00e3o impedir o fluxo

    except Exception as e:
        logger.error(f"Error alerting administrators: {e}")


# ========== MIDDLEWARE DE SEGURANÇA ==========


class SecurityHeadersMiddleware:
    """Middleware para adicionar headers de segurança.

    Quando o ``CSPNonceMiddleware`` está ativo, o header CSP usa
    ``'nonce-<value>'`` em vez de  ``'unsafe-inline'``.  Browsers modernos
    ignoram ``'unsafe-inline'`` quando um nonce está presente, oferecendo
    proteção real contra XSS.  O ``'unsafe-inline'`` é mantido como
    fallback para browsers legados que não suportam nonces.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Headers de segurança
        response["X-Content-Type-Options"] = "nosniff"
        response["X-Frame-Options"] = "DENY"
        response["X-XSS-Protection"] = "1; mode=block"
        response["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # CSP (Content Security Policy) com suporte a nonce
        if not settings.DEBUG:
            nonce = getattr(request, "csp_nonce", "")
            nonce_directive = f"'nonce-{nonce}' " if nonce else ""

            response["Content-Security-Policy"] = (
                "default-src 'self'; "
                f"script-src 'self' {nonce_directive}'unsafe-inline' "
                "https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.socket.io; "
                f"style-src 'self' {nonce_directive}'unsafe-inline' "
                "https://fonts.googleapis.com https://cdn.jsdelivr.net; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: https:; "
                "connect-src 'self' ws: wss: https://cdn.jsdelivr.net https://cdnjs.cloudflare.com https://cdn.socket.io; "
                "worker-src 'self'; "
                "frame-ancestors 'none'; "
                "base-uri 'self'; "
                "form-action 'self';"
            )

        # Permissions-Policy
        response["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), " "payment=(), usb=(), magnetometer=()"
        )

        return response


# ========== VALIDAÇÕES DE SEGURANÇA ==========


def validate_file_upload(uploaded_file):
    """
    Valida arquivos enviados pelo usuário com verificação de extensão,
    MIME type e magic bytes.

    Args:
        uploaded_file: Arquivo enviado

    Returns:
        tuple: (is_valid, error_message)
    """
    # Tamanho máximo (10MB)
    max_size = 10 * 1024 * 1024
    if uploaded_file.size > max_size:
        return False, "Arquivo muito grande. Máximo 10MB."

    # Extensões permitidas e seus MIME types esperados
    ALLOWED_TYPES = {
        ".jpg": ["image/jpeg"],
        ".jpeg": ["image/jpeg"],
        ".png": ["image/png"],
        ".gif": ["image/gif"],
        ".pdf": ["application/pdf"],
        ".doc": ["application/msword"],
        ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
        ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
        ".xls": ["application/vnd.ms-excel"],
        ".csv": ["text/csv", "application/csv"],
        ".txt": ["text/plain"],
    }

    # Magic bytes para validação de conteúdo real
    MAGIC_BYTES = {
        ".jpg": [b"\xff\xd8\xff"],
        ".jpeg": [b"\xff\xd8\xff"],
        ".png": [b"\x89PNG\r\n\x1a\n"],
        ".gif": [b"GIF87a", b"GIF89a"],
        ".pdf": [b"%PDF"],
    }

    import os

    file_extension = os.path.splitext(uploaded_file.name.lower())[1]

    if file_extension not in ALLOWED_TYPES:
        return False, f"Tipo de arquivo não permitido: {file_extension}"

    # Verificar MIME type (Content-Type header)
    content_type = getattr(uploaded_file, "content_type", "")
    if content_type and content_type not in ALLOWED_TYPES[file_extension]:
        logger.warning(f"Upload rejeitado: extensão {file_extension} com MIME type {content_type}")
        return False, "Tipo de arquivo não corresponde à extensão."

    # Verificar magic bytes se disponíveis
    if file_extension in MAGIC_BYTES and hasattr(uploaded_file, "read"):
        header = uploaded_file.read(16)
        uploaded_file.seek(0)

        expected_magics = MAGIC_BYTES[file_extension]
        if not any(header.startswith(magic) for magic in expected_magics):
            logger.warning(f"Upload rejeitado: {uploaded_file.name} falhou verificação de magic bytes")
            return False, "Conteúdo do arquivo não corresponde ao tipo declarado."

    # Verificar conteúdo malicioso
    if hasattr(uploaded_file, "read"):
        content = uploaded_file.read(4096)  # Ler primeiros 4KB
        uploaded_file.seek(0)

        # Padrões perigosos em qualquer tipo de arquivo
        suspicious_patterns = [
            b"<script",
            b"javascript:",
            b"<?php",
            b"<%",
            b"eval(",
            b"exec(",
            b"import os",
            b"subprocess",
            b"__import__",
        ]
        content_lower = content.lower()
        for pattern in suspicious_patterns:
            if pattern in content_lower:
                logger.warning(f"Upload rejeitado: conteúdo malicioso detectado em {uploaded_file.name}")
                return False, "Conteúdo malicioso detectado no arquivo."

    # Sanitizar nome do arquivo (prevenir path traversal)
    import re

    safe_name = re.sub(r"[^\w\-.]", "_", uploaded_file.name)
    if safe_name != uploaded_file.name:
        uploaded_file.name = safe_name

    return True, ""


def generate_csrf_token():
    """Gera token CSRF personalizado"""
    import secrets

    return secrets.token_urlsafe(32)


def hash_sensitive_data(data):
    """Hash de dados sensíveis para auditoria"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()[:16]  # Primeiros 16 chars


# ========== MONITORAMENTO ==========


def track_user_activity(user, activity, details=None):
    """
    Rastreia atividade do usuário para análise de comportamento

    Args:
        user: Usuário
        activity: Tipo de atividade
        details: Detalhes adicionais
    """
    try:
        activity_data = {
            "user_id": user.id,
            "username": user.username,
            "activity": activity,
            "details": details or {},
            "timestamp": timezone.now().isoformat(),
        }

        # Salvar no cache para análise
        cache_key = f"user_activity:{user.id}:{int(time.time())}"
        cache.set(cache_key, activity_data, 86400)  # 24 horas

    except Exception as e:
        logger.error(f"Error tracking user activity: {e}")


# ========== CONFIGURAÇÕES PADRÃO ==========

SECURITY_SETTINGS = {
    "LOGIN_RATE_LIMIT": {
        "max_attempts": 5,
        "window_seconds": 300,  # 5 minutos
    },
    "API_RATE_LIMIT": {
        "max_requests": 100,
        "window_seconds": 3600,  # 1 hora
    },
    "SESSION_TIMEOUT": 3600,  # 1 hora
    "PASSWORD_MIN_LENGTH": 8,
    "ENABLE_2FA": False,  # Para implementação futura
}
