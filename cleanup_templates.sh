#!/bin/bash

# 🧹 Script de Limpeza de Templates - Sistema iConnect
# Remove templates HTML não utilizados identificados pela análise

echo "🧹 Iniciando limpeza de templates não utilizados..."

# Criar diretório para backup dos templates removidos
mkdir -p .cleanup_backup/templates_unused

echo "🗂️ Templates não utilizados identificados:"
echo "  • cliente/dashboard_avancado.html"
echo "  • dashboard/automation/workflow_engine.html"
echo "  • dashboard/customer_portal.html"
echo "  • dashboard/includes/performance_monitor.html"
echo "  • dashboard/index_backup.html"
echo "  • dashboard/index_new.html"
echo "  • dashboard/performance_monitor_simple.html" 
echo "  • dashboard/pwa_install.html"
echo "  • dashboard/tickets/create_backup.html"
echo "  • dashboard/tickets/create_old.html"
echo "  • integration_example.html"

echo ""
echo "📦 Movendo templates não utilizados para backup..."

# Mover templates não utilizados para backup
templates_to_remove=(
    "templates/cliente/dashboard_avancado.html"
    "templates/dashboard/automation/workflow_engine.html"
    "templates/dashboard/customer_portal.html"
    "templates/dashboard/includes/performance_monitor.html"
    "templates/dashboard/index_backup.html"
    "templates/dashboard/index_new.html"
    "templates/dashboard/performance_monitor_simple.html"
    "templates/dashboard/pwa_install.html"
    "templates/dashboard/tickets/create_backup.html"
    "templates/dashboard/tickets/create_old.html"
    "templates/integration_example.html"
)

removed_count=0
for template in "${templates_to_remove[@]}"; do
    if [ -f "$template" ]; then
        # Criar diretório no backup se necessário
        backup_dir=".cleanup_backup/templates_unused/$(dirname "$template")"
        mkdir -p "$backup_dir"
        
        # Mover arquivo para backup
        mv "$template" "$backup_dir/"
        echo "  ✅ $template"
        ((removed_count++))
    else
        echo "  ⚠️  $template (não encontrado)"
    fi
done

echo ""
echo "🧹 Limpando diretórios vazios..."
# Remover diretórios vazios
find templates/ -type d -empty -delete 2>/dev/null || true

echo ""
echo "📊 Verificando economia de espaço..."
if [ -d ".cleanup_backup/templates_unused" ]; then
    backup_size=$(du -sh .cleanup_backup/templates_unused/ | cut -f1)
    echo "📁 Tamanho dos templates removidos: $backup_size"
fi

echo ""
echo "✅ Limpeza de templates concluída!"
echo ""
echo "📋 Resumo:"
echo "  • Templates removidos: $removed_count"
echo "  • Templates em uso mantidos: $((43 - removed_count))"
echo "  • Backup salvo em: .cleanup_backup/templates_unused/"
echo ""
echo "⚠️  Para restaurar templates, copie de .cleanup_backup/templates_unused/"
echo "💡 Para verificar se algum template é necessário, teste o sistema completamente"
