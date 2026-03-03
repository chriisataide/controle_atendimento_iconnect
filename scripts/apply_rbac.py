#!/usr/bin/env python3
"""
Script para aplicar RBAC (@role_required) em todas as views do dashboard.
Executa edições cirúrgicas mantendo formatação e lógica existente.
"""
import re
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWS_DIR = os.path.join(BASE, 'dashboard', 'views')

RBAC_IMPORT = "from ..utils.rbac import role_required"
RBAC_IMPORT_MIXIN = "from ..utils.rbac import role_required, RoleRequiredMixin"

# ─── Role groups ───
ROLES_FINANCEIRO = "('admin', 'gerente', 'financeiro')"
ROLES_OPERACIONAL = "('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')"
ROLES_GESTAO = "('admin', 'gerente', 'supervisor')"
ROLES_AGENTE_PLUS = "('admin', 'gerente', 'supervisor', 'agente')"


def add_import(content, import_line):
    """Add RBAC import after the login_required import if not already present."""
    if 'from ..utils.rbac import role_required' in content:
        return content
    if 'from dashboard.utils.rbac import role_required' in content:
        return content

    # Find the login_required import line and add after it
    patterns = [
        r'(from django\.contrib\.auth\.decorators import login_required\n)',
        r'(from django\.contrib\.auth\.decorators import login_required, user_passes_test\n)',
    ]
    for pattern in patterns:
        if re.search(pattern, content):
            content = re.sub(pattern, r'\1' + import_line + '\n', content)
            return content

    # Fallback: add after all imports
    lines = content.split('\n')
    last_import = 0
    for i, line in enumerate(lines):
        if line.startswith('from ') or line.startswith('import '):
            last_import = i
    lines.insert(last_import + 1, import_line)
    return '\n'.join(lines)


def add_role_to_function_views(content, roles, exclude_funcs=None):
    """Add @role_required(...) after @login_required for function views."""
    exclude_funcs = exclude_funcs or []
    role_decorator = f"@role_required{roles}"

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)

        # Check if this line is @login_required (standalone, not in method_decorator)
        stripped = line.strip()
        if stripped == '@login_required':
            # Look ahead for the function name
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('def '):
                    func_name = next_stripped.split('(')[0].replace('def ', '')
                    if func_name not in exclude_funcs:
                        # Check if role_required is already there
                        between = '\n'.join(lines[i+1:j])
                        if 'role_required' not in between:
                            indent = len(line) - len(line.lstrip())
                            new_lines.append(' ' * indent + role_decorator)
                    break
                elif next_stripped.startswith('@'):
                    # Another decorator, skip
                    break
                elif next_stripped == '':
                    break
                else:
                    break
                j += 1
        i += 1

    return '\n'.join(new_lines)


def add_role_to_class_views(content, roles, exclude_classes=None):
    """Replace @method_decorator(login_required, name='dispatch') with RBAC version."""
    exclude_classes = exclude_classes or []
    role_decorator = f"role_required{roles}"

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Match @method_decorator(login_required, name='dispatch')
        if re.match(r"@method_decorator\(login_required,\s*name=['\"]dispatch['\"]\)", stripped):
            # Look ahead for class name
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('class '):
                    class_name = next_stripped.split('(')[0].replace('class ', '')
                    if class_name not in exclude_classes:
                        indent = len(line) - len(line.lstrip())
                        new_line = f"{' ' * indent}@method_decorator([login_required, {role_decorator}], name='dispatch')"
                        new_lines.append(new_line)
                        i += 1
                        continue
                    break
                else:
                    break
                j += 1

        new_lines.append(line)
        i += 1

    return '\n'.join(new_lines)


def process_file(filepath, roles, import_line=RBAC_IMPORT, exclude_funcs=None, exclude_classes=None):
    """Process a single file: add import + decorators."""
    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    content = add_import(content, import_line)
    content = add_role_to_function_views(content, roles, exclude_funcs)
    content = add_role_to_class_views(content, roles, exclude_classes)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ {os.path.basename(filepath)} — RBAC aplicado")
    else:
        print(f"  ⏭️  {os.path.basename(filepath)} — já tem RBAC ou nenhuma alteração")

    return content != original


