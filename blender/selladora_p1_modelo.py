"""
Modelo Blender limpio de la Selladora P1 (linea larga de bolsas con cierre).

Solo el vehiculo: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): ~22 m de largo. Entrada negra (desbobinador, torre de acumulacion,
corte/plegado), tramo de acero inoxidable (sellado, cierre, estaciones transversales, troquel) y salida.
La linea avanza hacia -Y (salida de bolsas al frente); el piso en z=0.

Uso:
    python3 blender/selladora_p1_modelo.py     # con bpy de PyPI
    blender -b -P blender/selladora_p1_modelo.py
Guarda blender/selladora_p1_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Selladora_P1")
scene.collection.children.link(ROOT)
CUR = [ROOT]


def grupo(nombre):
    c = bpy.data.collections.new(nombre)
    ROOT.children.link(c)
    CUR[0] = c
    return c


def link(ob):
    CUR[0].objects.link(ob)
    return ob


def mesh_obj(name, bm, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return link(bpy.data.objects.new(name, me))


def box(name, size, loc, rot=(0, 0, 0), bevel=0.0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    ob = mesh_obj(name, bm, smooth=False)
    ob.location = loc
    ob.rotation_euler = rot
    if bevel:
        md = ob.modifiers.new("Bisel", "BEVEL")
        md.width = bevel
        md.segments = 3
    return ob


def cyl(name, r, depth, loc, axis="Z", verts=32, r2=None, rot=None):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts, radius1=r, radius2=r if r2 is None else r2, depth=depth)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    ob = mesh_obj(name, bm)
    for p in ob.data.polygons:
        p.use_smooth = len(p.vertices) == 4
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    return ob


def beam(name, p1, p2, t, t2=None, round_=False):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    ob = cyl(name, t / 2, d.length, (0, 0, 0), verts=12) if round_ else box(name, (t, t if t2 is None else t2, d.length), (0, 0, 0))
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.location = (p1 + p2) / 2
    return ob


def from_pydata(name, verts, faces, smooth=True, solidify=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    ob = link(bpy.data.objects.new(name, me))
    if solidify:
        md = ob.modifiers.new("Espesor", "SOLIDIFY")
        md.thickness = solidify
    return ob


def loft(name, stations, profile, closed_ends=True):
    """Superficie por secciones. stations: lista de x; profile(x) -> lista de (y, z) del
    medio perfil izquierdo (y>=0), se refleja para el lado derecho."""
    rings = []
    for x in stations:
        half = profile(x)
        full = half + [(-y, z) for (y, z) in reversed(half[1:-1])]
        rings.append([(x, y, z) for (y, z) in full])
    n = len(rings[0])
    verts = [v for r in rings for v in r]
    faces = []
    for i in range(len(rings) - 1):
        for j in range(n):
            j2 = (j + 1) % n
            faces.append((i * n + j, i * n + j2, (i + 1) * n + j2, (i + 1) * n + j))
    if closed_ends:
        faces.append(tuple(range(n))[::-1])
        faces.append(tuple(range((len(rings) - 1) * n, len(rings) * n)))
    return from_pydata(name, verts, faces)




def plate(name, prof, x, t=0.02, holes=()):
    """Placa lateral: perfil (y, z) extruido en X, con ventanas rectangulares (y, z, ancho, alto)."""
    n = len(prof)
    verts = [(x - t / 2, y, z) for y, z in prof] + [(x + t / 2, y, z) for y, z in prof]
    faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    ob = from_pydata(name, verts, faces, smooth=False)
    for (hy, hz, hwid, hh) in holes:
        c = box("Corte_Ventana", (t * 4, hwid, hh), (x, hy, hz))
        c.hide_render = c.hide_viewport = True
        md = ob.modifiers.new("Ventana", "BOOLEAN")
        md.object = c
        md.operation = "DIFFERENCE"
    return ob


def spiral_hose(name, p, turns=10, r=0.035, drop=0.40):
    pts = []
    n = turns * 10
    for i in range(n):
        a = i * math.tau / 10
        pts.append(Vector((p[0] + r * math.cos(a), p[1] + r * math.sin(a), p[2] - drop * i / n)))
    return curve_tube(name, pts, 0.005)


def curve_tube(name, pts, radius, res=8):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 3
    cu.resolution_u = res
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for q, v in zip(sp.points, pts):
        q.co = (v[0], v[1], v[2], 1)
    return link(bpy.data.objects.new(name, cu))


HW = 0.70           # semiancho del cuerpo inoxidable
ZT = 0.95           # paso del film sobre el tramo inoxidable
OP = 1              # lado del operador (+X): volantes, ventanas, puestos de mando


def knob_row(prefix, y0, y1, z, n, x):
    """Fila de perillas negras de ajuste (tipo estrella) sobre una viga."""
    for k in range(n):
        y = y0 + (y1 - y0) * k / max(1, n - 1)
        cyl(f"{prefix}_Vastago_Perilla", 0.008, 0.10, (x, y, z + 0.05), verts=8)
        cyl(f"{prefix}_Perilla", 0.03, 0.025, (x, y, z + 0.11), verts=6)


def handwheel(name, y, z, x=None):
    x = OP * (HW + 0.12) if x is None else x
    cyl(name, 0.09, 0.02, (x, y, z), axis="X", verts=24)
    cyl(name + "_Eje", 0.012, 0.12, (x - OP * 0.06, y, z), axis="X", verts=12)
    for k in range(3):
        a = k * math.tau / 3
        box(name + "_Rayo", (0.01, 0.16, 0.012), (x, y, z), rot=(a, 0, 0))


def seal_beam(tag, y0, y1, knobs=10):
    """Viga de sellado longitudinal: bastidor negro con agujeros, perillas y resortes en los extremos."""
    L = y0 - y1
    yc = (y0 + y1) / 2
    for sx in (-1, 1):
        box(f"{tag}_Larguero_Negro", (0.05, L, 0.16), (sx * (HW - 0.12), yc, ZT + 0.28), bevel=0.005)
    box(f"{tag}_Travesano_Negro", (2 * HW - 0.18, 0.08, 0.06), (0, y0 - 0.05, ZT + 0.38))
    box(f"{tag}_Travesano_Negro", (2 * HW - 0.18, 0.08, 0.06), (0, y1 + 0.05, ZT + 0.38))
    box(f"{tag}_Barra_Sellado", (0.14, L - 0.20, 0.06), (0.10, yc, ZT + 0.12), bevel=0.005)
    box(f"{tag}_Placa_Teflon", (0.40, L - 0.30, 0.01), (-0.20, yc, ZT + 0.03))
    knob_row(tag, y0 - 0.15, y1 + 0.15, ZT + 0.36, knobs, OP * (HW - 0.12))
    knob_row(tag + "_Interior", y0 - 0.25, y1 + 0.25, ZT + 0.36, max(3, knobs // 2), -OP * (HW - 0.12))
    for yy in (y0 - 0.12, y1 + 0.12):
        cyl(f"{tag}_Resorte_Negro", 0.04, 0.22, (OP * (HW - 0.05), yy, ZT + 0.12), verts=16)
        cyl(f"{tag}_Guia_Resorte", 0.012, 0.36, (OP * (HW - 0.05), yy, ZT + 0.18), verts=8)
    box(f"{tag}_Etiqueta_Seguridad", (0.012, 0.25, 0.10), (OP * (HW - 0.095), yc, ZT + 0.28))
    for k in range(3):
        cyl(f"{tag}_Agujero_Viga", 0.035, 0.01, (OP * (HW - 0.093), yc - 0.45 + k * 0.45, ZT + 0.30), axis="X", verts=16)


# ===========================================================================
# 01 Entrada negra: desbobinador y cabezal de alimentacion
# ===========================================================================
grupo("01_Entrada_Desbobinador")
EW = 0.75
A0, A1 = 17.40, 15.40
for sx, sn in ((1, "Op"), (-1, "Trasero")):
    plate(f"Placa_Lateral_Entrada_{sn}",
          [(A0, 0.10), (A1, 0.10), (A1, 2.05), (A1 + 0.70, 2.05), (A1 + 0.95, 1.55), (A0 - 0.30, 1.05), (A0, 0.70)],
          sx * EW, t=0.03, holes=[(A1 + 0.45, 0.45, 0.45, 0.45), (A1 + 1.25, 0.45, 0.35, 0.35),
                                   (A1 + 0.35, 1.55, 0.30, 0.25)])
    box(f"Pie_Entrada_{sn}", (0.12, 0.25, 0.10), (sx * EW, A0 - 0.20, 0.05))
    box(f"Pie_Entrada_{sn}", (0.12, 0.25, 0.10), (sx * EW, A1 + 0.15, 0.05))
for y, z in ((A0 - 0.25, 0.35), (A1 + 0.20, 0.35), (A1 + 0.30, 1.95)):
    box("Travesano_Entrada", (2 * EW, 0.08, 0.08), (0, y, z))
# brazo superior inclinado con rodillo de entrada
for sx in (-1, 1):
    beam("Brazo_Superior_Inclinado", (sx * (EW + 0.04), A1 + 0.95, 1.55), (sx * (EW + 0.04), A0 + 0.40, 2.05), 0.05, t2=0.14)
cyl("Rodillo_Superior_Entrada", 0.045, 2 * EW + 0.20, (0, A0 + 0.40, 2.12), axis="X")
# bobina de film en la parte baja y rodillos
cyl("Bobina_Film", 0.16, 1.05, (0, A0 + 0.15, 0.55), axis="X", verts=48)
cyl("Eje_Bobina", 0.03, 2 * EW + 0.45, (0, A0 + 0.15, 0.55), axis="X", verts=16)
for sx in (-1, 1):
    beam("Brazo_Bobina", (sx * (EW + 0.04), A0 - 0.20, 0.75), (sx * (EW + 0.04), A0 + 0.15, 0.55), 0.05, t2=0.10)
for k, (y, z) in enumerate(((A0 - 0.30, 1.05), (A0 - 0.60, 1.30), (A1 + 1.10, 1.45), (A1 + 0.70, 1.70),
                            (A1 + 0.40, 1.20), (A1 + 0.20, 0.95))):
    cyl("Rodillo_Guia_Entrada", 0.04, 2 * EW - 0.04, (0, y, z), axis="X")
cyl("Rodillo_Goma_Traccion_Entrada", 0.06, 2 * EW - 0.08, (0, A1 + 0.95, 1.20), axis="X")
# cubiertas de acero inoxidable con rejillas (motores) en el lado del operador
for k, (y, z) in enumerate(((A1 + 1.30, 1.55), (A0 - 0.25, 0.75))):
    box("Cubierta_Inoxidable_Motor", (0.30, 0.45, 0.35), (EW + 0.17, y, z), bevel=0.01)
    for j in range(5):
        box("Ranura_Rejilla", (0.006, 0.03, 0.22), (EW + 0.323, y - 0.12 + j * 0.06, z))
# paneles neumaticos con manometros y mangueras amarillas en espiral
for k, (y, z) in enumerate(((A1 + 0.80, 1.60), (A1 + 1.00, 0.60))):
    box("Panel_Neumatico_Inoxidable", (0.02, 0.45, 0.16), (EW + 0.03, y, z), bevel=0.003)
    for j in range(3):
        cyl("Manometro", 0.03, 0.02, (EW + 0.05, y - 0.13 + j * 0.13, z + 0.02), axis="X", verts=16)
    spiral_hose("Manguera_Espiral_Amarilla", (EW + 0.06, y + 0.25, z - 0.05), turns=12, drop=0.30)
# controladores de temperatura, motorreductores azules y caja electrica gris
for k in range(3):
    box("Controlador_Temperatura", (0.02, 0.10, 0.10), (EW + 0.025, A1 + 0.12, 1.40 - k * 0.14))
for k, z in enumerate((1.25, 0.55)):
    box("Reductor_Azul_Entrada", (0.16, 0.16, 0.16), (-(EW + 0.10), A1 + 0.60, z), bevel=0.012)
    cyl("Motor_Azul_Entrada", 0.07, 0.25, (-(EW + 0.10), A1 + 0.60, z - 0.20), verts=24)
box("Caja_Electrica_Gris", (0.30, 0.50, 0.70), (-(EW + 0.30), A1 + 0.20, 0.45), bevel=0.01)
for j in range(4):
    box("Rejilla_Caja_Electrica", (0.006, 0.20, 0.02), (-(EW + 0.453), A1 + 0.20, 0.70 + j * 0.03))

# ===========================================================================
# 02 Torre de acumulacion (portico negro con columnas de bailarin)
# ===========================================================================
grupo("02_Torre_de_Acumulacion")
T0, T1 = 15.40, 13.80
for sx in (-1, 1):
    for yy in (T0 - 0.05, T1 + 0.05):
        box("Columna_Portico", (0.08, 0.08, 2.05), (sx * EW, yy, 1.025), bevel=0.004)
    box("Larguero_Superior_Portico", (0.08, T0 - T1, 0.10), (sx * EW, (T0 + T1) / 2, 2.00))
    box("Larguero_Inferior_Portico", (0.08, T0 - T1, 0.08), (sx * EW, (T0 + T1) / 2, 0.15))
    plate("Placa_Agujereada_Portico", [(T0 - 0.05, 1.60), (T1 + 0.05, 1.60), (T1 + 0.05, 1.95), (T0 - 0.05, 1.95)],
          sx * (EW + 0.045), t=0.01, holes=[(T1 + 0.30 + k * 0.30, 1.78, 0.12, 0.12) for k in range(4)])
box("Travesano_Superior_Portico", (2 * EW + 0.08, 0.10, 0.10), (0, (T0 + T1) / 2, 2.05))
# columnas verticales del bailarin (acumulador)
for k, (x, y) in enumerate(((-0.25, 14.85), (0.25, 14.85), (-0.25, 14.35), (0.25, 14.35))):
    box("Columna_Bailarin", (0.07, 0.07, 1.70), (x, y, 1.05), bevel=0.004)
for z in (0.40, 1.80):
    cyl("Rodillo_Acumulador", 0.04, 2 * EW - 0.04, (0, 14.85, z), axis="X")
    cyl("Rodillo_Acumulador", 0.04, 2 * EW - 0.04, (0, 14.35, z), axis="X")
cyl("Rodillo_Bailarin_Movil", 0.045, 2 * EW - 0.10, (0, 14.60, 1.10), axis="X")
# base en marco y motor azul arriba
box("Marco_Base_Torre", (2 * EW, T0 - T1, 0.05), (0, (T0 + T1) / 2, 0.06))
for k in range(4):
    beam("Diagonal_Base_Torre", (-EW, T0 - 0.05 - k * 0.40, 0.06), (EW, T0 - 0.45 - k * 0.40, 0.06), 0.04)
box("Reductor_Azul_Torre", (0.18, 0.18, 0.16), (0.10, 14.60, 2.18), bevel=0.012)
cyl("Motor_Azul_Torre", 0.08, 0.28, (0.30, 14.60, 2.18), axis="X", verts=24)
cyl("Rodillo_Salida_Torre", 0.04, 2 * EW + 0.10, (0, T1 - 0.05, 2.12), axis="X")

# ===========================================================================
# 03 Modulo negro de corte y plegado + estacion auxiliar
# ===========================================================================
grupo("03_Modulo_Corte_y_Plegado")
M0, M1 = 13.80, 11.60
for sx, sn in ((1, "Op"), (-1, "Trasero")):
    plate(f"Placa_Lateral_Modulo_{sn}", [(M0, 0.10), (M1, 0.10), (M1, 1.15), (M0, 1.15)], sx * EW, t=0.03,
          holes=[(M0 - 0.50, 0.45, 0.45, 0.45), (M1 + 0.60, 0.45, 0.50, 0.40), (M0 - 1.10, 0.95, 0.15, 0.15)])
    for yy in (M0 - 0.15, M1 + 0.15):
        cyl(f"Pata_Nivelacion_Modulo_{sn}", 0.035, 0.10, (sx * EW, yy, 0.05), verts=16)
for k in range(5):
    cyl("Rodillo_Modulo", 0.035, 2 * EW - 0.04, (0, M0 - 0.25 - k * 0.42, 1.10), axis="X")
for k in range(3):
    cyl("Cuchilla_Circular", 0.10, 0.006, (-0.30 + k * 0.30, M0 - 1.20, 1.18), axis="X", verts=32)
cyl("Eje_Cuchillas", 0.015, 2 * EW - 0.04, (0, M0 - 1.20, 1.18), axis="X", verts=12)
for sx in (-1, 1):
    beam("Guia_Plegado", (sx * 0.55, M0 - 1.40, 1.15), (sx * 0.20, M1 + 0.10, 1.05), 0.03)
box("Tablero_Botonera_Modulo", (0.03, 0.25, 0.30), (EW + 0.03, M0 - 0.30, 1.00), bevel=0.004)
for k in range(3):
    cyl("Pulsador_Modulo", 0.018, 0.02, (EW + 0.05, M0 - 0.30, 1.08 - k * 0.07), axis="X", verts=16)
spiral_hose("Manguera_Espiral_Amarilla_Modulo", (EW + 0.06, M0 - 0.70, 1.10), turns=10, drop=0.30)
# estacion auxiliar (pedestal negro con brazos porta-rollos y botonera)
ax_, ay_ = EW + 0.70, 12.40
box("Estacion_Auxiliar_Pedestal", (0.35, 0.40, 0.95), (ax_, ay_, 0.475), bevel=0.01)
box("Estacion_Auxiliar_Panel", (0.02, 0.30, 0.40), (ax_ + 0.185, ay_, 0.75))
for k in range(3):
    cyl("Estacion_Auxiliar_Manometro", 0.03, 0.02, (ax_ + 0.20, ay_ - 0.08 + k * 0.08, 0.85), axis="X", verts=16)
cyl("Estacion_Auxiliar_Luz_Roja", 0.012, 0.02, (ax_ + 0.20, ay_ + 0.10, 0.62), axis="X", verts=12)
for k, z in enumerate((0.55, 0.75, 0.95, 1.10)):
    cyl("Estacion_Auxiliar_Brazo_Rollo", 0.025, 0.55, (ax_ + 0.25, ay_ - 0.10, z), axis="X", verts=12)

# ===========================================================================
# 04 Tramo de acero inoxidable (cuerpo continuo)
# ===========================================================================
grupo("04_Cuerpo_Inoxidable")
S0, S1 = 11.60, -2.90
box("Cuerpo_Inoxidable", (2 * HW, S0 - S1, ZT - 0.20), (0, (S0 + S1) / 2, 0.12 + (ZT - 0.20) / 2), bevel=0.012)
box("Bastidor_Negro_Superior", (2 * HW - 0.06, S0 - S1, 0.06), (0, (S0 + S1) / 2, ZT - 0.05))
for k, y in enumerate([10.6, 8.9, 7.0, 5.0, 3.0, 1.0, -0.9, -2.4]):
    box("Ventana_Inspeccion", (0.012, 0.32, 0.30), (OP * (HW + 0.006), y, 0.55))
    cyl("Perilla_Ventana", 0.025, 0.02, (OP * (HW + 0.016), y, 0.55), axis="X", verts=12)
for k in range(28):
    y = S0 - 0.25 - k * (S0 - S1 - 0.5) / 27
    cyl("Pata_Nivelacion_Cuerpo", 0.03, 0.12, (OP * (HW - 0.06), y, 0.06), verts=12)
    cyl("Pata_Nivelacion_Cuerpo", 0.03, 0.12, (-OP * (HW - 0.06), y, 0.06), verts=12)
    if k % 2 == 0:
        cyl("Cerradura_Puerta", 0.015, 0.02, (OP * (HW + 0.01), y, 0.82), axis="X", verts=12)
for k in range(30):
    y = S0 - 0.30 - k * (S0 - S1 - 0.6) / 29
    cyl("Barra_Transversal_Guia", 0.012, 0.35, (OP * (HW + 0.05), y, ZT - 0.02), axis="X", verts=8)

# ===========================================================================
# 05 Estaciones de sellado sobre el tramo inoxidable
# ===========================================================================
grupo("05_Estaciones_de_Sellado")
seal_beam("Viga_Sellado_1", 11.40, 9.40, knobs=12)
handwheel("Volante_Viga_1", 10.40, 0.70)
seal_beam("Viga_Sellado_2", 9.00, 7.00, knobs=12)
handwheel("Volante_Viga_2", 8.00, 0.70)
# puesto de mando inoxidable (paro de emergencia y pulsadores)
box("Puesto_Mando_Inoxidable", (0.25, 0.30, 0.35), (OP * (HW - 0.10), 9.20, ZT + 0.20), bevel=0.01)
cyl("Paro_Emergencia", 0.03, 0.03, (OP * (HW + 0.04), 9.20, ZT + 0.30), axis="X", verts=24)
for k in range(3):
    cyl("Pulsador_Puesto", 0.017, 0.02, (OP * (HW + 0.035), 9.20, ZT + 0.22 - k * 0.06), axis="X", verts=16)
# aplicador de cierre: alimentador vibratorio, generador ultrasonico rojo, calentador
grupo("06_Aplicador_de_Cierre")
cyl("Alimentador_Vibratorio_Base", 0.14, 0.25, (-0.25, 6.30, ZT + 0.45), verts=24)
cyl("Alimentador_Vibratorio_Taza", 0.26, 0.14, (-0.25, 6.30, ZT + 0.65), verts=48, r2=0.30)
beam("Riel_Alimentacion_Cierre", (-0.25, 6.05, ZT + 0.62), (0.05, 5.60, ZT + 0.20), 0.03)
box("Mesa_Alimentador", (0.45, 0.45, 0.02), (-0.25, 6.30, ZT + 0.32))
for sx in (-1, 1):
    for sy in (-1, 1):
        cyl("Pata_Mesa_Alimentador", 0.012, 0.30, (-0.25 + sx * 0.18, 6.30 + sy * 0.18, ZT + 0.16), verts=8)
box("Generador_Ultrasonico_Rojo", (0.35, 0.45, 0.16), (0.20, 5.85, ZT + 0.62), bevel=0.012)
box("Pantalla_Generador", (0.012, 0.12, 0.07), (0.38, 5.85, ZT + 0.64))
box("Soporte_Generador", (0.05, 0.05, 0.55), (0.30, 5.85, ZT + 0.27))
box("Calentador_Negro", (0.16, 0.16, 0.28), (-0.30, 5.40, ZT + 0.30), bevel=0.01)
box("Cabezal_Ultrasonico", (0.20, 0.25, 0.20), (0.10, 5.40, ZT + 0.20), bevel=0.01)
box("Puesto_Mando_Cierre", (0.25, 0.30, 0.35), (OP * (HW - 0.10), 5.10, ZT + 0.20), bevel=0.01)
cyl("Paro_Emergencia_Cierre", 0.03, 0.03, (OP * (HW + 0.04), 5.10, ZT + 0.30), axis="X", verts=24)
# estaciones de sellado transversal numeradas 1..8 (resortes rojos)
grupo("07_Sellado_Transversal_1_a_8")
for k in range(4):
    y = 4.60 - k * 0.65
    for j, dy in enumerate((0.0, -0.30)):
        n = 2 * k + 1 + j
        st = f"Estacion_{n}"
        box(f"{st}_Brazo_Negro", (2 * HW - 0.10, 0.08, 0.08), (0, y + dy, ZT + 0.48 + 0.06 * (1 - j)),
            rot=(0, 0, math.radians(8)))
        box(f"{st}_Cabezal_Cilindro", (0.16, 0.16, 0.14), (OP * (HW - 0.15), y + dy, ZT + 0.62 + 0.06 * (1 - j)),
            bevel=0.01)
        cyl(f"{st}_Resorte_Rojo", 0.045, 0.24, (OP * (HW - 0.15), y + dy, ZT + 0.32), verts=16)
        cyl(f"{st}_Guia_Resorte", 0.012, 0.44, (OP * (HW - 0.15), y + dy, ZT + 0.32), verts=8)
        box(f"{st}_Barra_Sellado", (2 * HW - 0.20, 0.03, 0.04), (0, y + dy, ZT + 0.08))
        box(f"{st}_Numero", (0.012, 0.06, 0.06), (OP * (HW - 0.065), y + dy, ZT + 0.62 + 0.06 * (1 - j)))
        handwheel(f"Volante_{st}", y + dy, 0.80)
for k in range(3):
    box("Separador_Estaciones", (2 * HW - 0.10, 0.03, 0.30), (0, 4.28 - k * 0.65, ZT + 0.15))
seal_beam("Viga_Sellado_3", 1.80, 0.40, knobs=10)
handwheel("Volante_Viga_3", 1.10, 0.70)
# troqueladora de asas con bolsa de recorte
grupo("08_Troquel")
for sx in (-1, 1):
    box("Troquel_Columna", (0.04, 0.04, 0.45), (sx * 0.35, -0.10, ZT + 0.22))
box("Troquel_Placa_Superior", (0.85, 0.40, 0.04), (0, -0.10, ZT + 0.46), bevel=0.005)
box("Troquel_Prensa", (0.30, 0.30, 0.20), (0, -0.10, ZT + 0.32), bevel=0.01)
for k in range(4):
    cyl("Troquel_Cilindro_Punzon", 0.035, 0.14, (-0.45 + k * 0.30, -0.75, ZT + 0.22), verts=16)
box("Troquel_Riel_Punzones", (1.10, 0.06, 0.05), (0, -0.75, ZT + 0.12))
box("Bolsa_Recorte_Azul", (0.35, 0.35, 0.40), (0.10, -0.10, ZT - 0.25), bevel=0.08)
for k in range(10):
    cyl("Barra_Guia_Salida", 0.012, 2 * HW - 0.10, (0, -1.30 - k * 0.15, ZT + 0.06), axis="X", verts=8)

# ===========================================================================
# 09 Salida: apilador de bandas verdes, tablero con pantalla y baliza
# ===========================================================================
grupo("09_Salida_y_Tablero")
O0, O1 = -2.90, -4.30
box("Carcasa_Inoxidable_Salida", (1.00, 0.60, ZT - 0.12), (0, O0 - 0.30, 0.12 + (ZT - 0.12) / 2), bevel=0.01)
box("Apilador_Base_Inoxidable", (1.10, O0 - O1 - 0.55, 0.30), (0, (O0 - 0.60 + O1) / 2, 0.70), bevel=0.01)
for k in range(8):
    box("Banda_Verde_Apilador", (0.95, 0.06, 0.012), (0, O0 - 0.70 - k * 0.09, 0.86))
for k in range(3):
    cyl("Perilla_Apilador", 0.02, 0.02, (OP * 0.56, O0 - 0.80 - k * 0.12, 0.68), axis="X", verts=12)
for sx in (-1, 1):
    box("Pata_Apilador", (0.05, 0.05, 0.55), (sx * 0.45, O1 + 0.10, 0.275))
box("Tope_Apilador", (0.30, 0.012, 0.15), (0.20, O0 - 0.62, 0.95))
cx_, cy_ = -OP * (HW + 0.45), O0 - 0.20
box("Gabinete_Tablero_Blanco", (0.55, 0.70, 1.20), (cx_, cy_, 0.60), bevel=0.012)
box("Brazo_Pantalla", (0.40, 0.08, 0.08), (cx_ + OP * 0.25, cy_ + 0.10, 1.30))
box("Caja_Pantalla_HMI", (0.12, 0.42, 0.34), (cx_ + OP * 0.45, cy_ + 0.10, 1.30), bevel=0.012)
box("Pantalla_HMI", (0.012, 0.30, 0.20), (cx_ + OP * 0.513, cy_ + 0.10, 1.33))
for k in range(3):
    cyl("Pulsador_HMI", 0.016, 0.02, (cx_ + OP * 0.52, cy_ + 0.00 + k * 0.08, 1.18), axis="X", verts=16)
cyl("Baliza_Poste", 0.015, 0.45, (cx_ + 0.10, cy_ - 0.25, 1.42), verts=12)
z = 1.65
for nm in ("Baliza_Verde", "Baliza_Ambar", "Baliza_Roja"):
    cyl(nm, 0.035, 0.07, (cx_ + 0.10, cy_ - 0.25, z + 0.035), verts=24)
    z += 0.072

# ===========================================================================
# 10 Film
# ===========================================================================
grupo("10_Film")
path = [(A0 + 0.15, 0.71), (A0 - 0.30, 1.09), (A0 - 0.60, 1.34), (A0 + 0.40, 2.17), (A1 + 1.10, 1.49),
        (A1 + 0.70, 1.74), (A1 + 0.30, 2.0), (14.85, 1.84), (14.85, 0.44), (14.60, 1.06), (14.35, 0.44),
        (14.35, 1.84), (T1 - 0.05, 2.17), (M0 - 0.25, 1.14), (M1 + 0.10, 1.10), (S0, ZT + 0.03),
        (O0 - 0.10, ZT + 0.03)]
verts, faces = [], []
for (y, z) in path:
    verts += [(-0.45, y, z), (0.45, y, z)]
for i in range(len(path) - 1):
    faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
from_pydata("Lamina_Film", verts, faces, smooth=False)
for k in range(4):
    box("Bolsa_Terminada", (0.55, 0.30, 0.004), (0.05, O0 - 1.05, 0.87 + 0.005 * k))

# ---------------------------------------------------------------------------
# Aplicar modificadores y limpiar auxiliares
# ---------------------------------------------------------------------------
dg = bpy.context.evaluated_depsgraph_get()
for ob in list(bpy.data.objects):
    if ob.type == "MESH" and ob.modifiers and not ob.hide_render:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
        old = ob.data
        ob.modifiers.clear()
        ob.data = me
        bpy.data.meshes.remove(old)
for ob in list(bpy.data.objects):
    if ob.hide_render:
        bpy.data.objects.remove(ob, do_unlink=True)

# numerar piezas repetidas (p.ej. rayos de llanta) y nombrar los datos igual que el objeto
grupos = {}
for ob in bpy.data.objects:
    grupos.setdefault(ob.name.split(".")[0], []).append(ob)
for base, obs in grupos.items():
    for ob in obs:
        ob.name = "__tmp__" + ob.name
for base, obs in grupos.items():
    obs.sort(key=lambda o: (round(o.matrix_world.translation.x, 3), round(o.matrix_world.translation.z, 3)))
    for k, ob in enumerate(obs):
        nm = base if len(obs) == 1 else f"{base}_{k + 1:02d}"
        ob.name = nm
        if ob.data is not None:
            ob.data.name = nm
for d in list(bpy.data.meshes):
    if d.users == 0:
        bpy.data.meshes.remove(d)

scene.unit_settings.system = "METRIC"
here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
out = os.path.join(here, "selladora_p1_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
