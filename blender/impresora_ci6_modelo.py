"""
Modelo Blender limpio de la Impresora Flexografica de tambor central CHCI6-800J (6 colores).

Solo la maquina: sin materiales, sin animacion, sin piso, luces ni camaras.
Cada pieza tiene nombre descriptivo y esta agrupada por sistema.
Medidas aproximadas (m): ~7.2 de largo x 2.6 de ancho x ~3.9 de alto (con baranda). Eje largo en X:
torre de impresion (-X), tramo central con desbobinador y tablero, extremo de rebobinado y mando (+X).
El piso en z=0.

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


# Eje largo de la maquina en X. Los bastidores octogonales son placas en el plano XZ (y = +-FY).
FY = 0.95           # cara interior de los bastidores (+-Y)
FT = 0.32           # espesor de cada bastidor
TX0, TX1 = -3.45, -0.90   # torre de impresion
DX, DZ, DR = (TX0 + TX1) / 2, 1.30, 0.75   # tambor central (eje en Y)
CX0, CX1 = -3.65, 2.75    # cubierta superior corrida
CW = 1.30                 # semiancho de la cubierta
CZ, CH = 2.40, 0.40       # base y alto de la cubierta


def octagon(cx, cz, w, h, c):
    return [(cx - w / 2 + c, cz - h / 2), (cx + w / 2 - c, cz - h / 2), (cx + w / 2, cz - h / 2 + c),
            (cx + w / 2, cz + h / 2 - c), (cx + w / 2 - c, cz + h / 2), (cx - w / 2 + c, cz + h / 2),
            (cx - w / 2, cz + h / 2 - c), (cx - w / 2, cz - h / 2 + c)]


def plate_y(name, prof, y, t, holes=()):
    """Placa en el plano XZ (perfil (x, z)) con espesor en Y y ventanas (x, z, ancho, alto)."""
    n = len(prof)
    verts = [(x, y - t / 2, z) for x, z in prof] + [(x, y + t / 2, z) for x, z in prof]
    faces = [tuple(range(n)), tuple(range(n, 2 * n))[::-1]]
    for i in range(n):
        j = (i + 1) % n
        faces.append((j, i, n + i, n + j))
    ob = from_pydata(name, verts, faces, smooth=False)
    for (hx, hz, hw, hh) in holes:
        c = box("Corte_Ventana", (hw, t * 4, hh), (hx, y, hz))
        c.hide_render = c.hide_viewport = True
        md = ob.modifiers.new("Ventana", "BOOLEAN")
        md.object = c
        md.operation = "DIFFERENCE"
    return ob


# ===========================================================================
# 01 Torre de impresion: bastidores octogonales
# ===========================================================================
grupo("01_Torre_Bastidores_Octogonales")
L = TX1 - TX0
wins = [(DX - 0.62, 1.78, 0.70, 0.62), (DX + 0.62, 1.78, 0.70, 0.62), (DX - 0.62, 0.68, 0.70, 0.62),
        (DX + 0.62, 0.68, 0.70, 0.62)]
for sy, sn in ((-1, "Operador"), (1, "Transmision")):
    y = sy * (FY + FT / 2)
    plate_y(f"Bastidor_Octogonal_{sn}", octagon(DX, 1.22, L, 2.30, 0.48), y, FT, holes=wins)
    for (wx, wz, ww, wh) in wins:
        box(f"Ventana_Acrilico_{sn}", (ww - 0.02, 0.008, wh - 0.02), (wx, y, wz))
    yo = sy * (FY + FT + 0.006)
    for k, dx in enumerate((-0.17, 0.17)):
        box(f"Puerta_Central_{sn}", (0.32, 0.012, 1.95), (DX + dx, yo, 1.10))
    box(f"Franja_Central_Oscura_{sn}", (0.22, 0.014, 1.90), (DX, yo + sy * 0.002, 1.10))
    box(f"Manija_Puerta_{sn}", (0.03, 0.03, 0.18), (DX + 0.10, yo + sy * 0.02, 1.15))
    box(f"Zocalo_Bastidor_{sn}", (L - 0.70, FT + 0.04, 0.08), (DX, y, 0.04))

# ===========================================================================
# 02 Tambor central y 6 grupos de impresion
# ===========================================================================
grupo("02_Tambor_y_Grupos_de_Impresion")
cyl("Tambor_Central", DR, 2 * FY - 0.04, (DX, 0, DZ), axis="Y", verts=96)
cyl("Eje_Tambor_Central", 0.09, 2 * (FY + FT) + 0.10, (DX, 0, DZ), axis="Y", verts=24)
for k, ang in enumerate((150, 180, 210, 330, 0, 30), start=1):
    a = math.radians(ang)
    dx, dz = math.cos(a), math.sin(a)
    g = f"Grupo_Impresion_{k}"
    rot = (0, -math.atan2(dz, dx), 0)
    P = lambda r: (DX + dx * r, 0, DZ + dz * r)
    cyl(f"{g}_Cilindro_Portaclise", 0.10, 2 * FY - 0.20, P(DR + 0.10), axis="Y", verts=32)
    cyl(f"{g}_Rodillo_Anilox", 0.08, 2 * FY - 0.20, P(DR + 0.29), axis="Y", verts=32)
    box(f"{g}_Camara_Racla", (0.12, 2 * FY - 0.30, 0.12), P(DR + 0.45), rot=rot, bevel=0.01)
    box(f"{g}_Barra_Botonera", (0.06, 2 * FY - 0.40, 0.06), (P(DR + 0.52)[0], 0, P(DR + 0.52)[2] + 0.12))
    for sy in (-1, 1):
        q = P(DR + 0.25)
        box(f"{g}_Soporte_Lateral", (0.46, 0.14, 0.22), (q[0], sy * (FY - 0.09), q[2]), rot=rot, bevel=0.01)
        q2 = P(DR + 0.52)
        box(f"{g}_Bloque_Ajuste", (0.14, 0.12, 0.18), (q2[0], sy * (FY - 0.09), q2[2]), rot=rot, bevel=0.008)
        for j in range(2):
            cyl(f"{g}_Perilla_Ajuste", 0.025, 0.03, (q2[0], sy * (FY - 0.02), q2[2] + (j - 0.5) * 0.07),
                axis="Y", verts=12)
        cyl(f"{g}_Servomotor", 0.06, 0.18, (q2[0], sy * (FY - 0.25), q2[2] - 0.12), axis="Y", verts=16)
    curve_tube(f"{g}_Manguera_Tinta", [Vector((P(DR + 0.45)[0], -(FY - 0.25), P(DR + 0.45)[2])),
                                       Vector((P(DR + 0.70)[0], -(FY - 0.15), P(DR + 0.45)[2] - 0.40)),
                                       Vector((P(DR + 0.70)[0], -(FY - 0.10), 0.12))], 0.014)
for x in (-0.55, -0.25, 0.25, 0.55):
    cyl("Rodillo_Guia_Superior", 0.045, 2 * FY - 0.04, (DX + x, 0, DZ + DR + 0.32), axis="Y")
for k in range(3):
    box("Caja_Secado_Entre_Colores", (0.14, 2 * FY - 0.20, 0.10), (DX - 0.40 + k * 0.40, 0, DZ + DR + 0.20), bevel=0.01)

# ===========================================================================
# 03 Tramo central: tablero electrico, desbobinador, guias
# ===========================================================================
grupo("03_Tramo_Central")
box("Tablero_Electrico_Gris", (0.85, 0.45, 1.85), (0.10, CW - 0.40, 0.08 + 0.925), bevel=0.01)
for k in range(3):
    box("Medidor_Analogico", (0.10, 0.012, 0.10), (-0.10 + k * 0.18, CW - 0.63, 1.65))
box("Puerta_Tablero_Electrico", (0.80, 0.012, 1.10), (0.10, CW - 0.63, 0.75))
box("Manija_Tablero", (0.03, 0.03, 0.15), (0.40, CW - 0.645, 0.90))
plate_y("Bastidor_Desbobinador_Operador", [(0.65, 0.08), (1.55, 0.08), (1.55, 1.95), (0.65, 1.95)], -(FY + 0.05), 0.08,
        holes=[(1.10, 0.55, 0.45, 0.45), (1.10, 1.45, 0.45, 0.40)])
plate_y("Bastidor_Desbobinador_Trasero", [(0.65, 0.08), (1.55, 0.08), (1.55, 1.95), (0.65, 1.95)], FY + 0.05, 0.08)
cyl("Desbobinador_Bobina", 0.25, 0.85, (1.10, 0, 0.45), axis="Y", verts=64)
cyl("Desbobinador_Nucleo", 0.05, 0.90, (1.10, 0, 0.45), axis="Y", verts=24)
cyl("Desbobinador_Eje_Neumatico", 0.035, 2 * FY + 0.40, (1.10, 0, 0.45), axis="Y", verts=16)
box("Desbobinador_Freno", (0.18, 0.12, 0.18), (1.10, -(FY + 0.20), 0.45), bevel=0.01)
spiral_hose("Desbobinador_Manguera_Espiral_Naranja", (1.35, -(FY + 0.15), 0.95), turns=10, drop=0.35)
for z in (0.95, 1.35, 1.75):
    cyl("Desbobinador_Rodillo_Guia", 0.04, 2 * FY - 0.04, (0.85 + (0.25 if z == 1.35 else 0), 0, z), axis="Y")
box("Display_Velocidad_m_min", (0.40, 0.12, 0.20), (-0.55, -0.50, CZ - 0.12))
box("Escalon_Operador", (0.55, 0.40, 0.25), (-0.40, -0.10, 0.125), bevel=0.01)

# ===========================================================================
# 04 Extremo de rebobinado (+X) con lamina impresa
# ===========================================================================
grupo("04_Rebobinador")
RX = 2.20
for sy in (-1, 1):
    plate_y(f"Bastidor_Rebobinador_{'Operador' if sy < 0 else 'Trasero'}",
            [(1.70, 0.08), (2.65, 0.08), (2.65, 1.05), (2.30, 1.95), (1.70, 1.95)], sy * (FY + 0.05), 0.08,
            holes=[(2.15, 0.55, 0.40, 0.40)])
    cyl(f"Rueda_Freno_Rebobinador_{'Operador' if sy < 0 else 'Trasero'}", 0.13, 0.06, (RX, sy * (FY + 0.15), 0.50),
        axis="Y", verts=32)
cyl("Rebobinador_Bobina", 0.22, 0.85, (RX + 0.10, 0, 0.50), axis="Y", verts=64)
cyl("Rebobinador_Nucleo", 0.05, 0.90, (RX + 0.10, 0, 0.50), axis="Y", verts=24)
cyl("Rebobinador_Eje_Neumatico", 0.035, 2 * FY + 0.40, (RX + 0.10, 0, 0.50), axis="Y", verts=16)
for x, z in ((2.45, 1.75), (2.20, 1.35), (2.45, 0.95), (1.95, 1.60)):
    cyl("Rebobinador_Rodillo_Guia", 0.045, 2 * FY - 0.04, (x, 0, z), axis="Y")
box("Rebobinador_Display", (0.20, 0.012, 0.10), (2.00, -(FY + 0.10), 1.70))
spiral_hose("Rebobinador_Manguera_Espiral_Naranja", (2.55, -(FY + 0.15), 1.10), turns=10, drop=0.35)

# ===========================================================================
# 05 Cubierta superior corrida, plataforma, tunel de secado y baranda
# ===========================================================================
grupo("05_Cubierta_Plataforma_y_Secado")
prof = [(CX0 + 0.30, CZ), (CX1 - 0.30, CZ), (CX1, CZ + CH * 0.55), (CX1, CZ + CH), (CX0, CZ + CH), (CX0, CZ + CH * 0.55)]
n = len(prof)
verts = [(x, -CW, z) for x, z in prof] + [(x, CW, z) for x, z in prof]
faces = [tuple(range(n)), tuple(range(n, 2 * n))[::-1]]
for i in range(n):
    j = (i + 1) % n
    faces.append((j, i, n + i, n + j))
from_pydata("Cubierta_Superior_Gris", verts, faces, smooth=False)
for nm, x, rz in (("Texto_Modelo_Extremo_Torre", CX0 - 0.004, -math.pi / 2), ("Texto_Modelo_Extremo_Rebobinado", CX1 + 0.004, math.pi / 2)):
    cu = bpy.data.curves.new(nm, "FONT")
    cu.body = "CHCI6-800J"
    cu.size = 0.16
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = 0.002
    t_ = link(bpy.data.objects.new(nm, cu))
    t_.location = (x, 0.20 if rz < 0 else -0.20, CZ + CH * 0.78)
    t_.rotation_euler = (math.pi / 2, 0, rz)
zb = CZ + CH
box("Piso_Plataforma_Superior", (CX1 - CX0 - 0.02, 2 * CW - 0.02, 0.02), ((CX0 + CX1) / 2, 0, zb + 0.01))
box("Tunel_Secado_Blanco", (4.20, 1.00, 0.60), (-1.10, 0.15, zb + 0.30), bevel=0.02)
for k in range(5):
    box("Tapa_Inspeccion_Tunel", (0.70, 0.012, 0.40), (-2.90 + k * 0.85, -0.356, zb + 0.30))
for k, x in enumerate((-2.80, -0.40)):
    curve_tube("Ducto_Flexible_Rojo", [Vector((x, 0.65, zb + 0.45)), Vector((x + 0.30, 1.05, zb + 0.75)),
                                      Vector((x + 0.90, 1.10, zb + 0.55)), Vector((x + 1.20, 0.80, zb + 0.35))], 0.09)
cyl("Soplador_Extractor_Gris", 0.26, 0.24, (1.40, 0.55, zb + 0.35), axis="X", verts=32)
cyl("Motor_Soplador", 0.11, 0.28, (1.65, 0.55, zb + 0.35), axis="X", verts=24)
curve_tube("Ducto_Aluminio_Flexible", [Vector((1.40, 0.30, zb + 0.35)), Vector((1.40, -0.30, zb + 0.20)),
                                       Vector((1.40, -(CW + 0.10), CZ + 0.10)), Vector((1.40, -(CW + 0.10), 1.70))], 0.09)
box("Marco_Salida_Lamina", (0.10, 1.10, 0.55), (2.35, 0, zb + 0.28))
# baranda de acero inoxidable (abierta donde llega la escalera, extremo +X lado trasero)
rh = 1.0
pts = [(CX0 + 0.05, -CW + 0.05), (CX1 - 0.05, -CW + 0.05), (CX1 - 0.05, CW - 0.05), (CX0 + 0.05, CW - 0.05)]
for i in range(4):
    a, b = pts[i], pts[(i + 1) % 4]
    segs = [((a[0], a[1]), (b[0], 0.35)), ((b[0], 0.95), (b[0], b[1]))] if i == 1 else [(a, b)]
    for p1, p2 in segs:
        for z in (zb + rh, zb + 0.50):
            beam("Baranda_Inoxidable", (p1[0], p1[1], z), (p2[0], p2[1], z), 0.04, round_=True)
        Ls = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        nn = max(1, round(Ls / 1.0))
        for k in range(nn + 1):
            px = p1[0] + (p2[0] - p1[0]) * k / nn
            py_ = p1[1] + (p2[1] - p1[1]) * k / nn
            cyl("Parante_Baranda_Inoxidable", 0.02, rh, (px, py_, zb + rh / 2), verts=12)

# ===========================================================================
# 06 Escalera de acero inoxidable (extremo +X, lado trasero)
# ===========================================================================
grupo("06_Escalera_Inoxidable")
ly0, ly1 = 0.38, 0.92
bot = Vector((CX1 + 1.35, 0, 0.0))
top = Vector((CX1 - 0.10, 0, zb))
for y in (ly0, ly1):
    beam("Larguero_Escalera_Inoxidable", (bot.x, y, 0), (top.x, y, top.z), 0.05, round_=True)
    beam("Pasamano_Escalera_Inoxidable", (bot.x - 0.15, y, 0.95), (top.x + 0.10, y, top.z + 1.0), 0.04, round_=True)
    beam("Pasamano_Escalera_Inoxidable", (top.x + 0.10, y, top.z + 1.0), (top.x - 0.30, y, top.z + 1.0), 0.04, round_=True)
    box("Pie_Goma_Escalera", (0.14, 0.08, 0.04), (bot.x, y, 0.02))
for i in range(1, 11):
    q = bot.lerp(top, i / 11)
    box("Peldano_Inoxidable", (0.14, ly1 - ly0 - 0.04, 0.025), (q.x - 0.03, (ly0 + ly1) / 2, q.z), bevel=0.004)

# ===========================================================================
# 07 Mando: columna, equipo de temperatura y gabinete electrico con baliza
# ===========================================================================
grupo("07_Mando_y_Gabinetes")
mx, my = 1.95, -(FY + 0.35)
box("Columna_Mando_Gris", (0.60, 0.45, CZ - 0.05), (mx, my, (CZ - 0.05) / 2), bevel=0.01)
fy = my - 0.23
box("Pantalla_Grande_HMI", (0.34, 0.012, 0.26), (mx, fy, 1.90))
box("Panel_Mandos_Inoxidable", (0.36, 0.012, 0.50), (mx, fy, 1.25))
box("Pantalla_HMI_Panel", (0.18, 0.014, 0.12), (mx, fy - 0.002, 1.33))
for k in range(2):
    box("Controlador_Temperatura", (0.09, 0.014, 0.06), (mx - 0.07 + k * 0.14, fy - 0.002, 1.45))
for r in range(2):
    for c in range(4):
        cyl("Pulsador_Mando", 0.018, 0.02, (mx - 0.11 + c * 0.07, fy - 0.01, 1.13 - r * 0.07), axis="Y", verts=16)
cyl("Baliza_Roja_Giratoria", 0.055, 0.10, (mx - 0.36, my + 0.05, 1.78), axis="Y", verts=24)
tx, ty = 2.75, -(FY + 0.45)
box("Equipo_Control_Temperatura", (0.60, 0.55, 1.10), (tx, ty, 0.05 + 0.55), bevel=0.012)
box("Pantalla_Equipo_Temperatura", (0.17, 0.012, 0.12), (tx - 0.08, ty - 0.28, 0.95))
cyl("Paro_Emergencia_Equipo", 0.03, 0.03, (tx + 0.20, ty - 0.28, 0.70), axis="Y", verts=24)
cyl("Baliza_Equipo_Poste", 0.012, 0.25, (tx + 0.20, ty + 0.15, 1.27), verts=12)
for k, nm in enumerate(("Baliza_Equipo_Verde", "Baliza_Equipo_Ambar", "Baliza_Equipo_Roja")):
    cyl(nm, 0.03, 0.06, (tx + 0.20, ty + 0.15, 1.42 + k * 0.062), verts=24)
gx, gy = 1.25, -(FY + 0.45)
box("Gabinete_Electrico_Blanco", (0.60, 0.55, 1.05), (gx, gy, 0.08 + 0.525), bevel=0.012)
for j in range(6):
    box("Rejilla_Gabinete", (0.22, 0.012, 0.02), (gx + 0.12, gy - 0.281, 0.80 + j * 0.035))
cyl("Baliza_Gabinete_Poste", 0.012, 0.25, (gx - 0.20, gy + 0.10, 1.25), verts=12)
for k, nm in enumerate(("Baliza_Gabinete_Verde", "Baliza_Gabinete_Ambar", "Baliza_Gabinete_Roja")):
    cyl(nm, 0.03, 0.06, (gx - 0.20, gy + 0.10, 1.40 + k * 0.062), verts=24)

# ===========================================================================
# 08 Polipasto con viga roja (sobre la maquina)
# ===========================================================================
grupo("08_Polipasto_Viga_Roja")
box("Viga_Roja_Polipasto", (6.80, 0.16, 0.22), (-0.40, -CW - 0.25, 3.90), bevel=0.005)
for x in (-3.60, 2.70):
    beam("Puntal_Viga_Roja", (x, -CW - 0.25, 3.80), (x, CW + 0.30, 3.30), 0.14, t2=0.18)
    box("Mensula_Muro", (0.30, 0.10, 0.35), (x, CW + 0.35, 3.30))
box("Polipasto_Electrico_Naranja", (0.30, 0.22, 0.38), (1.10, -CW - 0.25, 3.55), bevel=0.04)
box("Carro_Polipasto", (0.30, 0.24, 0.10), (1.10, -CW - 0.25, 3.76))
curve_tube("Cadena_Polipasto", [Vector((1.10, -CW - 0.25, 3.36)), Vector((1.10, -CW - 0.25, 1.40))], 0.008)
box("Gancho_Polipasto", (0.06, 0.03, 0.12), (1.10, -CW - 0.25, 1.33))
box("Botonera_Colgante", (0.08, 0.06, 0.22), (1.25, -CW - 0.25, 1.30), bevel=0.01)

# ===========================================================================
# 09 Bombas de tinta (6) junto a la torre
# ===========================================================================
grupo("09_Bombas_de_Tinta")
for k in range(6):
    x = TX0 + 0.10 + k * 0.40
    y = -(FY + FT + 0.55)
    cyl("Balde_Tinta", 0.15, 0.30, (x, y, 0.15), verts=24)
    cyl("Bomba_Diafragma", 0.05, 0.16, (x, y + 0.05, 0.42), axis="Y", verts=16)
    beam("Soporte_Bomba", (x, y + 0.05, 0.30), (x, y + 0.05, 0.40), 0.02, round_=True)
    curve_tube("Manguera_Bomba", [Vector((x, y + 0.13, 0.42)), Vector((x + 0.05, y + 0.35, 0.30)),
                                  Vector((x + 0.05, -(FY + FT), 0.40))], 0.010)

# ===========================================================================
# 10 Film impreso: desbobinador -> tambor -> tunel -> rebobinador
# ===========================================================================
grupo("10_Film_Impreso")
path = [(1.10, 0.70), (0.85, 0.99), (1.10, 1.39), (0.85, 1.79), (DX + 0.55, DZ + DR + 0.37),
        (DX + 0.40, DZ + 0.62), (DX, DZ + DR + 0.01), (DX - 0.40, DZ + 0.62), (DX - 0.55, DZ + DR + 0.37),
        (DX - 0.20, CZ - 0.05), (1.95, CZ - 0.05), (1.95, 1.65), (2.45, 1.79), (2.20, 1.39), (2.45, 0.99),
        (RX + 0.10, 0.72)]
verts, faces = [], []
for (x, z) in path:
    verts += [(x, -0.40, z), (x, 0.40, z)]
for i in range(len(path) - 1):
    faces.append((2 * i, 2 * i + 2, 2 * i + 3, 2 * i + 1))
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
