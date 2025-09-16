#!/bin/bash

# 🧹 Script de Limpeza - Sistema iConnect
# Remove arquivos desnecessários e organiza o projeto

echo "🧹 Iniciando limpeza do projeto iConnect..."

# Criar diretório para backup dos arquivos removidos
mkdir -p .cleanup_backup

echo "📁 Removendo arquivos de backup..."
# Mover arquivos backup para pasta temporária
mv README_backup.md .cleanup_backup/ 2>/dev/null || echo "README_backup.md não encontrado"
mv CHANGELOG_creative_tim.md.backup .cleanup_backup/ 2>/dev/null || echo "CHANGELOG_creative_tim.md.backup não encontrado"
mv dashboard/forms.py.backup .cleanup_backup/ 2>/dev/null || echo "forms.py.backup não encontrado"
mv templates/dashboard/profile.html.backup .cleanup_backup/ 2>/dev/null || echo "profile.html.backup não encontrado"

echo "🧪 Removendo arquivos de teste/debug..."
mv debug_template.html .cleanup_backup/ 2>/dev/null || echo "debug_template.html não encontrado"
mv test_template.html .cleanup_backup/ 2>/dev/null || echo "test_template.html não encontrado"
mv cookies.txt .cleanup_backup/ 2>/dev/null || echo "cookies.txt não encontrado"

echo "📋 Removendo configurações não utilizadas..."
mv composer.json .cleanup_backup/ 2>/dev/null || echo "composer.json não encontrado"

echo "📁 Movendo páginas do tema para backup..."
mv pages/ .cleanup_backup/ 2>/dev/null || echo "pages/ não encontrado"

echo "📚 Organizando documentação..."
# Criar diretório docs se não existir
mkdir -p docs/

# Mover documentação auxiliar
mv melhorias_sugeridas.md docs/ 2>/dev/null || echo "melhorias_sugeridas.md não encontrado"

echo "⚙️ Organizando arquivos de configuração exemplo..."
# Criar diretório config se não existir
mkdir -p config/

# Mover arquivos de exemplo de configuração
mv audit_settings_example.py config/ 2>/dev/null || echo "audit_settings_example.py não encontrado"
mv backup_settings_example.py config/ 2>/dev/null || echo "backup_settings_example.py não encontrado"
mv performance_settings_example.py config/ 2>/dev/null || echo "performance_settings_example.py não encontrado"

echo "🧹 Limpando diretórios temporários..."
# Limpar __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Limpar arquivos .pyc
find . -name "*.pyc" -delete 2>/dev/null || true

# Limpar arquivos .DS_Store (macOS)
find . -name ".DS_Store" -delete 2>/dev/null || true

echo "📊 Verificando tamanho dos diretórios..."
echo "📁 Tamanho antes da limpeza (pasta backup):"
du -sh .cleanup_backup/ 2>/dev/null || echo "Nenhum arquivo movido para backup"

echo ""
echo "✅ Limpeza concluída!"
echo ""
echo "📋 Resumo das ações:"
echo "  • Arquivos de backup movidos para .cleanup_backup/"
echo "  • Arquivos de teste/debug removidos"
echo "  • Configurações não utilizadas removidas"
echo "  • Documentação organizada em docs/"
echo "  • Configurações exemplo movidas para config/"
echo "  • Cache Python limpo"
echo ""
echo "⚠️  Para restaurar algum arquivo, verifique a pasta .cleanup_backup/"
echo "💡 Para remover definitivamente o backup: rm -rf .cleanup_backup/"
