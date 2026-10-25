"""Muebles, artefactos, puertas, ventanas y escaleras del plano, por capa.
Salida: [tipo, x0, y0, x1, y1, giro (grados), piso]. Uso: python3 dxf_muebles.py PLANO.dxf [--lista]"""
import ezdxf, sys, json, collections
from ezdxf import bbox
doc = ezdxf.readfile(sys.argv[1]); msp = doc.modelspace()
CAPAS = {
    '30_MOBILIARIO_SILLA_OFICINA': 'silla', '30_MOBILIARIO_OFICINA_SILLA': 'silla', '30_MOBILIARIO_COCINA_SILLA': 'silla_comedor',
    '30_MOBILIARIO_CASILLERO_METAL': 'casillero', '30_MOBILIARIO_BANCA_MADERA': 'banca', '30_MOBILIARIO_MESA_MADERA': 'mesa_madera',
    '30_MOBILIARIO_OFICINA_ESTANTERIA': 'estante', '30_MOBILIARIO_ESTANTERIA_MADERA': 'estante', '30_MOBILIARIO_ENCIMERA_MADERA': 'encimera',
    '30_MOBILIARIO_ELECTRODOMESTICO_COCINA': 'cocina', '30_MOBILIARIO_ELECTRODOMESTICO_REFRIGERADOR': 'refrigerador',
    '30_MOBILIARIO_DESINFECCION_ESTACION': 'desinfeccion', '80_SANITARIO_ARTEFACTO_INODORO': 'inodoro', '80_SANITARIO_ARTEFACTO_LAVADOR': 'lavatorio',
    '80_SANITARIO_ARTEFACTO_URINARIO': 'urinario', '80_SANITARIO_ARTEFACTO_DUCHA': 'ducha',
    '20_ARQUITECTURA_PUERTA_MADERA': 'puerta', '20_ARQUITECTURA_PUERTA_BAÑO': 'puerta', '20_ARQUITECTURA_PUERTA_METAL': 'puerta_metal',
    '20_ARQUITECTURA_VENTANA_VIDRIO': 'ventana', '20_ARQUITECTURA_VENTANA_ALTA_VIDRIO': 'ventana_alta', '10_ESTRUCTURA_ESCALERA_METAL': 'escalera',
    '60_ELECTRICO_TABLERO_ELECTRICO': 'tablero', '60_ELECTRICO_TABLERO_PEQUEÑO': 'tablero', '60_ELECTRICO_CARGADOR_MONTACARGAS': 'cargador',
}
# Los segundos pisos están dibujados aparte: [x0, y0, x1, y1] del dibujo, corrimiento a la planta y altura del piso (m)
PISOS = [
    ((34, 61.5, 46, 71), (0, -8.83), 3.35),        # comedor sobre SS.HH.
    ((58, 19, 71.5, 28.5), (-31.49, -0.13), 4.3),  # oficinas sobre laminado y laboratorio (h = 4,2 + losa)
    ((-7, 41, -1.5, 53.5), (9.87, 0), 2.85),       # 2.º piso del módulo de oficinas
]
def ubicar(x0, y0, x1, y1):
    for (a0, b0, a1, b1), (dx, dy), h in PISOS:
        if x0 >= a0 and x1 <= a1 and y0 >= b0 and y1 <= b1: return x0 + dx, y0 + dy, x1 + dx, y1 + dy, h
    if x0 >= -1 and x1 <= 52 and y1 <= 61.5: return x0, y0, x1, y1, 0
    return None
lista = '--lista' in sys.argv
muros2 = []
out, cuenta = [], collections.Counter()
for e in msp:
    t = CAPAS.get(e.dxf.layer)
    if not t or e.dxftype() not in ('INSERT', 'LWPOLYLINE', 'MLINE'): continue
    b = bbox.extents([e], fast=True)
    if not b.has_data: continue
    u = ubicar(b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)
    if not u or t == 'escalera': continue  # las escaleras se arman a mano (ver PF.escaleras)
    x0, y0, x1, y1, piso = u
    if max(x1 - x0, y1 - y0) < 0.15: continue
    rot = round(getattr(e.dxf, 'rotation', 0) or 0) if e.dxftype() == 'INSERT' else 0
    nombre = e.dxf.name if e.dxftype() == 'INSERT' else e.dxftype()
    out.append([t, round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2), rot, piso])
    cuenta[(t, nombre)] += 1
# Muros de los segundos pisos de oficinas (termopanel y drywall dibujados aparte)
for e in msp:
    if e.dxf.layer not in ('10_ESTRUCTURA_MURO_TERMOPANEL', '20_ARQUITECTURA_PARED_DRYWALL') or e.dxftype() != 'LWPOLYLINE': continue
    b = bbox.extents([e], fast=True); u = ubicar(b.extmin.x, b.extmin.y, b.extmax.x, b.extmax.y)
    if not u or u[4] < 2.8: continue  # solo segundos pisos: módulo (2,85), comedor (3,35) y oficinas (4,3)
    x0, y0, x1, y1, h = u
    if min(x1 - x0, y1 - y0) <= 0.3: muros2.append([round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2), h])
    else:  # contorno: sus 4 lados
        pts = [(p[0] + (u[0] - b.extmin.x), p[1] + (u[1] - b.extmin.y)) for p in e.get_points('xy')]
        for (ax, ay), (bx, by) in zip(pts, pts[1:] + ([pts[0]] if e.closed else [])):
            if abs(ax - bx) < 0.01 and abs(ay - by) < 0.01: continue
            muros2.append([round(min(ax, bx), 2), round(min(ay, by), 2), round(max(ax, bx), 2), round(max(ay, by), 2), h])
if lista:
    for (t, n), c in sorted(cuenta.items()): print(f'{t:14s} {c:4d}  {n}')
else:
    print('const MUEBLES_PF = ' + json.dumps(out, separators=(',', ':')) + ';')
    print('const MUROS2_PF = ' + json.dumps(muros2, separators=(',', ':')) + ';')
