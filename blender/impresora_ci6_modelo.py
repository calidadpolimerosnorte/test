"""
Modelo Blender limpio de la Impresora Flexografica de tambor central CHCI6-800J (6 colores).

Solo el vehiculo: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): torre ~2.6 x 3.2 x 2.75 de alto + plataforma superior con secador (~3.9 m total),
escalera, desbobinador/rebobinador, columna de mando, equipo de temperatura y gabinete electrico.
La linea avanza hacia -Y (salida de bolsas al frente); el piso en z=0.

Uso:
    python3 blender/impresora_ci6_modelo.py     # con bpy de PyPI
    blender -b -P blender/impresora_ci6_modelo.py
Guarda blender/impresora_ci6_modelo.blend.
"""
import math
import os

import bpy
import bmesh
from mathutils import Vector, Matrix

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
ROOT = bpy.data.collections.new("Impresora_CHCI6_800J")
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


FX = 0.85           # cara interior de los bastidores laterales (+-X)
FT = 0.30           # espesor de cada bastidor (carcasa)
FY = 1.30           # semilargo de los bastidores
FH = 2.30           # alto de los bastidores
DZ = 1.25           # eje del tambor central
DR = 0.72           # radio del tambor central
CZ = 2.35           # base de la cubierta superior


def octagon(cy, cz, w, h, c):
    return [(cy - w / 2 + c, cz - h / 2), (cy + w / 2 - c, cz - h / 2), (cy + w / 2, cz - h / 2 + c),
            (cy + w / 2, cz + h / 2 - c), (cy + w / 2 - c, cz + h / 2), (cy - w / 2 + c, cz + h / 2),
            (cy - w / 2, cz + h / 2 - c), (cy - w / 2, cz - h / 2 + c)]


# ===========================================================================
# 01 Bastidores laterales (carcasas blancas con marco octogonal y ventanas)
# ===========================================================================
grupo("01_Bastidores_Laterales")
for sx, sn in ((1, "Operador"), (-1, "Transmision")):
    x = sx * (FX + FT / 2)
    plate(f"Bastidor_Lateral_{sn}", octagon(0.0, FH / 2 + 0.05, 2 * FY, FH, 0.45), x, t=FT,
          holes=[(-0.62, 1.70, 0.62, 0.55), (0.62, 1.70, 0.62, 0.55), (-0.62, 0.62, 0.62, 0.55), (0.62, 0.62, 0.62, 0.55)])
    xo = sx * (FX + FT + 0.005)
    for (wy, wz) in ((-0.62, 1.70), (0.62, 1.70), (-0.62, 0.62), (0.62, 0.62)):
        box(f"Ventana_Acrilico_{sn}", (0.008, 0.60, 0.53), (sx * (FX + FT / 2), wy, wz))
    box(f"Puerta_Central_{sn}", (0.012, 0.40, 1.95), (xo, 0.0, 1.15))
    box(f"Manija_Puerta_{sn}", (0.03, 0.03, 0.18), (xo + sx * 0.02, -0.12, 1.15))
    box(f"Zocalo_Bastidor_{sn}", (FT + 0.04, 2 * FY - 0.60, 0.08), (x, 0, 0.04))

# ===========================================================================
# 02 Tambor central y 6 grupos de impresion
# ===========================================================================
grupo("02_Tambor_y_Grupos_de_Impresion")
cyl("Tambor_Central", DR, 2 * FX - 0.04, (0, 0, DZ), axis="X", verts=96)
cyl("Eje_Tambor_Central", 0.08, 2 * (FX + FT) + 0.10, (0, 0, DZ), axis="X", verts=24)
for k, ang in enumerate((200, 235, 270, 305, 340, 20) if False else (150, 180, 210, 330, 0, 30), start=1):
    a = math.radians(ang)
    dy, dz = math.cos(a), math.sin(a)
    g = f"Grupo_Impresion_{k}"
    pc = (0, dy * (DR + 0.09), DZ + dz * (DR + 0.09))
    an = (0, dy * (DR + 0.26), DZ + dz * (DR + 0.26))
    cyl(f"{g}_Cilindro_Portaclise", 0.09, 2 * FX - 0.20, pc, axis="X", verts=32)
    cyl(f"{g}_Rodillo_Anilox", 0.075, 2 * FX - 0.20, an, axis="X", verts=32)
    rot = (math.atan2(dz, dy), 0, 0)
    box(f"{g}_Camara_Racla", (2 * FX - 0.30, 0.10, 0.12), (0, dy * (DR + 0.40), DZ + dz * (DR + 0.40)), rot=rot, bevel=0.01)
    for sx in (-1, 1):
        box(f"{g}_Soporte_Lateral", (0.12, 0.42, 0.20), (sx * (FX - 0.08), dy * (DR + 0.22), DZ + dz * (DR + 0.22)),
            rot=rot, bevel=0.01)
        box(f"{g}_Bloque_Ajuste", (0.10, 0.12, 0.14), (sx * (FX - 0.08), dy * (DR + 0.48), DZ + dz * (DR + 0.48)),
            rot=rot, bevel=0.008)
        for j in range(2):
            cyl(f"{g}_Perilla_Ajuste", 0.02, 0.03, (sx * (FX - 0.02), dy * (DR + 0.48) + (j - 0.5) * 0.06,
                                                     DZ + dz * (DR + 0.48)), axis="X", verts=12)
    box(f"{g}_Botonera", (0.40, 0.012, 0.05), (0, dy * (DR + 0.47), DZ + dz * (DR + 0.47) + 0.10))
    curve_tube(f"{g}_Manguera_Tinta", [Vector((-(FX - 0.20), dy * (DR + 0.42), DZ + dz * (DR + 0.42))),
                                       Vector((-(FX - 0.10), dy * (DR + 0.70), DZ + dz * (DR + 0.42) - 0.30)),
                                       Vector((-(FX - 0.05), dy * (FY - 0.10), 0.15))], 0.012)
