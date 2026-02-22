"""
Email Inbound Service — Recebimento de emails via IMAP para criacao de tickets
"""
import email
import imaplib
import logging
import re
from email.header import decode_header
from email.utils import parseaddr

from django.utils import timezone

logger = logging.getLogger(__name__)


class EmailInboundService:
    """Servico de recebimento e processamento de emails"""

    def check_all_accounts(self):
        """Verificar todas as contas de email ativas"""
        from dashboard.models import EmailAccount
        accounts = EmailAccount.objects.filter(is_active=True)
        total_processed = 0

        for account in accounts:
            try:
                count = self.check_account(account)
                total_processed += count
                account.last_checked = timezone.now()
                account.save(update_fields=['last_checked'])
            except Exception as e:
                logger.error(f"Erro ao verificar conta {account.email}: {e}")

        return total_processed

    def check_account(self, account) -> int:
        """Verificar uma conta de email específica"""
        from dashboard.models import InboundEmail

        try:
            if account.use_ssl:
                mail = imaplib.IMAP4_SSL(account.server, account.port)
            else:
                mail = imaplib.IMAP4(account.server, account.port)

            mail.login(account.username, account.password)
            mail.select(account.folder)

            # Buscar emails não lidos
            status, messages = mail.search(None, 'UNSEEN')
            if status != 'OK':
                return 0

            email_ids = messages[0].split()
            processed = 0

            for eid in email_ids[:50]:  # Processar max 50 por vez
                try:
                    status, msg_data = mail.fetch(eid, '(RFC822)')
                    if status != 'OK':
                        continue

                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)

                    message_id = msg.get('Message-ID', '')
                    if not message_id:
                        continue

                    # Verificar se já processado
                    if InboundEmail.objects.filter(message_id=message_id).exists():
                        continue

                    inbound = self._parse_email(msg, account)
                    if inbound:
                        self._process_email(inbound, account)
                        processed += 1

                except Exception as e:
                    logger.error(f"Erro ao processar email {eid}: {e}")

            mail.logout()
            return processed

        except Exception as e:
            logger.error(f"Erro IMAP em {account.email}: {e}")
            return 0

    def _parse_email(self, msg, account):
        """Parsear email e criar registro InboundEmail"""
        from dashboard.models import InboundEmail

        message_id = msg.get('Message-ID', '')
        from_raw = msg.get('From', '')
        from_name, from_email = parseaddr(from_raw)
        subject = self._decode_header_value(msg.get('Subject', ''))
        in_reply_to = msg.get('In-Reply-To', '')
        references = msg.get('References', '')

        body_text, body_html = self._extract_body(msg)

        inbound = InboundEmail.objects.create(
            email_account=account,
            message_id=message_id,
            from_email=from_email,
            from_name=self._decode_header_value(from_name),
            subject=subject,
            body_text=body_text,
            body_html=body_html,
            in_reply_to=in_reply_to,
            references=references,
        )
        return inbound

    def _process_email(self, inbound, account):
        """Processar email — criar ticket ou adicionar interação"""
        from dashboard.models import Ticket, Cliente, InteracaoTicket

        # Verificar se é resposta a um ticket existente
        ticket = self._find_existing_ticket(inbound)

        if ticket:
            # Adicionar como interação
            InteracaoTicket.objects.create(
                ticket=ticket,
                mensagem=inbound.body_text or inbound.subject,
                tipo='resposta',
                canal='email',
            )
            inbound.ticket = ticket
            inbound.processed = True
            inbound.save(update_fields=['ticket', 'processed'])
            logger.info(f"Email adicionado como interação ao ticket {ticket.numero}")
            return

        if not account.auto_create_ticket:
            inbound.processed = True
            inbound.save(update_fields=['processed'])
            return

        # Criar novo ticket
        cliente = self._find_or_create_client(inbound.from_email, inbound.from_name)

        ticket = Ticket.objects.create(
            titulo=inbound.subject[:200] or "Email recebido",
            descricao=inbound.body_text or inbound.body_html or inbound.subject,
            cliente=cliente,
            categoria=account.default_category,
            origem='email',
        )

        inbound.ticket = ticket
        inbound.processed = True
        inbound.save(update_fields=['ticket', 'processed'])
        logger.info(f"Novo ticket {ticket.numero} criado a partir de email de {inbound.from_email}")

    def _find_existing_ticket(self, inbound):
        """Tentar encontrar ticket existente baseado em references ou subject"""
        from dashboard.models import Ticket

        # Verificar por ticket number no subject (ex: [TK-00001])
        match = re.search(r'\[TK-(\d+)\]', inbound.subject)
        if match:
            try:
                return Ticket.objects.get(numero=f"TK-{match.group(1)}")
            except Ticket.DoesNotExist:
                pass

        # Verificar por In-Reply-To
        if inbound.in_reply_to:
            from dashboard.models import InboundEmail as IE
            related = IE.objects.filter(
                message_id=inbound.in_reply_to,
                ticket__isnull=False
            ).first()
            if related:
                return related.ticket

        return None

    def _find_or_create_client(self, email_addr: str, name: str = ''):
        """Encontrar ou criar cliente pelo email"""
        from dashboard.models import Cliente

        try:
            return Cliente.objects.get(email=email_addr)
        except Cliente.DoesNotExist:
            return Cliente.objects.create(
                nome=name or email_addr.split('@')[0],
                email=email_addr,
            )

    def _decode_header_value(self, value):
        """Decodificar header de email"""
        if not value:
            return ''
        decoded_parts = decode_header(value)
        result = []
        for part, charset in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(charset or 'utf-8', errors='replace'))
            else:
                result.append(part)
        return ' '.join(result)

    def _extract_body(self, msg):
        """Extrair corpo texto e HTML do email"""
        body_text = ''
        body_html = ''

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                try:
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue
                    charset = part.get_content_charset() or 'utf-8'
                    text = payload.decode(charset, errors='replace')

                    if content_type == 'text/plain' and not body_text:
                        body_text = text
                    elif content_type == 'text/html' and not body_html:
                        body_html = text
                except Exception:
                    continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                charset = msg.get_content_charset() or 'utf-8'
                text = payload.decode(charset, errors='replace')
                if msg.get_content_type() == 'text/html':
                    body_html = text
                else:
                    body_text = text
            except Exception:
                pass

        return body_text, body_html


email_inbound_service = EmailInboundService()
