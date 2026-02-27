import openpyxl, re
from collections import Counter

wb = openpyxl.load_workbook('Pontos de vendas.xlsx', read_only=True)
ws = wb.active

status_count = Counter()
total = 0
ativos_com_cnpj = 0
ativos_sem_cnpj = 0
todos_com_cnpj = 0
todos_sem_cnpj = 0
cnpjs_ativos = []

for row in ws.iter_rows(min_row=2, values_only=True):
    total += 1
    status = str(row[11] or '').strip()
    cnpj_raw = str(row[8] or '').strip()
    digits = re.sub(r'\D', '', cnpj_raw)
    has_cnpj = bool(digits and digits != '0' * len(digits))
    status_count[status] += 1
    if has_cnpj:
        todos_com_cnpj += 1
    else:
        todos_sem_cnpj += 1
    if status == 'Ativo':
        if has_cnpj:
            ativos_com_cnpj += 1
            d = digits.zfill(14)[-14:]
            cnpj_fmt = f'{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:14]}'
            cnpjs_ativos.append(cnpj_fmt)
        else:
            ativos_sem_cnpj += 1

cnpj_counter = Counter(cnpjs_ativos)
duplicates = {k: v for k, v in cnpj_counter.items() if v > 1}

print(f'Total linhas: {total}')
print(f'Por status: {dict(status_count)}')
print()
print(f'TODOS - com CNPJ: {todos_com_cnpj}, sem CNPJ: {todos_sem_cnpj}')
print(f'ATIVOS - com CNPJ: {ativos_com_cnpj}, sem CNPJ: {ativos_sem_cnpj}')
print(f'ATIVOS - CNPJs unicos: {len(set(cnpjs_ativos))}')
print(f'ATIVOS - CNPJs duplicados: {len(duplicates)} (afetando {sum(v for v in duplicates.values())} linhas)')
print()
print(f'Se importar TODOS com CNPJ: {todos_com_cnpj}')
wb.close()
