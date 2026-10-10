"""
Modelo Blender limpio de la Selladora de Fondo F1 (maquina de bolsas) con la mesa de trabajo.

Solo el vehiculo: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): linea de ~6.4 m (desbobinador, cuerpo, sellado, transportador) + mesa.
La linea avanza hacia -Y (salida de bolsas al frente); el piso en z=0.

Uso:
    python3 blender/selladora_f1_modelo.py     # con bpy de PyPI
    blender -b -P blender/selladora_f1_modelo.py
Guarda blender/selladora_f1_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Selladora_de_Fondo_F1")
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


HW = 0.80           # semiancho entre placas
ZT = 1.08           # plano de trabajo (paso del film)

# ---------------------------------------------------------------------------
# 01 Desbobinador (atras)
# ---------------------------------------------------------------------------
grupo("01_Desbobinador")
Y0, Y1 = 3.60, 2.10
for sx, sn in ((1, "Izq"), (-1, "Der")):
    plate(f"Placa_Lateral_Desbobinador_{sn}", [(Y0, 0.08), (Y1, 0.08), (Y1, 1.10), (Y1 + 0.35, 1.18), (Y0 - 0.20, 0.95),
                                               (Y0, 0.70)], sx * HW, holes=[(Y1 + 0.45, 0.35, 0.30, 0.22)])
    box(f"Pie_Desbobinador_{sn}", (0.10, 0.12, 0.08), (sx * HW, Y0 - 0.10, 0.04))
    box(f"Pie_Desbobinador_Trasero_{sn}", (0.10, 0.12, 0.08), (sx * HW, Y1 + 0.10, 0.04))
    cyl(f"Rodamiento_Eje_Bobina_{sn}", 0.06, 0.06, (sx * (HW + 0.04), Y0 - 0.55, 0.62), axis="X", verts=24)
box("Piso_Chapa_Estriada_Desbobinador", (2 * HW - 0.04, Y0 - Y1 - 0.20, 0.03), (0, (Y0 + Y1) / 2, 0.10))
# bobina de film a desbobinar
cyl("Bobina_Film", 0.30, 1.20, (0, Y0 - 0.55, 0.62), axis="X", verts=64)
cyl("Nucleo_Carton_Bobina", 0.05, 1.26, (0, Y0 - 0.55, 0.62), axis="X", verts=24)
cyl("Eje_Bobina", 0.03, 2 * HW + 0.30, (0, Y0 - 0.55, 0.62), axis="X", verts=16)
for sx, sn in ((1, "Izq"), (-1, "Der")):
    cyl(f"Mandril_Bobina_{sn}", 0.05, 0.06, (sx * 0.66, Y0 - 0.55, 0.62), axis="X", verts=6)
# rodillos guia y bailarin
for k, (y, z, r) in enumerate(((Y1 + 0.95, 1.00, 0.04), (Y1 + 0.70, 1.05, 0.05), (Y1 + 0.45, 0.85, 0.04),
                               (Y1 + 0.20, 1.06, 0.045))):
    cyl("Rodillo_Guia_Desbobinador", r, 2 * HW - 0.04, (0, y, z), axis="X")
cyl("Rodillo_Bailarin", 0.045, 2 * HW - 0.04, (0, Y1 + 0.55, 0.62), axis="X")
for sx, sn in ((1, "Izq"), (-1, "Der")):
    beam(f"Brazo_Bailarin_{sn}", (sx * (HW - 0.04), Y1 + 0.85, 0.90), (sx * (HW - 0.04), Y1 + 0.55, 0.62), 0.04, t2=0.02)
# motorreductor azul y caja de control negra
box("Reductor_Desbobinador", (0.18, 0.20, 0.20), (HW + 0.12, Y1 + 0.55, 0.45), bevel=0.015)
cyl("Motor_Desbobinador", 0.09, 0.28, (HW + 0.12, Y1 + 0.55, 0.69), verts=24)
cyl("Tapa_Ventilador_Motor_Desbobinador", 0.09, 0.05, (HW + 0.12, Y1 + 0.55, 0.85), verts=24)
box("Caja_Control_Desbobinador", (0.14, 0.40, 0.45), (-(HW + 0.09), Y1 + 0.60, 0.62), bevel=0.01)
box("Valvula_Neumatica_Desbobinador", (0.08, 0.16, 0.10), (-(HW + 0.06), Y1 + 0.95, 0.90), bevel=0.005)

# ---------------------------------------------------------------------------
# 02 Cuerpo principal (placas con ventanas, gabinete electrico)
# ---------------------------------------------------------------------------
grupo("02_Cuerpo_Principal")
B0, B1 = 2.10, -0.45
for sx, sn in ((1, "Izq"), (-1, "Der")):
    plate(f"Placa_Lateral_Cuerpo_{sn}", [(B0, 0.08), (B1, 0.08), (B1, ZT + 0.02), (B0, ZT + 0.02)], sx * HW,
          holes=[(1.55, 0.50, 0.55, 0.45), (0.85, 0.50, 0.60, 0.45), (1.20, 0.88, 0.30, 0.16)])
    for yy in (B0 - 0.10, (B0 + B1) / 2, B1 + 0.10):
        cyl(f"Pata_Nivelacion_{sn}", 0.04, 0.08, (sx * HW, yy, 0.04), verts=16)
for y in (B0 - 0.15, 1.20, B1 + 0.15):
    cyl("Travesano_Inferior", 0.035, 2 * HW, (0, y, 0.22), axis="X")
# rodillos de traccion y guia sobre el cuerpo
for k, (y, z, r) in enumerate(((1.85, ZT - 0.04, 0.05), (1.45, ZT - 0.05, 0.06), (1.05, ZT - 0.04, 0.05),
                               (0.65, ZT - 0.05, 0.055))):
    cyl("Rodillo_Cromado_Cuerpo", r, 2 * HW - 0.04, (0, y, z), axis="X")
cyl("Rodillo_Goma_Traccion", 0.06, 2 * HW - 0.08, (0, 1.45, ZT + 0.07), axis="X")
cyl("Rodillo_Goma_Traccion", 0.06, 2 * HW - 0.08, (0, 0.30, ZT + 0.07), axis="X")
cyl("Rodillo_Cromado_Traccion", 0.06, 2 * HW - 0.04, (0, 0.30, ZT - 0.05), axis="X")
# gabinete electrico con puertas negras (lado izquierdo, frente)
gx = HW + 0.14
box("Gabinete_Electrico", (0.26, 1.20, 0.95), (gx, 0.25, 0.08 + 0.475), bevel=0.01)
for k, yy in enumerate((0.55, -0.05)):
    box("Puerta_Gabinete", (0.012, 0.55, 0.78), (gx + 0.135, yy, 0.55))
    cyl("Cerradura_Puerta", 0.018, 0.02, (gx + 0.145, yy - 0.20, 0.62), axis="X", verts=16)
    from_pydata("Senal_Riesgo_Electrico", [(gx + 0.143, yy - 0.05, 0.28), (gx + 0.143, yy + 0.05, 0.28),
                                           (gx + 0.143, yy, 0.37)], [(0, 1, 2)], smooth=False)
cyl("Ventilador_Gabinete", 0.04, 0.012, (gx, 0.85, 0.80), axis="X", verts=24)
box("Placa_CE", (0.012, 0.10, 0.07), (gx + 0.135, 0.70, 0.86))

# ---------------------------------------------------------------------------
# 03 Unidad de sellado (cabezal negro, placa perforada, cilindros, baliza)
# ---------------------------------------------------------------------------
grupo("03_Unidad_de_Sellado")
SY = -0.10
box("Mesa_Sellado", (2 * HW - 0.04, 0.55, 0.03), (0, SY, ZT - 0.02))
box("Cubierta_Cabezal_Sellado", (2 * HW + 0.10, 0.22, 0.16), (0, SY + 0.18, ZT + 0.22), bevel=0.02)
box("Asa_Cubierta", (0.18, 0.03, 0.04), (0.55, SY + 0.07, ZT + 0.24), bevel=0.008)
# placa perforada negra (ranuras)
box("Placa_Perforada", (2 * HW - 0.10, 0.42, 0.02), (0, SY - 0.20, ZT + 0.08))
for i in range(12):
    for j in range(3):
        c = box("Corte_Ranura", (0.07, 0.05, 0.08), (-0.70 + i * 0.127, SY - 0.33 + j * 0.13, ZT + 0.08))
        c.hide_render = c.hide_viewport = True
        md = bpy.data.objects["Placa_Perforada"].modifiers.new("Ranura", "BOOLEAN")
        md.object = c
        md.operation = "DIFFERENCE"
for k in range(5):
    x = -0.64 + k * 0.32
    cyl("Cilindro_Neumatico_Sellado", 0.03, 0.18, (x, SY + 0.18, ZT + 0.39), verts=16)
    cyl("Vastago_Cilindro", 0.008, 0.08, (x, SY + 0.18, ZT + 0.52), verts=8)
box("Barra_Sellado_Caliente", (2 * HW - 0.12, 0.04, 0.05), (0, SY + 0.18, ZT + 0.115))
cyl("Volante_Ajuste", 0.07, 0.02, (-(HW + 0.06), SY + 0.15, ZT + 0.22), axis="X", verts=24)
# postes con varillas (soporte de sensores/fotocelda)
for sx, sn in ((1, "Izq"), (-1, "Der")):
    cyl(f"Varilla_Soporte_Sensor_{sn}", 0.012, 1.40, (sx * (HW - 0.05), SY + 0.45, ZT + 0.70), verts=12)
beam("Barra_Sensor", (-(HW - 0.05), SY + 0.45, ZT + 1.38), (HW - 0.05, SY + 0.45, ZT + 1.38), 0.025, round_=True)
# baliza (torre de luces) en la esquina izquierda delantera
bx, by = HW - 0.05, SY - 0.38
cyl("Baliza_Poste", 0.012, 0.30, (bx, by, ZT + 0.15), verts=12)
z = ZT + 0.30
for nm in ("Baliza_Verde", "Baliza_Ambar", "Baliza_Roja"):
    cyl(nm, 0.035, 0.07, (bx, by, z + 0.035), verts=24)
    z += 0.072
cyl("Baliza_Tapa", 0.036, 0.015, (bx, by, z + 0.008), verts=24)
box("Caja_Herramientas", (0.30, 0.18, 0.12), (0.20, SY - 0.30, ZT + 0.06), bevel=0.02)

# ---------------------------------------------------------------------------
# 04 Tablero de control (lado derecho, frente)
# ---------------------------------------------------------------------------
grupo("04_Tablero_de_Control")
cx, cy = -(HW + 0.25), -0.15
box("Gabinete_Tablero", (0.45, 0.55, 1.15), (cx, cy, 0.08 + 0.575), bevel=0.01)
for k, yy in enumerate((cy + 0.12, cy - 0.15)):
    box("Puerta_Tablero", (0.012, 0.24, 0.80), (cx - 0.23, yy, 0.62))
box("Etiqueta_Selladora_F1", (0.012, 0.22, 0.16), (cx - 0.236, cy, 0.95))
cu = bpy.data.curves.new("Texto_Selladora_F1", "FONT")
cu.body = "SELLADORA\nDE FONDO\nF1"
cu.size = 0.032
cu.align_x = "CENTER"
cu.align_y = "CENTER"
cu.extrude = 0.001
txt = link(bpy.data.objects.new("Texto_Selladora_F1", cu))
txt.location = (cx - 0.244, cy, 0.95)
txt.rotation_euler = (math.pi / 2, 0, -math.pi / 2)
box("Consola_Mandos", (0.42, 0.16, 0.34), (cx, cy - 0.05, 1.42), rot=(math.radians(-15), 0, 0), bevel=0.01)
box("Pantalla_HMI", (0.15, 0.012, 0.10), (cx + 0.10, cy - 0.14, 1.48), rot=(math.radians(-15), 0, 0))
for r in range(3):
    for c in range(4):
        cyl("Perilla_Mando", 0.017, 0.025, (cx - 0.16 + c * 0.065, cy - 0.15, 1.40 - r * 0.06), axis="Y", verts=16)
cyl("Parada_Emergencia", 0.03, 0.03, (cx - 0.16, cy - 0.15, 1.55), axis="Y", verts=24)
for k in range(4):
    cyl("Manometro", 0.025, 0.02, (cx - 0.236, cy + 0.18, 0.40 + k * 0.08), axis="X", verts=16)

# ---------------------------------------------------------------------------
# 05 Transportador de banda verde (salida de bolsas)
# ---------------------------------------------------------------------------
grupo("05_Transportador_Banda")
T0, T1 = -0.55, -2.25
TW = 0.70
TZ = 0.80
box("Banda_Transportadora", (2 * TW - 0.04, T0 - T1, 0.025), (0, (T0 + T1) / 2, TZ))
for sx, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Perfil_Aluminio_Lateral_{sn}", (0.04, T0 - T1, 0.09), (sx * TW, (T0 + T1) / 2, TZ - 0.02))
    for yy in (T0 - 0.15, T1 + 0.15):
        box(f"Pata_Perfil_Aluminio_{sn}", (0.04, 0.04, TZ - 0.12), (sx * TW, yy, (TZ - 0.12) / 2 + 0.06))
        cyl(f"Rueda_Transportador_{sn}", 0.035, 0.03, (sx * TW, yy, 0.035), axis="X", verts=16)
    beam(f"Diagonal_Transportador_{sn}", (sx * TW, T0 - 0.15, 0.30), (sx * TW, T1 + 0.15, 0.55), 0.035)
for yy in (T0 - 0.15, T1 + 0.15):
    box("Travesano_Transportador", (2 * TW, 0.04, 0.04), (0, yy, 0.30))
for yy in (T0 - 0.02, T1 + 0.02):
    cyl("Rodillo_Banda", 0.035, 2 * TW - 0.04, (0, yy, TZ - 0.02), axis="X")
box("Reductor_Transportador", (0.14, 0.14, 0.14), (-(TW + 0.10), T1 + 0.05, TZ - 0.05), bevel=0.01)
cyl("Motor_Transportador", 0.06, 0.18, (-(TW + 0.10), T1 + 0.05, TZ - 0.22), verts=24)

# ---------------------------------------------------------------------------
# 06 Mesa de trabajo (frente)
# ---------------------------------------------------------------------------
grupo("06_Mesa_de_Trabajo")
MY, MZ = -3.30, 0.90
MLX, MLY = 2.40, 1.20
box("Tablero_Mesa", (MLX, MLY, 0.03), (0, MY, MZ - 0.015), bevel=0.003)
for sx in (-1, 1):
    box("Larguero_Mesa", (0.03, MLY - 0.10, 0.06), (sx * (MLX / 2 - 0.08), MY, MZ - 0.06))
for sy in (-1, 1):
    box("Travesano_Mesa", (MLX - 0.16, 0.03, 0.06), (0, MY + sy * (MLY / 2 - 0.08), MZ - 0.06))
for sx in (-1, 1):
    for sy in (-1, 1):
        box("Pata_Mesa", (0.035, 0.035, MZ - 0.03), (sx * (MLX / 2 - 0.10), MY + sy * (MLY / 2 - 0.10), (MZ - 0.03) / 2))
box("Regla_Metalica", (1.10, 0.04, 0.005), (-0.20, MY - 0.35, MZ + 0.003))

# ---------------------------------------------------------------------------
# 07 Lamina de film (de la bobina al sellado)
# ---------------------------------------------------------------------------
grupo("07_Film")
path = [(Y0 - 0.55 - 0.30, 0.62), (Y1 + 0.95, 1.04), (Y1 + 0.70, 1.10), (Y1 + 0.55, 0.67), (Y1 + 0.45, 0.89),
        (Y1 + 0.20, 1.11), (1.85, ZT + 0.01), (0.30, ZT + 0.01), (SY - 0.40, ZT + 0.01)]
verts, faces = [], []
for (y, z) in path:
    verts += [(-0.60, y, z), (0.60, y, z)]
for i in range(len(path) - 1):
    faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
from_pydata("Lamina_Film", verts, faces, smooth=False)
# bolsas terminadas sobre la banda
for k in range(3):
    box("Bolsa_Terminada", (1.10, 0.45, 0.004 + 0.002 * k), (0, -0.95 - k * 0.48, TZ + 0.015 + 0.002 * k))

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
out = os.path.join(here, "selladora_f1_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
