"""
Webhook Service — Entrega de webhooks outbound com retry via Celery
"""
import hashlib
import hmac
import json
import logging
import time

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)


class WebhookService:
    """Servico para despacho de webhooks"""

    @staticmethod
    def trigger_event(event_type: str, payload: dict):
        """Dispara webhook para todos os endpoints inscritos neste evento"""
        from dashboard.models import WebhookEndpoint

        endpoints = WebhookEndpoint.objects.filter(
            is_active=True,
            failure_count__lt=10
        )

        for endpoint in endpoints:
            events = endpoint.events or []
            if event_type in events or '*' in events:
                # Despachar via Celery se disponível
                try:
                    from dashboard.tasks import deliver_webhook
                    deliver_webhook.delay(endpoint.id, event_type, payload)
                except Exception:
                    # Fallback síncrono
                    WebhookService._deliver(endpoint, event_type, payload)

    @staticmethod
    def _deliver(endpoint, event_type: str, payload: dict, attempt: int = 1):
        """Entrega síncrona de webhook com log"""
        from dashboard.models import WebhookDelivery

        body = json.dumps({
            "event": event_type,
            "timestamp": timezone.now().isoformat(),
            "data": payload,
        }, default=str)

        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Event": event_type,
            "X-Webhook-Delivery": str(timezone.now().timestamp()),
        }

        # HMAC signature
        if endpoint.secret:
            signature = hmac.new(
                endpoint.secret.encode(),
                body.encode(),
                hashlib.sha256
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"

        # Custom headers
        if endpoint.headers:
            headers.update(endpoint.headers)

        start = time.time()
        delivery = WebhookDelivery(
            webhook=endpoint,
            event=event_type,
            payload=json.loads(body),
            attempt=attempt,
        )

        try:
            resp = requests.post(
                endpoint.url,
                data=body,
                headers=headers,
                timeout=10,
            )
            delivery.response_status = resp.status_code
            delivery.response_body = resp.text[:1000]
            delivery.success = 200 <= resp.status_code < 300
            delivery.duration_ms = int((time.time() - start) * 1000)

            if delivery.success:
                endpoint.failure_count = 0
                endpoint.last_triggered = timezone.now()
            else:
                endpoint.failure_count += 1

        except requests.RequestException as e:
            delivery.response_body = str(e)[:1000]
            delivery.success = False
            delivery.duration_ms = int((time.time() - start) * 1000)
            endpoint.failure_count += 1
            logger.error(f"Webhook delivery failed for {endpoint.nome}: {e}")

        delivery.save()
        endpoint.save(update_fields=['failure_count', 'last_triggered'])

        # Desativar após muitas falhas
        if endpoint.failure_count >= 10:
            endpoint.is_active = False
            endpoint.save(update_fields=['is_active'])
            logger.warning(f"Webhook {endpoint.nome} desativado após {endpoint.failure_count} falhas")

        return delivery


webhook_service = WebhookService()
