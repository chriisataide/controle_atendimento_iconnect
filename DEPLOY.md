# 🚀 Guia Completo de Deploy - iConnect

## 📋 Pré-requisitos

### Servidor de Produção
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Docker Desktop
- **CPU**: 2+ cores
- **RAM**: 4GB+ (8GB recomendado)
- **Disco**: 50GB+ SSD
- **Rede**: IP público, portas 80/443/22 abertas

### Software Necessário
```bash
# Docker & Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo pip3 install docker-compose

# Git
sudo apt install git -y

# SSL/HTTPS (Certbot)
sudo apt install certbot python3-certbot-nginx -y
```

---

## 🔧 Configuração Inicial

### 1. Clone do Repositório
```bash
git clone https://github.com/chriisataide/controle_atendimento_iconnect.git
cd controle_atendimento_iconnect
```

### 2. Configuração de Ambiente
```bash
# Copie o arquivo de exemplo
cp .env.example .env

# Configure as variáveis (IMPORTANTE!)
nano .env
```

**Variáveis críticas para alterar:**
```bash
SECRET_KEY=gere-uma-chave-secreta-de-50-caracteres-aqui
DEBUG=False
ENVIRONMENT=production
ALLOWED_HOSTS=seu-dominio.com,www.seu-dominio.com
DATABASE_URL=postgresql://iconnect_user:sua_senha_segura@db:5432/iconnect_db
```

### 3. Configuração do Docker Compose
```bash
# Edite as senhas no docker-compose.yml
nano docker-compose.yml
```

Altere as senhas padrão:
- `POSTGRES_PASSWORD`
- `redis requirepass`
- `SECRET_KEY`

---

## 🐳 Deploy com Docker

### Deploy Simples (Desenvolvimento)
```bash
# Build e inicialização
docker-compose up -d --build

# Migrations iniciais
docker-compose exec web python manage.py migrate

# Criar superusuário
docker-compose exec web python manage.py createsuperuser

# Coletar arquivos estáticos
docker-compose exec web python manage.py collectstatic --noinput
```

### Deploy Produção Completo
```bash
# 1. Build da aplicação
docker-compose -f docker-compose.yml up -d --build

# 2. Aguardar inicialização do banco
sleep 30

# 3. Executar migrations
docker-compose exec web python manage.py migrate

# 4. Criar dados iniciais
docker-compose exec web python manage.py loaddata initial_data.json

# 5. Configurar nginx
sudo cp nginx.conf /etc/nginx/sites-available/iconnect
sudo ln -s /etc/nginx/sites-available/iconnect /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

---

## 🔒 Configuração SSL/HTTPS

### Certificado Let's Encrypt
```bash
# Pare o nginx temporariamente
sudo systemctl stop nginx

# Obter certificado SSL
sudo certbot certonly --standalone -d seu-dominio.com -d www.seu-dominio.com

# Configurar renovação automática
echo "0 12 * * * /usr/bin/certbot renew --quiet" | sudo crontab -

# Reiniciar nginx
sudo systemctl start nginx
```

### Configuração Nginx para HTTPS
```nginx
# Adicione ao nginx.conf
server {
    listen 443 ssl http2;
    server_name seu-dominio.com;
    
    ssl_certificate /etc/letsencrypt/live/seu-dominio.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/seu-dominio.com/privkey.pem;
    
    # Resto da configuração...
}

# Redirect HTTP para HTTPS
server {
    listen 80;
    server_name seu-dominio.com;
    return 301 https://$server_name$request_uri;
}
```

---

## 📊 Configuração de Monitoramento

### 1. Health Checks
```bash
# Teste básico
curl http://localhost/health/

# Métricas detalhadas
curl http://localhost/metrics/
```

### 2. Logs Centralizados
```bash
# Visualizar logs em tempo real
docker-compose logs -f web

# Logs específicos
docker-compose logs -f --tail=100 web
docker-compose logs -f --tail=100 db
docker-compose logs -f --tail=100 redis
```

### 3. Backup Automático
```bash
# Configurar cron para backup diário
echo "0 2 * * * /opt/iconnect/scripts/backup.sh" | crontab -

