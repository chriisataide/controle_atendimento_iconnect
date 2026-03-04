"""
Módulo de criptografia para campos sensíveis.

Implementa criptografia Fernet (AES-128-CBC) para campos de modelo Django
que armazenam credenciais, tokens e segredos.

Padrão: BACEN/PCI-DSS — dados sensíveis devem ser criptografados em repouso.

Uso:
    from dashboard.crypto import EncryptedCharField, EncryptedTextField

    class MyModel(models.Model):
        api_key = EncryptedCharField(max_length=255)
        token = EncryptedTextField()
"""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

logger = logging.getLogger("dashboard")


def _get_fernet_key():
    """
    Obtém a chave Fernet a partir do SECRET_KEY do Django.

    Em produção, use uma variável de ambiente dedicada (FIELD_ENCRYPTION_KEY).
    A chave deve ser um token Fernet válido de 32 bytes URL-safe base64.
    """
    # Prioridade: variável de ambiente dedicada
    key = getattr(settings, "FIELD_ENCRYPTION_KEY", None)
    if key:
        if isinstance(key, str):
            key = key.encode("utf-8")
        return key

    # Fallback: derivar do SECRET_KEY do Django (não ideal para produção)
    import hashlib

    secret = settings.SECRET_KEY.encode("utf-8")
    # Derivar chave de 32 bytes e codificar em base64 URL-safe (formato Fernet)
    derived = hashlib.sha256(secret).digest()
    return base64.urlsafe_b64encode(derived)


def _get_fernet():
    """Retorna instância Fernet configurada."""
    return Fernet(_get_fernet_key())


def encrypt_value(value):
    """
    Criptografa um valor string usando Fernet.

    Args:
        value: String para criptografar

    Returns:
        String criptografada (base64) prefixada com 'enc::' para identificação
    """
    if not value:
        return value

    # Não re-criptografar valores já criptografados
    if isinstance(value, str) and value.startswith("enc::"):
        return value

    f = _get_fernet()
    encrypted = f.encrypt(value.encode("utf-8"))
    return f'enc::{encrypted.decode("utf-8")}'


def decrypt_value(value):
    """
    Descriptografa um valor criptografado com Fernet.

    Args:
        value: String criptografada (prefixada com 'enc::')

    Returns:
        String original descriptografada
    """
    if not value:
        return value

    if isinstance(value, str) and value.startswith("enc::"):
        try:
            f = _get_fernet()
            encrypted_data = value[5:]  # Remove 'enc::' prefix
            decrypted = f.decrypt(encrypted_data.encode("utf-8"))
            return decrypted.decode("utf-8")
        except (InvalidToken, Exception) as e:
            logger.error("Falha ao descriptografar campo: %s", type(e).__name__)
            # Retorna valor vazio por segurança em vez de expor o ciphertext
            return ""

    # Valor não está criptografado (dados legados) — retorna como está
    return value


class EncryptedCharField(models.CharField):
    """
    CharField que criptografa dados em repouso usando Fernet (AES-128-CBC).

    Os dados são automaticamente criptografados ao salvar e
    descriptografados ao ler do banco de dados.
    """

    def get_prep_value(self, value):
        """Criptografa antes de salvar no banco."""
        value = super().get_prep_value(value)
        return encrypt_value(value)

    def from_db_value(self, value, expression, connection):
        """Descriptografa ao ler do banco."""
        return decrypt_value(value)

    def to_python(self, value):
        """Descriptografa para uso em Python."""
        value = super().to_python(value)
        if value and isinstance(value, str) and value.startswith("enc::"):
            return decrypt_value(value)
        return value


class EncryptedTextField(models.TextField):
    """
    TextField que criptografa dados em repouso usando Fernet (AES-128-CBC).

    Os dados são automaticamente criptografados ao salvar e
    descriptografados ao ler do banco de dados.
    """

    def get_prep_value(self, value):
        """Criptografa antes de salvar no banco."""
        value = super().get_prep_value(value)
        return encrypt_value(value)

    def from_db_value(self, value, expression, connection):
        """Descriptografa ao ler do banco."""
        return decrypt_value(value)

    def to_python(self, value):
        """Descriptografa para uso em Python."""
        value = super().to_python(value)
        if value and isinstance(value, str) and value.startswith("enc::"):
            return decrypt_value(value)
        return value
