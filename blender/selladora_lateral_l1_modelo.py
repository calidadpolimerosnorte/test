"""
Modelo Blender limpio de la Selladora Lateral L1 (maquina de bolsas).

Solo el vehiculo: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): ~4.8 m de largo (bastidor trasero con desbobinador, cuerpo, sellado y salida).
La linea avanza hacia -Y (salida de bolsas al frente); el piso en z=0.

Uso:
    python3 blender/selladora_lateral_l1_modelo.py     # con bpy de PyPI
    blender -b -P blender/selladora_lateral_l1_modelo.py
Guarda blender/selladora_lateral_l1_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Selladora_Lateral_L1")
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


HW = 0.85           # semiancho entre bastidores
ZT = 0.92           # plano de trabajo

# ---------------------------------------------------------------------------
# 01 Bastidor trasero alto y desbobinador
# ---------------------------------------------------------------------------
grupo("01_Bastidor_Trasero_y_Desbobinador")
RY = 2.05
for sx, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Poste_Bastidor_Trasero_{sn}", (0.10, 0.10, 2.00), (sx * HW, RY, 1.00), bevel=0.004)
    # brazo negro curvo superior (lleva el rodillo de reenvio)
    prof = [(RY - 0.05, 1.86), (RY + 0.05, 1.98), (RY + 0.40, 2.10), (RY + 0.62, 2.02), (RY + 0.62, 1.94),
            (RY + 0.40, 1.98), (RY + 0.08, 1.80)]
    plate(f"Brazo_Negro_Superior_{sn}", prof, sx * (HW + 0.07), t=0.02)
    # placas inferiores con ventana
    plate(f"Placa_Inferior_Trasera_{sn}", [(RY + 0.10, 0.08), (1.30, 0.08), (1.30, 0.85), (RY + 0.10, 0.85)], sx * HW,
          holes=[((RY + 1.30) / 2 + 0.05, 0.45, 0.40, 0.42)])
    # brazo del desbobinador hacia la bobina al piso
    beam(f"Brazo_Desbobinador_{sn}", (sx * (HW + 0.06), RY + 0.05, 0.55), (sx * (HW + 0.06), RY + 0.55, 0.34), 0.06, t2=0.08)
box("Travesano_Superior_Trasero", (2 * HW + 0.10, 0.10, 0.08), (0, RY, 1.96), bevel=0.004)
for z in (1.75, 1.55, 1.38, 1.20, 1.02):
    cyl("Rodillo_Cromado_Bastidor", 0.035, 2 * HW - 0.06, (0, RY + (0.06 if z in (1.55, 1.20) else -0.06), z), axis="X")
cyl("Rodillo_Reenvio_Superior", 0.04, 2 * HW + 0.10, (0, RY + 0.55, 2.02), axis="X")
cyl("Barra_Bobinita", 0.012, 2 * HW + 0.10, (0, RY + 0.25, 1.86), axis="X", verts=12)
cyl("Bobinita_Hilo", 0.04, 0.10, (0.10, RY + 0.25, 1.86), axis="X", verts=24)
for sx in (-1, 1):
    box("Soporte_Rodillo_Negro", (0.06, 0.12, 0.10), (sx * (HW - 0.02), RY - 0.10, 1.55), bevel=0.01)
# bobina de film apoyada al piso, eje con volante y rueda de freno
BY, BZ = RY + 0.55, 0.34
cyl("Bobina_Film", 0.32, 1.10, (0, BY, BZ), axis="X", verts=64)
cyl("Nucleo_Carton_Bobina", 0.05, 1.16, (0, BY, BZ), axis="X", verts=24)
cyl("Eje_Bobina", 0.03, 2 * HW + 0.45, (0, BY, BZ), axis="X", verts=16)
cyl("Mandril_Verde", 0.055, 0.10, (0.62, BY, BZ), axis="X", verts=24)
cyl("Volante_Eje_Bobina", 0.09, 0.02, (HW + 0.20, BY, BZ), axis="X", verts=24)
cyl("Rueda_Freno_Bobina", 0.10, 0.05, (-(HW + 0.20), BY, BZ - 0.18), axis="X", verts=32)
cyl("Engranaje_Eje_Bobina", 0.06, 0.03, (-(HW + 0.12), BY, BZ), axis="X", verts=24)
# motorreductor azul vertical y caja de control gris
box("Reductor_Azul", (0.14, 0.14, 0.14), (-(HW + 0.12), RY - 0.15, 0.95), bevel=0.01)
cyl("Motor_Azul", 0.065, 0.30, (-(HW + 0.12), RY - 0.15, 0.73), verts=24)
box("Caja_Control_Trasera", (0.36, 0.14, 0.40), (-0.30, RY + 0.12, 1.35), bevel=0.01)
for k, (dx, dz) in enumerate(((-0.10, 0.08), (0.08, 0.08), (-0.10, -0.06), (0.08, -0.06))):
    cyl("Pulsador_Caja_Trasera", 0.02, 0.02, (-0.30 + dx, RY + 0.20, 1.35 + dz), axis="Y", verts=16)
cyl("Rodillo_Azul_Inferior", 0.05, 2 * HW - 0.06, (0, 1.50, 0.30), axis="X")

# ---------------------------------------------------------------------------
# 02 Cuerpo principal (gabinete con puertas negras)
# ---------------------------------------------------------------------------
grupo("02_Cuerpo_Principal")
C0, C1 = 1.30, -0.05
CW = 0.95
box("Gabinete_Cuerpo", (2 * CW, C0 - C1, ZT - 0.10), (0, (C0 + C1) / 2, 0.10 + (ZT - 0.10) / 2), bevel=0.012)
box("Tapa_Cuerpo", (2 * CW + 0.04, C0 - C1 + 0.04, 0.03), (0, (C0 + C1) / 2, ZT + 0.015), bevel=0.006)
for k, yy in enumerate((0.95, 0.35)):
    box("Puerta_Negra_Gabinete", (0.012, 0.58, 0.62), (CW + 0.006, yy, 0.50))
box("Manija_Puerta", (0.02, 0.04, 0.12), (CW + 0.02, 0.65, 0.55))
cyl("Ventilador_Gabinete", 0.04, 0.012, (-(CW + 0.006), 1.00, 0.45), axis="X", verts=24)
for sx in (-1, 1):
    for yy in (C0 - 0.08, C1 + 0.08):
        cyl("Pata_Nivelacion", 0.035, 0.08, (sx * (CW - 0.08), yy, 0.04), verts=16)
for y, z, r in ((1.15, ZT + 0.10, 0.04), (0.90, ZT + 0.06, 0.045), (0.60, ZT + 0.10, 0.04), (0.30, ZT + 0.06, 0.05)):
    cyl("Rodillo_Guia_Cuerpo", r, 2 * HW - 0.06, (0, y, z), axis="X")
for sx in (-1, 1):
    box("Riel_Guia_Superior", (0.04, C0 - C1, 0.06), (sx * (HW - 0.02), (C0 + C1) / 2, ZT + 0.06))
cyl("Rodillo_Azul_Alimentacion", 0.055, 2 * HW - 0.06, (0, 0.10, ZT + 0.14), axis="X")
box("Motorreductor_Sinfin", (0.16, 0.16, 0.16), (CW + 0.10, 1.10, ZT - 0.20), bevel=0.01)

# ---------------------------------------------------------------------------
# 03 Unidad de sellado lateral
# ---------------------------------------------------------------------------
grupo("03_Unidad_de_Sellado")
SY = -0.20
for sx, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Placa_Lateral_Sellado_{sn}", (0.03, 0.40, 0.55), (sx * (HW - 0.02), SY, ZT + 0.20), bevel=0.005)
box("Viga_Sellado", (2 * HW - 0.08, 0.10, 0.10), (0, SY, ZT + 0.45), bevel=0.01)
box("Barra_Sellado_Caliente", (2 * HW - 0.14, 0.04, 0.05), (0, SY, ZT + 0.22), bevel=0.004)
box("Cabezal_Ajuste_Central", (0.16, 0.14, 0.28), (0.10, SY + 0.05, ZT + 0.62), bevel=0.01)
cyl("Husillo_Ajuste", 0.025, 0.40, (0.10, SY + 0.05, ZT + 0.32), verts=16)
cyl("Volante_Ajuste_Sellado", 0.08, 0.02, (0.10, SY - 0.05, ZT + 0.78), axis="Y", verts=24)
for x in (-0.55, 0.55):
    cyl("Cilindro_Neumatico_Sellado", 0.035, 0.20, (x, SY, ZT + 0.60), verts=16)
box("Regla_Madera_Guia", (0.04, 0.02, 0.85), (0.35, SY - 0.12, ZT + 0.35), rot=(0, math.radians(-40), 0))
cyl("Barra_Cromada_Sellado", 0.02, 2 * HW - 0.06, (0, SY - 0.15, ZT + 0.15), axis="X", verts=12)

# ---------------------------------------------------------------------------
# 04 Tablero de control en poste (con letrero L1)
# ---------------------------------------------------------------------------
grupo("04_Tablero_de_Control")
px, py = -(HW + 0.20), -0.40
box("Gabinete_Base_Tablero", (0.30, 0.34, 0.75), (px, py, 0.08 + 0.375), bevel=0.01)
box("Letrero_Selladora_L1", (0.012, 0.26, 0.30), (px - 0.157, py, 0.62))
cu = bpy.data.curves.new("Texto_Selladora_Lateral_L1", "FONT")
cu.body = "SELLADORA\nLATERAL\nL1"
cu.size = 0.045
cu.align_x = "CENTER"
cu.align_y = "CENTER"
cu.extrude = 0.001
txt = link(bpy.data.objects.new("Texto_Selladora_Lateral_L1", cu))
txt.location = (px - 0.165, py, 0.62)
txt.rotation_euler = (math.pi / 2, 0, -math.pi / 2)
box("Poste_Tablero", (0.07, 0.07, 0.55), (px, py, 0.83 + 0.275))
curve_tube("Conducto_Flexible_Tablero", [Vector((px + 0.05, py + 0.10, 1.30)), Vector((px + 0.30, py + 0.35, 1.25)),
                                          Vector((-HW + 0.10, SY + 0.20, ZT + 0.50))], 0.025)
box("Consola_Mandos", (0.48, 0.22, 0.32), (px + 0.15, py, 1.50), bevel=0.012)
fy = py - 0.112
box("Pantalla_HMI", (0.22, 0.012, 0.15), (px + 0.05, fy, 1.50))
for k in range(3):
    cyl("Perilla_Amarilla", 0.018, 0.025, (px + 0.24 + (k - 1) * 0.05, fy, 1.46), axis="Y", verts=16)
cyl("Parada_Emergencia", 0.025, 0.03, (px + 0.24 - 0.05, fy, 1.56), axis="Y", verts=24)
box("Display_Contador", (0.06, 0.012, 0.03), (px + 0.29, fy, 1.57))

# ---------------------------------------------------------------------------
# 05 Transportador de cintas y bandeja de salida
# ---------------------------------------------------------------------------
grupo("05_Transportador_y_Bandeja_Salida")
T0, T1 = -0.40, -1.00
for sx, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Larguero_Transportador_{sn}", (0.04, T0 - T1, 0.08), (sx * (HW - 0.05), (T0 + T1) / 2, ZT - 0.02))
for k in range(14):
    x = -0.65 + k * 0.10
    box("Cinta_Negra_Transportador", (0.05, T0 - T1, 0.012), (x, (T0 + T1) / 2, ZT + 0.03))
cyl("Rodillo_Entrada_Cintas", 0.035, 2 * HW - 0.12, (0, T0, ZT + 0.0), axis="X")
cyl("Rodillo_Salida_Pernos", 0.035, 2 * HW - 0.12, (0, T1, ZT + 0.0), axis="X")
for k in range(16):
    cyl("Perno_Rodillo_Salida", 0.012, 0.05, (-0.72 + k * 0.096, T1 - 0.03, ZT + 0.0), axis="Y", verts=8)
box("Barra_Soporte_Superior", (2 * HW - 0.10, 0.04, 0.04), (0, (T0 + T1) / 2, ZT + 0.12))
cyl("Tubo_Beige_Guia", 0.015, 2 * HW + 0.10, (0, T1 - 0.08, ZT + 0.06), axis="X", verts=12)
for x in (-0.55, 0.0, 0.55):
    box("Abrazadera_Tubo", (0.04, 0.05, 0.05), (x, T1 - 0.08, ZT + 0.06))
# bandeja de acero inoxidable inclinada con topes y botonera
B0, B1 = -1.05, -2.05
box("Bandeja_Salida_Acero", (2 * HW + 0.10, B0 - B1, 0.015), (0, (B0 + B1) / 2, ZT - 0.10), rot=(math.radians(4), 0, 0))
box("Regla_Bandeja", (1.30, 0.04, 0.004), (-0.10, B1 + 0.15, ZT - 0.112), rot=(math.radians(4), 0, 0))
for x in (-0.30, 0.20):
    box("Tope_Inoxidable", (0.20, 0.012, 0.18), (x, B0 - 0.20, ZT - 0.02))
box("Botonera_Bandeja", (0.10, 0.16, 0.04), (HW - 0.12, B1 + 0.25, ZT - 0.07), bevel=0.005)
for k in range(3):
    cyl("Pulsador_Bandeja", 0.015, 0.02, (HW - 0.12, B1 + 0.20 + k * 0.05, ZT - 0.04), verts=16)
for sx in (-1, 1):
    beam("Soporte_Bandeja", (sx * (HW - 0.10), C1, ZT - 0.30), (sx * (HW - 0.10), B1 + 0.20, ZT - 0.13), 0.03)

# ---------------------------------------------------------------------------
# 06 Film
# ---------------------------------------------------------------------------
grupo("06_Film")
path = [(BY - 0.20, BZ + 0.25), (RY - 0.06, 1.02), (RY + 0.06, 1.20), (RY - 0.06, 1.38), (RY + 0.06, 1.55),
        (RY - 0.06, 1.75), (RY + 0.50, 2.06), (RY + 0.10, 1.95), (1.15, ZT + 0.14), (0.90, ZT + 0.11),
        (0.30, ZT + 0.11), (0.10, ZT + 0.19), (SY, ZT + 0.05), (T1, ZT + 0.04)]
verts, faces = [], []
for (y, z) in path:
    verts += [(-0.55, y, z), (0.55, y, z)]
for i in range(len(path) - 1):
    faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
from_pydata("Lamina_Film", verts, faces, smooth=False)
for k in range(3):
    box("Bolsa_Terminada", (0.55, 0.45, 0.004), (-0.20 + k * 0.08, B0 - 0.55, ZT - 0.08 + 0.005 * k),
        rot=(math.radians(4), 0, 0))

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
out = os.path.join(here, "selladora_lateral_l1_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
