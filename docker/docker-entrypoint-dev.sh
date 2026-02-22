#!/bin/bash

# =================================================
# SCRIPT DE DESENVOLVIMENTO - iConnect Container
# =================================================

set -e

echo "🚀 Iniciando iConnect em modo DESENVOLVIMENTO..."

# Criar diretórios necessários se não existirem
echo "📁 Criando diretórios..."
mkdir -p /app/logs/django
mkdir -p /app/staticfiles
mkdir -p /app/media

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

echo "🎉 Iniciando servidor Django de desenvolvimento..."
python manage.py runserver 0.0.0.0:8000
