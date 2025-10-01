#!/bin/bash

# 🖼️ Script de Limpeza de Imagens - Sistema iConnect
# Move imagens não utilizadas para backup

echo "🖼️ Iniciando limpeza de imagens não utilizadas..."
echo "📊 Encontradas 67 imagens não utilizadas (~11.9 MB)"

# Criar diretório para backup das imagens
mkdir -p .cleanup_backup/images_unused/img/{icons/flags,illustrations,logos/gray-logos,small-logos}

echo ""
echo "📦 Movendo imagens não utilizadas para backup..."

# Contador de imagens movidas
moved_count=0

# Imagens principais não utilizadas
main_images=(
    "assets/img/bg-pricing.jpg"
    "assets/img/bg-smart-home-1.jpg"
    "assets/img/bg-smart-home-2.jpg"
    "assets/img/bruce-mars.jpg"
    "assets/img/down-arrow-dark.svg"
    "assets/img/down-arrow-white.svg"
    "assets/img/down-arrow.svg"
    "assets/img/drake.jpg"
    "assets/img/home-decor-1.jpg"
    "assets/img/home-decor-2.jpg"
    "assets/img/home-decor-3.jpg"
    "assets/img/icodev-logo-full.png"
    "assets/img/icodev-logo-full.svg"
    "assets/img/icodev-logo.png"
    "assets/img/icodev-logo.svg"
    "assets/img/ivana-square.jpg"
    "assets/img/ivana-squares.jpg"
    "assets/img/ivancik.jpg"
    "assets/img/kal-visuals-square.jpg"
    "assets/img/marie.jpg"
    "assets/img/meeting.jpg"
    "assets/img/office-dark.jpg"
    "assets/img/product-12.jpg"
    "assets/img/team-1.jpg"
    "assets/img/team-2.jpg"
    "assets/img/team-3.jpg"
    "assets/img/team-4.jpg"
    "assets/img/team-5.jpg"
    "assets/img/vr-bg.jpg"
)

echo "🖼️ Movendo imagens principais..."
for image in "${main_images[@]}"; do
    if [ -f "$image" ]; then
        mv "$image" ".cleanup_backup/images_unused/img/"
        echo "  ✅ $(basename "$image")"
        ((moved_count++))
    fi
done

# Flags
echo "🏁 Movendo flags..."
flags=(
    "assets/img/icons/flags/AU.png"
    "assets/img/icons/flags/BR.png"
    "assets/img/icons/flags/DE.png"
    "assets/img/icons/flags/GB.png"
    "assets/img/icons/flags/US.png"
)

for flag in "${flags[@]}"; do
    if [ -f "$flag" ]; then
        mv "$flag" ".cleanup_backup/images_unused/img/icons/flags/"
        echo "  ✅ $(basename "$flag")"
        ((moved_count++))
    fi
done

# Illustrations
echo "🎨 Movendo ilustrações..."
illustrations=(
    "assets/img/illustrations/chat.png"
    "assets/img/illustrations/danger-chat-ill.png"
    "assets/img/illustrations/dark-lock-ill.png"
    "assets/img/illustrations/error-404.png"
    "assets/img/illustrations/error-500.png"
    "assets/img/illustrations/illustration-lock.jpg"
    "assets/img/illustrations/illustration-reset.jpg"
    "assets/img/illustrations/illustration-signin.jpg"
    "assets/img/illustrations/illustration-signup.jpg"
    "assets/img/illustrations/illustration-verification.jpg"
    "assets/img/illustrations/lock.png"
    "assets/img/illustrations/pattern-tree.svg"
    "assets/img/illustrations/rocket-white.png"
)

for illustration in "${illustrations[@]}"; do
    if [ -f "$illustration" ]; then
        mv "$illustration" ".cleanup_backup/images_unused/img/illustrations/"
        echo "  ✅ $(basename "$illustration")"
        ((moved_count++))
    fi
done

# Gray logos
echo "🏢 Movendo logos cinza..."
gray_logos=(
    "assets/img/logos/gray-logos/logo-coinbase.svg"
    "assets/img/logos/gray-logos/logo-nasa.svg"
    "assets/img/logos/gray-logos/logo-netflix.svg"
    "assets/img/logos/gray-logos/logo-pinterest.svg"
    "assets/img/logos/gray-logos/logo-spotify.svg"
    "assets/img/logos/gray-logos/logo-vodafone.svg"
)

for logo in "${gray_logos[@]}"; do
    if [ -f "$logo" ]; then
        mv "$logo" ".cleanup_backup/images_unused/img/logos/gray-logos/"
        echo "  ✅ $(basename "$logo")"
        ((moved_count++))
    fi
done

# Small logos
echo "📱 Movendo small logos..."
small_logos=(
    "assets/img/small-logos/bootstrap.svg"
    "assets/img/small-logos/devto.svg"
    "assets/img/small-logos/github.svg"
    "assets/img/small-logos/google-webdev.svg"
    "assets/img/small-logos/icon-bulb.svg"
    "assets/img/small-logos/icon-sun-cloud.png"
    "assets/img/small-logos/iconnect-logo.svg"
    "assets/img/small-logos/logo-asana.svg"
    "assets/img/small-logos/logo-atlassian.svg"
    "assets/img/small-logos/logo-invision.svg"
    "assets/img/small-logos/logo-jira.svg"
    "assets/img/small-logos/logo-slack.svg"
    "assets/img/small-logos/logo-spotify.svg"
    "assets/img/small-logos/logo-xd.svg"
)

for small_logo in "${small_logos[@]}"; do
    if [ -f "$small_logo" ]; then
        mv "$small_logo" ".cleanup_backup/images_unused/img/small-logos/"
        echo "  ✅ $(basename "$small_logo")"
        ((moved_count++))
    fi
done

echo ""
echo "🧹 Limpando diretórios vazios..."
find assets/img/ -type d -empty -delete 2>/dev/null || true

echo ""
echo "📊 Verificando economia de espaço..."
backup_size=$(du -sh .cleanup_backup/images_unused/ 2>/dev/null | cut -f1 || echo "0")
echo "📁 Tamanho das imagens removidas: $backup_size"

echo ""
echo "✅ Limpeza de imagens concluída!"
echo ""
echo "📋 Resumo:"
echo "  • Imagens movidas: $moved_count"
echo "  • Imagens em uso mantidas: 5"
echo "  • Economia de espaço: ~11.9 MB"
echo "  • Backup salvo em: .cleanup_backup/images_unused/"
echo ""
echo "🖼️ Imagens mantidas (EM USO):"
echo "  • fonts/nucleo-icons.svg"
echo "  • img/apple-icon.png"
echo "  • img/favicon.png"
echo "  • img/logo-ct-dark.png"
echo "  • img/logo-ct.png"
echo ""
echo "⚠️  Para restaurar imagens, copie de .cleanup_backup/images_unused/"
echo "💡 Para usar imagens do backup, mova de volta para assets/img/"