def process_financeiro():
    """Todas as views financeiras: admin, gerente, financeiro"""
    print("\n📁 financeiro.py")
    filepath = os.path.join(VIEWS_DIR, 'financeiro.py')
    process_file(filepath, ROLES_FINANCEIRO)


def process_estoque():
    """Estoque: admin, gerente, supervisor, tecnico_senior, agente"""
    print("\n📁 estoque.py")
    filepath = os.path.join(VIEWS_DIR, 'estoque.py')
    process_file(filepath, ROLES_OPERACIONAL, import_line=RBAC_IMPORT)


def process_equipamentos():
    """Equipamentos: admin, gerente, supervisor, tecnico_senior, agente"""
    print("\n📁 equipamentos.py")
    filepath = os.path.join(VIEWS_DIR, 'equipamentos.py')
    process_file(filepath, ROLES_OPERACIONAL)


def process_banking_features():
    """Mixed: KB read=all, KB write=gestao, macros=agente+, timetrack=operacional"""
    print("\n📁 banking_features.py")
    filepath = os.path.join(VIEWS_DIR, 'banking_features.py')

    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    content = add_import(content, RBAC_IMPORT)

    # KB write functions need @role_required('admin', 'gerente', 'supervisor')
    kb_write_funcs = ['knowledge_create', 'knowledge_edit', 'knowledge_delete',
                      'knowledge_category_create', 'knowledge_category_delete']
    # Macros need agente+
    macro_funcs = ['macros_list', 'macro_create', 'macro_delete']
    # Time tracking needs operacional
    time_funcs = ['ticket_timetrack']
    # KB read stays login_required only
    kb_read_funcs = ['knowledge_article_detail', 'knowledge_vote',
                     'knowledge_category_list']

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        stripped = line.strip()

        if stripped == '@login_required':
            # Look ahead for function name
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('def '):
                    func_name = next_stripped.split('(')[0].replace('def ', '')
                    indent = len(line) - len(line.lstrip())
                    if func_name in kb_write_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_GESTAO}")
                    elif func_name in macro_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_AGENTE_PLUS}")
                    elif func_name in time_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_OPERACIONAL}")
                    # KB read funcs and KnowledgeBaseView: no role_required
                    break
                elif next_stripped.startswith('@'):
                    break
                else:
                    break
                j += 1

        # KnowledgeBaseView class — keep as-is (all users can read)
        i += 1

    content = '\n'.join(new_lines)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ banking_features.py — RBAC aplicado (mixed)")
    else:
        print(f"  ⏭️  banking_features.py — nenhuma alteração")


def process_chat():
    """Chat: agent usage=operacional, admin settings=gestao"""
    print("\n📁 chat.py")
    filepath = os.path.join(VIEWS_DIR, 'chat.py')
    # chatbot_settings (admin) needs gestao, rest needs operacional
    # For simplicity, all chat views need at least agent role
    process_file(filepath, ROLES_OPERACIONAL)


def process_chatbot_ai():
    """Chatbot: interface=all, admin views=gestao"""
    print("\n📁 chatbot_ai.py")
    filepath = os.path.join(VIEWS_DIR, 'chatbot_ai.py')

    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    content = add_import(content, RBAC_IMPORT)

    # Admin views with @login_required need @role_required('admin', 'gerente', 'supervisor')
    admin_funcs = ['chatbot_dashboard', 'chatbot_knowledge_base', 'chatbot_add_knowledge',
                   'chatbot_conversations', 'chatbot_conversation_detail',
                   'chatbot_analytics_api', 'chatbot_settings']
    # Agent+ funcs
    agent_funcs = ['chatbot_create_ticket_from_conversation']
    # User funcs — keep login_required only
    user_funcs = ['chatbot_api', 'chatbot_feedback']
    # chatbot_interface — keep without auth (or add login_required)

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        stripped = line.strip()

        if stripped == '@login_required':
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('def '):
                    func_name = next_stripped.split('(')[0].replace('def ', '')
                    indent = len(line) - len(line.lstrip())
                    if func_name in admin_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_GESTAO}")
                    elif func_name in agent_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_OPERACIONAL}")
                    break
                elif next_stripped.startswith('@'):
                    break
                else:
                    break
                j += 1

        i += 1

    content = '\n'.join(new_lines)

    # Also add @login_required to chatbot_interface if missing
    content = content.replace(
        'def chatbot_interface(request):\n    """Interface do chatbot para usuários"""',
        '@login_required\ndef chatbot_interface(request):\n    """Interface do chatbot para usuários"""'
    )
    # Avoid double @login_required
    content = content.replace('@login_required\n@login_required\n', '@login_required\n')

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ chatbot_ai.py — RBAC aplicado (mixed)")
    else:
        print(f"  ⏭️  chatbot_ai.py — nenhuma alteração")


