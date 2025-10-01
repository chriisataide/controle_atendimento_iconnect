#!/bin/bash

# Script de Inicialização do Sistema de Notificações em Tempo Real
# iConnect Support System

echo "🚀 Iniciando Sistema de Notificações em Tempo Real - iConnect"
echo "================================================================="

# Verificar se Redis está rodando
echo "📡 Verificando Redis..."
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis não está rodando. Iniciando Redis..."
    
    # Tentar iniciar Redis
    if command -v redis-server &> /dev/null; then
        redis-server --daemonize yes
        sleep 2
        if redis-cli ping > /dev/null 2>&1; then
            echo "✅ Redis iniciado com sucesso"
        else
            echo "❌ Falha ao iniciar Redis"
            echo "📝 Instale Redis: brew install redis (macOS) ou apt-get install redis-server (Ubuntu)"
            exit 1
        fi
    else
        echo "❌ Redis não está instalado"
        echo "📝 Instale Redis: brew install redis (macOS) ou apt-get install redis-server (Ubuntu)"
        exit 1
    fi
else
    echo "✅ Redis está rodando"
fi

# Verificar dependências Python
echo "📦 Verificando dependências Python..."
python -c "import channels, channels_redis, redis" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "✅ Dependências Python OK"
else
    echo "❌ Instalando dependências Python..."
    pip install channels[daphne] channels-redis redis
fi

# Executar migrações
echo "💾 Executando migrações..."
python manage.py makemigrations
python manage.py migrate

# Testar configuração WebSocket
echo "🧪 Testando configuração WebSocket..."
python -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'controle_atendimento.settings')
import django
django.setup()

from channels.routing import get_default_application
from django.conf import settings

print('✅ ASGI Application:', settings.ASGI_APPLICATION)
print('✅ Channel Layers:', 'channels' in settings.INSTALLED_APPS)
print('✅ Redis Config:', settings.CHANNEL_LAYERS)

try:
    app = get_default_application()
    print('✅ WebSocket routing configurado corretamente')
except Exception as e:
    print('❌ Erro na configuração WebSocket:', e)
"

# Testar conexão Redis
echo "🔗 Testando conexão Redis..."
python -c "
import redis
import json

try:
    r = redis.Redis(host='localhost', port=6379, db=0)
    r.ping()
    print('✅ Conexão Redis OK')
    
    # Testar channel layer
    from channels_redis.core import RedisChannelLayer
    channel_layer = RedisChannelLayer()
    print('✅ Channel Layer configurado')
    
except Exception as e:
    print('❌ Erro Redis:', e)
"

echo ""
echo "🎯 COMANDOS PARA INICIAR O SISTEMA:"
echo "================================================================="
echo "1. Terminal 1 - Servidor Django (HTTP):"
echo "   python manage.py runserver"
echo ""
echo "2. Terminal 2 - Servidor Daphne (WebSocket):"
echo "   daphne -p 8001 controle_atendimento.asgi:application"
echo ""
echo "3. Terminal 3 - Worker de Background (opcional):"
echo "   python manage.py runworker"
echo ""
echo "🔧 CONFIGURAÇÃO NGINX (Produção):"
echo "================================================================="
cat << 'EOF'
server {
    listen 80;
    server_name seu-dominio.com;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    location /ws/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
EOF

echo ""
echo "📱 RECURSOS IMPLEMENTADOS:"
echo "================================================================="
echo "✅ WebSocket em tempo real"
echo "✅ Notificações automáticas"
echo "✅ Alertas de SLA"
echo "✅ Interface responsiva"
echo "✅ Reconexão automática"
echo "✅ Som e vibração"
echo "✅ Histórico completo"
echo "✅ API REST para mobile"
echo ""

echo "🚀 Sistema pronto para uso!"
echo "📖 Acesse: http://localhost:8000"
echo "🔌 WebSocket: ws://localhost:8001/ws/"
