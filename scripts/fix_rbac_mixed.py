#!/usr/bin/env python3
"""
Fix RBAC for files that got 0 decorators because function names changed.
Handles: chatbot_ai.py, clientes.py, features.py, auth_profile.py, tickets.py
"""
import os
import re

BASE = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'views')
IMPORT_LINE = "from ..utils.rbac import role_required"

ROLES_OPS = "@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')"
ROLES_MGT = "@role_required('admin', 'gerente', 'supervisor')"


def add_import(content):
    if IMPORT_LINE in content:
        return content
    lines = content.split('\n')
    idx = 0
    for i, l in enumerate(lines):
        if l.startswith('from ') or l.startswith('import '):
            idx = i + 1
    lines.insert(idx, IMPORT_LINE)
    return '\n'.join(lines)


def add_role_selective(content, func_role_map):
    """Add role_required after @login_required for specific functions."""
    lines = content.split('\n')
    new_lines = []
    count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        if line.strip() == '@login_required':
            indent = len(line) - len(line.lstrip())
            # Look ahead for function name
            func_name = None
            for j in range(i + 1, min(i + 6, len(lines))):
                m = re.match(r'\s*def\s+(\w+)', lines[j])
                if m:
                    func_name = m.group(1)
                    break
            if func_name and func_name in func_role_map:
                role = func_role_map[func_name]
                if role:
                    new_lines.append(' ' * indent + role)
                    count += 1
        i += 1
    return '\n'.join(new_lines), count


def add_role_to_cbv_method_decorator(content, cbv_role_map):
    """Add role_required method_decorator to CBVs that have @method_decorator([login_required] or login_required)."""
    lines = content.split('\n')
    new_lines = []
    count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Match @method_decorator([login_required], ...) or @method_decorator(login_required, ...)
        if re.search(r'@method_decorator\(\[?login_required\]?,?\s*name', line.strip()):
            # Check if next line already has role_required
            if i + 1 < len(lines) and 'role_required' in lines[i + 1]:
                i += 1
                continue
                
            indent = len(line) - len(line.lstrip())
            # Look ahead for class name
            class_name = None
            for j in range(i + 1, min(i + 4, len(lines))):
                m = re.match(r'\s*class\s+(\w+)', lines[j])
                if m:
                    class_name = m.group(1)
                    break
            if class_name and class_name in cbv_role_map:
                role = cbv_role_map[class_name]
                if role:
                    roles_match = re.findall(r"'(\w+)'", role)
                    roles_str = ', '.join(f"'{r}'" for r in roles_match)
                    new_lines.append(f"{' ' * indent}@method_decorator(role_required({roles_str}), name='dispatch')")
                    count += 1
        i += 1
    return '\n'.join(new_lines), count


print("Fixing RBAC for refactored files...\n")
total = 0

# === chatbot_ai.py ===
fpath = os.path.join(BASE, 'chatbot_ai.py')
with open(fpath, 'r') as f:
    content = f.read()
content = add_import(content)
content, c = add_role_selective(content, {
    'chatbot_api': None,
    'chatbot_feedback': ROLES_OPS,
    'chatbot_dashboard': ROLES_MGT,
    'chatbot_knowledge_base': ROLES_MGT,
    'chatbot_add_knowledge': ROLES_MGT,
    'chatbot_conversations': ROLES_MGT,
    'chatbot_conversation_detail': ROLES_MGT,
    'chatbot_create_ticket_from_conversation': ROLES_OPS,
    'chatbot_analytics_api': ROLES_MGT,
    'chatbot_settings': ROLES_MGT,
})
with open(fpath, 'w') as f:
    f.write(content)
print(f"  OK chatbot_ai.py ({c} decorators)")
total += c

# === clientes.py ===
fpath = os.path.join(BASE, 'clientes.py')
with open(fpath, 'r') as f:
    content = f.read()
content = add_import(content)
content, c = add_role_selective(content, {
    'cliente_detail_view': ROLES_OPS,
    'cliente_delete_view': ROLES_MGT,
    'cliente_stats_ajax': ROLES_OPS,
})
with open(fpath, 'w') as f:
    f.write(content)
print(f"  OK clientes.py ({c} decorators)")
total += c

# === features.py ===
fpath = os.path.join(BASE, 'features.py')
with open(fpath, 'r') as f:
    content = f.read()
content = add_import(content)
content, c = add_role_selective(content, {
    'chatbot_interface': None,
    'chatbot_api': None,
    'chat_interface': ROLES_OPS,
    'reports_dashboard': ROLES_MGT,
    'generate_report': ROLES_MGT,
    'download_report': ROLES_MGT,
    'custom_reports': ROLES_MGT,
    'advanced_search': None,
    'pwa_info': None,
    'pwa_install_guide': None,
    'export_tickets': ROLES_MGT,
    'communication_center': ROLES_OPS,
})
with open(fpath, 'w') as f:
    f.write(content)
print(f"  OK features.py ({c} decorators)")
total += c

# === auth_profile.py ===
fpath = os.path.join(BASE, 'auth_profile.py')
with open(fpath, 'r') as f:
    content = f.read()
content = add_import(content)
# FBVs
content, c1 = add_role_selective(content, {
    'api_pontos_de_venda_por_cliente': ROLES_OPS,
    'get_user_info': None,
    'update_agent_status': None,
})
# CBVs
content, c2 = add_role_to_cbv_method_decorator(content, {
    'PontoDeVendaListView': ROLES_MGT,
    'PontoDeVendaCreateView': ROLES_MGT,
    'PontoDeVendaDetailView': ROLES_MGT,
    'PontoDeVendaUpdateView': ROLES_MGT,
    'UserListView': ROLES_MGT,
    'UserCreateView': ROLES_MGT,
    'UserUpdateView': ROLES_MGT,
    'UserDeleteView': ROLES_MGT,
    'ProfileView': None,
})
with open(fpath, 'w') as f:
    f.write(content)
print(f"  OK auth_profile.py ({c1 + c2} decorators)")
total += c1 + c2

# === tickets.py ===
fpath = os.path.join(BASE, 'tickets.py')
with open(fpath, 'r') as f:
    content = f.read()
content = add_import(content)
# FBVs
content, c1 = add_role_selective(content, {
    'add_interaction': ROLES_OPS,
    'update_ticket_status': ROLES_OPS,
})
# CBVs (some already have role_required, skip those)
content, c2 = add_role_to_cbv_method_decorator(content, {
    'KanbanBoardView': ROLES_OPS,
    'TicketListView': None,  # already has it
    'TicketDetailView': None,
    'TicketCreateView': None,
    'TicketUpdateView': None,  # already has it
    'AgenteDashboardView': ROLES_OPS,
    'AgenteTicketsView': ROLES_OPS,
})
with open(fpath, 'w') as f:
    f.write(content)
print(f"  OK tickets.py ({c1 + c2} decorators)")
total += c1 + c2

print(f"\nDone! {total} additional decorators added.")