# rodillos guia y de secado entre colores (arriba del tambor)
for y in (-0.55, -0.25, 0.25, 0.55):
    cyl("Rodillo_Guia_Superior", 0.04, 2 * FX - 0.04, (0, y, DZ + DR + 0.30), axis="X")
for y in (-0.95, 0.95):
    cyl("Rodillo_Guia_Lateral", 0.045, 2 * FX - 0.04, (0, y, DZ + 0.05), axis="X")
for k in range(3):
    box("Caja_Secado_Entre_Colores", (2 * FX - 0.20, 0.14, 0.10), (0, -0.40 + k * 0.40, DZ + DR + 0.18), bevel=0.01)

# ===========================================================================
# 03 Cubierta superior (tunel de secado) y plataforma con baranda
# ===========================================================================
grupo("03_Cubierta_y_Plataforma")
CX0, CX1 = -(FX + FT + 0.20), FX + FT + 0.20
CY0, CY1 = -(FY + 0.35), FY + 0.35
CH = 0.42
verts = []
for x in (CX0, CX1):
    verts += [(x, CY0 + 0.25, CZ), (x, CY1 - 0.25, CZ), (x, CY1, CZ + CH * 0.55), (x, CY1, CZ + CH),
              (x, CY0, CZ + CH), (x, CY0, CZ + CH * 0.55)]
faces = [(0, 1, 2, 3, 4, 5)[::-1], (6, 7, 8, 9, 10, 11)]
for i in range(6):
    j = (i + 1) % 6
    faces.append((i, j, 6 + j, 6 + i))
from_pydata("Cubierta_Superior_Gris", verts, faces, smooth=False)
cu = bpy.data.curves.new("Texto_Modelo_CHCI6_800J", "FONT")
cu.body = "CHCI6-800J"
cu.size = 0.16
cu.align_x = "CENTER"
cu.align_y = "CENTER"
cu.extrude = 0.002
txt = link(bpy.data.objects.new("Texto_Modelo_CHCI6_800J", cu))
txt.location = (0.25, CY0 - 0.004, CZ + CH * 0.78)
txt.rotation_euler = (math.pi / 2, 0, 0)
box("Placa_Plataforma_Superior", (CX1 - CX0 - 0.02, CY1 - CY0 - 0.02, 0.02), (0, 0, CZ + CH + 0.01))
# baranda de acero inoxidable (tubo redondo) alrededor, abierta donde llega la escalera
rh = 1.0
pts = [(CX0 + 0.05, CY0 + 0.05), (CX1 - 0.05, CY0 + 0.05), (CX1 - 0.05, CY1 - 0.05), (CX0 + 0.05, CY1 - 0.05)]
zb = CZ + CH + 0.02
for i in range(4):
    p1, p2 = pts[i], pts[(i + 1) % 4]
    if i == 1:   # lado derecho: hueco para la escalera
        segs = [(p1, (p1[0], CY0 + 0.35)), ((p1[0], CY0 + 0.95), p2)]
    else:
        segs = [(p1, p2)]
    for a, b in segs:
        for z in (zb + rh, zb + 0.50):
            beam("Baranda_Inoxidable", (a[0], a[1], z), (b[0], b[1], z), 0.04, round_=True)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, round(L / 0.9))
        for k in range(n + 1):
            px = a[0] + (b[0] - a[0]) * k / n
            py_ = a[1] + (b[1] - a[1]) * k / n
            cyl("Parante_Baranda_Inoxidable", 0.02, rh, (px, py_, zb + rh / 2), verts=12)
