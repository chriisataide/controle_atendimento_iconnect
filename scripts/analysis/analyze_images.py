#!/usr/bin/env python3
"""
Script para identificar imagens não utilizadas no projeto iConnect
"""

import os
import re


def find_images_in_directory(assets_dir):
    """Encontra todas as imagens no diretório assets"""
    images = []
    image_extensions = [".png", ".jpg", ".jpeg", ".svg", ".gif", ".ico", ".webp"]

    for root, dirs, files in os.walk(assets_dir):
        for file in files:
            if any(file.lower().endswith(ext) for ext in image_extensions):
                rel_path = os.path.relpath(os.path.join(root, file), assets_dir)
                images.append(rel_path)
    return sorted(images)


def find_image_references_in_code(project_dir):
    """Encontra referências a imagens no código"""
    references = set()

    # Padrões para encontrar referências a imagens
    patterns = [
        r"['\"]([^'\"]*\.(?:png|jpg|jpeg|svg|gif|ico|webp))['\"]",  # Geral
        r"src=['\"]([^'\"]*)['\"]",  # src attribute
        r"href=['\"]([^'\"]*\.(?:png|jpg|jpeg|svg|gif|ico|webp))['\"]",  # href para icons
        r"background-image:\s*url\(['\"]?([^'\"]*)['\"]?\)",  # CSS background
        r"static\s+['\"]([^'\"]*\.(?:png|jpg|jpeg|svg|gif|ico|webp))['\"]",  # Django static
        r"{% static ['\"]([^'\"]*)['\"] %}",  # Django template tags
    ]

    # Tipos de arquivo para verificar
    file_extensions = [".py", ".html", ".css", ".js", ".md"]

    for root, dirs, files in os.walk(project_dir):
        # Ignorar diretórios não relevantes
        dirs[:] = [
            d for d in dirs if not d.startswith(".") and d not in ["node_modules", "staticfiles", "__pycache__", ".git"]
        ]

        for file in files:
            if any(file.endswith(ext) for ext in file_extensions):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()

                    for pattern in patterns:
                        matches = re.findall(pattern, content, re.IGNORECASE)
                        for match in matches:
                            # Limpar path e extrair apenas o nome do arquivo
                            clean_match = match.strip().split("/")[-1]
                            if any(
                                clean_match.lower().endswith(ext)
                                for ext in [".png", ".jpg", ".jpeg", ".svg", ".gif", ".ico", ".webp"]
                            ):
                                references.add(clean_match)
                            # Também adicionar o path completo se contém img/
                            if "img/" in match:
                                img_path = match.split("img/")[-1] if "img/" in match else match
                                references.add(img_path)

                except Exception as e:
                    print(f"Erro ao ler {file_path}: {e}")

    return references


def analyze_specific_images(project_dir, image_list):
    """Analisa imagens específicas no código"""
    found_refs = {}

    for image in image_list:
        image_name = os.path.basename(image)
        found_refs[image] = []

        # Buscar referências específicas
        for root, dirs, files in os.walk(project_dir):
            dirs[:] = [
                d
                for d in dirs
                if not d.startswith(".") and d not in ["node_modules", "staticfiles", "__pycache__", ".git"]
            ]

            for file in files:
                if file.endswith((".py", ".html", ".css", ".js")):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                            content = f.read()

                        if image_name in content or image in content:
                            rel_file_path = os.path.relpath(file_path, project_dir)
                            found_refs[image].append(rel_file_path)

                    except Exception:
                        continue

    return found_refs


def main():
    project_dir = "/Users/chrisataide/Documents/controle_atendimento_iconnect"
    assets_dir = os.path.join(project_dir, "assets")

    print("🖼️  Analisando imagens do projeto iConnect...")
    print("=" * 60)

    # Encontrar todas as imagens
    all_images = find_images_in_directory(assets_dir)
    print(f"📁 Total de imagens encontradas: {len(all_images)}")

    # Encontrar referências no código
    code_references = find_image_references_in_code(project_dir)
    print(f"🔗 Referências de imagens encontradas: {len(code_references)}")

    # Análise específica das imagens
    image_analysis = analyze_specific_images(project_dir, all_images)

    # Classificar imagens
    used_images = []
    unused_images = []

    for image in all_images:
        image_name = os.path.basename(image)
        is_used = False

        # Verificar se a imagem é referenciada
        if image_analysis[image] or image_name in code_references or image in str(code_references):
            used_images.append((image, image_analysis[image]))
            is_used = True

        if not is_used:
            unused_images.append(image)

    print("\n" + "=" * 60)
    print("📊 RESULTADOS DA ANÁLISE DE IMAGENS")
    print("=" * 60)

    print(f"\n✅ IMAGENS EM USO ({len(used_images)}):")
    for image, refs in used_images[:15]:  # Mostrar apenas as primeiras 15
        print(f"  • {image}")
        if refs:
            for ref in refs[:2]:  # Mostrar até 2 referências
                print(f"    └─ {ref}")
    if len(used_images) > 15:
        print(f"  ... e mais {len(used_images) - 15} imagens")

    print(f"\n❌ IMAGENS POSSIVELMENTE NÃO UTILIZADAS ({len(unused_images)}):")
    for image in unused_images:
        print(f"  • {image}")

    # Calcular tamanho das imagens não utilizadas
    total_unused_size = 0
    for image in unused_images:
        image_path = os.path.join(assets_dir, image)
        if os.path.exists(image_path):
            total_unused_size += os.path.getsize(image_path)

    print(f"\n📊 Estatísticas:")
    print(f"  • Total de imagens: {len(all_images)}")
    print(f"  • Imagens em uso: {len(used_images)}")
    print(f"  • Imagens não utilizadas: {len(unused_images)}")
    print(f"  • Tamanho das não utilizadas: {total_unused_size / 1024:.1f} KB")

    # Salvar resultado em arquivo
    with open(os.path.join(project_dir, "image_usage_analysis.txt"), "w", encoding="utf-8") as f:
        f.write("ANÁLISE DE USO DE IMAGENS - iConnect\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total de imagens: {len(all_images)}\n")
        f.write(f"Imagens em uso: {len(used_images)}\n")
        f.write(f"Imagens não utilizadas: {len(unused_images)}\n")
        f.write(f"Tamanho não utilizado: {total_unused_size / 1024:.1f} KB\n\n")

        f.write("IMAGENS NÃO UTILIZADAS:\n")
        f.write("-" * 30 + "\n")
        for image in unused_images:
            f.write(f"{image}\n")

        f.write("\nIMAGENS EM USO:\n")
        f.write("-" * 30 + "\n")
        for image, refs in used_images:
            f.write(f"{image}\n")
            for ref in refs:
                f.write(f"  -> {ref}\n")

    print(f"\n💾 Resultado salvo em: image_usage_analysis.txt")


if __name__ == "__main__":
    main()
