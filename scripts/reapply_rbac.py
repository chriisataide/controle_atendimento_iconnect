#!/usr/bin/env python3
"""
Re-apply RBAC decorators to all view files after merge overwrote them.
"""
import os
import re

BASE = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'views')
IMPORT_LINE = "from ..utils.rbac import role_required"

ROLES_OPS = "@role_required('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')"
ROLES_MGT = "@role_required('admin', 'gerente', 'supervisor')"
ROLES_FIN = "@role_required('admin', 'gerente', 'financeiro')"
ROLES_AGT = "@role_required('admin', 'gerente', 'supervisor', 'agente')"


def add_import(content):
    """Add import line if not present."""
    if IMPORT_LINE in content:
        return content
    lines = content.split('\n')
    idx = 0
    for i, l in enumerate(lines):
        if l.startswith('from ') or l.startswith('import '):
            idx = i + 1
    lines.insert(idx, IMPORT_LINE)
    return '\n'.join(lines)


def add_role_after_login(content, role_str):
    """Add role_required after every @login_required."""
    lines = content.split('\n')
    new_lines = []
    count = 0
    for line in lines:
        new_lines.append(line)
        if line.strip() == '@login_required':
            indent = len(line) - len(line.lstrip())
            new_lines.append(' ' * indent + role_str)
            count += 1
    return '\n'.join(new_lines), count


def add_role_selective(content, func_role_map, default_role=None):
    """Add role_required only to specific functions, with optional default for rest."""
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
            for j in range(i + 1, min(i + 5, len(lines))):
                m = re.match(r'\s*def\s+(\w+)', lines[j])
                if m:
                    func_name = m.group(1)
                    break
            
            if func_name and func_name in func_role_map:
                role = func_role_map[func_name]
                if role:  # None means skip (no RBAC for this view)
                    new_lines.append(' ' * indent + role)
                    count += 1
            elif default_role:
                new_lines.append(' ' * indent + default_role)
                count += 1
        i += 1
    return '\n'.join(new_lines), count


def add_role_to_cbv(content, class_role_map):
    """Add allowed_roles to CBVs via method_decorator or class attribute."""
    # For now we handle CBVs that use @method_decorator(login_required)
    # by adding role_required after login_required in the decorator
    lines = content.split('\n')
    new_lines = []
    count = 0
    i = 0
    while i < len(lines):
        line = lines[i]
        new_lines.append(line)
        
        # Check for @method_decorator(login_required, ...)
        if '@method_decorator(login_required' in line.strip():
            indent = len(line) - len(line.lstrip())
            # Look ahead for class name
            class_name = None
            for j in range(i + 1, min(i + 5, len(lines))):
                m = re.match(r'\s*class\s+(\w+)', lines[j])
                if m:
                    class_name = m.group(1)
                    break
            
            if class_name and class_name in class_role_map:
                role = class_role_map[class_name]
                if role:
                    # Extract the roles from the string
                    roles_match = re.findall(r"'(\w+)'", role)
                    roles_str = ', '.join(f"'{r}'" for r in roles_match)
                    new_lines.append(f"{' ' * indent}@method_decorator(role_required({roles_str}), name='dispatch')")
                    count += 1
        i += 1
    return '\n'.join(new_lines), count


# =====================================================================
# FILE DEFINITIONS - what role each view gets
# =====================================================================

# Simple files: ALL views get the same role
SIMPLE_FILES = {
    'financeiro.py': ROLES_FIN,
    'executive.py': ROLES_MGT,
    'analytics.py': ROLES_MGT,
    'automation.py': ROLES_MGT,
    'workflow_builder.py': ROLES_MGT,
    'sla.py': ROLES_MGT,
}

# Simple operational files: ALL views get ROLES_OPS
SIMPLE_OPS_FILES = {
    'estoque.py': ROLES_OPS,
    'equipamentos.py': ROLES_OPS,
    'chat.py': ROLES_OPS,
    'itens_atendimento.py': ROLES_OPS,
    'mobile.py': ROLES_OPS,
}

# Ticket operations: management roles
SIMPLE_MGT_FILES = {
    'ticket_operations.py': ROLES_MGT,
}

