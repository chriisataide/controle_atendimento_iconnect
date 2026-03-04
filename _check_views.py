import os
files = [
    'dashboard/views/financeiro.py',
    'dashboard/views/estoque.py',
    'dashboard/views/equipamentos.py',
    'dashboard/views/chat.py',
    'dashboard/views/itens_atendimento.py',
    'dashboard/views/ticket_operations.py',
    'dashboard/views/mobile.py',
    'dashboard/views/banking_features.py',
    'dashboard/views/chatbot_ai.py',
    'dashboard/views/clientes.py',
    'dashboard/views/features.py',
    'dashboard/views/tickets.py',
    'dashboard/views/dashboard.py',
    'dashboard/views/auth_profile.py',
    'dashboard/views/executive.py',
    'dashboard/views/analytics.py',
    'dashboard/views/automation.py',
    'dashboard/views/workflow_builder.py',
    'dashboard/views/sla.py',
]
print(f"{'Arquivo':<45} | {'Import?':^8} | {'@role_req':^10} | {'@login_req':^11}")
print('-' * 85)
for f in files:
    if not os.path.isfile(f):
        print(f"{f:<45} | {'N/A':^8} | {'-':^10} | {'-':^11}")
        continue
    with open(f) as fh:
        content = fh.read()
    has_import = 'role_required' in content and 'from ..utils.rbac' in content
    role_count = content.count('@role_required')
    login_count = content.count('@login_required')
    imp = 'yes' if has_import else 'no'
    print(f"{f:<45} | {imp:^8} | {role_count:^10} | {login_count:^11}")