# secador / extractor sobre la plataforma con ductos
box("Caja_Secador_Superior", (1.40, 1.20, 0.55), (-0.20, 0.30, zb + 0.275), bevel=0.02)
for sy in (-1, 1):
    curve_tube("Ducto_Flexible_Rojo", [Vector((-0.90, 0.30 + sy * 0.30, zb + 0.35)), Vector((CX0 - 0.10, 0.30 + sy * 0.50, zb + 0.10)),
                                      Vector((CX0 - 0.05, 0.30 + sy * 0.70, CZ - 0.30))], 0.07)
cyl("Soplador_Gris", 0.22, 0.20, (CX1 - 0.35, -0.95, zb + 0.30), axis="X", verts=32)
cyl("Motor_Soplador", 0.10, 0.25, (CX1 - 0.12, -0.95, zb + 0.30), axis="X", verts=24)
curve_tube("Ducto_Aluminio_Flexible", [Vector((CX1 - 0.35, -1.15, zb + 0.30)), Vector((CX1 - 0.30, -1.45, zb + 0.10)),
                                       Vector((CX1 - 0.25, CY0 - 0.15, CZ - 0.20)), Vector((CX1 - 0.25, CY0 - 0.10, 1.70))], 0.08)
box("Display_Velocidad", (0.30, 0.10, 0.15), (CX0 + 0.40, CY0 - 0.04, CZ - 0.10))

# ===========================================================================
# 04 Escalera de acero inoxidable a la plataforma
# ===========================================================================
grupo("04_Escalera_Inoxidable")
lx, lw = CX1 + 0.05, 0.55
bot = Vector((0, CY0 - 1.30, 0.0))
top = Vector((0, CY0 + 0.65, zb))
for sx in (0, 1):
    x = lx + sx * lw
    beam("Larguero_Escalera_Inoxidable", (x, bot.y, bot.z), (x, top.y, top.z), 0.05, round_=True)
    beam("Pasamano_Escalera_Inoxidable", (x, bot.y + 0.20, 0.95), (x, top.y + 0.10, top.z + 1.0), 0.04, round_=True)
    beam("Pasamano_Escalera_Inoxidable", (x, top.y + 0.10, top.z + 1.0), (x, top.y + 0.45, top.z + 1.0), 0.04, round_=True)
    box("Pie_Goma_Escalera", (0.08, 0.14, 0.04), (x, bot.y, 0.02))
n = 10
for i in range(1, n):
    p = bot.lerp(top, i / n)
    box("Peldano_Inoxidable", (lw - 0.04, 0.14, 0.025), (lx + lw / 2, p.y + 0.03, p.z), bevel=0.004)

# ===========================================================================
# 05 Desbobinador (atras) y rebobinador (adelante)
# ===========================================================================
grupo("05_Desbobinador_y_Rebobinador")
for nm, yy, sg in (("Rebobinador", -(FY + 0.25), -1), ("Desbobinador", FY + 0.25, 1)):
    for sx in (-1, 1):
        box(f"{nm}_Brazo_Soporte", (0.10, 0.35, 0.65), (sx * (FX - 0.05), yy, 0.36), bevel=0.01)
        cyl(f"{nm}_Rueda_Freno", 0.12, 0.06, (sx * (FX + 0.05), yy, 0.48), axis="X", verts=32)
    cyl(f"{nm}_Bobina", 0.22, 0.85, (0, yy + sg * 0.05, 0.48), axis="X", verts=64)
    cyl(f"{nm}_Nucleo", 0.05, 0.90, (0, yy + sg * 0.05, 0.48), axis="X", verts=24)
    cyl(f"{nm}_Eje_Neumatico", 0.035, 2 * FX + 0.30, (0, yy + sg * 0.05, 0.48), axis="X", verts=16)
    cyl(f"{nm}_Rodillo_Tension", 0.04, 2 * FX - 0.10, (0, yy - sg * 0.25, 0.95), axis="X")
    cyl(f"{nm}_Rodillo_Guia", 0.04, 2 * FX - 0.10, (0, yy - sg * 0.15, 1.35), axis="X")
    spiral_hose(f"{nm}_Manguera_Espiral_Naranja", (FX + 0.10, yy, 0.90), turns=10, drop=0.35)