# Mixed files: different functions get different roles
MIXED_FILES = {
    'chatbot_ai.py': {
        'func_map': {
            'chatbot_admin': ROLES_MGT,
            'chatbot_config': ROLES_MGT,
            'chatbot_analytics': ROLES_MGT,
            'chatbot_train': ROLES_MGT,
            'chatbot_templates': ROLES_MGT,
            'chatbot_template_save': ROLES_MGT,
            'chatbot_template_delete': ROLES_MGT,
            'chatbot_export_conversations': ROLES_MGT,
            # User-facing views: no RBAC
            'chatbot_interface': None,
            'chatbot_message': None,
            'chatbot_create_ticket': ROLES_OPS,
        },
        'default': None,
    },
    'clientes.py': {
        'func_map': {
            'cliente_list': ROLES_OPS,
            'cliente_create': ROLES_OPS,
            'cliente_edit': ROLES_OPS,
            'cliente_delete': ROLES_MGT,
            'cliente_detail': ROLES_OPS,
            # Portal views: no RBAC
            'portal_cliente': None,
            'portal_tickets': None,
            'portal_novo_ticket': None,
        },
        'default': None,
    },
    'features.py': {
        'func_map': {
            'relatorios': ROLES_MGT,
            'export_csv': ROLES_MGT,
            'export_pdf': ROLES_MGT,
            'report_satisfaction': ROLES_MGT,
            'report_performance': ROLES_MGT,
            'report_sla': ROLES_MGT,
            'communication_center': ROLES_OPS,
            'send_communication': ROLES_OPS,
            # Search/PWA: no RBAC
            'advanced_search': None,
            'pwa_offline': None,
            'search_results': None,
            'pwa_manifest': None,
            'service_worker': None,
        },
        'default': None,
    },
    'tickets.py': {
        'func_map': {
            'update_ticket_status': ROLES_OPS,
            # Detail/Create: no RBAC (user-scoped)
            'ticket_detail': None,
            'ticket_create': None,
        },
        'default': None,
        'cbv_map': {
            'TicketKanbanView': ROLES_OPS,
            'TicketListView': ROLES_OPS,
            'TicketUpdateView': ROLES_OPS,
            'AgentTicketListView': ROLES_OPS,
        },
    },
    'dashboard.py': {
        'func_map': {
            'admin_dashboard': ROLES_MGT,
            'ajax_metrics': ROLES_MGT,
            # Home/Dashboard: no RBAC (role-based redirects internally)
            'home_redirect': None,
            'tickets_chart_api': None,
        },
        'default': None,
    },
    'auth_profile.py': {
        'func_map': {
            'pdv_list': ROLES_MGT,
            'pdv_create': ROLES_MGT,
            'pdv_edit': ROLES_MGT,
            'pdv_delete': ROLES_MGT,
            # Login/logout/profile: no RBAC
            'custom_login': None,
            'custom_logout': None,
            'profile': None,
            'update_agent_status': None,
        },
        'default': None,
        'cbv_map': {
            'UserListView': ROLES_MGT,
            'UserCreateView': ROLES_MGT,
            'UserUpdateView': ROLES_MGT,
        },
    },
}


def process_file(filepath, role_str):
    """Process a simple file: add import + role to all @login_required."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    content = add_import(content)
    content, count = add_role_after_login(content, role_str)
    
    with open(filepath, 'w') as f:
        f.write(content)
    return count


def process_mixed_file(filepath, config):
    """Process a mixed file with different roles per function."""
    with open(filepath, 'r') as f:
        content = f.read()
    
    content = add_import(content)
    content, func_count = add_role_selective(
        content,
        config['func_map'],
        config.get('default'),
    )
    
    cbv_count = 0
    if 'cbv_map' in config:
        content, cbv_count = add_role_to_cbv(content, config['cbv_map'])
    
    with open(filepath, 'w') as f:
        f.write(content)
    return func_count + cbv_count


print("Re-applying RBAC to all view files...\n")
total = 0

# Simple files
for group in [SIMPLE_FILES, SIMPLE_OPS_FILES, SIMPLE_MGT_FILES]:
    for fname, role in group.items():
        fpath = os.path.join(BASE, fname)
        if not os.path.exists(fpath):
            print(f"  SKIP {fname} (not found)")
            continue
        count = process_file(fpath, role)
        print(f"  OK {fname} ({count} decorators)")
        total += count

# Mixed files
for fname, config in MIXED_FILES.items():
    fpath = os.path.join(BASE, fname)
    if not os.path.exists(fpath):
        print(f"  SKIP {fname} (not found)")
        continue
    count = process_mixed_file(fpath, config)
    print(f"  OK {fname} ({count} decorators)")
    total += count

# banking_features.py already has RBAC, skip it
print(f"\n  SKIP banking_features.py (already has RBAC)")

print(f"\nDone! {total} decorators added.")
