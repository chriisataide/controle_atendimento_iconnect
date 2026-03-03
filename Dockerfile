# ================================
# CONTROLE ATENDIMENTO ICONNECT
# Dockerfile Multi-stage para Produção
# ================================

# Stage 1: Build
FROM python:3.13-slim as builder

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org setuptools
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org --user -r requirements.txt

# Stage 2: Runtime
FROM python:3.13-slim

LABEL maintainer="Chris Ataide <chris@iconnect.com>"
LABEL description="Sistema de Controle de Atendimento iConnect"
LABEL version="1.0.0"

WORKDIR /app

RUN apt-get update && apt-get install -y \
    libpq5 \
    curl \
    netcat-traditional \
    && rm -rf /var/lib/apt/lists/*

# Copiar dependencias Python do stage builder
COPY --from=builder /root/.local /usr/local

# setuptools é necessário em runtime (drf-yasg usa pkg_resources)
# pkg_resources foi removido no setuptools 82+, pinnar versão compatível
RUN pip install --no-cache-dir --trusted-host pypi.org --trusted-host files.pythonhosted.org "setuptools<81"

# Variaveis de ambiente
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV DJANGO_SETTINGS_MODULE=controle_atendimento.settings
ENV ENVIRONMENT=production

# Copiar codigo da aplicacao (apenas uma vez)
COPY . .

# Criar diretorios necessarios
RUN mkdir -p logs/django staticfiles media

# Dar permissao de execucao aos scripts de entrada
RUN chmod +x docker/docker-entrypoint.sh docker/docker-entrypoint-dev.sh

# Verificar instalacao do Django
RUN python -c "import django; print(f'Django {django.get_version()} instalado com sucesso')"

# Criar usuario nao-root para seguranca
RUN groupadd -r appuser && useradd -r -g appuser appuser
RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/health/ || exit 1

ENTRYPOINT ["./docker/docker-entrypoint.sh"]

# ASGI com daphne para suporte a WebSocket + HTTP
CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "--proxy-headers", "controle_atendimento.asgi:application"]
