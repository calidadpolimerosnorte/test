"""
Modelo Blender limpio de una camioneta pickup doble cabina (tipo JMC Vigus EV).

Solo el vehiculo: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): largo 5.33, ancho 1.90, alto 1.83, distancia entre ejes 3.08.
Ejes: X hacia adelante, Y hacia la izquierda, Z hacia arriba; el piso en z=0.

Uso:
    python3 blender/vehiculo_pickup_modelo.py     # con bpy de PyPI
    blender -b -P blender/vehiculo_pickup_modelo.py
Guarda blender/vehiculo_pickup_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Pickup_Doble_Cabina")
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
XF, XR = 2.665, -2.665        # paragolpes delantero / trasero
AXF, AXR = 1.70, -1.38        # ejes (distancia entre ejes 3.08)
TRACK = 0.80                  # semitrocha
RT = 0.385                    # radio del neumatico (265/65 R17)
WT = 0.265                    # ancho del neumatico
HW = 0.95                     # semiancho de carroceria (1.90 m)
BED_X0, BED_X1 = -0.98, -2.58 # caja de carga (interior)
BED_Z = 0.86                  # piso de la caja

# carroceria inferior: (x, semiancho, z_inferior, z_superior/cintura)
BODY = [
    (2.665, 0.80, 0.46, 0.96),
    (2.63, 0.88, 0.42, 1.05),
    (2.52, 0.93, 0.40, 1.12),
    (2.20, 0.95, 0.39, 1.16),
    (1.60, 0.95, 0.39, 1.19),
    (1.25, 0.95, 0.39, 1.22),
    (0.00, 0.95, 0.41, 1.24),
    (-0.90, 0.95, 0.43, 1.25),
    (-1.20, 0.95, 0.44, 1.25),
    (-2.45, 0.95, 0.50, 1.25),
    (-2.60, 0.94, 0.53, 1.245),
    (-2.665, 0.92, 0.56, 1.24),
]
# cabina doble: (x, z_base, z_techo, semiancho_base, semiancho_techo)
CAB = [
    (1.25, 1.22, 1.24, 0.90, 0.86),
    (1.00, 1.225, 1.42, 0.90, 0.80),
    (0.75, 1.23, 1.62, 0.90, 0.75),
    (0.55, 1.235, 1.76, 0.90, 0.73),
    (0.30, 1.24, 1.82, 0.90, 0.73),
    (-0.40, 1.245, 1.83, 0.90, 0.73),
    (-0.80, 1.25, 1.815, 0.90, 0.73),
    (-0.86, 1.25, 1.70, 0.90, 0.73),
    (-0.89, 1.25, 1.27, 0.90, 0.73),
]


def body_profile(x):
    w, zb, zt = lerp_table(BODY, x)
    r = 0.08
    return [(0.0, zb), (w - r, zb), (w - 0.02, zb + 0.04), (w, zb + r + 0.03), (w, zt - 0.08),
            (w - 0.01, zt - 0.03), (w - 0.04, zt), (w * 0.5, zt + 0.005), (0.0, zt + 0.008)]


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
# 01 Carroceria y caja de carga
# ---------------------------------------------------------------------------
grupo("01_Carroceria")
xs = [XF - i * (XF - XR) / 70 for i in range(71)]
carro = loft("Carroceria", xs, body_profile)
sub = carro.modifiers.new("Suavizado", "SUBSURF")
sub.levels = 2
for ax, nm in ((AXF, "Delantero"), (AXR, "Trasero")):
    c = cyl(f"Corte_Paso_Rueda_{nm}", RT + 0.06, 2.6, (ax, 0, RT), axis="Y", verts=48)
    c.hide_render = c.hide_viewport = True
    md = carro.modifiers.new(f"PasoRueda{nm}", "BOOLEAN")
    md.object = c
    md.operation = "DIFFERENCE"
# vaciado de la caja de carga
cj = box("Corte_Caja", (BED_X0 - BED_X1, 2 * (HW - 0.06), 1.2), ((BED_X0 + BED_X1) / 2, 0, BED_Z + 0.6))
cj.hide_render = cj.hide_viewport = True
md = carro.modifiers.new("Caja", "BOOLEAN")
md.object = cj
md.operation = "DIFFERENCE"
hood = loft("Capo", [2.50 - i * (2.50 - 1.28) / 16 for i in range(17)],
            lambda x: [(0.0, lerp_table(BODY, x)[2] + 0.014),
                       (0.30, lerp_table(BODY, x)[2] + 0.030),
                       (lerp_table(BODY, x)[0] * 0.80, lerp_table(BODY, x)[2] + 0.006),
                       (lerp_table(BODY, x)[0] * 0.94, lerp_table(BODY, x)[2] - 0.015)])
hood.modifiers.new("Espesor", "SOLIDIFY").thickness = 0.006
for side, sn in ((1, "Izq"), (-1, "Der")):
    for xd, nm in ((1.24, "Delantera_Inicio"), (0.18, "Delantera_Fin"), (-0.90, "Trasera_Fin")):
        beam(f"Linea_Puerta_{nm}_{sn}", (xd, side * (HW + 0.001), 0.50), (xd + 0.03, side * (HW + 0.001), 1.21),
             0.006, t2=0.004)
    beam(f"Linea_Puerta_Inferior_{sn}", (1.24, side * (HW + 0.001), 0.50), (-0.90, side * (HW + 0.001), 0.50),
         0.006, t2=0.004)
    beam(f"Nervio_Lateral_{sn}", (2.35, side * (HW - 0.002), 1.05), (-2.55, side * (HW - 0.004), 1.10),
         0.014, t2=0.012)
grupo("01b_Caja_de_Carga")
box("Piso_Caja", (BED_X0 - BED_X1, 2 * (HW - 0.06), 0.03), ((BED_X0 + BED_X1) / 2, 0, BED_Z), bevel=0.005)
for k in range(7):
    box("Nervio_Piso_Caja", (BED_X0 - BED_X1 - 0.06, 0.03, 0.015),
        ((BED_X0 + BED_X1) / 2, -0.66 + k * 0.22, BED_Z + 0.022))
for side, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Guardafango_Interior_Caja_{sn}", (0.95, 0.22, 0.25), (AXR, side * (HW - 0.17), BED_Z + 0.13), bevel=0.06)
    box(f"Tapa_Borde_Caja_{sn}", (BED_X0 - BED_X1 + 0.06, 0.08, 0.025),
        ((BED_X0 + BED_X1) / 2, side * (HW - 0.03), 1.262), bevel=0.008)
    for xg in (-0.70, -2.30):
        box(f"Gancho_Amarre_{sn}", (0.06, 0.02, 0.04), (xg, side * (HW - 0.065), 1.15))
box("Porton_Trasero", (0.06, 2 * HW - 0.08, 0.66), (XR + 0.03, 0, 0.92), bevel=0.01)
box("Manija_Porton", (0.02, 0.22, 0.05), (XR - 0.002, 0, 1.12), bevel=0.008)
box("Emblema_Porton", (0.012, 0.50, 0.06), (XR - 0.002, 0, 0.98))
# barra antivuelco (sport bar) negra detras de la cabina
for side, sn in ((1, "Izq"), (-1, "Der")):
    beam(f"Barra_Antivuelco_Pata_{sn}", (-1.04, side * (HW - 0.04), 1.26), (-1.12, side * 0.72, 1.62), 0.07, round_=True)
    beam(f"Barra_Antivuelco_Diagonal_{sn}", (-1.14, side * 0.70, 1.62), (-1.65, side * (HW - 0.04), 1.27), 0.06,
         round_=True)
beam("Barra_Antivuelco_Superior", (-1.12, 0.72, 1.62), (-1.12, -0.72, 1.62), 0.07, round_=True)

# ---------------------------------------------------------------------------
# 02 Cabina doble, pilares y vidrios
# ---------------------------------------------------------------------------
grupo("02_Cabina_y_Vidrios")
xc = [CAB[0][0] - i * (CAB[0][0] - CAB[-1][0]) / 40 for i in range(41)]
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
    side_window(f"Vidrio_Puerta_Delantera_{sn}", 1.08, 0.22, side, slant0=-0.30)
    side_window(f"Vidrio_Puerta_Trasera_{sn}", 0.14, -0.76, side, f1=0.92, slant1=-0.04)
    beam(f"Pilar_B_{sn}", cab_point(0.18, 0.05, side, 0.009), cab_point(0.16, 0.95, side, 0.009), 0.08, t2=0.01)
    # deflectores de lluvia sobre las ventanas
    beam(f"Deflector_Lluvia_Delantero_{sn}", cab_point(0.78, 0.97, side, 0.02), cab_point(0.22, 0.97, side, 0.02), 0.04, t2=0.01)
    beam(f"Deflector_Lluvia_Trasero_{sn}", cab_point(0.12, 0.97, side, 0.02), cab_point(-0.76, 0.97, side, 0.02), 0.04, t2=0.01)


def glass_band(name, xa, xb, n=10, inset=0.06):
    verts, faces = [], []
    for i in range(n + 1):
        x = xa + (xb - xa) * i / n
        zb, zt, wb, wtop = lerp_table(CAB, x)
        verts += [(x + 0.004, -(wtop - inset), zt + 0.010), (x + 0.004, (wtop - inset), zt + 0.010)]
    for i in range(n):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    from_pydata(name, verts, faces, smooth=False, solidify=0.004)


glass_band("Parabrisas", 1.22, 0.58)
box("Ventana_Trasera_Cabina", (0.01, 1.10, 0.30), (-0.895, 0, 1.52))
for k, y in enumerate((0.35, -0.30)):
    beam(f"Limpiaparabrisas_{k + 1}", (1.24, y, 1.25), (1.10, y + 0.48, 1.36), 0.02, t2=0.012)
cyl("Antena_Aleta_Tiburon", 0.05, 0.16, (-0.70, 0, 1.87), verts=12, r2=0.01, rot=(0, math.radians(20), 0))

# ---------------------------------------------------------------------------
# 03 Frente: parrilla grande octogonal, faros, antinieblas, protector
# ---------------------------------------------------------------------------
grupo("03_Frente")
oct_ = [(0.52, 0.98), (-0.52, 0.98), (-0.66, 0.86), (-0.66, 0.62), (-0.54, 0.52), (0.54, 0.52), (0.66, 0.62),
        (0.66, 0.86)]
from_pydata("Parrilla_Marco", [(XF - 0.005, y, z) for y, z in oct_], [tuple(range(8))], smooth=False, solidify=0.04)
for k in range(6):
    z = 0.92 - k * 0.07
    box(f"Lama_Parrilla_{k + 1}", (0.02, 1.16, 0.022), (XF + 0.012, 0, z), bevel=0.004)
for side, sn in ((1, "Izq"), (-1, "Der")):
    beam(f"Barra_Vertical_Parrilla_{sn}", (XF + 0.015, side * 0.40, 0.95), (XF + 0.015, side * 0.40, 0.55), 0.02)
box("Emblema_Capo", (0.02, 0.36, 0.06), (XF - 0.08, 0, 1.06), bevel=0.005)
box("Placa_Delantera", (0.012, 0.36, 0.12), (XF + 0.03, 0, 0.62))
for side, sn in ((1, "Izq"), (-1, "Der")):
    verts = [(XF - 0.04, side * 0.56, 1.02), (XF - 0.035, side * 0.56, 1.07),
             (XF - 0.22, side * 0.90, 1.11), (XF - 0.26, side * 0.90, 1.05)]
    from_pydata(f"Faro_Delantero_{sn}", verts, [(0, 1, 2, 3) if side > 0 else (3, 2, 1, 0)], smooth=False,
                solidify=0.04)
    beam(f"Luz_Diurna_LED_{sn}", (XF - 0.04, side * 0.57, 1.075), (XF - 0.22, side * 0.89, 1.115), 0.012, t2=0.01)
    # nichos negros de esquina con antiniebla redondo
    box(f"Nicho_Antiniebla_{sn}", (0.06, 0.22, 0.26), (XF - 0.06, side * 0.80, 0.70), bevel=0.03)
    cyl(f"Antiniebla_{sn}", 0.055, 0.03, (XF - 0.02, side * 0.80, 0.70), axis="X", verts=24)
    cyl(f"Aro_Antiniebla_{sn}", 0.07, 0.015, (XF - 0.025, side * 0.80, 0.70), axis="X", verts=24)
box("Paragolpes_Inferior_Delantero", (0.12, 1.70, 0.12), (XF - 0.07, 0, 0.48), bevel=0.03)
box("Protector_Inferior_Plateado", (0.08, 1.10, 0.10), (XF - 0.05, 0, 0.40), rot=(0, math.radians(20), 0), bevel=0.02)
for k in range(3):
    box(f"Ranura_Protector_{k + 1}", (0.02, 0.14, 0.03), (XF - 0.01, -0.30 + k * 0.30, 0.40))

# ---------------------------------------------------------------------------
# 04 Trasera
# ---------------------------------------------------------------------------
grupo("04_Trasera")
for side, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Calavera_Trasera_{sn}", (0.05, 0.12, 0.34), (XR + 0.02, side * (HW - 0.07), 1.04), bevel=0.01)
box("Paragolpes_Trasero", (0.16, 1.85, 0.16), (XR - 0.02, 0, 0.55), bevel=0.02)
box("Estribo_Paragolpes", (0.10, 0.50, 0.03), (XR - 0.06, 0, 0.64))
box("Placa_Trasera", (0.012, 0.36, 0.12), (XR - 0.10, 0, 0.52))
box("Tercera_Luz_Freno", (0.03, 0.30, 0.03), (-0.895, 0, 1.79))

# ---------------------------------------------------------------------------
# 05 Ruedas
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
        yo = side * (WT / 2 - 0.04)
        aro = cyl(f"Llanta_Aro_{tag}", 0.222, WT - 0.05, c, axis="Y", verts=48)
        hueco = cyl(f"Hueco_Aro_{tag}", 0.200, WT, c, axis="Y", verts=48)
        hueco.hide_render = hueco.hide_viewport = True
        md = aro.modifiers.new("Hueco", "BOOLEAN")
        md.object = hueco
        md.operation = "DIFFERENCE"
        cyl(f"Llanta_Fondo_{tag}", 0.20, 0.01, c + Vector((0, -side * 0.03, 0)), axis="Y", verts=48)
        cyl(f"Llanta_Centro_{tag}", 0.07, 0.035, c + Vector((0, yo + side * 0.012, 0)), axis="Y", verts=24)
        for k in range(6):
            a = k * math.tau / 6
            for da in (-0.08, 0.08):
                p1 = c + Vector((math.cos(a + da * 0.5) * 0.07, yo + side * 0.012, math.sin(a + da * 0.5) * 0.07))
                p2 = c + Vector((math.cos(a + da) * 0.205, yo + side * 0.004, math.sin(a + da) * 0.205))
                beam(f"Rayo_Llanta_{tag}", p1, p2, 0.028, t2=0.022)
        cyl(f"Disco_Freno_{tag}", 0.16, 0.025, c + Vector((0, -side * 0.02, 0)), axis="Y", verts=32)
        box(f"Pinza_Freno_{tag}", (0.10, 0.05, 0.07), c + Vector((-0.10 if ax > 0 else 0.10, -side * 0.01, 0.10)),
            bevel=0.01)
        # tacos del neumatico todoterreno
        for k in range(28):
            a = k * math.tau / 28
            box(f"Taco_Neumatico_{tag}", (0.05, WT * 0.8, 0.012),
                c + Vector((math.cos(a) * (RT - 0.002), 0, math.sin(a) * (RT - 0.002))), rot=(0, -a + math.pi / 2, 0))

# ---------------------------------------------------------------------------
# 06 Laterales: guardabarros ensanchados, estribos, espejos, manijas
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
    arch(f"Guardabarros_Ensanchado_Delantero_{sn}", AXF, side)
    arch(f"Guardabarros_Ensanchado_Trasero_{sn}", AXR, side)
    # estribo tubular
    beam(f"Estribo_Tubular_{sn}", (AXF - RT - 0.18, side * (HW + 0.06), 0.42), (AXR + RT + 0.18, side * (HW + 0.06), 0.42),
         0.09, t2=0.05)
    for xs_ in (AXF - RT - 0.30, (AXF + AXR) / 2, AXR + RT + 0.30):
        beam(f"Soporte_Estribo_{sn}", (xs_, side * (HW - 0.10), 0.44), (xs_, side * (HW + 0.05), 0.42), 0.04)
    box(f"Moldura_Inferior_Puertas_{sn}", (2.10, 0.03, 0.10), (0.17, side * (HW + 0.01), 0.53), bevel=0.01)
    beam(f"Brazo_Espejo_{sn}", (1.06, side * 0.90, 1.27), (1.02, side * 1.04, 1.31), 0.05, t2=0.04)
    box(f"Espejo_Retrovisor_{sn}", (0.12, 0.22, 0.16), (1.00, side * 1.10, 1.35), bevel=0.035)
    box(f"Intermitente_Espejo_{sn}", (0.012, 0.16, 0.02), (1.065, side * 1.11, 1.32))
    for xh, nm in ((0.42, "Delantera"), (-0.62, "Trasera")):
        box(f"Manija_Puerta_{nm}_{sn}", (0.16, 0.028, 0.04), (xh, side * (HW + 0.014), 1.16), bevel=0.01)
    if side < 0:
        cyl("Tapa_Carga_Electrica", 0.085, 0.008, (-1.95, -(HW + 0.004), 1.10), axis="Y", verts=24)

# ---------------------------------------------------------------------------
# 07 Techo: rieles
# ---------------------------------------------------------------------------
grupo("07_Techo")
for side, sn in ((1, "Izq"), (-1, "Der")):
    y = side * 0.60
    z0 = lerp_table(CAB, 0.40)[1] + 0.01
    z1 = lerp_table(CAB, -0.75)[1] + 0.01
    beam(f"Riel_Techo_{sn}", (0.40, y, z0 + 0.045), (-0.75, y, z1 + 0.045), 0.035, t2=0.03)
    for xs_, zz, nm in ((0.40, z0, "Delantero"), (-0.75, z1, "Trasero")):
        box(f"Soporte_Riel_{nm}_{sn}", (0.08, 0.04, 0.06), (xs_, y, zz + 0.02), bevel=0.01)

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
out = os.path.join(here, "vehiculo_pickup_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
