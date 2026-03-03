#!/usr/bin/env python3
"""
Script para identificar templates HTML não utilizados no projeto iConnect
"""

import os
import re


def find_templates_in_directory(templates_dir):
    """Encontra todos os templates HTML no diretório"""
    templates = []
    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith(".html"):
                rel_path = os.path.relpath(os.path.join(root, file), templates_dir)
                templates.append(rel_path)
    return sorted(templates)


def find_template_references_in_code(project_dir):
    """Encontra referências a templates no código Python"""
    references = set()

    # Padrões para encontrar referências a templates
    patterns = [
        r"render\([^,]*,\s*['\"]([^'\"]+\.html)['\"]",
        r"template_name\s*=\s*['\"]([^'\"]+\.html)['\"]",
        r"get_template\(['\"]([^'\"]+\.html)['\"]",
        r"select_template\(\[['\"]([^'\"]+\.html)['\"]",
    ]

    # Buscar em arquivos Python
    for root, dirs, files in os.walk(project_dir):
        # Ignorar diretórios não relevantes
        dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ["node_modules", "staticfiles", "__pycache__"]]

        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    for pattern in patterns:
                        matches = re.findall(pattern, content)
                        for match in matches:
                            references.add(match)
                except Exception as e:
                    print(f"Erro ao ler {file_path}: {e}")

    return references


def find_template_extends_and_includes(templates_dir):
    """Encontra templates referenciados via extends e include"""
    references = set()

    for root, dirs, files in os.walk(templates_dir):
        for file in files:
            if file.endswith(".html"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    # Buscar extends e includes
                    extends_pattern = r"{%\s*extends\s+['\"]([^'\"]+)['\"]"
                    include_pattern = r"{%\s*include\s+['\"]([^'\"]+)['\"]"

                    extends_matches = re.findall(extends_pattern, content)
                    include_matches = re.findall(include_pattern, content)

                    for match in extends_matches + include_matches:
                        references.add(match)

                except Exception as e:
                    print(f"Erro ao ler {file_path}: {e}")

    return references


def main():
    project_dir = "/Users/chrisataide/Documents/controle_atendimento_iconnect"
    templates_dir = os.path.join(project_dir, "templates")

    print("🔍 Analisando templates do projeto iConnect...")
    print("=" * 60)

    # Encontrar todos os templates
    all_templates = find_templates_in_directory(templates_dir)
    print(f"📁 Total de templates encontrados: {len(all_templates)}")

    # Encontrar referências no código Python
    code_references = find_template_references_in_code(project_dir)
    print(f"🐍 Templates referenciados no código Python: {len(code_references)}")

    # Encontrar referências em outros templates (extends/include)
    template_references = find_template_extends_and_includes(templates_dir)
    print(f"📄 Templates referenciados em outros templates: {len(template_references)}")

    # Combinar todas as referências
    all_references = code_references.union(template_references)
    print(f"🔗 Total de templates referenciados: {len(all_references)}")

    # Encontrar templates não utilizados
    unused_templates = []
    for template in all_templates:
        is_used = False
        for ref in all_references:
            if template.endswith(ref) or ref.endswith(template):
                is_used = True
                break
        if not is_used:
            unused_templates.append(template)

    print("\n" + "=" * 60)
    print("📊 RESULTADOS DA ANÁLISE")
    print("=" * 60)

    print(f"\n✅ TEMPLATES EM USO ({len(all_templates) - len(unused_templates)}):")
    used_templates = [t for t in all_templates if t not in unused_templates]
    for template in sorted(used_templates)[:20]:  # Mostrar apenas os primeiros 20
        print(f"  • {template}")
    if len(used_templates) > 20:
        print(f"  ... e mais {len(used_templates) - 20} templates")

    print(f"\n❌ TEMPLATES POSSIVELMENTE NÃO UTILIZADOS ({len(unused_templates)}):")
    for template in sorted(unused_templates):
        print(f"  • {template}")

    print(f"\n🔍 REFERÊNCIAS ENCONTRADAS NO CÓDIGO:")
    for ref in sorted(list(all_references))[:15]:  # Mostrar apenas as primeiras 15
        print(f"  • {ref}")
    if len(all_references) > 15:
        print(f"  ... e mais {len(all_references) - 15} referências")

    # Salvar resultado em arquivo
    with open(os.path.join(project_dir, "template_usage_analysis.txt"), "w", encoding="utf-8") as f:
        f.write("ANÁLISE DE USO DE TEMPLATES - iConnect\n")
        f.write("=" * 50 + "\n\n")
        f.write(f"Total de templates: {len(all_templates)}\n")
        f.write(f"Templates em uso: {len(all_templates) - len(unused_templates)}\n")
        f.write(f"Templates não utilizados: {len(unused_templates)}\n\n")

        f.write("TEMPLATES NÃO UTILIZADOS:\n")
        f.write("-" * 30 + "\n")
        for template in sorted(unused_templates):
            f.write(f"{template}\n")

        f.write("\nTEMPLATES EM USO:\n")
        f.write("-" * 30 + "\n")
        for template in sorted(used_templates):
            f.write(f"{template}\n")

    print(f"\n💾 Resultado salvo em: template_usage_analysis.txt")


if __name__ == "__main__":
    main()
