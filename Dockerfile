# ================================
# CONTROLE ATENDIMENTO ICONNECT
# Dockerfile Multi-stage para Produção
# ================================

# Stage 1: Build
FROM python:3.11-slim as builder

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.11-slim

# Metadados
LABEL maintainer="Chris Ataíde <chris@iconnect.com>"
LABEL description="Sistema de Controle de Atendimento iConnect"
LABEL version="1.0.0"

# Definir diretório de trabalho
WORKDIR /app

# Instalar dependências de runtime
RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependências Python do stage builder para local global
COPY --from=builder /root/.local /usr/local

# PATH já está configurado para /usr/local

# Definir variáveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DJANGO_SETTINGS_MODULE=controle_atendimento.settings
ENV ENVIRONMENT=production

# Copiar código da aplicação
COPY . .

# Criar diretórios necessários (incluindo logs do sistema)
RUN mkdir -p logs staticfiles media /var/log/django
RUN chmod 755 /var/log/django

# Testar se Django está disponível
RUN python -c "import django; print(f'Django {django.get_version()} instalado com sucesso')"

# Copiar código da aplicação
COPY . .

# Dar permissão de execução ao script de entrada
RUN chmod +x docker-entrypoint.sh

# Criar diretórios necessários (incluindo logs do sistema)
RUN mkdir -p logs staticfiles media /var/log/django
RUN chmod 755 /var/log/django

# Testar se Django está disponível
RUN python -c "import django; print(f'Django {django.get_version()} instalado com sucesso')"

# Remover collectstatic do build (será executado no entrypoint)
# RUN python manage.py collectstatic --noinput

# Criar usuário não-root para segurança
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Definir permissões após setup
RUN chown -R appuser:appuser /app
USER appuser

# Expor porta
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Usar script de entrada
ENTRYPOINT ["./docker-entrypoint.sh"]

# Comando padrão
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120", "--worker-class", "sync", "--max-requests", "1000", "--preload", "controle_atendimento.wsgi:application"]
