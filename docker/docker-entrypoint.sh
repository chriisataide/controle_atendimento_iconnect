#!/bin/bash

# =================================================
# SCRIPT DE ENTRADA - iConnect Container
# =================================================

set -e

echo "🚀 Iniciando container iConnect..."

# Criar diretórios necessários se não existirem
echo "📁 Criando diretórios..."
mkdir -p /app/logs
mkdir -p /app/staticfiles
mkdir -p /app/media

# Usar diretórios locais para logs (não /var/log)
mkdir -p /app/logs/django

# Garantir permissões corretas
echo "🔐 Configurando permissões..."
chmod -R 755 /app/logs 2>/dev/null || true
chmod -R 755 /app/staticfiles 2>/dev/null || true
chmod -R 755 /app/media 2>/dev/null || true

# Aguardar banco de dados estar disponível
echo "🗄️  Aguardando banco de dados..."
while ! nc -z ${DB_HOST:-db} ${DB_PORT:-5432}; do
    echo "   Aguardando PostgreSQL..."
    sleep 2
done
echo "✅ Banco de dados disponível!"

# Executar migrações
echo "🔄 Executando migrações..."
python manage.py migrate --noinput

# Coletar arquivos estáticos
echo "📦 Coletando arquivos estáticos..."
python manage.py collectstatic --noinput

# Importar Pontos de Venda (idempotente - só importa se não existirem)
echo "📍 Verificando importação de Pontos de Venda..."
python manage.py importar_pdv

# Criar superusuário se não existir
# SEGURANÇA: Usa variáveis de ambiente em vez de credenciais hardcoded
echo "👤 Verificando superusuário..."
python manage.py shell << 'PYEOF'
from django.contrib.auth import get_user_model
import os
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    username = os.environ.get('DJANGO_SUPERUSER_USERNAME', 'admin')
    email = os.environ.get('DJANGO_SUPERUSER_EMAIL', 'admin@iconnect.com')
    password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
    if not password:
        print('⚠️  DJANGO_SUPERUSER_PASSWORD não definida! Superusuário NÃO criado.')
    else:
        User.objects.create_superuser(username=username, email=email, password=password)
        print(f'✅ Superusuário criado: {username}')
else:
    print('✅ Superusuário já existe')
PYEOF

echo "🎉 Container iConnect pronto!"

# Executar comando passado como argumento
exec "$@"