def process_clientes():
    """Clientes: portal=all, admin=agente+"""
    print("\n📁 clientes.py")
    filepath = os.path.join(VIEWS_DIR, 'clientes.py')
    # Admin CRUD views need agent+, portal views accessible to all
    exclude_funcs = ['_calcular_tempo_medio_resposta']  # helper function
    process_file(filepath, ROLES_OPERACIONAL, import_line=RBAC_IMPORT,
                 exclude_funcs=exclude_funcs,
                 exclude_classes=['ClientePortalView', 'ClienteTicketsView'])


def process_features():
    """Features: reports/export=gestao, search/PWA=all"""
    print("\n📁 features.py")
    filepath = os.path.join(VIEWS_DIR, 'features.py')

    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    content = add_import(content, RBAC_IMPORT)

    # Admin/reports functions
    gestao_funcs = ['reports_dashboard', 'generate_report', 'download_report',
                    'custom_reports', 'export_tickets']
    operacional_funcs = ['chat_interface', 'communication_center']
    # User funcs: chatbot_interface, chatbot_api, advanced_search, pwa_info, pwa_install_guide
    # Public funcs: manifest, service_worker, search_suggestions

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        stripped = line.strip()

        if stripped == '@login_required':
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('def '):
                    func_name = next_stripped.split('(')[0].replace('def ', '')
                    indent = len(line) - len(line.lstrip())
                    if func_name in gestao_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_GESTAO}")
                    elif func_name in operacional_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_OPERACIONAL}")
                    break
                elif next_stripped.startswith('@'):
                    break
                else:
                    break
                j += 1

        i += 1

    content = '\n'.join(new_lines)

    # Add @login_required to search_suggestions if missing
    if 'def search_suggestions(request):' in content:
        content = content.replace(
            'def search_suggestions(request):',
            '@login_required\ndef search_suggestions(request):'
        )
        # Avoid double decorator
        content = content.replace('@login_required\n@login_required\n', '@login_required\n')

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ features.py — RBAC aplicado (mixed)")
    else:
        print(f"  ⏭️  features.py — nenhuma alteração")


def process_itens_atendimento():
    """Itens atendimento: operacional"""
    print("\n📁 itens_atendimento.py")
    filepath = os.path.join(VIEWS_DIR, 'itens_atendimento.py')
    process_file(filepath, ROLES_OPERACIONAL)


def process_ticket_operations():
    """Ticket operations: gestao"""
    print("\n📁 ticket_operations.py")
    filepath = os.path.join(VIEWS_DIR, 'ticket_operations.py')
    process_file(filepath, ROLES_GESTAO)


def process_tickets():
    """Tickets: CBVs=operacional, create/interact=all, status update=operacional"""
    print("\n📁 tickets.py")
    filepath = os.path.join(VIEWS_DIR, 'tickets.py')

    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    content = add_import(content, RBAC_IMPORT)

    # Function views that need RBAC
    operacional_funcs = ['update_ticket_status']
    # Function views that stay login_required only (clients can interact)
    user_funcs = ['add_interaction']

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        stripped = line.strip()

        if stripped == '@login_required':
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('def '):
                    func_name = next_stripped.split('(')[0].replace('def ', '')
                    indent = len(line) - len(line.lstrip())
                    if func_name in operacional_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_OPERACIONAL}")
                    break
                elif next_stripped.startswith('@'):
                    break
                else:
                    break
                j += 1

        i += 1

    content = '\n'.join(new_lines)

    # Class-based views: KanbanBoardView, TicketListView, TicketUpdateView,
    # AgenteDashboardView, AgenteTicketsView = operacional
    # TicketDetailView, TicketCreateView = all authenticated (clients can see/create)
    cbv_operacional = ['KanbanBoardView', 'TicketListView', 'TicketUpdateView',
                       'AgenteDashboardView', 'AgenteTicketsView']
    cbv_all = ['TicketDetailView', 'TicketCreateView']

    content = add_role_to_class_views(content, ROLES_OPERACIONAL,
                                       exclude_classes=cbv_all)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ tickets.py — RBAC aplicado (mixed)")
    else:
        print(f"  ⏭️  tickets.py — nenhuma alteração")


