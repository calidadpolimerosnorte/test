"""
Modelo Blender limpio de la Cortadora Nº 1 (corte de film/bolsas en rollo).

Solo la maquina: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): ~2.3 m de largo x 2.1 m de ancho (desbobinador doble, cabezal de corte, gabinete).
El piso en z=0.

Uso:
    python3 blender/cortadora_1_modelo.py     # con bpy de PyPI
    blender -b -P blender/cortadora_1_modelo.py
Guarda blender/cortadora_1_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Cortadora_N1")
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


HW = 0.98           # posicion de las guardas laterales (medio disco)
ZT = 0.95           # plano de trabajo
GX0, GX1 = 0.42, 1.06   # gabinete en el extremo derecho (+X)

# ---------------------------------------------------------------------------
# 01 Estructura y gabinete
# ---------------------------------------------------------------------------
grupo("01_Estructura_y_Gabinete")
Y0, Y1 = -0.45, 0.50
box("Gabinete", (GX1 - GX0, Y1 - Y0, ZT - 0.08), ((GX0 + GX1) / 2, (Y0 + Y1) / 2, 0.08 + (ZT - 0.08) / 2), bevel=0.012)
box("Tapa_Gabinete", (GX1 - GX0 + 0.04, Y1 - Y0 + 0.04, 0.03), ((GX0 + GX1) / 2, (Y0 + Y1) / 2, ZT + 0.015), bevel=0.006)
box("Zocalo_Gabinete", (GX1 - GX0 - 0.04, Y1 - Y0 - 0.04, 0.08), ((GX0 + GX1) / 2, (Y0 + Y1) / 2, 0.04))
for k, xx in enumerate((GX0 + 0.16, GX1 - 0.16)):
    box("Puerta_Gabinete_Frontal", (0.29, 0.012, 0.70), (xx, Y0 - 0.006, 0.50))
cyl("Cerradura_Puerta", 0.015, 0.02, ((GX0 + GX1) / 2, Y0 - 0.015, 0.62), axis="Y", verts=16)
box("Puerta_Gabinete_Lateral", (0.012, 0.75, 0.70), (GX1 + 0.006, (Y0 + Y1) / 2, 0.50))
cyl("Rueda_Gabinete", 0.035, 0.03, (GX1 - 0.08, Y0 + 0.08, 0.035), axis="X", verts=16)
# bastidor blanco abierto (lado izquierdo) bajo el cabezal
for x in (-HW + 0.02, GX0 - 0.02):
    for y in (Y0 + 0.03, Y1 - 0.03):
        box("Pata_Bastidor", (0.05, 0.05, ZT), (x, y, ZT / 2), bevel=0.003)
for y in (Y0 + 0.03, Y1 - 0.03):
    box("Larguero_Superior", (GX0 + HW - 0.02, 0.05, 0.05), ((GX0 - HW) / 2, y, ZT - 0.03))
    box("Larguero_Inferior", (GX0 + HW - 0.02, 0.05, 0.05), ((GX0 - HW) / 2, y, 0.08))
box("Travesano_Lateral", (0.05, Y1 - Y0, 0.05), (-HW + 0.02, (Y0 + Y1) / 2, 0.08))
# bandeja de acero inoxidable donde caen los cortes
box("Bandeja_Acero_Inoxidable", (GX0 + HW - 0.06, Y1 - Y0 - 0.06, 0.01), ((GX0 - HW) / 2, (Y0 + Y1) / 2, 0.30))
for y in (Y0 + 0.03, Y1 - 0.03):
    box("Soporte_Bandeja", (GX0 + HW - 0.02, 0.04, 0.03), ((GX0 - HW) / 2, y, 0.28))

# ---------------------------------------------------------------------------
# 02 Cabezal de corte (guardas en medio disco y rodillos)
# ---------------------------------------------------------------------------
grupo("02_Cabezal_de_Corte")
CY, CZ, R = 0.02, ZT + 0.02, 0.55
for sx, sn in ((1, "Der"), (-1, "Izq")):
    n = 24
    prof = [(CY + R * math.cos(math.pi * i / n), CZ + R * math.sin(math.pi * i / n)) for i in range(n + 1)]
    plate(f"Guarda_Medio_Disco_{sn}", prof, sx * HW, t=0.03)
    box(f"Placa_Soporte_Rodillos_{sn}", (0.03, 0.85, 0.20), (sx * (HW - 0.03), CY, ZT - 0.05))
box("Letrero_Cortadora_N1", (0.012, 0.20, 0.10), (-(HW + 0.017), CY + 0.20, CZ + 0.35))
cu = bpy.data.curves.new("Texto_Cortadora_N1", "FONT")
cu.body = "CORTADORA N\u00ba 1"
cu.size = 0.025
cu.align_x = "CENTER"
cu.align_y = "CENTER"
cu.extrude = 0.001
txt = link(bpy.data.objects.new("Texto_Cortadora_N1", cu))
txt.location = (-(HW + 0.024), CY + 0.20, CZ + 0.35)
txt.rotation_euler = (math.pi / 2, 0, math.pi / 2)
for y, z, r, nm in ((CY - 0.32, ZT + 0.05, 0.045, "Rodillo_Entrada"), (CY - 0.15, ZT + 0.10, 0.07, "Rodillo_Azul_Arrastre"),
                    (CY + 0.02, ZT + 0.07, 0.06, "Rodillo_Negro_Presion"), (CY + 0.18, ZT + 0.06, 0.05, "Rodillo_Cromado_Salida"),
                    (CY - 0.05, ZT + 0.22, 0.035, "Rodillo_Superior")):
    cyl(nm, r, 2 * HW - 0.06, (0, y, z), axis="X")
box("Cuchilla_Corte", (2 * HW - 0.10, 0.02, 0.08), (0, CY + 0.10, ZT + 0.16), rot=(math.radians(20), 0, 0))
box("Viga_Cuchilla", (2 * HW - 0.08, 0.08, 0.06), (0, CY + 0.12, ZT + 0.24), bevel=0.006)
cyl("Barra_Guia_Dedos", 0.012, 2 * HW - 0.06, (0, CY - 0.40, ZT + 0.20), axis="X", verts=12)
for k in range(9):
    beam("Dedo_Guia", (-0.80 + k * 0.20, CY - 0.40, ZT + 0.20), (-0.80 + k * 0.20, CY - 0.22, ZT + 0.12), 0.012, round_=True)
box("Barra_Superior_Guardas", (2 * HW + 0.04, 0.05, 0.05), (0, CY + 0.10, CZ + R - 0.04))
box("Sensor_Fotocelda", (0.06, 0.05, 0.05), (0.30, CY - 0.30, ZT + 0.30))
box("Brazo_Fotocelda", (0.02, 0.02, 0.20), (0.30, CY - 0.30, ZT + 0.18))

# ---------------------------------------------------------------------------
# 03 Tablero de control (sobre el gabinete)
# ---------------------------------------------------------------------------
grupo("03_Tablero_de_Control")
tx = (GX0 + GX1) / 2
for k, dy in enumerate((-0.30, -0.12)):
    box("Display_Digital", (0.14, 0.10, 0.03), (tx - 0.10, dy, ZT + 0.045), bevel=0.004)
box("Pantalla_HMI", (0.16, 0.12, 0.02), (tx + 0.10, -0.20, ZT + 0.04))
for r in range(2):
    for c in range(5):
        cyl("Pulsador", 0.015, 0.02, (tx - 0.20 + c * 0.09, 0.05 + r * 0.07, ZT + 0.04),
            verts=16)
cyl("Parada_Emergencia", 0.025, 0.03, (tx + 0.22, 0.20, ZT + 0.045), verts=24)
box("Placa_Metalica_Vertical", (0.10, 0.012, 0.16), (tx - 0.25, 0.28, ZT + 0.11))

# ---------------------------------------------------------------------------
# 04 Desbobinador doble (bastidor blanco al frente)
# ---------------------------------------------------------------------------
grupo("04_Desbobinador_Doble")
F0, F1 = Y0, -1.55
FX = 0.80
for sx, sn in ((1, "Der"), (-1, "Izq")):
    box(f"Riel_Superior_Desbobinador_{sn}", (0.06, F0 - F1, 0.06), (sx * FX, (F0 + F1) / 2, 0.72), bevel=0.003)
    box(f"Riel_Inferior_Desbobinador_{sn}", (0.06, F0 - F1, 0.06), (sx * FX, (F0 + F1) / 2, 0.20), bevel=0.003)
    for yy in (F0 - 0.05, F1 + 0.05):
        box(f"Pata_Desbobinador_{sn}", (0.06, 0.06, 0.75), (sx * FX, yy, 0.375), bevel=0.003)
    box(f"Placa_Soporte_Eje_Superior_{sn}", (0.10, 0.12, 0.10), (sx * (FX + 0.05), -0.90, 0.72), bevel=0.005)
    box(f"Placa_Soporte_Eje_Inferior_{sn}", (0.10, 0.12, 0.10), (sx * (FX + 0.05), F1 + 0.05, 0.30), bevel=0.005)
for z in (0.72, 0.20):
    box("Travesano_Desbobinador", (2 * FX, 0.06, 0.06), (0, F1 + 0.05, z))
for k, (yb, zb, rr) in enumerate(((-0.90, 0.72, 0.17), (F1 + 0.05, 0.30, 0.17)), start=1):
    tg = "Superior" if k == 1 else "Inferior"
    cyl(f"Bobina_{tg}", rr, 0.70, (-0.05, yb, zb), axis="X", verts=48)
    cyl(f"Nucleo_Bobina_{tg}", 0.045, 0.74, (-0.05, yb, zb), axis="X", verts=24)
    cyl(f"Eje_Bobina_{tg}", 0.03, 2 * FX + 0.40, (0, yb, zb), axis="X", verts=16)
    cyl(f"Freno_Magnetico_{tg}", 0.10, 0.08, (-(FX + 0.16), yb, zb), axis="X", verts=32)
    for j in range(10):
        a = j * math.tau / 10
        box(f"Aleta_Freno_{tg}", (0.09, 0.006, 0.02), (-(FX + 0.21), yb + 0.065 * math.cos(a), zb + 0.065 * math.sin(a)),
            rot=(a, 0, 0))
    cyl(f"Mandril_{tg}", 0.06, 0.05, (0.36, yb, zb), axis="X", verts=6)
curve_tube("Cable_Freno", [Vector((-(FX + 0.16), -0.90, 0.62)), Vector((-(FX + 0.10), -1.20, 0.25)),
                           Vector((-(FX + 0.16), F1 + 0.05, 0.20))], 0.008)

# ---------------------------------------------------------------------------
# 05 Film (dos hojas hacia el cabezal)
# ---------------------------------------------------------------------------
grupo("05_Film")
for k, pth in enumerate((
        [(-0.90, 0.89), (-0.65, 0.95), (CY - 0.32, ZT + 0.095), (CY - 0.15, ZT + 0.17), (CY + 0.02, ZT + 0.13),
         (CY + 0.18, ZT + 0.11), (CY + 0.30, 0.31)],
        [(F1 + 0.05, 0.47), (-0.95, 0.78), (-0.60, 0.98), (CY - 0.32, ZT + 0.10)]), start=1):
    verts, faces = [], []
    for (y, z) in pth:
        verts += [(-0.40, y, z), (0.30, y, z)]
    for i in range(len(pth) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    from_pydata(f"Lamina_Film_{k}", verts, faces, smooth=False)
for k in range(4):
    box("Corte_Film_en_Bandeja", (0.70, 0.40, 0.004), (-0.10, 0.10, 0.31 + 0.005 * k))

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
out = os.path.join(here, "cortadora_1_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
