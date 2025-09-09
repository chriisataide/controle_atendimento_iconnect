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
chmod -R 755 /app/logs
chmod -R 755 /app/staticfiles
chmod -R 755 /app/media

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
echo "👤 Verificando superusuário..."
python manage.py shell << EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser(
        username='admin',
        email='admin@iconnect.com',
        password='admin123'
    )
    print('✅ Superusuário criado: admin/admin123')
else:
    print('✅ Superusuário já existe')
EOF

echo "🎉 Container iConnect pronto!"

# Executar comando passado como argumento
exec "$@"
