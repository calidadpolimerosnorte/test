"""
Modelo Blender limpio de la Selladora (maquina de bolsas con desbobinador doble), sin mesa.

Solo la maquina: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): linea de ~6.6 m (desbobinador doble, alimentacion, cuerpo y sellado).
La linea avanza hacia -Y (salida de bolsas al frente); el piso en z=0.

Uso:
    python3 blender/selladora_2_modelo.py     # con bpy de PyPI
    blender -b -P blender/selladora_2_modelo.py
Guarda blender/selladora_2_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Selladora_2")
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


HW = 0.85           # semiancho entre placas
ZT = 0.98           # plano de trabajo (tapa del cuerpo)

# ---------------------------------------------------------------------------
# 01 Desbobinador doble (atras)
# ---------------------------------------------------------------------------
grupo("01_Desbobinador_Doble")
U0, U1 = 4.70, 3.30
for sx, sn in ((1, "Izq"), (-1, "Der")):
    plate(f"Placa_Lateral_Desbobinador_{sn}",
          [(U0 - 0.20, 0.06), (U1, 0.06), (U1, 1.30), (U1 + 0.30, 1.38), (U1 + 0.80, 1.05), (U0 - 0.05, 0.62),
           (U0 + 0.05, 0.40)], sx * HW, holes=[(U1 + 0.55, 0.45, 0.35, 0.30)])
    box(f"Pie_Desbobinador_{sn}", (0.12, 0.30, 0.04), (sx * HW, U0 - 0.25, 0.02))
    box(f"Pie_Desbobinador_Trasero_{sn}", (0.12, 0.30, 0.04), (sx * HW, U1 + 0.15, 0.02))
for y in (U0 - 0.40, U1 + 0.25):
    cyl("Travesano_Desbobinador", 0.035, 2 * HW, (0, y, 0.20), axis="X")
box("Viga_Superior_Desbobinador", (2 * HW + 0.06, 0.12, 0.10), (0, U1 + 0.20, 1.32), bevel=0.01)
# dos estaciones de bobina (una baja atras y otra mas alta adelante)
for k, (yb, zb, rr) in enumerate(((U0 + 0.05, 0.42, 0.32), (U1 + 0.85, 0.92, 0.26)), start=1):
    tg = f"Estacion_{k}"
    cyl(f"Bobina_Film_{tg}", rr, 1.15, (0, yb, zb), axis="X", verts=64)
    cyl(f"Nucleo_Carton_{tg}", 0.05, 1.20, (0, yb, zb), axis="X", verts=24)
    cyl(f"Eje_Neumatico_{tg}", 0.035, 2 * HW + 0.40, (0, yb, zb), axis="X", verts=16)
    for sx, sn in ((1, "Izq"), (-1, "Der")):
        # brazo de soporte, cilindro neumatico de elevacion y freno magnetico
        beam(f"Brazo_Soporte_{tg}_{sn}", (sx * (HW + 0.05), yb - 0.25 * (1 if k == 1 else -1), zb + 0.18),
             (sx * (HW + 0.05), yb, zb), 0.06, t2=0.10)
        cyl(f"Cilindro_Neumatico_{tg}_{sn}", 0.04, 0.28, (sx * (HW + 0.06), yb - 0.35, zb + 0.30), verts=16)
        box(f"Cabeza_Cilindro_{tg}_{sn}", (0.08, 0.08, 0.06), (sx * (HW + 0.06), yb - 0.35, zb + 0.46))
        if sx > 0:
            cyl(f"Freno_Magnetico_{tg}", 0.10, 0.08, (HW + 0.24, yb, zb), axis="X", verts=32)
            for j in range(8):
                box(f"Aleta_Freno_{tg}", (0.07, 0.008, 0.02), (HW + 0.24, yb + 0.07 * math.cos(j * math.tau / 8),
                                                               zb + 0.07 * math.sin(j * math.tau / 8)))
        else:
            cyl(f"Engranaje_Eje_{tg}", 0.07, 0.03, (-(HW + 0.20), yb, zb), axis="X", verts=24)
    spiral_hose(f"Manguera_Espiral_Naranja_{tg}", (HW + 0.16, yb - 0.55, zb + 0.55), turns=14, drop=0.55)
for k, (y, z) in enumerate(((U1 + 0.35, 1.22), (U1 + 0.60, 1.08), (U1 + 0.15, 0.95), (U0 - 0.45, 0.85))):
    cyl("Rodillo_Guia_Desbobinador", 0.04, 2 * HW - 0.04, (0, y, z), axis="X")
box("Unidad_Neumatica_FRL", (0.10, 0.25, 0.16), (HW + 0.07, U1 + 0.40, 1.00), bevel=0.008)

# ---------------------------------------------------------------------------
# 02 Modulo de alimentacion y plegado (rodillos azules)
# ---------------------------------------------------------------------------
grupo("02_Modulo_Alimentacion")
A0, A1 = 3.30, 1.85
for sx, sn in ((1, "Izq"), (-1, "Der")):
    plate(f"Placa_Lateral_Alimentacion_{sn}", [(A0, 0.06), (A1, 0.06), (A1, 1.25), (A0, 1.25)], sx * HW,
          holes=[(A0 - 0.45, 0.55, 0.40, 0.38), (A1 + 0.45, 0.50, 0.35, 0.30)])
    for yy in (A0 - 0.08, A1 + 0.08):
        cyl(f"Pata_Nivelacion_Alimentacion_{sn}", 0.035, 0.06, (sx * HW, yy, 0.03), verts=16)
    c = cyl(f"Agujero_Inspeccion_{sn}", 0.07, 0.05, (sx * HW, A0 - 0.95, 1.00), axis="X", verts=24)
for y, z, r, nm in ((A0 - 0.15, 1.15, 0.04, "Rodillo_Cromado_Alimentacion"),
                    (A0 - 0.45, 1.10, 0.07, "Rodillo_Goma_Azul"), (A0 - 0.70, 0.95, 0.05, "Rodillo_Cromado_Alimentacion"),
                    (A0 - 0.95, 1.12, 0.07, "Rodillo_Goma_Azul"), (A1 + 0.25, 1.05, 0.045, "Rodillo_Cromado_Alimentacion"),
                    (A0 - 0.55, 0.40, 0.04, "Rodillo_Bailarin_Alimentacion"), (A1 + 0.45, 0.30, 0.04, "Rodillo_Bailarin_Alimentacion")):
    cyl(nm, r, 2 * HW - 0.04, (0, y, z), axis="X")
for y in (A0 - 0.08, A1 + 0.08):
    box("Travesano_Superior_Alimentacion", (2 * HW, 0.06, 0.06), (0, y, 1.25))
# motorreductor de tornillo sin fin (gris) en el costado
box("Reductor_Sinfin_Alimentacion", (0.16, 0.18, 0.18), (-(HW + 0.11), A0 - 0.70, 0.95), bevel=0.012)
cyl("Motor_Alimentacion", 0.08, 0.28, (-(HW + 0.11), A0 - 0.95, 0.95), axis="Y", verts=24)
box("Caja_Fotocelda", (0.08, 0.10, 0.08), (HW + 0.06, A1 + 0.30, 1.18))

# ---------------------------------------------------------------------------
# 03 Cuerpo principal (gabinete con puertas negras, tablero, manometros)
# ---------------------------------------------------------------------------
grupo("03_Cuerpo_Principal")
C0, C1 = 1.85, -0.45
CW = 1.10
box("Gabinete_Cuerpo", (2 * CW, C0 - C1, ZT - 0.08), (0, (C0 + C1) / 2, 0.08 + (ZT - 0.08) / 2), bevel=0.012)
box("Tapa_Cuerpo", (2 * CW + 0.04, C0 - C1 + 0.04, 0.03), (0, (C0 + C1) / 2, ZT + 0.015), bevel=0.006)
for sx in (-1, 1):
    for yy in (C0 - 0.10, C1 + 0.10):
        cyl("Rueda_Gabinete", 0.035, 0.03, (sx * (CW - 0.10), yy, 0.035), axis="X", verts=16)
# frente (salida, -Y): puerta izquierda, puerta doble central, puerta derecha
fy = C1 - 0.006
for k, (x, w) in enumerate(((-0.82, 0.38), (-0.20, 0.40), (0.22, 0.40), (0.82, 0.38))):
    box("Puerta_Negra_Gabinete", (w, 0.012, 0.62 if abs(x) < 0.5 else 0.78), (x, fy, 0.45 if abs(x) < 0.5 else 0.52))
    box("Manija_Puerta", (0.04, 0.02, 0.10), (x + (0.12 if x < 0 else -0.12), fy - 0.01, 0.55))
from_pydata("Senal_Riesgo_Electrico", [(-0.06, fy - 0.008, 0.62), (0.06, fy - 0.008, 0.62), (0.0, fy - 0.008, 0.72)],
            [(2, 1, 0)], smooth=False)
# tablero frontal (pantalla, pulsadores, perillas) y manometros azules
box("Panel_Mandos_Frontal", (0.80, 0.012, 0.18), (-0.20, fy, 0.86))
box("Pantalla_HMI", (0.18, 0.015, 0.12), (-0.48, fy - 0.006, 0.86))
for c in range(4):
    cyl("Pulsador", 0.022, 0.02, (-0.30 + c * 0.07, fy - 0.01, 0.88), axis="Y", verts=16)
for c in range(3):
    box("Selector", (0.04, 0.02, 0.08), (0.02 + c * 0.08, fy - 0.01, 0.86))
for c in range(3):
    cyl("Manometro_Azul", 0.035, 0.02, (0.55 + c * 0.12, fy - 0.01, 0.88), axis="Y", verts=24)
box("Controlador_Temperatura", (0.20, 0.14, 0.08), (0.75, C1 + 0.30, ZT + 0.07), bevel=0.01)

# ---------------------------------------------------------------------------
# 04 Unidad de sellado (sobre el cuerpo)
# ---------------------------------------------------------------------------
grupo("04_Unidad_de_Sellado")
SY = 0.55
for sx, sn in ((1, "Izq"), (-1, "Der")):
    plate(f"Placa_Lateral_Sellado_{sn}", [(1.70, ZT), (-0.30, ZT), (-0.30, ZT + 0.42), (1.70, ZT + 0.42)], sx * (HW - 0.05),
          t=0.025, holes=[(0.90, ZT + 0.21, 0.70, 0.22)])
box("Viga_Sellado", (2 * HW - 0.14, 0.12, 0.10), (0, SY, ZT + 0.40), bevel=0.01)
box("Barra_Sellado_Caliente", (2 * HW - 0.20, 0.05, 0.06), (0, SY, ZT + 0.20), bevel=0.005)
for k in range(2):
    cyl("Cilindro_Neumatico_Sellado", 0.04, 0.20, (-0.45 + k * 0.90, SY, ZT + 0.55), verts=16)
curve_tube("Cable_Rojo_Resistencia", [Vector((-0.60, SY - 0.04, ZT + 0.22)), Vector((-0.30, SY - 0.10, ZT + 0.32)),
                                      Vector((0.20, SY - 0.12, ZT + 0.30)), Vector((0.62, SY - 0.06, ZT + 0.24))], 0.008)
for x in (-0.60, 0.0, 0.60):
    cyl("Volante_Ajuste", 0.07, 0.02, (x, -0.28, ZT + 0.30), axis="Y", verts=24)
    cyl("Eje_Volante", 0.012, 0.25, (x, -0.16, ZT + 0.30), axis="Y", verts=12)
for y, z, r in ((1.55, ZT + 0.30, 0.04), (1.20, ZT + 0.12, 0.05), (0.15, ZT + 0.12, 0.05), (-0.15, ZT + 0.25, 0.04)):
    cyl("Rodillo_Traccion_Sellado", r, 2 * HW - 0.14, (0, y, z), axis="X")
box("Cuchilla_Corte", (2 * HW - 0.20, 0.02, 0.08), (0, 0.10, ZT + 0.22))
box("Bandeja_Salida_Bolsas", (2 * HW - 0.10, 0.70, 0.015), (0, C1 - 0.35, ZT - 0.10), rot=(math.radians(-6), 0, 0))
for sx in (-1, 1):
    beam("Soporte_Bandeja", (sx * (HW - 0.10), C1, ZT - 0.20), (sx * (HW - 0.10), C1 - 0.60, ZT - 0.16), 0.03)

# ---------------------------------------------------------------------------
# 05 Porticos altos de acero inoxidable (guias de film y fotocelda)
# ---------------------------------------------------------------------------
grupo("05_Porticos_Inoxidables")
for k, (py, ph) in enumerate(((1.30, 2.35), (0.05, 2.05)), start=1):
    for sx, sn in ((1, "Izq"), (-1, "Der")):
        box(f"Poste_Portico_{k}_{sn}", (0.05, 0.05, ph - ZT), (sx * (HW - 0.02), py, (ph + ZT) / 2), bevel=0.004)
    for z in (ph - 0.03, ph - 0.30):
        cyl(f"Barra_Portico_{k}", 0.015, 2 * HW - 0.02, (0, py, z), axis="X", verts=12)
    for sx in (-1, 1):
        cyl(f"Rueda_Guia_Amarilla_{k}", 0.045, 0.02, (sx * 0.55, py, ph - 0.30), axis="X", verts=24)
cyl("Barra_Guia_Superior", 0.015, 1.30, (HW - 0.02, 0.675, 2.05), axis="Y", verts=12)
cyl("Barra_Guia_Superior", 0.015, 1.30, (-(HW - 0.02), 0.675, 2.05), axis="Y", verts=12)
box("Fotocelda", (0.06, 0.05, 0.05), (0.0, 0.05, 2.0))

# ---------------------------------------------------------------------------
# 06 Film (de las bobinas al sellado)
# ---------------------------------------------------------------------------
grupo("06_Film")
path = [(U0 + 0.05 - 0.10, 0.74), (U1 + 0.35, 1.26), (U1 + 0.60, 1.12), (A0 - 0.15, 1.19), (A0 - 0.45, 1.17),
        (A0 - 0.70, 0.90), (A0 - 0.95, 1.19), (A1 + 0.25, 1.09), (1.55, ZT + 0.34), (1.20, ZT + 0.17),
        (0.15, ZT + 0.17), (-0.15, ZT + 0.29)]
verts, faces = [], []
for (y, z) in path:
    verts += [(-0.58, y, z), (0.58, y, z)]
for i in range(len(path) - 1):
    faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
from_pydata("Lamina_Film", verts, faces, smooth=False)
for k in range(3):
    box("Bolsa_Terminada", (1.00, 0.45, 0.004), (0, C1 - 0.30, ZT - 0.08 + 0.005 * k), rot=(math.radians(-6), 0, 0))

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
out = os.path.join(here, "selladora_2_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
