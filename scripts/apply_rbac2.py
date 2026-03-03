#!/usr/bin/env python3
"""Apply RBAC decorators to all view files that need them."""
import re
import os

VIEWS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'dashboard', 'views')
RBAC_IMPORT = 'from ..utils.rbac import role_required'

ROLES_FIN = "('admin', 'gerente', 'financeiro')"
ROLES_OPS = "('admin', 'gerente', 'supervisor', 'tecnico_senior', 'agente')"
ROLES_MGT = "('admin', 'gerente', 'supervisor')"
ROLES_AGT = "('admin', 'gerente', 'supervisor', 'agente')"


def add_import(content):
    if 'from ..utils.rbac import role_required' in content:
        return content
    target = 'from django.contrib.auth.decorators import login_required'
    if target in content:
        return content.replace(target, target + '\n' + RBAC_IMPORT)
    return content


def add_role_func(content, roles, protect=None, skip=None):
    """Add @role_required after @login_required for function-based views."""
    protect = protect or []
    skip = skip or []
    lines = content.split('\n')
    out = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == '@login_required':
            for j in range(i + 1, min(i + 5, len(lines))):
                nxt = lines[j].strip()
                if nxt.startswith('def '):
                    fn = nxt.split('(')[0].replace('def ', '')
                    do_add = True
                    if skip and fn in skip:
                        do_add = False
                    if protect and fn not in protect:
                        do_add = False
                    if do_add:
                        between = '\n'.join(lines[i + 1:j])
                        if 'role_required' not in between:
                            indent = len(lines[i]) - len(lines[i].lstrip())
                            out.append(' ' * indent + '@role_required' + roles)
                    break
                elif nxt.startswith('@') or nxt == '':
                    break
        i += 1
    return '\n'.join(out)


def add_role_cbv(content, roles, skip_classes=None):
    """Replace @method_decorator(login_required, ...) with RBAC version for CBVs."""
    skip_classes = skip_classes or []
    lines = content.split('\n')
    out = []
    for i, line in enumerate(lines):
        s = line.strip()
        if re.match(r"@method_decorator\(login_required,\s*name=['\"]dispatch['\"]\)", s):
            cls = None
            for j in range(i + 1, min(i + 3, len(lines))):
                if lines[j].strip().startswith('class '):
                    cls = lines[j].strip().split('(')[0].replace('class ', '')
                    break
            if cls and cls not in skip_classes:
                indent = len(line) - len(line.lstrip())
                out.append(f"{' ' * indent}@method_decorator([login_required, role_required{roles}], name='dispatch')")
                continue
        out.append(line)
    return '\n'.join(out)


def process(filepath, roles, protect=None, skip=None, skip_classes=None):
    with open(filepath) as f:
        content = f.read()
    orig = content
    content = add_import(content)
    content = add_role_func(content, roles, protect, skip)
    content = add_role_cbv(content, roles, skip_classes)
    if content != orig:
        with open(filepath, 'w') as f:
            f.write(content)
        cnt = content.count('role_required') - 1  # minus the import
        print(f'  OK {os.path.basename(filepath)} ({cnt} decorators)')
        return True
    print(f'  -- {os.path.basename(filepath)} (unchanged)')
    return False


def process_mixed(filepath, func_roles_map, default_roles=None, skip_funcs=None, skip_classes=None):
    """Process file where different functions need different roles."""
    with open(filepath) as f:
        content = f.read()
    orig = content
    content = add_import(content)

    lines = content.split('\n')
    out = []
    i = 0
    while i < len(lines):
        out.append(lines[i])
        if lines[i].strip() == '@login_required':
            for j in range(i + 1, min(i + 5, len(lines))):
                nxt = lines[j].strip()
                if nxt.startswith('def '):
                    fn = nxt.split('(')[0].replace('def ', '')
                    roles = func_roles_map.get(fn, default_roles)
                    if roles and (not skip_funcs or fn not in skip_funcs):
                        between = '\n'.join(lines[i + 1:j])
                        if 'role_required' not in between:
                            indent = len(lines[i]) - len(lines[i].lstrip())
                            out.append(' ' * indent + '@role_required' + roles)
                    break
                elif nxt.startswith('@') or nxt == '':
                    break
        i += 1

    content = '\n'.join(out)
    content = add_role_cbv(content, default_roles or ROLES_OPS, skip_classes)

    if content != orig:
        with open(filepath, 'w') as f:
            f.write(content)
        cnt = content.count('role_required') - 1
        print(f'  OK {os.path.basename(filepath)} ({cnt} decorators)')
        return True
    print(f'  -- {os.path.basename(filepath)} (unchanged)')
    return False


