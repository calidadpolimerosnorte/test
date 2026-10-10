"""
Modelo Blender limpio de un SUV compacto (tipo Chevrolet Tracker 2021+).

Solo el vehiculo: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): largo 4.27, ancho 1.79, alto 1.63, distancia entre ejes 2.57.
Ejes: X hacia adelante, Y hacia la izquierda, Z hacia arriba; el piso en z=0.

Uso:
    python3 blender/vehiculo_suv_modelo.py     # con bpy de PyPI
    blender -b -P blender/vehiculo_suv_modelo.py
Guarda blender/vehiculo_suv_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("SUV_Compacto")
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


def lerp_table(table, x):
    """Interpola linealmente columnas de una tabla [(x, a, b, ...)] ordenada por x descendente."""
    if x >= table[0][0]:
        return table[0][1:]
    for a, b in zip(table, table[1:]):
        if a[0] >= x >= b[0]:
            t = (x - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0
            return tuple(va + (vb - va) * t for va, vb in zip(a[1:], b[1:]))
    return table[-1][1:]


# ---------------------------------------------------------------------------
# Medidas principales
# ---------------------------------------------------------------------------
XF, XR = 2.135, -2.135        # paragolpes delantero / trasero
AXF, AXR = 1.30, -1.27        # ejes (distancia entre ejes 2.57)
TRACK = 0.77                  # semitrocha
RT = 0.345                    # radio del neumatico (215/55 R18)
WT = 0.215                    # ancho del neumatico
HW = 0.895                    # semiancho de carroceria (1.79 m)

# carroceria inferior: (x, semiancho, z_inferior, z_superior/cintura)
BODY = [
    (2.135, 0.70, 0.30, 0.74),
    (2.10, 0.80, 0.27, 0.82),
    (2.00, 0.86, 0.25, 0.90),
    (1.75, 0.885, 0.23, 0.96),
    (1.40, 0.895, 0.22, 1.00),
    (0.95, 0.895, 0.22, 1.04),
    (0.40, 0.895, 0.22, 1.06),
    (-0.50, 0.895, 0.22, 1.08),
    (-1.30, 0.890, 0.24, 1.10),
    (-1.80, 0.870, 0.30, 1.10),
    (-2.02, 0.830, 0.36, 1.08),
    (-2.135, 0.75, 0.42, 1.02),
]
# cabina: (x, z_base, z_techo, semiancho_base, semiancho_techo)
CAB = [
    (0.95, 1.04, 1.06, 0.84, 0.80),
    (0.70, 1.05, 1.22, 0.85, 0.74),
    (0.40, 1.06, 1.41, 0.85, 0.68),
    (0.12, 1.065, 1.545, 0.855, 0.66),
    (-0.10, 1.07, 1.585, 0.855, 0.66),
    (-0.70, 1.08, 1.605, 0.855, 0.66),
    (-1.30, 1.10, 1.595, 0.85, 0.66),
    (-1.70, 1.10, 1.555, 0.84, 0.65),
    (-1.90, 1.10, 1.47, 0.83, 0.63),
    (-2.00, 1.09, 1.30, 0.82, 0.62),
    (-2.04, 1.085, 1.12, 0.815, 0.62),
]


def body_profile(x):
    w, zb, zt = lerp_table(BODY, x)
    r = 0.09
    return [(0.0, zb), (w - r, zb), (w - 0.02, zb + 0.05), (w, zb + r + 0.03), (w, zt - 0.12),
            (w - 0.015, zt - 0.05), (w - 0.06, zt - 0.01), (w * 0.5, zt + 0.005), (0.0, zt + 0.01)]


def cab_profile(x):
    zb, zt, wb, wtop = lerp_table(CAB, x)
    return [(0.0, zb), (wb, zb), (wb - (wb - wtop) * 0.55, zb + (zt - zb) * 0.62),
            (wtop + 0.03, zt - 0.03), (wtop - 0.06, zt), (0.0, zt + 0.012)]


def cab_point(x, frac, side=1, out=0.006):
    """Punto sobre el costado de la cabina: frac 0 = base, 1 = borde del techo."""
    zb, zt, wb, wtop = lerp_table(CAB, x)
    z = zb + (zt - 0.03 - zb) * frac
    if frac <= 0.62 / 0.97:
        y = wb - (wb - wtop) * 0.55 * (frac / (0.62 / 0.97))
    else:
        f = (frac - 0.639) / (1 - 0.639)
        y = wb - (wb - wtop) * 0.55 - ((wb - (wb - wtop) * 0.55) - (wtop + 0.03)) * f
    return (x, side * (y + out), z)


# ---------------------------------------------------------------------------
# 01 Carroceria
# ---------------------------------------------------------------------------
grupo("01_Carroceria")
xs = [XF - i * (XF - XR) / 60 for i in range(61)]
body = loft("Carroceria", xs, body_profile)
sub = body.modifiers.new("Suavizado", "SUBSURF")
sub.levels = 2
for ax, nm in ((AXF, "Delantero"), (AXR, "Trasero")):
    c = cyl(f"Corte_Paso_Rueda_{nm}", RT + 0.055, 2.4, (ax, 0, RT), axis="Y", verts=48)
    c.hide_render = c.hide_viewport = True
    md = body.modifiers.new(f"PasoRueda{nm}", "BOOLEAN")
    md.object = c
    md.operation = "DIFFERENCE"
# capo (panel separado levemente elevado) y portón trasero
hood = loft("Capo", [2.02 - i * (2.02 - 0.98) / 16 for i in range(17)],
            lambda x: [(0.0, lerp_table(BODY, x)[2] + 0.012),
                       (lerp_table(BODY, x)[0] * 0.80, lerp_table(BODY, x)[2] + 0.004),
                       (lerp_table(BODY, x)[0] * 0.93, lerp_table(BODY, x)[2] - 0.015)])
hood.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.006
# lineas de puertas (ranuras finas) en ambos lados
for side, sn in ((1, "Izq"), (-1, "Der")):
    for xd, nm in ((0.98, "Delantera_Inicio"), (-0.02, "Delantera_Fin"), (-1.02, "Trasera_Fin")):
        beam(f"Linea_Puerta_{nm}_{sn}", (xd, side * (HW + 0.001), 0.34), (xd + 0.03, side * (HW + 0.001), 1.03),
             0.006, t2=0.004)
    beam(f"Linea_Puerta_Inferior_{sn}", (0.98, side * (HW + 0.001), 0.36), (-1.02, side * (HW + 0.001), 0.36),
         0.006, t2=0.004)
    # nervadura lateral (linea de caracter alta)
    beam(f"Nervio_Lateral_{sn}", (1.75, side * (HW - 0.002), 0.90), (-1.95, side * (HW - 0.010), 0.98),
         0.012, t2=0.012)

# ---------------------------------------------------------------------------
# 02 Cabina, pilares y vidrios
# ---------------------------------------------------------------------------
grupo("02_Cabina_y_Vidrios")
xc = [CAB[0][0] - i * (CAB[0][0] - CAB[-1][0]) / 50 for i in range(51)]
loft("Cabina", xc, cab_profile)


def side_window(name, x0, x1, side, f0=0.10, f1=0.90, slant0=0.0, slant1=0.0, n=8):
    """Vidrio lateral sobre el costado de la cabina (con inclinacion de los pilares)."""
    pts_bot = [cab_point(x0 + (x1 - x0) * i / n, f0, side) for i in range(n + 1)]
    pts_top = [cab_point(x0 + slant0 + (x1 - slant1 - x0 - slant0) * i / n, f1, side) for i in range(n + 1)]
    verts = pts_bot + pts_top
    faces = [(i, i + 1, n + 2 + i, n + 1 + i) for i in range(n)]
    if side < 0:
        faces = [f[::-1] for f in faces]
    from_pydata(name, verts, faces, smooth=False, solidify=0.004)


for side, sn in ((1, "Izq"), (-1, "Der")):
    side_window(f"Vidrio_Puerta_Delantera_{sn}", 0.78, 0.02, side, slant0=-0.30, slant1=0.0)
    side_window(f"Vidrio_Puerta_Trasera_{sn}", -0.06, -0.98, side, slant1=-0.05)
    side_window(f"Vidrio_Cuarto_Trasero_{sn}", -1.06, -1.72, side, f1=0.82, slant1=-0.10)
    # espejo del pilar A (triangulo) y pilares visibles en negro
    beam(f"Pilar_B_{sn}", cab_point(-0.02, 0.05, side, 0.009), cab_point(-0.04, 0.95, side, 0.009), 0.06, t2=0.01)
    beam(f"Pilar_C_{sn}", cab_point(-1.02, 0.05, side, 0.009), cab_point(-1.04, 0.95, side, 0.009), 0.05, t2=0.01)
# parabrisas y luneta (siguen la cabina por delante y por detras)


def glass_band(name, xa, xb, n=10, inset=0.06):
    verts, faces = [], []
    for i in range(n + 1):
        x = xa + (xb - xa) * i / n
        zb, zt, wb, wtop = lerp_table(CAB, x)
        verts += [(x + 0.004, -(wtop - inset), zt + 0.010), (x + 0.004, (wtop - inset), zt + 0.010)]
    for i in range(n):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    from_pydata(name, verts, faces, smooth=False, solidify=0.004)


glass_band("Parabrisas", 0.92, 0.14)
glass_band("Luneta_Trasera", -1.74, -2.02)
# limpiaparabrisas
for k, y in enumerate((0.30, -0.25)):
    beam(f"Limpiaparabrisas_{k + 1}", (0.93, y, 1.075), (0.80, y + 0.42, 1.17), 0.02, t2=0.012)
beam("Limpiaparabrisas_Trasero", (-2.02, 0.0, 1.16), (-1.98, 0.30, 1.32), 0.018, t2=0.012)
# antena aleta de tiburon
cyl("Antena_Aleta_Tiburon", 0.05, 0.16, (-1.60, 0, 1.64), verts=12, r2=0.01, rot=(0, math.radians(20), 0))

# ---------------------------------------------------------------------------
# 03 Frente: parrillas, faros, emblema, paragolpes
# ---------------------------------------------------------------------------
grupo("03_Frente")
# parrilla superior delgada con barra cromada y emblema
box("Parrilla_Superior", (0.03, 1.10, 0.09), (XF - 0.015, 0, 0.80), bevel=0.01)
box("Barra_Cromada_Superior", (0.02, 1.30, 0.035), (XF + 0.002, 0, 0.745), bevel=0.008)
for side, sn in ((1, "Izq"), (-1, "Der")):
    beam(f"Barra_Cromada_Extension_{sn}", (XF - 0.005, side * 0.65, 0.745), (XF - 0.09, side * 0.80, 0.78), 0.03)
box("Emblema_Frontal", (0.015, 0.16, 0.055), (XF + 0.012, 0, 0.80), bevel=0.005)
# parrilla inferior grande (trapecio) con lamas horizontales
v = []
for (y, z) in ((0.52, 0.66), (-0.52, 0.66), (-0.42, 0.40), (0.42, 0.40)):
    v.append((XF - 0.01, y, z))
from_pydata("Parrilla_Inferior_Marco", v, [(0, 1, 2, 3)], smooth=False, solidify=0.03)
for k in range(5):
    z = 0.62 - k * 0.05
    w = 0.50 - k * 0.022
    box(f"Lama_Parrilla_{k + 1}", (0.02, 2 * w, 0.012), (XF + 0.005, 0, z))
box("Soporte_Placa_Delantera", (0.01, 0.40, 0.12), (XF + 0.02, 0, 0.52))
# faros delanteros alargados (afilados hacia el centro) y luces diurnas
for side, sn in ((1, "Izq"), (-1, "Der")):
    verts = [(XF - 0.05, side * 0.56, 0.835), (XF - 0.04, side * 0.56, 0.875),
             (XF - 0.20, side * 0.86, 0.905), (XF - 0.24, side * 0.86, 0.855)]
    from_pydata(f"Faro_Delantero_{sn}", verts, [(0, 1, 2, 3) if side > 0 else (3, 2, 1, 0)], smooth=False,
                solidify=0.035)
    beam(f"Luz_Diurna_LED_{sn}", (XF - 0.04, side * 0.57, 0.882), (XF - 0.20, side * 0.85, 0.91), 0.01, t2=0.008)
    # acentos cromados verticales en "C" con antiniebla
    beam(f"Acento_Cromado_Vertical_{sn}", (XF - 0.06, side * 0.66, 0.66), (XF - 0.08, side * 0.70, 0.40), 0.025)
    box(f"Antiniebla_{sn}", (0.02, 0.05, 0.16), (XF - 0.05, side * 0.62, 0.52))
    box(f"Toma_Aire_Lateral_{sn}", (0.02, 0.14, 0.20), (XF - 0.10, side * 0.76, 0.53), bevel=0.01)
# paragolpes inferior negro y protector inferior
box("Paragolpes_Inferior_Delantero", (0.10, 1.50, 0.08), (XF - 0.06, 0, 0.32), bevel=0.02)
box("Protector_Inferior_Delantero", (0.06, 0.90, 0.025), (XF - 0.05, 0, 0.275), bevel=0.008)

# ---------------------------------------------------------------------------
# 04 Trasera: calaveras, porton, paragolpes, placa, escape, aleron
# ---------------------------------------------------------------------------
grupo("04_Trasera")
for side, sn in ((1, "Izq"), (-1, "Der")):
    verts = [(XR + 0.06, side * 0.45, 0.98), (XR + 0.05, side * 0.45, 1.04),
             (XR + 0.30, side * 0.86, 1.06), (XR + 0.32, side * 0.86, 0.96)]
    from_pydata(f"Calavera_Trasera_{sn}", verts, [(0, 1, 2, 3) if side < 0 else (3, 2, 1, 0)], smooth=False,
                solidify=0.03)
    box(f"Reflector_Trasero_{sn}", (0.02, 0.10, 0.03), (XR + 0.02, side * 0.70, 0.50))
box("Moldura_Porton_Trasero", (0.015, 0.95, 0.04), (XR + 0.005, 0, 0.98), bevel=0.006)
box("Emblema_Trasero", (0.012, 0.13, 0.045), (XR + 0.006, 0, 0.88), bevel=0.004)
box("Placa_Trasera", (0.012, 0.36, 0.13), (XR + 0.02, 0, 0.66))
box("Manija_Porton", (0.02, 0.18, 0.03), (XR + 0.02, 0, 0.75))
box("Paragolpes_Trasero_Inferior", (0.12, 1.55, 0.14), (XR + 0.06, 0, 0.47), bevel=0.02)
box("Difusor_Trasero", (0.08, 1.00, 0.05), (XR + 0.08, 0, 0.40), bevel=0.01)
cyl("Escape", 0.035, 0.12, (XR + 0.08, -0.45, 0.36), axis="X", verts=16)
za = lerp_table(CAB, -1.80)[1]
box("Aleron_Trasero", (0.26, 1.28, 0.03), (-1.86, 0, za + 0.015), rot=(0, math.radians(-8), 0), bevel=0.01)
box("Tercera_Luz_Freno", (0.02, 0.30, 0.02), (-1.99, 0, za - 0.005))

# ---------------------------------------------------------------------------
# 05 Ruedas: neumaticos, llantas de 5 rayos dobles, discos y pinzas
# ---------------------------------------------------------------------------
grupo("05_Ruedas")


def tire(name, loc, side):
    """Neumatico por revolucion de una seccion redondeada."""
    bm = bmesh.new()
    prof = []
    rin, rout, w = 0.235, RT, WT
    for k in range(13):
        a = math.pi * k / 12
        prof.append((rout - 0.035 + 0.035 * math.sin(a), -w / 2 + w * k / 12 if False else (w / 2) * -math.cos(a)))
    pts = [(rin, -w / 2 + 0.02)] + [(r, y) for r, y in prof] + [(rin, w / 2 - 0.02)]
    vs = [bm.verts.new((r, y, 0)) for r, y in pts]
    edges = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    edges.append(bm.edges.new((vs[-1], vs[0])))
    bmesh.ops.spin(bm, geom=vs + edges, cent=(0, 0, 0), axis=(0, 1, 0), angle=math.tau, steps=64, use_duplicate=False)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    ob = mesh_obj(name, bm)
    ob.location = loc
    return ob


for ax, en in ((AXF, "Delantera"), (AXR, "Trasera")):
    for side, sn in ((1, "Izq"), (-1, "Der")):
        tag = f"{en}_{sn}"
        c = Vector((ax, side * TRACK, RT))
        tire(f"Neumatico_{tag}", c, side)
        yo = side * (WT / 2 - 0.035)
        aro = cyl(f"Llanta_Aro_{tag}", 0.237, WT - 0.04, c, axis="Y", verts=48)
        hueco = cyl(f"Hueco_Aro_{tag}", 0.215, WT, c, axis="Y", verts=48)
        hueco.hide_render = hueco.hide_viewport = True
        md = aro.modifiers.new("Hueco", "BOOLEAN")
        md.object = hueco
        md.operation = "DIFFERENCE"
        borde = cyl(f"Llanta_Borde_Exterior_{tag}", 0.236, 0.012, c + Vector((0, yo + side * 0.004, 0)), axis="Y", verts=48)
        hb = cyl(f"Hueco_Borde_{tag}", 0.205, 0.05, c + Vector((0, yo + side * 0.004, 0)), axis="Y", verts=48)
        hb.hide_render = hb.hide_viewport = True
        mb = borde.modifiers.new("Hueco", "BOOLEAN")
        mb.object = hb
        mb.operation = "DIFFERENCE"
        cyl(f"Llanta_Fondo_{tag}", 0.214, 0.01, c + Vector((0, -side * 0.03, 0)), axis="Y", verts=48)
        cyl(f"Llanta_Centro_{tag}", 0.06, 0.03, c + Vector((0, yo + side * 0.012, 0)), axis="Y", verts=24)
        cyl(f"Emblema_Llanta_{tag}", 0.028, 0.01, c + Vector((0, yo + side * 0.028, 0)), axis="Y", verts=16)
        for k in range(5):
            a = k * math.tau / 5
            for da in (-0.09, 0.09):
                p1 = c + Vector((math.cos(a + da * 0.6) * 0.06, yo + side * 0.012, math.sin(a + da * 0.6) * 0.06))
                p2 = c + Vector((math.cos(a + da) * 0.215, yo + side * 0.004, math.sin(a + da) * 0.215))
                beam(f"Rayo_Llanta_{tag}", p1, p2, 0.026, t2=0.02)
        cyl(f"Disco_Freno_{tag}", 0.16, 0.025, c + Vector((0, -side * 0.02, 0)), axis="Y", verts=32)
        box(f"Pinza_Freno_{tag}", (0.10, 0.05, 0.07), c + Vector((-0.10 if ax > 0 else 0.10, -side * 0.01, 0.10)),
            bevel=0.01)

# ---------------------------------------------------------------------------
# 06 Laterales: molduras de pasos de rueda, estribos, espejos, manijas
# ---------------------------------------------------------------------------
grupo("06_Laterales")


def arch(name, ax, side):
    """Moldura negra del paso de rueda: sector de anillo extruido."""
    r0, r1 = RT + 0.055, RT + 0.115
    n = 24
    a0, a1 = math.radians(-8), math.radians(188)
    verts = []
    for i in range(n + 1):
        a = a0 + (a1 - a0) * i / n
        for r in (r0, r1):
            verts.append((ax + r * math.cos(a), r * math.sin(a) + RT))
    y0, y1 = side * (HW - 0.045), side * (HW + 0.012)
    vv = [(x, y0, z) for (x, z) in verts] + [(x, y1, z) for (x, z) in verts]
    m = len(verts)
    faces = []
    for i in range(n):
        a, b, c_, d = 2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2
        faces += [(a, b, c_, d), (m + d, m + c_, m + b, m + a), (b, m + b, m + c_, c_), (a, d, m + d, m + a)]
    faces += [(0, m, m + 1, 1), (2 * n, 2 * n + 1, m + 2 * n + 1, m + 2 * n)]
    if side < 0:
        faces = [f[::-1] for f in faces]
    from_pydata(name, vv, faces, smooth=False)


for side, sn in ((1, "Izq"), (-1, "Der")):
    arch(f"Moldura_Paso_Rueda_Delantera_{sn}", AXF, side)
    arch(f"Moldura_Paso_Rueda_Trasera_{sn}", AXR, side)
    # moldura inferior negra (estribo) con filete cromado
    box(f"Estribo_Lateral_{sn}", (AXF - AXR - 2 * (RT + 0.10), 0.06, 0.13),
        ((AXF + AXR) / 2, side * (HW - 0.005), 0.30), bevel=0.02)
    box(f"Filete_Cromado_Estribo_{sn}", (AXF - AXR - 2 * (RT + 0.14), 0.01, 0.012),
        ((AXF + AXR) / 2, side * (HW + 0.026), 0.35))
    # espejos retrovisores
    beam(f"Brazo_Espejo_{sn}", (0.74, side * 0.84, 1.08), (0.70, side * 0.98, 1.12), 0.05, t2=0.04)
    box(f"Espejo_Retrovisor_{sn}", (0.10, 0.20, 0.13), (0.68, side * 1.03, 1.15), bevel=0.03)
    box(f"Intermitente_Espejo_{sn}", (0.012, 0.15, 0.02), (0.735, side * 1.04, 1.13))
    # manijas de puertas
    for xh, nm in ((0.18, "Delantera"), (-0.80, "Trasera")):
        box(f"Manija_Puerta_{nm}_{sn}", (0.15, 0.025, 0.035), (xh, side * (HW + 0.012), 0.99), bevel=0.01)
    # tapa de combustible (lado derecho)
    if side < 0:
        cyl("Tapa_Combustible", 0.08, 0.008, (-1.62, -(HW + 0.004), 0.95), axis="Y", verts=24)

# ---------------------------------------------------------------------------
# 07 Techo: rieles portaequipaje
# ---------------------------------------------------------------------------
grupo("07_Techo")
for side, sn in ((1, "Izq"), (-1, "Der")):
    y = side * 0.56
    zf = lerp_table(CAB, 0.0)[1] + 0.01
    zr = lerp_table(CAB, -1.58)[1] + 0.01
    beam(f"Riel_Techo_{sn}", (0.0, y, zf + 0.045), (-1.58, y, zr + 0.045), 0.035, t2=0.03)
    for xs_, zz, nm in ((0.02, zf, "Delantero"), (-1.60, zr, "Trasero")):
        box(f"Soporte_Riel_{nm}_{sn}", (0.10, 0.04, 0.06), (xs_, y, zz + 0.02), bevel=0.01)

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
out = os.path.join(here, "vehiculo_suv_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
