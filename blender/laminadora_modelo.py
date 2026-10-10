"""
Modelo Blender limpio de la Laminadora (laminado sin solvente).

Solo la maquina: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): ~6.3 de largo x 2.3 de ancho x ~2.75 de alto. Eje largo en X, frente hacia -Y:
pilar izquierdo, bahia de laminado, pilar de mando central, bahia de rebobinado y unidad de recubrimiento (+X).
El piso en z=0.

Uso:
    python3 blender/laminadora_modelo.py     # con bpy de PyPI
    blender -b -P blender/laminadora_modelo.py
Guarda blender/laminadora_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Laminadora")
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


# Eje largo en X; frente (operador) hacia -Y.
FY0, FY1 = -1.05, -0.85   # bastidor frontal (pilares)
BY0, BY1 = 0.85, 1.05     # bastidor trasero
XL, XR = -2.95, 2.25      # cuerpo principal (sin la unidad de recubrimiento)
CZ0, CZ1 = 2.05, 2.40     # cubierta superior
RL = BY0 - FY1            # largo de rodillos entre bastidores (~1.7)


def pillar(name, x0, x1, front=True, h=CZ0):
    """Pilar: frente blanco con laterales gris oscuro."""
    y0, y1 = (FY0, FY1) if front else (BY0, BY1)
    xc, w = (x0 + x1) / 2, x1 - x0
    box(f"{name}_Cuerpo_Gris", (w, y1 - y0, h), (xc, (y0 + y1) / 2, h / 2), bevel=0.01)
    yf = y0 - 0.006 if front else y1 + 0.006
    box(f"{name}_Frente_Blanco", (w - 0.18, 0.012, h - 0.05), (xc, yf, h / 2))
    for j in range(8):
        box(f"{name}_Rejilla_Inferior", (w - 0.30, 0.014, 0.012), (xc, yf, 0.12 + j * 0.025))
    return xc, yf


def roller_stack(prefix, xc, zs):
    for k, (z, r, kind) in enumerate(zs):
        cyl(f"{prefix}_{kind}", r, RL, (xc, (FY1 + BY0) / 2, z), axis="Y", verts=32)
        for sy in (-1, 1):
            cyl(f"{prefix}_Rodamiento_{kind}", r * 0.6, 0.05, (xc, (FY1 + BY0) / 2 + sy * (RL / 2 + 0.02), z), axis="Y",
                verts=16)


def arm_roll(prefix, xc, z, rr):
    """Bobina sobre eje con carcasas blancas en voladizo (desbobinador/rebobinador)."""
    yc = (FY1 + BY0) / 2
    cyl(f"{prefix}_Bobina", rr, 1.10, (xc, yc - 0.10, z), axis="Y", verts=64)
    cyl(f"{prefix}_Nucleo", 0.045, 1.16, (xc, yc - 0.10, z), axis="Y", verts=24)
    cyl(f"{prefix}_Eje_Neumatico", 0.035, RL + 0.20, (xc, yc, z), axis="Y", verts=16)
    for sy, sn in ((-1, "Frontal"), (1, "Trasero")):
        box(f"{prefix}_Carcasa_Brazo_{sn}", (0.30, 0.22, 0.32), (xc + 0.05, yc + sy * (RL / 2 - 0.05), z), bevel=0.04)
        box(f"{prefix}_Brazo_{sn}", (0.12, 0.10, 0.40), (xc + 0.20, yc + sy * (RL / 2 - 0.05), z - 0.25))
    spiral_hose(f"{prefix}_Cable_Espiral", (xc - 0.10, FY1 - 0.05, z - 0.15), turns=12, drop=0.35)


# ===========================================================================
# 01 Bastidores: pilares frontales (blancos) y traseros (gris oscuro)
# ===========================================================================
grupo("01_Pilares_y_Bastidores")
xa, yfa = pillar("Pilar_Izquierdo", XL, -2.35)
box("Panel_Botonera_Vertical", (0.16, 0.014, 0.85), (xa, yfa - 0.004, 1.30))
for k in range(8):
    for c in range(2):
        cyl("Pulsador_Panel_Izquierdo", 0.014, 0.02, (xa - 0.04 + c * 0.08, yfa - 0.012, 1.62 - k * 0.09), axis="Y",
            verts=12)
box("Controlador_Digital_Izquierdo", (0.10, 0.014, 0.06), (xa + 0.18, yfa - 0.004, 1.05))
xb, yfb = pillar("Pilar_Mando_Central", -0.55, 0.55)
box("Panel_Mando_Negro", (0.80, 0.014, 1.15), (xb, yfb - 0.004, 1.30))
box("Pantalla_HMI", (0.32, 0.016, 0.24), (xb, yfb - 0.010, 1.62))
for r in range(4):
    cyl("Pulsador_Mando", 0.016, 0.02, (xb - 0.30, yfb - 0.012, 1.72 - r * 0.08), axis="Y", verts=12)
    cyl("Pulsador_Mando", 0.016, 0.02, (xb + 0.30, yfb - 0.012, 1.72 - r * 0.08), axis="Y", verts=12)
for c in range(6):
    cyl("Pulsador_Color", 0.016, 0.02, (xb - 0.25 + c * 0.10, yfb - 0.012, 1.40), axis="Y", verts=12)
for c in range(4):
    cyl("Manometro", 0.04, 0.02, (xb - 0.27 + c * 0.18, yfb - 0.012, 1.22), axis="Y", verts=24)
    cyl("Regulador_Rojo", 0.02, 0.03, (xb - 0.27 + c * 0.18, yfb - 0.015, 1.10), axis="Y", verts=12)
box("Franja_Panel", (0.70, 0.015, 0.02), (xb, yfb - 0.012, 0.85))
box("Controlador_Digital_Central", (0.10, 0.014, 0.08), (0.62, FY0 - 0.006, 1.05))
xc_, yfc = pillar("Pilar_Derecho", 2.10, 2.25 + 0.10)
for x0, x1, nm in ((XL, -2.35, "Izquierdo"), (-0.55, 0.55, "Central"), (2.10, 2.35, "Derecho")):
    pillar(f"Bastidor_Trasero_{nm}", x0, x1, front=False)

# ===========================================================================
# 02 Cubierta superior y equipos de arriba
# ===========================================================================
grupo("02_Cubierta_Superior")
L = 2.35 - XL
box("Cubierta_Superior_Blanca", (L, BY1 - FY0 + 0.10, CZ1 - CZ0), ((XL + 2.35) / 2, (FY0 + BY1) / 2, (CZ0 + CZ1) / 2),
    bevel=0.08)
box("Display_LED_Caja", (0.75, 0.04, 0.24), (0.10, FY0 - 0.065, (CZ0 + CZ1) / 2), bevel=0.03)
for k in range(2):
    box("Display_LED_Digitos", (0.25, 0.01, 0.12), (-0.07 + k * 0.34, FY0 - 0.088, (CZ0 + CZ1) / 2 - 0.01))
box("Franja_Azul_Display", (0.70, 0.01, 0.015), (0.10, FY0 - 0.088, CZ1 - 0.06))
cyl("Soplador_Superior", 0.22, 0.22, (1.20, 0.30, CZ1 + 0.24), axis="X", verts=32)
cyl("Motor_Soplador", 0.10, 0.28, (1.45, 0.30, CZ1 + 0.24), axis="X", verts=24)
box("Base_Soplador", (0.60, 0.45, 0.04), (1.30, 0.30, CZ1 + 0.02))
cyl("Motor_Superior_Izquierdo", 0.09, 0.22, (-1.80, 0.40, CZ1 + 0.13), verts=24)
box("Ducto_Rectangular_Superior", (0.80, 0.30, 0.25), (-0.40, 0.55, CZ1 + 0.13), bevel=0.01)
curve_tube("Codo_Ducto_Blanco", [Vector((XL + 0.15, 0.55, CZ1 + 0.05)), Vector((XL + 0.15, 0.55, CZ1 + 0.35)),
                                 Vector((XL - 0.20, 0.55, CZ1 + 0.45))], 0.09)
curve_tube("Ducto_Flexible_Bajada", [Vector((1.20, BY1 + 0.10, CZ1 + 0.10)), Vector((1.25, BY1 + 0.25, CZ0 - 0.30)),
                                     Vector((1.30, BY1 + 0.25, 0.10))], 0.10)
# marco de rodillos de entrada sobre el extremo izquierdo
for sy in (-1, 1):
    box("Marco_Rodillos_Entrada", (0.06, 0.06, 0.40), (XL + 0.35, sy * 0.80, CZ1 + 0.20))
box("Travesano_Marco_Entrada", (0.06, 1.66, 0.06), (XL + 0.35, 0, CZ1 + 0.40))
for z in (CZ1 + 0.30, CZ1 + 0.12):
    cyl("Rodillo_Entrada_Superior", 0.045, 1.60, (XL + 0.42, 0, z), axis="Y")

# ===========================================================================
# 03 Bahia de laminado (izquierda): rodillos y desbobinador
# ===========================================================================
grupo("03_Bahia_Laminado")
roller_stack("Laminado", -1.45, [(1.88, 0.06, "Rodillo_Negro"), (1.72, 0.06, "Rodillo_Negro"),
                                 (1.56, 0.07, "Rodillo_Goma_Laminado"), (1.40, 0.06, "Rodillo_Cubierta_Amarilla"),
                                 (1.24, 0.065, "Rodillo_Negro"), (1.08, 0.08, "Rodillo_Cromado_Calefactado")])
for k, z in enumerate((1.88, 1.72, 1.56, 1.24)):
    for sy in (-1, 1):
        cyl("Laminado_Punta_Dorada", 0.025, 0.06, (-1.45, sy * (RL / 2 + 0.06), z), axis="Y", verts=12)
box("Laminado_Cubierta_Amarilla_Guarda", (0.25, RL - 0.10, 0.04), (-1.45, (FY1 + BY0) / 2, 1.46))
box("Laminado_Placa_Soporte_Trasera", (1.70, 0.04, 1.20), (-1.45, 0.83, 1.40))
arm_roll("Desbobinador_1", -1.55, 0.55, 0.22)
cyl("Rodillo_Guia_Inferior_Laminado", 0.04, RL, (-0.90, (FY1 + BY0) / 2, 0.30), axis="Y")

# ===========================================================================
# 04 Bahia de rebobinado (derecha): rodillos con soportes naranjas y rebobinador
# ===========================================================================
grupo("04_Bahia_Rebobinado")
roller_stack("Rebobinado", 1.32, [(1.90, 0.055, "Rodillo_Negro"), (1.74, 0.055, "Rodillo_Negro"),
                                  (1.55, 0.065, "Rodillo_Negro"), (1.38, 0.06, "Rodillo_Tension"),
                                  (1.18, 0.075, "Rodillo_Cromado"), (0.98, 0.06, "Rodillo_Negro")])
for sy in (-1, 1):
    beam("Rebobinado_Brazo_Naranja", (1.05, sy * 0.80, 1.70), (1.60, sy * 0.80, 1.45), 0.06, t2=0.10)
box("Rebobinado_Placa_Soporte_Trasera", (1.70, 0.04, 1.20), (1.32, 0.83, 1.40))
arm_roll("Rebobinador", 1.30, 0.55, 0.18)
box("Rebobinado_Fotocelda", (0.08, 0.06, 0.06), (1.00, -0.60, 1.30))

# ===========================================================================
# 05 Unidad de recubrimiento (extremo derecho, carcasa gris con ventana)
# ===========================================================================
grupo("05_Unidad_Recubrimiento")
UX0, UX1 = 2.35, 3.30
box("Carcasa_Recubrimiento_Gris", (UX1 - UX0, BY1 - FY0, 2.20), ((UX0 + UX1) / 2, (FY0 + BY1) / 2, 1.10), bevel=0.02)
box("Capota_Redondeada_Blanca", (UX1 - UX0 + 0.12, BY1 - FY0 + 0.12, 0.40), ((UX0 + UX1) / 2 + 0.04, (FY0 + BY1) / 2, 2.35),
    bevel=0.12)
box("Ranura_Luz_Capota", (0.012, 1.60, 0.03), (UX1 + 0.10, (FY0 + BY1) / 2, 2.22))
box("Ventana_Vidrio_Recubrimiento", (0.012, 1.40, 0.55), (UX1 + 0.006, (FY0 + BY1) / 2, 1.55))
box("Marco_Ventana", (0.016, 1.50, 0.65), (UX1 + 0.004, (FY0 + BY1) / 2, 1.55))
c = box("Corte_Abertura_Rodillos", (0.40, 1.50, 0.75), (UX1, (FY0 + BY1) / 2, 0.80))
c.hide_render = c.hide_viewport = True
md = bpy.data.objects["Carcasa_Recubrimiento_Gris"].modifiers.new("Abertura", "BOOLEAN")
md.object = c
md.operation = "DIFFERENCE"
for z, r, nm in ((1.08, 0.08, "Rodillo_Recubrimiento_Cromado"), (1.08, 0.05, "Rodillo_Dosificador_Verde"),
                 (0.88, 0.07, "Rodillo_Aplicador_Cromado"), (0.70, 0.04, "Rodillo_Guia_Inferior"),
                 (0.35, 0.05, "Rodillo_Blanco_Base")):
    cyl(nm, r, 1.45, (UX1 - 0.08 + (0.10 if "Verde" in nm else 0), (FY0 + BY1) / 2, z), axis="Y", verts=32)
box("Barra_Perforada_Racla", (0.05, 1.40, 0.06), (UX1 - 0.02, (FY0 + BY1) / 2, 0.98))
box("Panel_Pulsadores_Inoxidable", (0.012, 0.18, 0.30), (UX1 + 0.006, FY0 + 0.35, 1.60))
for k in range(4):
    cyl("Pulsador_Recubrimiento", 0.016, 0.02, (UX1 + 0.012, FY0 + 0.35, 1.70 - k * 0.07), axis="X", verts=12)
cyl("Paro_Emergencia_Recubrimiento", 0.03, 0.03, (UX1 + 0.015, FY0 + 0.35, 1.42), axis="X", verts=24)
for sy in (-1, 1):
    box("Pata_Carcasa", (0.12, 0.12, 0.05), (UX1 - 0.15, sy * 0.85, 0.025))
curve_tube("Ducto_Flexible_Recubrimiento", [Vector((UX0 + 0.30, -0.30, 2.40)), Vector((UX0 + 0.50, 0.20, 2.10)),
                                            Vector((UX0 + 0.70, 0.30, 1.85))], 0.07)

# ===========================================================================
# 06 Film: dos laminas que se unen en el rodillo de laminado
# ===========================================================================
grupo("06_Film")
yc = (FY1 + BY0) / 2
w = 0.55
paths = {
    "Lamina_Base_Desbobinador_1": [(-1.55, 0.77), (-0.90, 0.34), (-1.20, 1.08), (-1.40, 1.56), (-1.20, 1.88), (0.0, 1.95),
                                    (1.10, 1.95), (1.32, 1.18), (1.30, 0.73)],
    "Lamina_Recubierta": [(UX1 - 0.08, 1.16), (2.60, 1.70), (2.30, 1.98), (0.0, 1.98)],
}
for nm, pth in paths.items():
    verts, faces = [], []
    for (x, z) in pth:
        verts += [(x, yc - w, z), (x, yc + w, z)]
    for i in range(len(pth) - 1):
        faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
    from_pydata(nm, verts, faces, smooth=False)

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
out = os.path.join(here, "laminadora_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
