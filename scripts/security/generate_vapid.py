#!/usr/bin/env python
"""
Script para gerar chaves VAPID para push notifications
"""
import os
import sys
import django
from pywebpush import webpush

# Setup Django
sys.path.append('/Users/chrisataide/Documents/controle_atendimento_iconnect')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
django.setup()

def generate_vapid_keys():
    print("🔑 Gerando chaves VAPID para Push Notifications...\n")
    
    try:
        # Gerar chaves VAPID
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.backends import default_backend
        import base64
        
        # Gerar chave privada
        private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
        
        # Obter chave pública
        public_key = private_key.public_key()
        
        # Serializar chaves
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint
        )
        
        # Converter para formato base64url
        private_key_b64 = base64.urlsafe_b64encode(private_bytes).decode('utf-8').rstrip('=')
        public_key_b64 = base64.urlsafe_b64encode(public_bytes).decode('utf-8').rstrip('=')
        
        print("✅ Chaves VAPID geradas com sucesso!\n")
        print("📋 Copie estas chaves para seu arquivo .env:\n")
        print("# Chaves VAPID para Push Notifications")
        print(f"VAPID_PUBLIC_KEY={public_key_b64}")
        print(f"VAPID_PRIVATE_KEY={private_key_b64}")
        print("VAPID_CLAIMS_EMAIL=admin@seudominio.com")
        print("\n" + "="*60)
        print("IMPORTANTE:")
        print("1. Substitua 'admin@seudominio.com' pelo seu email real")
        print("2. Mantenha a chave privada em segurança")
        print("3. Use a chave pública no frontend para subscrições")
        print("="*60)
        
        # Salvar em arquivo para referência
        with open('/Users/chrisataide/Documents/controle_atendimento_iconnect/vapid_keys.txt', 'w') as f:
            f.write("# Chaves VAPID para Push Notifications\n")
            f.write(f"VAPID_PUBLIC_KEY={public_key_b64}\n")
            f.write(f"VAPID_PRIVATE_KEY={private_key_b64}\n")
            f.write("VAPID_CLAIMS_EMAIL=admin@seudominio.com\n")
        
        print(f"\n💾 Chaves salvas em: vapid_keys.txt")
        
    except Exception as e:
        print(f"❌ Erro ao gerar chaves VAPID: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    generate_vapid_keys()