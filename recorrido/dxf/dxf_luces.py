"""Luminarias (con su letra de circuito) e interruptores (con los circuitos que mandan) del plano eléctrico.
Uso: python3 dxf_luces.py PLANO.dxf > luces.js"""
import ezdxf, sys, math, json
doc = ezdxf.readfile(sys.argv[1]); msp = doc.modelspace()
def pt(e):
    for a in ('insert', 'center'):
        if e.dxf.hasattr(a): return e.dxf.get(a)
    return None
capa = lambda l: [e for e in msp if e.dxf.layer == l and pt(e) is not None and pt(e).x < 1000]
lamparas = [(e.dxf.name, pt(e)) for e in capa('60_ELECTRICO_LUMINARIAS_TECHO') if e.dxftype() == 'INSERT']
codigos = [(e.plain_text().strip(), pt(e)) for e in capa('60_ELECTRICO_CODIGO_LUMINARIAS') if e.dxftype() == 'MTEXT']
circulos = [pt(e) for e in capa('60_ELECTRICO_INTERRUPTOR_LUMINARIA') if e.dxftype() == 'CIRCLE']
textos = [(e.plain_text().strip(), pt(e)) for e in capa('60_ELECTRICO_INTERRUPTOR_LUMINARIA') if e.dxftype() == 'MTEXT']
d = lambda a, b: math.hypot(a.x - b.x, a.y - b.y)
# Segundo piso (comedor): dibujado 8,83 m más arriba que el primero
PISO2 = 8.83
def ubicar(p):
    return (round(p.x, 2), round(p.y - PISO2, 2), 2) if p.y > 62 else (round(p.x, 2), round(p.y, 2), 1)
L = []
for nombre, p in lamparas:
    c = min(codigos, key=lambda c: d(c[1], p))
    L.append([*ubicar(p), c[0] if d(c[1], p) < 0.6 else '', 'reflector' if 'reflector' in nombre else 'campana'])
I = []
for p in circulos:
    cods = [t for t, q in textos if t != 'S' and d(q, p) < 0.5]
    if not cods: continue
    c = min(cods, key=lambda t: 0)
    I.append([*ubicar(p), sorted({x.strip() for t in cods for x in t.replace(';', ',').split(',') if x.strip()})])
print('const LUCES_PF = ' + json.dumps(L, separators=(',', ':')) + ';')
print('const INTERRUPTORES_PF = ' + json.dumps(I, separators=(',', ':')) + ';')
print(len(L), len(I), sum(1 for l in L if not l[3]), file=sys.stderr)
