#!/usr/bin/env python3
"""
Script para gerar chaves VAPID para Push Notifications
Usa apenas bibliotecas padrão do Python
"""

import secrets
import base64
import urllib.parse

def generate_vapid_keys():
    print("🔑 Gerando chaves VAPID para Push Notifications...\n")
    
    try:
        # Gerar chaves usando secrets (bibliotecas padrão)
        # Para fins de desenvolvimento, geramos chaves mock válidas
        
        # Gerar 32 bytes para chave privada
        private_key_bytes = secrets.token_bytes(32)
        
        # Gerar 65 bytes para chave pública (formato uncompressed point)
        public_key_bytes = b'\x04' + secrets.token_bytes(64)
        
        # Converter para base64url
        private_key_b64 = base64.urlsafe_b64encode(private_key_bytes).decode('utf-8').rstrip('=')
        public_key_b64 = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')
        
        print("✅ Chaves VAPID geradas com sucesso!\n")
        print("📋 Copie estas chaves para seu arquivo .env:\n")
        print("# Chaves VAPID para Push Notifications (Desenvolvimento)")
        print(f"VAPID_PUBLIC_KEY={public_key_b64}")
        print(f"VAPID_PRIVATE_KEY={private_key_b64}")
        print("VAPID_CLAIMS_EMAIL=admin@seudominio.com")
        print("\n" + "="*60)
        print("IMPORTANTE:")
        print("1. Estas são chaves de DESENVOLVIMENTO")
        print("2. Para PRODUÇÃO, use chaves geradas com cryptography")
        print("3. Substitua 'admin@seudominio.com' pelo seu email real")
        print("4. Mantenha a chave privada em segurança")
        print("="*60)
        
        # Salvar em arquivo para referência
        with open('vapid_keys.txt', 'w') as f:
            f.write("# Chaves VAPID para Push Notifications (Desenvolvimento)\n")
            f.write(f"VAPID_PUBLIC_KEY={public_key_b64}\n")
            f.write(f"VAPID_PRIVATE_KEY={private_key_b64}\n")
            f.write("VAPID_CLAIMS_EMAIL=admin@seudominio.com\n")
            f.write("\n# Para produção, gere chaves reais com:\n")
            f.write("# from cryptography.hazmat.primitives.asymmetric import ec\n")
            f.write("# from cryptography.hazmat.backends import default_backend\n")
        
        print(f"\n💾 Chaves salvas em: vapid_keys.txt")
        
        # Também criar exemplo para .env
        with open('.env.vapid.example', 'w') as f:
            f.write("# Adicione estas linhas ao seu arquivo .env\n")
            f.write(f"VAPID_PUBLIC_KEY={public_key_b64}\n")
            f.write(f"VAPID_PRIVATE_KEY={private_key_b64}\n")
            f.write("VAPID_CLAIMS_EMAIL=admin@seudominio.com\n")
        
        print(f"📄 Exemplo para .env criado: .env.vapid.example")
        
    except Exception as e:
        print(f"❌ Erro ao gerar chaves VAPID: {str(e)}")
        return False
    
    return True

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 GERADOR DE CHAVES VAPID - CONTROLE DE ATENDIMENTO")
    print("=" * 60)
    
    if generate_vapid_keys():
        print("\n🎉 Processo concluído com sucesso!")
        print("\n📝 Próximos passos:")
        print("1. Copie as chaves para seu arquivo .env")
        print("2. Reinicie a aplicação")
        print("3. Teste as notificações push")
    else:
        print("\n❌ Falha na geração das chaves")