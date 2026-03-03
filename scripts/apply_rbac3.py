#!/usr/bin/env python3
"""Apply RBAC to the 5 files that were reverted by git checkout."""
import re, os

BASE = os.path.join(os.path.dirname(__file__), '..', 'dashboard', 'views')
IMPORT_LINE = "from dashboard.utils.rbac import role_required"
ROLES_MGT = "@role_required('admin', 'gerente', 'supervisor')"

def add_import(content):
    if IMPORT_LINE in content:
        return content
    lines = content.split('\n')
    # Insert after last 'from' import
    idx = 0
    for i, l in enumerate(lines):
        if l.startswith('from ') or l.startswith('import '):
            idx = i + 1
    lines.insert(idx, IMPORT_LINE)
    return '\n'.join(lines)

def add_role_after_login(content, role_str):
    """Add role_required after every @login_required line."""
    lines = content.split('\n')
    new_lines = []
    count = 0
    for i, line in enumerate(lines):
        new_lines.append(line)
        if line.strip() == '@login_required':
            indent = len(line) - len(line.lstrip())
            new_lines.append(' ' * indent + role_str)
            count += 1
    return '\n'.join(new_lines), count

files = {
    'executive.py': ROLES_MGT,        # 5 views - all management
    'analytics.py': ROLES_MGT,        # 2 views - all management
    'automation.py': ROLES_MGT,       # 3 views - all management
    'workflow_builder.py': ROLES_MGT, # 11 views - all management
    'sla.py': ROLES_MGT,             # 11 views - all management
}

print("Applying RBAC to reverted files...\n")
total = 0
for fname, role in files.items():
    fpath = os.path.join(BASE, fname)
    with open(fpath, 'r') as f:
        content = f.read()
    
    content = add_import(content)
    content, count = add_role_after_login(content, role)
    
    with open(fpath, 'w') as f:
        f.write(content)
    
    print(f"  OK {fname} ({count} decorators)")
    total += count

print(f"\nDone! {total} decorators added across 5 files.")