# ===========================================================================
# 06 Columna de mando, equipo de temperatura y gabinete electrico
# ===========================================================================
grupo("06_Mando_y_Gabinetes")
mx, my = FX + FT + 0.30, -(FY - 0.30)
box("Columna_Mando_Gris", (0.45, 0.55, CZ - 0.05), (mx, my, (CZ - 0.05) / 2), bevel=0.01)
fy = my - 0.28
box("Pantalla_Grande_HMI", (0.32, 0.012, 0.25), (mx, fy, 1.85))
box("Panel_Mandos", (0.30, 0.012, 0.45), (mx, fy, 1.25))
box("Pantalla_HMI_Panel", (0.16, 0.014, 0.11), (mx, fy - 0.002, 1.35))
for k in range(2):
    box("Controlador_Temperatura", (0.08, 0.014, 0.06), (mx - 0.06 + k * 0.12, fy - 0.002, 1.47))
for r in range(2):
    for c in range(4):
        cyl("Pulsador_Mando", 0.018, 0.02, (mx - 0.10 + c * 0.065, fy - 0.01, 1.15 - r * 0.07), axis="Y", verts=16)
cyl("Baliza_Roja_Giratoria", 0.05, 0.08, (mx - 0.18, my - 0.10, 1.68), axis="X", verts=24)
# equipo de control de temperatura (blanco) junto a la columna
tx, ty = mx + 0.60, my + 0.05
box("Equipo_Control_Temperatura", (0.55, 0.65, 1.10), (tx, ty, 0.05 + 0.55), bevel=0.012)
box("Pantalla_Equipo_Temperatura", (0.16, 0.012, 0.11), (tx - 0.08, ty - 0.33, 0.95))
cyl("Paro_Emergencia_Equipo", 0.03, 0.03, (tx + 0.18, ty - 0.33, 0.75), axis="Y", verts=24)
for sx in (-1, 1):
    cyl("Rueda_Equipo_Temperatura", 0.035, 0.03, (tx + sx * 0.20, ty, 0.035), axis="X", verts=16)
cyl("Baliza_Equipo_Poste", 0.012, 0.25, (tx + 0.18, ty + 0.20, 1.27), verts=12)
for k, nm in enumerate(("Baliza_Verde", "Baliza_Ambar", "Baliza_Roja")):
    cyl(nm, 0.03, 0.06, (tx + 0.18, ty + 0.20, 1.42 + k * 0.062), verts=24)
# gabinete electrico blanco (lado opuesto) con rejilla y baliza
gx, gy = -(FX + FT + 0.55), -(FY - 0.10)
box("Gabinete_Electrico", (0.75, 0.60, 1.00), (gx, gy, 0.08 + 0.50), bevel=0.012)
for j in range(6):
    box("Rejilla_Gabinete", (0.25, 0.012, 0.02), (gx + 0.15, gy - 0.306, 0.75 + j * 0.035))
box("Placa_Advertencia", (0.10, 0.012, 0.06), (gx - 0.25, gy - 0.306, 0.70))
cyl("Baliza_Gabinete_Poste", 0.012, 0.25, (gx - 0.25, gy + 0.15, 1.20), verts=12)
for k, nm in enumerate(("Baliza_Gabinete_Verde", "Baliza_Gabinete_Ambar", "Baliza_Gabinete_Roja")):
    cyl(nm, 0.03, 0.06, (gx - 0.25, gy + 0.15, 1.35 + k * 0.062), verts=24)
for sx in (-1, 1):
    cyl("Rueda_Gabinete", 0.035, 0.03, (gx + sx * 0.28, gy, 0.035), axis="X", verts=16)

# ===========================================================================
# 07 Film impreso (desbobinador -> tambor -> rebobinador)
# ===========================================================================
grupo("07_Film_Impreso")
path = [(FY + 0.30, 0.70), (FY + 0.10, 1.35), (0.95, DZ + 0.05), (0.62, DZ + 0.41), (0.40, DZ + 0.62),
        (0.0, DZ + DR + 0.01), (-0.40, DZ + 0.62), (-0.62, DZ + 0.41), (-0.95, DZ + 0.05),
        (-(FY + 0.10), 1.35), (-(FY + 0.25) + 0.25, 0.95), (-(FY + 0.30), 0.70)]
verts, faces = [], []
for (y, z) in path:
    verts += [(-0.40, y, z), (0.40, y, z)]
for i in range(len(path) - 1):
    faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
from_pydata("Lamina_Film_Impreso", verts, faces, smooth=False)

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
out = os.path.join(here, "impresora_ci6_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en", len(bpy.data.collections) - 1, "grupos", flush=True)
