import pickle, sys, json
res = pickle.load(open(sys.argv[1], 'rb'))
dentro = lambda r, x0, y0, x1, y1: r[0] >= x0 and r[2] <= x1 and r[1] >= y0 and r[3] <= y1
delgado = lambda r: min(r[2] - r[0], r[3] - r[1]) <= 0.3 and max(r[2] - r[0], r[3] - r[1]) >= 0.2
muros = []
for t, n, r, rot in res['10_ESTRUCTURA_MURO_HORMIGON']:
    if dentro(r, 2.5, 1.5, 51.5, 61.5) and delgado(r) and not dentro(r, 14.5, 58.9, 17.2, 61.5): muros.append(list(r) + [3.15])
for t, n, r, rot in res['10_ESTRUCTURA_MURO_TERMOPANEL']:
    if dentro(r, 26, 19, 39.5, 35) and delgado(r): muros.append(list(r) + [4.2 if r[3] < 27.3 else 5.0])
for t, n, r, rot in res['20_ARQUITECTURA_PARED_DRYWALL']:
    if t == 'LWPOLYLINE' and dentro(r, 22, 19, 35.5, 31) and delgado(r): muros.append(list(r) + [3.15 if r[0] < 27 else 4.2])
muros += [[23.98, 30.35, 26.57, 30.45, 3.15], [23.98, 27.59, 24.03, 30.45, 3.15],  # cierre del cuarto al lado de desinfección (polilínea)
          [26.52, 27.59, 26.57, 45.48, 3.15], [26.57, 45.43, 50.74, 45.48, 3.15]]  # almacén: cerramiento oeste y norte (viga metálica)
puertas = [r for t, n, r, rot in res['20_ARQUITECTURA_PUERTA_ENROLLABLE'] if dentro(r, 2.5, 1.5, 51.5, 61.5) and r[2] - r[0] > 1]
puertas.append((23.0, 29.4, 23.1, 30.3))  # puerta de 90 cm de desinfección
def restar(m, p):
    x0, y0, x1, y1, h = m
    horiz = x1 - x0 >= y1 - y0
    if horiz and p[1] <= y1 + 0.05 and p[3] >= y0 - 0.05 and p[0] < x1 and p[2] > x0:
        return [s for s in ([x0, y0, p[0], y1, h], [p[2], y0, x1, y1, h]) if s[2] - s[0] > 0.05]
    if not horiz and p[0] <= x1 + 0.05 and p[2] >= x0 - 0.05 and p[1] < y1 and p[3] > y0:
        return [s for s in ([x0, y0, x1, p[1], h], [x0, p[3], x1, y1, h]) if s[3] - s[1] > 0.05]
    return [m]
for p in puertas:
    muros = [s for m in muros for s in restar(m, p)]
# Columnas de los pórticos de las naves (0,35 x 0,60 y 0,50 x 0,50) hasta el arranque del arco (+6,15); las de amarre del cerco hasta la viga (+3,55)
def alto_col(r):
    w, d = r[2] - r[0], r[3] - r[1]
    return 6.15 if (abs(w - 0.35) < 0.02 and abs(d - 0.6) < 0.02) or (abs(w - 0.5) < 0.02 and abs(d - 0.5) < 0.02) else 3.55
cols = [list(r) + [alto_col(r)] for t, n, r, rot in res['10_ESTRUCTURA_COLUMNA_HORMIGON'] if dentro(r, 2.5, 1.5, 51.5, 61.5)]
cols = [c for i, c in enumerate(cols) if c not in cols[:i]]
f = lambda a: '[' + ','.join(f'{v:.2f}'.rstrip('0').rstrip('.') for v in a) + ']'
print('const MUROS_PF = [' + ','.join(f(m) for m in muros) + '];')
print('const COLUMNAS_PF = [' + ','.join(f(c) for c in cols) + '];')
print(len(muros), len(cols), file=sys.stderr)