def main():
    print('Applying RBAC to views...\n')
    changed = 0

    # 1. estoque.py - all operacional
    if process(f'{VIEWS_DIR}/estoque.py', ROLES_OPS):
        changed += 1

    # 2. equipamentos.py - all operacional
    if process(f'{VIEWS_DIR}/equipamentos.py', ROLES_OPS):
        changed += 1

    # 3. chat.py - all operacional
    if process(f'{VIEWS_DIR}/chat.py', ROLES_OPS):
        changed += 1

    # 4. itens_atendimento.py - all operacional
    if process(f'{VIEWS_DIR}/itens_atendimento.py', ROLES_OPS):
        changed += 1

    # 5. ticket_operations.py - all gestao
    if process(f'{VIEWS_DIR}/ticket_operations.py', ROLES_MGT):
        changed += 1

    # 6. mobile.py - all operacional (skip mobile_offline)
    if process(f'{VIEWS_DIR}/mobile.py', ROLES_OPS, skip=['mobile_offline']):
        changed += 1

    # 7. banking_features.py - mixed
    kb_write = {
        'knowledge_create': ROLES_MGT,
        'knowledge_edit': ROLES_MGT,
        'knowledge_delete': ROLES_MGT,
        'knowledge_category_create': ROLES_MGT,
        'knowledge_category_delete': ROLES_MGT,
        'macros_list': ROLES_AGT,
        'macro_create': ROLES_AGT,
        'macro_delete': ROLES_AGT,
        'ticket_timetrack': ROLES_OPS,
    }
    if process_mixed(f'{VIEWS_DIR}/banking_features.py', kb_write,
                     skip_funcs=['knowledge_article_detail', 'knowledge_vote', 'knowledge_category_list'],
                     skip_classes=['KnowledgeBaseView']):
        changed += 1

    # 8. chatbot_ai.py - mixed
    chatbot_roles = {
        'chatbot_dashboard': ROLES_MGT,
        'chatbot_knowledge_base': ROLES_MGT,
        'chatbot_add_knowledge': ROLES_MGT,
        'chatbot_conversations': ROLES_MGT,
        'chatbot_conversation_detail': ROLES_MGT,
        'chatbot_analytics_api': ROLES_MGT,
        'chatbot_settings': ROLES_MGT,
        'chatbot_create_ticket_from_conversation': ROLES_OPS,
    }
    if process_mixed(f'{VIEWS_DIR}/chatbot_ai.py', chatbot_roles,
                     skip_funcs=['chatbot_api', 'chatbot_feedback']):
        changed += 1

    # 9. clientes.py - mixed
    if process(f'{VIEWS_DIR}/clientes.py', ROLES_OPS,
               skip=['_calcular_tempo_medio_resposta'],
               skip_classes=['ClientePortalView', 'ClienteTicketsView']):
        changed += 1

    # 10. features.py - mixed
    feat_roles = {
        'reports_dashboard': ROLES_MGT,
        'generate_report': ROLES_MGT,
        'download_report': ROLES_MGT,
        'custom_reports': ROLES_MGT,
        'export_tickets': ROLES_MGT,
        'chat_interface': ROLES_OPS,
        'communication_center': ROLES_OPS,
    }
    if process_mixed(f'{VIEWS_DIR}/features.py', feat_roles,
                     skip_funcs=['chatbot_interface', 'chatbot_api',
                                 'advanced_search', 'pwa_info', 'pwa_install_guide']):
        changed += 1

    # 11. tickets.py - mixed
    tkt_roles = {'update_ticket_status': ROLES_OPS}
    if process_mixed(f'{VIEWS_DIR}/tickets.py', tkt_roles,
                     skip_funcs=['add_interaction'],
                     skip_classes=['TicketDetailView', 'TicketCreateView']):
        changed += 1

    # 12. dashboard.py - mixed
    dash_roles = {
        'admin_dashboard': ROLES_MGT,
        'ajax_metrics': ROLES_MGT,
    }
    if process_mixed(f'{VIEWS_DIR}/dashboard.py', dash_roles,
                     skip_funcs=['home_redirect', 'tickets_chart_api']):
        changed += 1

    # 13. auth_profile.py - mixed
    auth_roles = {'update_agent_status': ROLES_MGT}
    if process_mixed(f'{VIEWS_DIR}/auth_profile.py', auth_roles,
                     skip_funcs=['custom_login', 'custom_logout', 'get_user_info'],
                     skip_classes=['ProfileView']):
        changed += 1

    print(f'\nDone! {changed} files modified.')


if __name__ == '__main__':
    main()
