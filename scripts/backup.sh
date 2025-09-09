#!/bin/bash

# ================================
# SISTEMA DE BACKUP AUTOMATIZADO
# iConnect Controle de Atendimento
# ================================

set -e  # Parar em caso de erro

# Configurações
BACKUP_DIR="/opt/backups/iconnect"
DATE=$(date +"%Y%m%d_%H%M%S")
RETENTION_DAYS=30
MAX_BACKUPS=50

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função de log
log() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
}

success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Verificar se o Docker está rodando
check_docker() {
    if ! docker info >/dev/null 2>&1; then
        error "Docker não está rodando!"
        exit 1
    fi
}

# Criar diretório de backup
setup_backup_dir() {
    mkdir -p "$BACKUP_DIR"/{database,media,logs,config}
    log "Diretório de backup preparado: $BACKUP_DIR"
}

# Backup do banco de dados
backup_database() {
    log "Iniciando backup do banco de dados..."
    
    # PostgreSQL backup
    docker-compose exec -T db pg_dump -U iconnect_user -d iconnect_db --verbose \
        > "$BACKUP_DIR/database/db_backup_$DATE.sql" 2>/dev/null
    
    if [ $? -eq 0 ]; then
        # Comprimir o backup
        gzip "$BACKUP_DIR/database/db_backup_$DATE.sql"
        success "Backup do banco de dados concluído: db_backup_$DATE.sql.gz"
    else
        error "Falha no backup do banco de dados"
        return 1
    fi
}

# Backup dos arquivos de media
backup_media() {
    log "Iniciando backup dos arquivos de media..."
    
    if [ -d "./media" ] && [ "$(ls -A ./media 2>/dev/null)" ]; then
        tar -czf "$BACKUP_DIR/media/media_backup_$DATE.tar.gz" -C . media/
        success "Backup de media concluído: media_backup_$DATE.tar.gz"
    else
        warning "Diretório media vazio ou não encontrado"
    fi
}

# Backup dos logs
backup_logs() {
    log "Iniciando backup dos logs..."
    
    if [ -d "./logs" ] && [ "$(ls -A ./logs 2>/dev/null)" ]; then
        tar -czf "$BACKUP_DIR/logs/logs_backup_$DATE.tar.gz" -C . logs/
        success "Backup de logs concluído: logs_backup_$DATE.tar.gz"
    else
        warning "Diretório de logs vazio ou não encontrado"
    fi
}

# Backup das configurações
backup_config() {
    log "Iniciando backup das configurações..."
    
    tar -czf "$BACKUP_DIR/config/config_backup_$DATE.tar.gz" \
        docker-compose.yml \
        nginx.conf \
        .env.example \
        requirements.txt \
        Dockerfile \
        2>/dev/null || true
    
    success "Backup de configurações concluído: config_backup_$DATE.tar.gz"
}

# Limpeza de backups antigos
cleanup_old_backups() {
    log "Iniciando limpeza de backups antigos..."
    
    # Remover backups mais antigos que RETENTION_DAYS
    find "$BACKUP_DIR" -name "*backup_*" -type f -mtime +$RETENTION_DAYS -delete
    
    # Manter apenas os últimos MAX_BACKUPS arquivos por tipo
    for dir in database media logs config; do
        ls -t "$BACKUP_DIR/$dir"/*backup_* 2>/dev/null | tail -n +$((MAX_BACKUPS + 1)) | xargs -r rm -f
    done
    
    success "Limpeza de backups concluída"
}

# Verificar integridade dos backups
verify_backups() {
    log "Verificando integridade dos backups..."
    
    # Verificar se os arquivos foram criados corretamente
    for backup_file in "$BACKUP_DIR"/database/db_backup_$DATE.sql.gz \
                      "$BACKUP_DIR"/media/media_backup_$DATE.tar.gz \
                      "$BACKUP_DIR"/logs/logs_backup_$DATE.tar.gz \
                      "$BACKUP_DIR"/config/config_backup_$DATE.tar.gz; do
        
        if [ -f "$backup_file" ]; then
            # Testar integridade dos arquivos comprimidos
            if [[ "$backup_file" == *.gz ]]; then
                if gzip -t "$backup_file" 2>/dev/null; then
                    success "✓ $(basename "$backup_file") - OK"
                else
                    error "✗ $(basename "$backup_file") - CORROMPIDO"
                fi
            else
                success "✓ $(basename "$backup_file") - OK"
            fi
        fi
    done
}

# Enviar notificação
send_notification() {
    local status=$1
    local message=$2
    
    # Webhook do Slack (se configurado)
    if [ -n "$SLACK_WEBHOOK_URL" ]; then
        curl -X POST -H 'Content-type: application/json' \
            --data "{\"text\":\"🔄 iConnect Backup: $status\\n$message\"}" \
            "$SLACK_WEBHOOK_URL" 2>/dev/null || true
    fi
    
    # Log local
    echo "$(date '+%Y-%m-%d %H:%M:%S'): $status - $message" >> "$BACKUP_DIR/backup.log"
}

# Gerar relatório
generate_report() {
    local backup_size=$(du -sh "$BACKUP_DIR" | cut -f1)
    local db_count=$(ls -1 "$BACKUP_DIR/database"/*backup_* 2>/dev/null | wc -l)
    local media_count=$(ls -1 "$BACKUP_DIR/media"/*backup_* 2>/dev/null | wc -l)
    
    cat << EOF > "$BACKUP_DIR/backup_report_$DATE.txt"
=================================
RELATÓRIO DE BACKUP - iConnect
=================================
Data: $(date '+%Y-%m-%d %H:%M:%S')
Tamanho total: $backup_size

Backups disponíveis:
- Banco de dados: $db_count arquivos
- Media files: $media_count arquivos
- Logs: $(ls -1 "$BACKUP_DIR/logs"/*backup_* 2>/dev/null | wc -l) arquivos
- Configurações: $(ls -1 "$BACKUP_DIR/config"/*backup_* 2>/dev/null | wc -l) arquivos

Último backup:
$(ls -la "$BACKUP_DIR"/*/backup_$DATE.* 2>/dev/null || echo "Nenhum backup encontrado")

Status: CONCLUÍDO COM SUCESSO
=================================
EOF

    success "Relatório gerado: backup_report_$DATE.txt"
}

# Função principal
main() {
    log "=== INICIANDO BACKUP AUTOMATIZADO iConnect ==="
    
    # Verificações iniciais
    check_docker
    setup_backup_dir
    
    # Executar backups
    backup_database || { error "Falha no backup do banco"; exit 1; }
    backup_media
    backup_logs
    backup_config
    
    # Verificações e limpeza
    verify_backups
    cleanup_old_backups
    generate_report
    
    # Notificação
    send_notification "SUCCESS" "Backup concluído com sucesso em $(date '+%Y-%m-%d %H:%M:%S')"
    
    success "=== BACKUP CONCLUÍDO COM SUCESSO ==="
    log "Backup salvo em: $BACKUP_DIR"
    log "Total de espaço usado: $(du -sh "$BACKUP_DIR" | cut -f1)"
}

# Executar função principal
main "$@"