# Teste manual
./scripts/backup.sh
```

---

## 🚀 GitHub Actions (CI/CD)

### Configuração de Secrets
No GitHub, vá em: **Settings** → **Secrets and variables** → **Actions**

Adicione os secrets:
```
DOCKER_USERNAME=seu_usuario_dockerhub
DOCKER_PASSWORD=sua_senha_dockerhub
PRODUCTION_HOST=ip_do_seu_servidor
PRODUCTION_USER=usuario_ssh
PRODUCTION_SSH_KEY=sua_chave_ssh_privada
SLACK_WEBHOOK=webhook_do_slack_opcional
```

### Deploy Automático
```bash
# Push para main = deploy automático
git add .
git commit -m "feat: deploy para produção"
git push origin main

# Acompanhar deploy
gh run watch
```

---

## 🔧 Comandos Úteis de Produção

### Manutenção da Aplicação
```bash
# Atualizar aplicação
git pull origin main
docker-compose up -d --build
docker-compose exec web python manage.py migrate
docker-compose exec web python manage.py collectstatic --noinput

# Reiniciar serviços
docker-compose restart web
docker-compose restart celery

# Backup manual
./scripts/backup.sh

# Logs em tempo real
docker-compose logs -f web
```

### Monitoramento
```bash
# Status dos containers
docker-compose ps

# Uso de recursos
docker stats

# Espaço em disco
df -h
docker system df

# Limpeza
docker system prune -f
```

---

## 🚨 Troubleshooting

### Problemas Comuns

**1. Erro de conexão com banco**
```bash
# Verificar se PostgreSQL está rodando
docker-compose ps db

# Logs do banco
docker-compose logs db

# Testar conexão
docker-compose exec web python manage.py dbshell
```

**2. Erro 502 Bad Gateway**
```bash
# Verificar se a aplicação está rodando
curl http://localhost:8000/health/

# Reiniciar nginx
sudo systemctl restart nginx

# Logs do nginx
sudo tail -f /var/log/nginx/error.log
```

**3. SSL não funciona**
```bash
# Verificar certificado
sudo certbot certificates

# Renovar se necessário
sudo certbot renew

# Testar configuração nginx
sudo nginx -t
```

**4. Performance lenta**
```bash
# Verificar recursos
htop
docker stats

# Otimizar banco
docker-compose exec web python manage.py optimize_db
```

---

## 📈 Scaling e Performance

### Múltiplos Workers
```yaml
# docker-compose.yml
web:
  # Aumentar workers
  command: gunicorn --bind 0.0.0.0:8000 --workers 6 --threads 4

celery:
  # Múltiplos workers Celery
  command: celery -A controle_atendimento worker --loglevel=info --concurrency=4
```

### Load Balancer
```nginx
# nginx.conf
upstream iconnect_backend {
    server web1:8000;
    server web2:8000;
    server web3:8000;
}

server {
    location / {
        proxy_pass http://iconnect_backend;
    }
}
```

---

## 🔐 Checklist de Segurança

- [ ] Alterar todas as senhas padrão
- [ ] Configurar HTTPS/SSL
- [ ] Firewall configurado (ufw/iptables)
- [ ] Backups automáticos funcionando
- [ ] Monitoramento ativo
- [ ] Logs centralizados
- [ ] Updates automáticos do OS
- [ ] SSH com chave, sem senha
- [ ] Fail2ban instalado
- [ ] Secrets não commitados no Git

---

## 📞 Suporte

**Em caso de problemas:**

1. Consulte os logs: `docker-compose logs -f`
2. Verifique o health check: `curl /health/`
3. Consulte a documentação
4. Abra uma issue no GitHub

**Contato:**
- 📧 Email: chris@iconnect.com
- 🐙 GitHub: https://github.com/chriisataide/controle_atendimento_iconnect

---

**🎉 Parabéns! Seu sistema iConnect está pronto para produção!**