def process_dashboard():
    """Dashboard: admin_dashboard=gestao, DashboardView=all, ajax_metrics=gestao"""
    print("\n📁 dashboard.py")
    filepath = os.path.join(VIEWS_DIR, 'dashboard.py')

    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    content = add_import(content, RBAC_IMPORT)

    gestao_funcs = ['admin_dashboard', 'ajax_metrics']
    # home_redirect, tickets_chart_api = all authenticated
    # DashboardView = all authenticated (renders based on role)

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        stripped = line.strip()

        if stripped == '@login_required':
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('def '):
                    func_name = next_stripped.split('(')[0].replace('def ', '')
                    indent = len(line) - len(line.lstrip())
                    if func_name in gestao_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_GESTAO}")
                    break
                elif next_stripped.startswith('@'):
                    break
                else:
                    break
                j += 1

        i += 1

    content = '\n'.join(new_lines)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ dashboard.py — RBAC aplicado (mixed)")
    else:
        print(f"  ⏭️  dashboard.py — nenhuma alteração")


def process_auth_profile():
    """Auth/profile: user CRUD=admin+gerente, PdV=gestao, profile=all"""
    print("\n📁 auth_profile.py")
    filepath = os.path.join(VIEWS_DIR, 'auth_profile.py')

    with open(filepath, 'r') as f:
        content = f.read()

    original = content
    content = add_import(content, RBAC_IMPORT)

    # Admin only
    gestao_funcs = ['update_agent_status']

    lines = content.split('\n')
    new_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        stripped = line.strip()

        if stripped == '@login_required':
            j = i + 1
            while j < len(lines):
                next_stripped = lines[j].strip()
                if next_stripped.startswith('def '):
                    func_name = next_stripped.split('(')[0].replace('def ', '')
                    indent = len(line) - len(line.lstrip())
                    if func_name in gestao_funcs:
                        new_lines.append(f"{' ' * indent}@role_required{ROLES_GESTAO}")
                    break
                elif next_stripped.startswith('@'):
                    break
                else:
                    break
                j += 1

        i += 1

    content = '\n'.join(new_lines)

    # Class-based views
    # PontoDeVendaListView, PontoDeVendaCreateView, PontoDeVendaUpdateView = gestao
    # UserListView, UserCreateView, UserEditView = admin + gerente
    # ProfileView = all authenticated
    cbv_all = ['ProfileView']
    content = add_role_to_class_views(content, ROLES_GESTAO,
                                       exclude_classes=cbv_all)

    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✅ auth_profile.py — RBAC aplicado (mixed)")
    else:
        print(f"  ⏭️  auth_profile.py — nenhuma alteração")


def process_mobile():
    """Mobile: same rules as desktop views, but most filter by user already"""
    print("\n📁 mobile.py")
    filepath = os.path.join(VIEWS_DIR, 'mobile.py')
    # Mobile views are user-scoped (use get_role_filtered_tickets or filter by user)
    # Still need at minimum role check to prevent clients from accessing agent views
    exclude = ['mobile_offline']  # Public offline page
    process_file(filepath, ROLES_OPERACIONAL, exclude_funcs=exclude)


def main():
    print("=" * 60)
    print("🔒 Aplicando RBAC em todas as views do dashboard")
    print("=" * 60)

    process_financeiro()
    process_estoque()
    process_equipamentos()
    process_banking_features()
    process_chat()
    process_chatbot_ai()
    process_clientes()
    process_features()
    process_itens_atendimento()
    process_ticket_operations()
    process_tickets()
    process_dashboard()
    process_auth_profile()
    process_mobile()

    print("\n" + "=" * 60)
    print("✅ RBAC aplicado com sucesso!")
    print("=" * 60)


if __name__ == '__main__':
    main()
