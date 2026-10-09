"""
Modelo Blender limpio de la Extrusora Nº 4 (linea de pelicula soplada, la mas grande).

Solo la maquina: sin materiales/colores, sin animacion, sin galpon, piso,
luces ni camaras. Cada pieza tiene un nombre descriptivo y esta agrupada en
colecciones por sistema (torre, plataforma, extrusora, tablero, etc.).

Uso:
    python3 blender/extrusora4_modelo.py           # con bpy de PyPI
    blender -b -P blender/extrusora4_modelo.py     # con Blender

Guarda blender/extrusora4_modelo.blend.
"""
import math
import os
import sys

import bpy
import bmesh
from mathutils import Vector, Matrix


# ---------------------------------------------------------------------------
# Escena limpia
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection
ROOT = bpy.data.collections.new("Extrusora_N4")
col.children.link(ROOT)


class _SinMaterial(dict):
    """Se conserva la firma de las funciones pero no se asigna ningun material."""
    def __missing__(self, key):
        return None


M = _SinMaterial()
CUR = [None]   # coleccion activa


def grupo(nombre, padre=None):
    """Crea (o reutiliza) una coleccion y la deja activa para las piezas nuevas."""
    c = bpy.data.collections.get(nombre)
    if c is None:
        c = bpy.data.collections.new(nombre)
        (padre or ROOT).children.link(c)
    CUR[0] = c
    return c


# ---------------------------------------------------------------------------
# Utilidades de geometria
# ---------------------------------------------------------------------------
def link(obj, mat):
    (CUR[0] or col).objects.link(obj)
    return obj


def box(name, size, loc, mat, bevel=0.0, rot=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=Vector(size), verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    if rot:
        ob.rotation_euler = rot
    link(ob, mat)
    if bevel > 0:
        md = ob.modifiers.new("Bevel", "BEVEL")
        md.width = bevel
        md.segments = 2
        md.limit_method = "ANGLE"
    return ob


def cyl(name, r, depth, loc, mat, axis="Z", verts=48, smooth=True, bevel=0.0, r2=None):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=verts,
                          radius1=r, radius2=r if r2 is None else r2, depth=depth)
    if axis == "X":
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, "Y"))
    elif axis == "Y":
        bmesh.ops.rotate(bm, verts=bm.verts, matrix=Matrix.Rotation(math.pi / 2, 3, "X"))
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    ob.location = loc
    link(ob, mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = len(p.vertices) == 4
    if bevel > 0:
        md = ob.modifiers.new("Bevel", "BEVEL")
        md.width = bevel
        md.segments = 2
        md.limit_method = "ANGLE"
    return ob


def beam(name, p1, p2, t, mat, round_=False, t2=None):
    """Perfil cuadrado (o tubo redondo) entre dos puntos."""
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    L = d.length
    if round_:
        ob = cyl(name, t / 2, L, (0, 0, 0), mat, verts=16)
    else:
        ob = box(name, (t, t if t2 is None else t2, L), (0, 0, 0), mat)
    ob.rotation_mode = "QUATERNION"
    ob.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(d.normalized())
    ob.location = (p1 + p2) / 2
    return ob


def text(name, body, size, loc, mat, rot=(math.pi / 2, 0, 0), extrude=0.001, align="CENTER"):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.align_x = align
    cu.align_y = "CENTER"
    try:
        cu.font = bpy.data.fonts.load(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", check_existing=True)
    except Exception:
        pass
    ob = bpy.data.objects.new(name, cu)
    ob.location = loc
    ob.rotation_euler = rot
    link(ob, mat)
    return ob


def curve_tube(name, pts, radius, mat, res=16):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    cu.resolution_u = res
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    cu.use_fill_caps = True
    ob = bpy.data.objects.new(name, cu)
    link(ob, mat)
    return ob


def mesh_from(name, verts, faces, mat, smooth=True, solidify=0.0):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    link(ob, mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    if solidify:
        md = ob.modifiers.new("Solid", "SOLIDIFY")
        md.thickness = solidify
    return ob


# ---------------------------------------------------------------------------
# Dimensiones principales (metros). Frente de la maquina hacia -Y.
# ---------------------------------------------------------------------------
# Mismas referencias de planta que las Nº 1-3 (piso en z=0, metros).
PZ = 3.30            # plataforma principal
PX, PY = 1.45, 1.20  # semi-dimensiones de la plataforma principal
CX, CY = 1.30, 1.05  # columnas principales
DIE_Z = 1.35         # parte superior del cabezal / anillo de aire
TZ = 6.40            # plataforma superior (nivel del arrastre)
NIP_Z = TZ + 0.55    # rodillos de arrastre (nip)
CAN_Z0 = PZ + 2.05   # inicio de la canasta colapsadora
R_BUB = 0.42         # burbuja mas ancha
WY0, WY1 = -2.30, -6.60   # embobinadora doble (4.3 m, mas larga que la Nº 3)
LAYFLAT = math.pi * R_BUB / 2  # semi-ancho de la lamina aplanada


def stair(bot, top, width, tag=""):
    """Escalera metalica delgada: largueros de platina, peldanos planos
    (reposapies) y pasamanos de tubo a ambos lados."""
    bot, top = Vector(bot), Vector(top)
    run = Vector((top.x - bot.x, top.y - bot.y, 0))
    d = run.normalized()
    side = Vector((-d.y, d.x, 0)) * (width / 2)
    rise = top.z - bot.z
    for sg in (-1, 1):
        o = side * sg
        beam(f"Larguero{tag}", bot + o, top + o, 0.012, M["negro"], t2=0.13)
        hb = bot + o + Vector((0, 0, 0.90))
        ht = top + o + Vector((0, 0, 1.00))
        beam(f"Pasamano{tag}", hb, ht, 0.032, M["negro"], round_=True)
        beam(f"Pasamano{tag}", ht, ht + d * 0.35, 0.032, M["negro"], round_=True)
        for f in (0.06, 0.5, 0.94):
            p_ = bot.lerp(top, f) + o
            beam(f"ParantePasamano{tag}", p_, p_ + Vector((0, 0, 0.92 + 0.08 * f)), 0.025, M["negro"], round_=True)
    n = max(4, round(rise / 0.25))
    ang = math.atan2(d.y, d.x)
    for i in range(1, n):
        p_ = bot.lerp(top, i / n)
        # peldano plano horizontal (chapa estriada) con pestana delantera
        st = box(f"Peldano{tag}", (0.20, width - 0.02, 0.012), (0, 0, 0), M["negro"])
        st.location = p_ + d * 0.03
        st.rotation_euler = (0, 0, ang)
        lip = box(f"PestanaPeldano{tag}", (0.012, width - 0.02, 0.04), (0, 0, 0), M["negro"])
        lip.location = p_ + d * (0.03 - 0.10) + Vector((0, 0, -0.014))
        lip.rotation_euler = (0, 0, ang)
    for sg in (-1, 1):
        box(f"Pie{tag}", (0.10, 0.06, 0.012), bot + side * sg + Vector((0, 0, 0.006)), M["negro"])


# ---------------------------------------------------------------------------
# Torre: columnas, plataforma, barandas
# ---------------------------------------------------------------------------
def tower():
    grupo("01_Estructura_Torre")
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * CX, sy * CY
            box("Columna", (0.22, 0.22, PZ - 0.14), (x, y, (PZ - 0.14) / 2), M["blanco"], 0.006)
            box("PlacaBase", (0.45, 0.45, 0.025), (x, y, 0.0125), M["blanco"], 0.004)
            for k in range(4):
                cyl("PernoAnclaje", 0.018, 0.04, (x + (k % 2 - 0.5) * 0.32, y + (k // 2 - 0.5) * 0.32, 0.045),
                    M["acero"], verts=6)
    for sy in (-1, 1):
        box("VigaX", (2 * PX, 0.18, 0.32), (0, sy * CY, PZ - 0.30), M["blanco"], 0.004)
    for sx in (-1, 1):
        box("VigaY", (0.18, 2 * PY, 0.32), (sx * CX, 0, PZ - 0.30), M["blanco"], 0.004)
    for sx in (-1, 1):
        box("VigaInterior", (0.14, 2 * CY, 0.24), (sx * 0.85, 0, PZ - 0.26), M["blanco"], 0.004)
    for x in (-0.45, 0.45):
        box("Vigueta", (0.08, 2 * CY, 0.14), (x, 0, PZ - 0.21), M["blanco"])
    # marco intermedio a 2.35 m y riostras
    FZ = 2.35
    for sy in (-1, 1):
        box("VigaMarco", (2 * CX - 0.2, 0.14, 0.14), (0, sy * CY, FZ), M["blanco"], 0.004)
    for sx in (-1, 1):
        box("VigaMarco", (0.14, 2 * CY - 0.2, 0.14), (sx * CX, 0, FZ), M["blanco"], 0.004)
    for sx in (-1, 1):
        for sy in (-1, 1):
            beam("Riostra", (sx * CX, sy * CY, FZ - 0.55), (sx * (CX - 0.55), sy * CY, FZ - 0.07), 0.09, M["blanco"])
            beam("Riostra", (sx * CX, sy * CY, FZ - 0.55), (sx * CX, sy * (CY - 0.55), FZ - 0.07), 0.09, M["blanco"])

    grupo("02_Plataforma")
    H = 0.60
    t = 0.12
    zc = PZ - t / 2
    box("Plataforma", (2 * PX, PY - H, t), (0, -(PY + H) / 2, zc), M["blanco"], 0.008)
    box("Plataforma", (2 * PX, PY - H, t), (0, (PY + H) / 2, zc), M["blanco"], 0.008)
    box("Plataforma", (PX - H, 2 * H, t), (-(PX + H) / 2, 0, zc), M["blanco"], 0.008)
    box("Plataforma", (PX - H, 2 * H, t), ((PX + H) / 2, 0, zc), M["blanco"], 0.008)
    # descanso de la escalera principal (derecha)
    LX0, LX1, LY0, LY1 = PX, PX + 0.80, -0.30, 0.90
    box("Descanso", (LX1 - LX0, LY1 - LY0, t), ((LX0 + LX1) / 2, (LY0 + LY1) / 2, zc), M["blanco"], 0.006)
    box("PosteDescanso", (0.12, 0.12, PZ - 0.12), (LX1 - 0.07, LY1 - 0.07, (PZ - 0.12) / 2), M["blanco"], 0.004)
    box("PosteDescanso", (0.12, 0.12, PZ - 0.12), (LX1 - 0.07, LY0 + 0.07, (PZ - 0.12) / 2), M["blanco"], 0.004)
    box("PlacaBase", (0.26, 0.26, 0.02), (LX1 - 0.07, LY1 - 0.07, 0.01), M["blanco"])
    box("PlacaBase", (0.26, 0.26, 0.02), (LX1 - 0.07, LY0 + 0.07, 0.01), M["blanco"])
    # plataforma en voladizo (izquierda) para el equipo de enfriamiento
    VX0, VX1, VY0, VY1 = -PX - 1.35, -PX, -0.75, 0.95
    box("PlataformaEnfriador", (VX1 - VX0, VY1 - VY0, t), ((VX0 + VX1) / 2, (VY0 + VY1) / 2, zc), M["blanco"], 0.006)
    for y in (VY0 + 0.06, VY1 - 0.06):
        box("VigaVoladizo", (VX1 - VX0, 0.12, 0.20), ((VX0 + VX1) / 2, y, PZ - 0.22), M["blanco"], 0.004)
        beam("PuntalVoladizo", (-CX, y, 2.0), (VX0 + 0.25, y, PZ - 0.30), 0.10, M["blanco"])
    box("ColumnaVoladizo", (0.14, 0.14, PZ - 0.12), (VX0 + 0.08, VY1 - 0.08, (PZ - 0.12) / 2), M["blanco"], 0.004)
    box("PlacaBase", (0.30, 0.30, 0.02), (VX0 + 0.08, VY1 - 0.08, 0.01), M["blanco"])

    grupo("03_Barandas")
    rh = 1.05
    tt = 0.04

    def rail_segment(p1, p2):
        p1, p2 = Vector(p1), Vector(p2)
        for z in (PZ + rh, PZ + 0.55):
            beam("Baranda", (p1.x, p1.y, z), (p2.x, p2.y, z), tt, M["negro"])
        n = max(1, round((p2 - p1).length / 0.6))
        for i in range(n + 1):
            p = p1.lerp(p2, i / n)
            box("Parante", (tt, tt, rh), (p.x, p.y, PZ + rh / 2), M["negro"])

    ex, ey = PX - 0.02, PY - 0.02
    rail_segment((-ex, -ey, 0), (ex, -ey, 0))
    rail_segment((-ex, ey, 0), (ex, ey, 0))
    rail_segment((-ex, -ey, 0), (-ex, VY0, 0))
    rail_segment((-ex, VY1, 0), (-ex, ey, 0))
    rail_segment((ex, -ey, 0), (ex, LY0, 0))
    rail_segment((ex, LY1, 0), (ex, ey, 0))
    # descanso
    rail_segment((LX1 - 0.02, LY0 + 0.02, 0), (LX1 - 0.02, LY1 - 0.02, 0))
    rail_segment((ex, LY1 - 0.02, 0), (LX1 - 0.02, LY1 - 0.02, 0))
    # voladizo del enfriador
    rail_segment((VX0 + 0.02, VY0 + 0.02, 0), (VX0 + 0.02, VY1 - 0.02, 0))
    rail_segment((VX0 + 0.02, VY0 + 0.02, 0), (-ex, VY0 + 0.02, 0))
    rail_segment((VX0 + 0.02, VY1 - 0.02, 0), (-ex, VY1 - 0.02, 0))

    grupo("03b_Enfriador_de_Aire")
    # equipo de enfriamiento del aire (chiller) sobre el voladizo
    ux, uy, uw, ud, uh = (VX0 + VX1) / 2, (VY0 + VY1) / 2, 1.05, 1.30, 1.60
    box("Enfriador", (uw, ud, uh), (ux, uy, PZ + uh / 2), M["blanco"], 0.01)
    for sz in (0.05, uh - 0.05):
        box("MarcoEnfriador", (uw + 0.02, ud + 0.02, 0.06), (ux, uy, PZ + sz), M["azul"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("MarcoEnfriador", (0.05, 0.05, uh), (ux + sx * uw / 2, uy + sy * ud / 2, PZ + uh / 2), M["azul"])
    for sy in (-0.3, 0.3):
        box("RejillaEnfriador", (0.01, 0.5, 0.55), (ux + uw / 2 + 0.006, uy + sy, PZ + 1.15), M["gris_oscuro"])
        box("PanelFiltro", (0.01, 0.5, 0.55), (ux + uw / 2 + 0.006, uy + sy, PZ + 0.50), M["gris_oscuro"])
    box("PantallaEnfriador", (0.18, 0.01, 0.12), (ux + 0.25, uy - ud / 2 - 0.006, PZ + 1.30), M["negro"])
    # ducto blanco de aire frio que baja hasta el anillo
    curve_tube("DuctoAireFrio", [Vector((ux + 0.30, uy - 0.30, PZ - 0.02)), Vector((ux + 0.32, uy - 0.30, 2.2)),
                                 Vector((-0.95, -0.40, 1.85)), Vector((-0.45, -0.25, DIE_Z + 0.16))], 0.08, M["blanco"])


# ---------------------------------------------------------------------------
# Torre superior: marco, canasta colapsadora de madera, rodillos nip, motor
# ---------------------------------------------------------------------------
def upper_tower():
    grupo("05_Torre_Superior_Marco")
    fx, fy = 0.85, 0.62
    top = NIP_Z + 0.40
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("ColSup", (0.08, 0.08, top - PZ), (sx * fx, sy * fy, (top + PZ) / 2), M["blanco"], 0.004)
    for z in (PZ + 1.30, TZ - 0.10, top - 0.04):
        for sy in (-1, 1):
            box("TravSupX", (2 * fx + 0.08, 0.08, 0.08), (0, sy * fy, z), M["blanco"], 0.004)
        for sx in (-1, 1):
            box("TravSupY", (0.08, 2 * fy, 0.08), (sx * fx, 0, z), M["blanco"], 0.004)
    # chapas laterales del cabezal de arrastre
    for sx in (-1, 1):
        box("ChapaNip", (0.025, 2 * fy + 0.1, 0.42), (sx * (fx + 0.06), 0, NIP_Z + 0.02), M["blanco"], 0.004)
    grupo("06_Rodillos_Arrastre_Nip")
    # rodillos nip: uno cromado y uno de goma
    cyl("NipCromo", 0.085, 2 * fx + 0.1, (0, -0.088, NIP_Z), M["cromo"], axis="X")
    cyl("NipGoma", 0.085, 2 * fx - 0.05, (0, 0.088, NIP_Z), M["goma"], axis="X")
    for sx in (-1, 1):
        cyl("EjeNip", 0.03, 0.25, (sx * (fx + 0.06), -0.088, NIP_Z), M["acero"], axis="X")
        cyl("EjeNip", 0.03, 0.25, (sx * (fx + 0.06), 0.088, NIP_Z), M["acero"], axis="X")
        # cilindros neumaticos de presion
        cyl("Neumatico", 0.035, 0.28, (sx * (fx + 0.06), 0.22, NIP_Z + 0.36), M["aluminio"])
        cyl("Vastago", 0.01, 0.12, (sx * (fx + 0.06), 0.22, NIP_Z + 0.16), M["cromo"])
    # rodillo de retorno arriba-adelante
    cyl("RodilloRetorno", 0.05, 2 * fx, (0, -0.42, NIP_Z + 0.12), M["acero"], axis="X")
    grupo("07_Motorreductor_Nip")
    # Motorreductor: caja azul + motor plateado vertical
    mx = -fx - 0.06
    box("Reductor", (0.2, 0.22, 0.22), (mx - 0.13, -0.088, NIP_Z), M["azul"], 0.015)
    cyl("Brida", 0.11, 0.04, (mx - 0.13, -0.088, NIP_Z + 0.13), M["azul"])
    cyl("Motor", 0.10, 0.36, (mx - 0.13, -0.088, NIP_Z + 0.33), M["aluminio"], bevel=0.01)
    for k in range(12):
        a = k * math.tau / 12
        box("Aleta", (0.012, 0.03, 0.3),
            (mx - 0.13 + math.cos(a) * 0.105, -0.088 + math.sin(a) * 0.105, NIP_Z + 0.33),
            M["aluminio"], rot=(0, 0, a))
    cyl("TapaVentilador", 0.10, 0.06, (mx - 0.13, -0.088, NIP_Z + 0.54), M["negro"], bevel=0.01)
    box("CajaBornes", (0.08, 0.1, 0.08), (mx - 0.02, -0.088, NIP_Z + 0.36), M["aluminio"], 0.005)

    grupo("05c_Nivel_Superior")
    # columnas exteriores del segundo nivel y vigas
    ox, oy = PX - 0.07, PY - 0.07
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("ColumnaNivel2", (0.12, 0.12, TZ - PZ), (sx * ox, sy * oy, (TZ + PZ) / 2), M["blanco"], 0.004)
    for z in (PZ + 1.30, TZ - 0.12):
        for sy in (-1, 1):
            box("VigaNivel2", (2 * ox, 0.12, 0.14), (0, sy * oy, z), M["blanco"], 0.004)
        for sx in (-1, 1):
            box("VigaNivel2", (0.12, 2 * oy, 0.14), (sx * ox, 0, z), M["blanco"], 0.004)
    # plataforma superior con hueco central (burbuja) y hueco de escalera (derecha)
    t = 0.08
    zc = TZ - t / 2
    HX, HY = 0.62, 0.50
    SX0, SY0 = 0.90, -0.25          # hueco de escalera: x>SX0, y>SY0
    for (x0, x1, y0, y1) in [(-PX, PX, -PY, -HY), (-PX, SX0, HY, PY), (-PX, -HX, -HY, HY),
                             (HX, SX0, -HY, HY), (SX0, PX, -HY, SY0)]:
        box("PlataformaSup", (x1 - x0, y1 - y0, t), ((x0 + x1) / 2, (y0 + y1) / 2, zc), M["blanco"], 0.005)
    rh = 1.05

    def rail(p1, p2):
        p1, p2 = Vector(p1), Vector(p2)
        for z in (TZ + rh, TZ + 0.55):
            beam("BarandaSup", (p1.x, p1.y, z), (p2.x, p2.y, z), 0.04, M["negro"])
        n = max(1, round((p2 - p1).length / 0.6))
        for k in range(n + 1):
            p = p1.lerp(p2, k / n)
            box("ParanteSup", (0.04, 0.04, rh), (p.x, p.y, TZ + rh / 2), M["negro"])

    ex, ey = PX - 0.02, PY - 0.02
    rail((-ex, -ey, 0), (ex, -ey, 0))
    rail((-ex, ey, 0), (SX0, ey, 0))
    rail((-ex, -ey, 0), (-ex, ey, 0))
    rail((ex, -ey, 0), (ex, SY0, 0))
    rail((SX0, SY0 + 0.6, 0), (SX0, ey, 0))      # protege el borde del hueco de escalera
    # escalera metalica de la plataforma principal a la superior
    stair((1.11, 1.10, PZ), (1.11, -0.20, TZ), 0.36, tag="Sup")

    grupo("05d_Tablero_LED")
    # tablero de LEDs rojos (velocidad, espesor, kg/h, temperatura...) arriba a la derecha
    bx_, by_, bz_ = 0.70, -PY - 0.06, TZ + 1.45
    box("TableroLED", (1.10, 0.08, 0.60), (bx_, by_, bz_), M["negro"], 0.006)
    for k in range(5):
        box("FilaLED", (0.55, 0.01, 0.07), (bx_ + 0.20, by_ - 0.045, bz_ + 0.22 - k * 0.11), M["rojo_led"])
        box("EtiquetaLED", (0.30, 0.01, 0.06), (bx_ - 0.32, by_ - 0.045, bz_ + 0.22 - k * 0.11), M["blanco"])
    for sx in (-1, 1):
        box("SoporteLED", (0.05, 0.05, 0.75), (bx_ + sx * 0.45, by_ + 0.05, TZ + 0.80), M["negro"])

    grupo("04b_Letrero_Nivel_Superior")
    sx_, sz_ = -1.20, TZ - 0.30
    box("Letrero1", (0.22, 0.008, 0.30), (sx_, -PY - 0.01, sz_), M["blanco"], 0.002)
    text("TxtExtrusora", "EXTRUSORA", 0.032, (sx_, -PY - 0.016, sz_ + 0.11), M["negro_mate"])
    text("TxtN", "Nº", 0.03, (sx_ - 0.07, -PY - 0.016, sz_ - 0.01), M["negro_mate"])
    text("Txt1", "4", 0.17, (sx_ + 0.02, -PY - 0.016, sz_ - 0.03), M["negro_mate"])

    grupo("05e_Calibrador_Burbuja")
    # calibrador azul: marco horizontal con rodillos verticales que tocan la burbuja
    cz = PZ + 1.45
    for sy in (-1, 1):
        beam("CalibradorViga", (-fx, sy * (R_BUB + 0.10), cz), (fx, sy * (R_BUB + 0.10), cz), 0.06, M["azul"])
        for k in range(6):
            x = -0.40 + k * 0.16
            cyl("CalibradorRodillo", 0.025, 0.18, (x, sy * (R_BUB + 0.035), cz), M["negro"], verts=16)
    for sx in (-1, 1):
        beam("CalibradorBrazo", (sx * fx, -(R_BUB + 0.10), cz), (sx * fx, R_BUB + 0.10, cz), 0.05, M["azul"])

    grupo("08_Canasta_Colapsadora")
    # Canasta colapsadora (dos planos de listones de madera en V)
    z0, z1 = CAN_Z0, NIP_Z - 0.16
    n = 15
    for side in (-1, 1):
        for i in range(n):
            t = i / (n - 1)
            z = z0 + (z1 - z0) * t
            y = side * (R_BUB * (1 - t) + 0.10 * (1 - t) + 0.09)
            w = 2 * (R_BUB + (LAYFLAT - R_BUB) * t) + 0.25
            box("Liston", (w, 0.025, 0.07), (0, y, z), M["madera"], 0.004)
        # largueros inclinados
        for sx in (-1, 1):
            beam("Larguero", (sx * 0.55, side * (R_BUB + 0.2), z0 - 0.05),
                 (sx * 0.55, side * 0.10, z1 + 0.05), 0.045, M["blanco"])
    # guias laterales (tablas laterales)
    for sx in (-1, 1):
        beam("GuiaLat", (sx * 0.6, -0.15, z0), (sx * 0.6, -0.15, z1), 0.03, M["madera"])
        beam("GuiaLat", (sx * 0.6, 0.15, z0), (sx * 0.6, 0.15, z1), 0.03, M["madera"])
    grupo("09_Anillo_Calibrador_Iris")
    # anillo de calibracion (iris) sobre la plataforma
    ring = cyl("Iris", R_BUB + 0.06, 0.05, (0, 0, PZ + 0.35), M["aluminio"], verts=64)
    hole = cyl("IrisHueco", R_BUB + 0.012, 0.2, (0, 0, PZ + 0.35), None, verts=64)
    md = ring.modifiers.new("Hueco", "BOOLEAN")
    md.object = hole
    hole.hide_render = hole.hide_viewport = True
    for k in range(4):
        a = k * math.pi / 2 + math.pi / 4
        beam("SoporteIris", (math.cos(a) * (R_BUB + 0.06), math.sin(a) * (R_BUB + 0.06), PZ + 0.35),
             (math.cos(a) * 0.75, math.sin(a) * 0.55, PZ + 0.35), 0.03, M["aluminio"])


# ---------------------------------------------------------------------------
# Burbuja de film y recorrido de la lamina
# ---------------------------------------------------------------------------
def bubble():
    grupo("10_Pelicula_Burbuja_y_Lamina")
    seg = 96
    prof = []  # (z, a, b): elipse de semiejes a (x) y b (y)
    nz = 70
    z_frost, z_col0 = DIE_Z + 1.00, CAN_Z0
    for i in range(nz + 1):
        z = DIE_Z + 0.01 + (NIP_Z - DIE_Z - 0.01) * i / nz
        if z < z_frost:
            t = (z - DIE_Z) / (z_frost - DIE_Z)
            s = 3 * t * t - 2 * t * t * t
            r = 0.17 + (R_BUB - 0.17) * s
            a = b = r
        elif z < z_col0:
            a = b = R_BUB
        else:
            t = (z - z_col0) / (NIP_Z - z_col0)
            s = t ** 1.15
            a = R_BUB + (LAYFLAT - R_BUB) * s
            b = max(0.004, R_BUB * (1 - s))
        prof.append((z, a, b))
    verts, faces = [], []
    for (z, a, b) in prof:
        for k in range(seg):
            th = k * math.tau / seg
            verts.append((a * math.cos(th), b * math.sin(th), z))
    for i in range(nz):
        for k in range(seg):
            k2 = (k + 1) % seg
            faces.append((i * seg + k, i * seg + k2, (i + 1) * seg + k2, (i + 1) * seg + k))
    mesh_from("Burbuja", verts, faces, M["film"])

    # Lamina aplanada: nip -> rodillo de retorno -> baja por el frente ->
    # rodillo bajo la plataforma -> soporte guia -> embobinadora
    w = LAYFLAT
    YS = WY0 - 1.30   # punto donde se separan las dos hojas
    path = [
        (0.0, NIP_Z + 0.08),
        (-0.30, NIP_Z + 0.17),
        (-0.47, NIP_Z + 0.10),
        (-0.50, PZ + 0.40),
        (-0.52, PZ - 0.32),
        (-0.62, PZ - 0.42),
        (-0.80, 2.48),
        (WY0 - 0.10, 2.44),
        (WY0 - 0.22, 2.12),
        (WY0 - 0.45, 1.90),
        (WY0 - 0.70, 1.72),
        (WY0 - 1.00, 1.47),
        (YS, 1.27),
    ]
    ramas = [("LaminaEstacion1", [(YS, 1.27), (YS - 0.30, 1.10), (-4.30, 1.13), (-4.52, 1.22)]),
             ("LaminaEstacion2", [(YS, 1.27), (YS - 0.25, 1.62), (-4.95, 1.76), (-5.10, 1.70),
                                  (-5.45, 1.26), (-5.80, 1.13), (-6.02, 1.22)])]
    verts, faces = [], []
    for (y, z) in path:
        verts += [(-w, y, z), (w, y, z)]
    for i in range(len(path) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    mesh_from("Lamina", verts, faces, M["film_doble"], smooth=True)
    for nombre, pth in ramas:
        vv, ff = [], []
        for (y, z) in pth:
            vv += [(-w, y, z), (w, y, z)]
        for i in range(len(pth) - 1):
            ff.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
        mesh_from(nombre, vv, ff, M["film"], smooth=True)
    grupo("11_Rodillo_Bajo_Plataforma")
    # rodillo guia bajo la plataforma
    cyl("RodilloPlataforma", 0.05, 2 * 0.62, (0, -0.56, PZ - 0.37), M["acero"], axis="X")
    for sx in (-1, 1):
        box("SoporteRodillo", (0.03, 0.12, 0.22), (sx * 0.64, -0.56, PZ - 0.26), M["blanco"])


# ---------------------------------------------------------------------------
# Extrusora (planta baja): cabezal, anillo de aire, husillo, tolva, soplador
# ---------------------------------------------------------------------------
def extruder():
    grupo("12_Cabezal_y_Anillo_de_Aire")
    box("PedestalCabezal", (0.80, 0.80, 0.45), (0, 0, 0.225), M["negro"], 0.02)
    cyl("BaseCabezal", 0.28, 0.25, (0, 0, 0.57), M["negro"], bevel=0.01)
    cyl("Cabezal", 0.30, 0.50, (0, 0, DIE_Z - 0.35), M["acero"], bevel=0.01)
    for k in range(9):
        cyl("ResistenciaCabezal", 0.335, 0.025, (0, 0, DIE_Z - 0.56 + k * 0.055), M["aluminio"], bevel=0.003)
    cyl("AnilloAire", 0.62, 0.15, (0, 0, DIE_Z - 0.03), M["negro"], verts=64, bevel=0.01)
    cyl("LabioAnillo", 0.36, 0.12, (0, 0, DIE_Z + 0.08), M["negro"], verts=64, r2=0.29)
    cyl("Dado", 0.24, 0.02, (0, 0, DIE_Z + 0.03), M["cromo"], verts=64)
    box("CajaControlCabezal", (0.32, 0.12, 0.20), (0.0, -0.45, DIE_Z - 0.40), M["negro"], 0.006)
    # 8 mangueras repartidas evitando el sector de la extrusora (+Y)
    nh = 8
    angs = [math.radians(180 + k * 240 / (nh - 1)) for k in range(nh)]
    for a in angs:
        cyl("Entrada", 0.06, 0.12, (math.cos(a) * 0.66, math.sin(a) * 0.66, DIE_Z - 0.03),
            M["negro"], axis="X").rotation_euler = (0, 0, a)

    grupo("13_Extrusora_Cilindro_y_Bancada")
    bz = 0.95
    cyl("Adaptador", 0.09, 0.50, (0, 0.50, bz), M["acero"], axis="Y")
    cyl("Cilindro", 0.10, 2.1, (0, 1.80, bz), M["acero"], axis="Y")
    box("Cubierta", (0.45, 1.95, 0.40), (0, 1.80, bz + 0.02), M["aluminio"], 0.03)
    box("BancadaExtrusora", (0.80, 2.9, 0.60), (0, 2.45, 0.40), M["negro"], 0.02)
    for sy in (-1, 1):
        box("PataBancada", (0.75, 0.10, 0.10), (0, 2.45 + sy * 1.35, 0.05), M["negro"])

    grupo("14_Tolva")
    hx, hy = 0, 2.65
    box("Garganta", (0.26, 0.26, 0.25), (hx, hy, bz + 0.32), M["aluminio"], 0.005)
    cyl("TolvaCono", 0.12, 0.35, (hx, hy, bz + 0.62), M["aluminio"], r2=0.32, bevel=0.005)
    cyl("Tolva", 0.32, 0.85, (hx, hy, bz + 1.22), M["film"], bevel=0.01)   # tolva envuelta en film
    cyl("TapaTolva", 0.33, 0.04, (hx, hy, bz + 1.66), M["aluminio"], bevel=0.005)
    cyl("CargadorVacio", 0.12, 0.30, (hx, hy, bz + 1.83), M["aluminio"], bevel=0.01)

    grupo("15_Reductor_y_Motor_Principal")
    box("ReductorPpal", (0.70, 0.60, 0.65), (0, 3.55, 1.00), M["aluminio"], 0.03)
    cyl("MotorPpal", 0.30, 0.80, (0, 4.25, 0.95), M["gris_oscuro"], axis="Y", bevel=0.02)
    for k in range(20):
        a = k * math.tau / 20
        box("AletaMotor", (0.015, 0.70, 0.05),
            (math.cos(a) * 0.305, 4.25, 0.95 + math.sin(a) * 0.305), M["gris_oscuro"], rot=(0, -a, 0))
    cyl("TapaMotorPpal", 0.27, 0.10, (0, 4.70, 0.95), M["gris_oscuro"], axis="Y", bevel=0.02)

    grupo("16_Soplador_de_Aire")
    bx, by = -1.60, 2.10
    cyl("Voluta", 0.45, 0.30, (bx, by, 0.55), M["negro"], axis="X", bevel=0.02)
    box("Descarga", (0.30, 0.38, 0.30), (bx, by - 0.36, 0.88), M["negro"], 0.02)
    cyl("MotorSoplador", 0.19, 0.38, (bx - 0.34, by, 0.55), M["negro"], axis="X", bevel=0.01)
    box("BaseSoplador", (0.8, 0.7, 0.10), (bx - 0.1, by, 0.05), M["negro"], 0.01)
    cyl("Colector", 0.24, 0.26, (bx, by - 0.62, 0.95), M["negro"], bevel=0.01)

    grupo("17_Mangueras_de_Aire")
    # anillo distribuidor bajo el cabezal: cada manguera sube en su propio plano
    # radial hasta su entrada del anillo de aire, asi no se cruzan entre si
    RD, ZD = 0.75, 0.55
    dist = bpy.data.curves.new("AnilloDistribuidor", "CURVE")
    dist.dimensions = "3D"
    dist.bevel_depth = 0.07
    sp = dist.splines.new("NURBS")
    sp.points.add(31)
    for i in range(32):
        a = i * math.tau / 32
        sp.points[i].co = (RD * math.cos(a), RD * math.sin(a), ZD, 1)
    sp.use_cyclic_u = True
    link(bpy.data.objects.new("AnilloDistribuidor", dist), None)
    for a in angs:
        c, sn = math.cos(a), math.sin(a)
        st = Vector((RD * c, RD * sn, ZD + 0.05))
        out = Vector((1.02 * c, 1.02 * sn, 0.85))
        end = Vector((0.72 * c, 0.72 * sn, DIE_Z - 0.03))
        top = Vector((0.92 * c, 0.92 * sn, DIE_Z - 0.06))
        curve_tube("Manguera", [st, out, top, end], 0.055, M["manguera"])
    # manguera de alimentacion: soplador -> anillo distribuidor (sector libre, atras-izquierda)
    a = math.radians(140)
    curve_tube("MangueraAlimentacion", [Vector((bx, by - 0.62, 0.86)), Vector((-1.0, 1.42, 0.50)),
                                        Vector((RD * math.cos(a) - 0.05, RD * math.sin(a) + 0.05, ZD))],
               0.09, M["manguera"])

# ---------------------------------------------------------------------------
# Tablero de control
# ---------------------------------------------------------------------------
def control_panel():
    grupo("18_Tablero_Electrico")
    x, y = 2.60, 1.40
    w, d, h = 0.85, 0.50, 1.75
    box("Tablero", (w, d, h), (x, y, 0.12 + h / 2), M["gris_panel"], 0.01)
    box("Zocalo", (w - 0.04, d - 0.04, 0.12), (x, y, 0.06), M["gris_oscuro"])
    fy = y - d / 2 - 0.004
    box("Puerta", (w - 0.04, 0.01, h - 0.05), (x, fy, 0.12 + h / 2), M["gris_panel"], 0.005)
    # controladores de temperatura (displays rojos) y pulsadores
    for row in range(2):
        for c in range(5):
            px = x - 0.30 + c * 0.15
            pz = 1.58 - row * 0.20
            box("Controlador", (0.10, 0.02, 0.09), (px, fy - 0.01, pz), M["negro"], 0.003)
            box("Display", (0.07, 0.005, 0.025), (px, fy - 0.022, pz + 0.018), M["rojo_led"])
            box("Display2", (0.07, 0.005, 0.018), (px, fy - 0.022, pz - 0.015), M["verde_led"])
    for c in range(5):
        px = x - 0.30 + c * 0.15
        mat = M["verde_led"] if c in (0, 2) else M["rojo_led"]
        cyl("Piloto", 0.022, 0.02, (px, fy - 0.015, 1.18), mat, axis="Y")
        cyl("Pulsador", 0.024, 0.025, (px, fy - 0.017, 1.06), M["rojo"] if c % 2 else M["verde"], axis="Y")
    cyl("Amperimetro", 0.05, 0.02, (x - 0.15, fy - 0.012, 0.93), M["negro"], axis="Y")
    cyl("Voltimetro", 0.05, 0.02, (x + 0.15, fy - 0.012, 0.93), M["negro"], axis="Y")
    cyl("Selector", 0.03, 0.04, (x, fy - 0.02, 0.93), M["negro"], axis="Y")
    # senal amarilla de riesgo electrico
    tri = mesh_from("RiesgoElectrico",
                    [(x - 0.09, fy - 0.012, 0.66), (x + 0.09, fy - 0.012, 0.66), (x, fy - 0.012, 0.815)],
                    [(0, 1, 2)], M["amarillo"], smooth=False)
    box("RiesgoTexto", (0.2, 0.004, 0.07), (x, fy - 0.011, 0.58), M["amarillo"])
    text("Rayo", "⚡", 0.08, (x, fy - 0.014, 0.71), M["negro_mate"])
    # bisagras y chapa
    box("Manija", (0.03, 0.03, 0.12), (x + w / 2 - 0.08, fy - 0.02, 1.0), M["negro"], 0.005)
    # canaleta de cables hacia la maquina
    beam("Ducto", (x - 0.2, y, 0.12 + h), (x - 0.2, y, 2.55), 0.08, M["gris_panel"])
    beam("Ducto", (x - 0.2, y, 2.55), (CX, y, 2.55), 0.08, M["gris_panel"])


# ---------------------------------------------------------------------------
# Escalera de gato (negra) al costado derecho
# ---------------------------------------------------------------------------
def ladder():
    grupo("19_Escalera")
    # escalera metalica principal: sube de adelante hacia atras al descanso derecho
    x = PX + 0.40
    stair((x, -2.65, 0.0), (x, -0.32, PZ), 0.70)


# ---------------------------------------------------------------------------
# Embobinadora (frente)
# ---------------------------------------------------------------------------
def winder():
    grupo("20_Embobinadora_Doble")
    hw = 0.85
    yb, yf = WY0, WY1
    L = yb - yf
    ym = yb - 1.55          # fin del cuerpo alto
    box("BaseNegra", (2 * hw + 0.30, L, 0.12), (0, (yb + yf) / 2, 0.06), M["negro"], 0.005)
    box("PisoChapaEstriada", (2 * hw - 0.16, L - 0.4, 0.01), (0, (yb + yf) / 2 - 0.1, 0.125), M["negro"])
    for sx in (-1, 1):
        x = sx * hw
        xo = x + sx * 0.085
        # cuerpo alto (entrada)
        box("BastidorAlto", (0.16, yb - ym, 2.10), (x, (yb + ym) / 2, 0.12 + 1.05), M["blanco"], 0.01)
        box("PanelOscuro", (0.01, 0.65, 0.75), (xo, yb - 0.45, 1.65), M["gris_oscuro"])
        box("PanelOscuro", (0.01, 0.65, 0.75), (xo, yb - 1.15, 1.65), M["gris_oscuro"])
        box("PanelOscuro", (0.01, 1.30, 0.70), (xo, yb - 0.80, 0.62), M["gris_oscuro"])
        # cuerpo bajo continuo hasta la puntera, con paneles por estacion
        box("BastidorBajo", (0.16, ym - (yf + 0.35), 1.15), (x, (ym + yf + 0.35) / 2, 0.12 + 0.575), M["blanco"], 0.01)
        box("BastidorPuntera", (0.16, 0.35, 0.65), (x, yf + 0.175, 0.12 + 0.325), M["blanco"], 0.01)
        for yc_ in (-4.40, -5.85):
            box("PanelOscuro", (0.01, 1.05, 0.65), (xo, yc_, 0.65), M["gris_oscuro"])
        # portico intermedio que lleva la hoja 2 por encima de la estacion 1
        box("PosteIntermedio", (0.12, 0.12, 0.70), (x, -4.95, 1.27 + 0.35), M["blanco"], 0.005)
    box("TravesanoIntermedio", (2 * hw + 0.12, 0.12, 0.10), (0, -4.95, 1.98), M["blanco"], 0.005)
    # rodillos del cuerpo alto (tramo comun)
    for py, pz, r in ((yb - 0.12, 2.12, 0.05), (yb - 0.25, 1.92, 0.06), (yb - 0.50, 1.88, 0.06),
                      (yb - 0.75, 1.68, 0.06), (yb - 1.00, 1.45, 0.07)):
        cyl("RodilloCromado", r, 2 * hw - 0.16, (0, py, pz), M["cromo"], axis="X")
    cyl("RodilloSeparador", 0.07, 2 * hw - 0.16, (0, yb - 1.30, 1.20), M["cromo"], axis="X")
    for sx in (-1, 1):
        cyl("AnilloRojo", 0.08, 0.06, (sx * (hw - 0.14), yb - 1.00, 1.45), M["rojo"], axis="X")
        cyl("AnilloRojo", 0.08, 0.06, (sx * (hw - 0.14), yb - 1.30, 1.20), M["rojo"], axis="X")
    # cuchillas que cortan los bordes (separan las dos hojas)
    for sx in (-1, 1):
        box("PortaCuchilla", (0.05, 0.10, 0.12), (sx * (LAYFLAT + 0.01), yb - 1.18, 1.42), M["aluminio"], 0.004)
    beam("BarraCuchillas", (-hw + 0.08, yb - 1.18, 1.48), (hw - 0.08, yb - 1.18, 1.48), 0.03, M["acero"], round_=True)
    # rodillos de la hoja 2
    cyl("RodilloHoja2", 0.05, 2 * hw - 0.16, (0, yb - 1.55, 1.58), M["cromo"], axis="X")
    cyl("RodilloHoja2", 0.06, 2 * hw - 0.16, (0, -4.95, 1.70), M["cromo"], axis="X")
    cyl("RodilloHoja2", 0.05, 2 * hw - 0.16, (0, -5.45, 1.20), M["cromo"], axis="X")
    cyl("RodilloHoja1", 0.05, 2 * hw - 0.16, (0, yb - 1.60, 1.05), M["cromo"], axis="X")

    # dos estaciones de bobinado (tambor de goma + barra verde + bobina)
    for k, (yd, rr) in enumerate(((-4.35, 0.22), (-5.80, 0.18)), start=1):
        grupo(f"20{'cd'[k - 1]}_Estacion_Bobinado_{k}")
        tg = f"E{k}"
        cyl(f"TamborGoma{tg}", 0.17, 2 * hw - 0.16, (0, yd, 0.95), M["goma"], axis="X", verts=64)
        for sx in (-1, 1):
            cyl(f"TapaTamborRoja{tg}", 0.10, 0.05, (sx * (hw - 0.12), yd, 0.95), M["rojo"], axis="X")
        cyl(f"EjeVerde{tg}", 0.035, 2 * hw + 0.40, (0, yd + 0.38, 1.30), M["acero"], axis="X")
        cyl(f"MangaVerde{tg}", 0.06, 1.25, (0, yd + 0.38, 1.30), M["verde"], axis="X")
        yb_ = yd - (0.17 + rr) * 0.85
        zb_ = 0.95 + (0.17 + rr) * 0.53
        cyl(f"Bobina{tg}", rr, 2 * LAYFLAT + 0.02, (0, yb_, zb_), M["bobina"], axis="X", verts=96, bevel=0.01)
        cyl(f"Nucleo{tg}", 0.045, 2 * LAYFLAT + 0.08, (0, yb_, zb_), M["carton"], axis="X")
        cyl(f"EjeBobina{tg}", 0.035, 2 * hw + 0.50, (0, yb_, zb_), M["acero"], axis="X")
        for sx in (-1, 1):
            cyl(f"Mandril{tg}", 0.06, 0.08, (sx * (hw + 0.14), yb_, zb_), M["negro"], axis="X", verts=6)
            beam(f"BrazoBobina{tg}", (sx * (hw + 0.09), yd + 0.30, 1.05), (sx * (hw + 0.09), yb_, zb_ - 0.05),
                 0.06, M["blanco"], t2=0.10)

    grupo("20_Embobinadora_Doble")
    # rodillos de piso al frente (descarga de bobinas)
    cyl("RodilloPiso", 0.05, 2 * hw + 0.10, (0, yf + 0.50, 0.42), M["blanco"], axis="X")
    cyl("RodilloPiso", 0.06, 2 * hw + 0.10, (0, yf + 0.18, 0.22), M["blanco"], axis="X")
    for sx in (-1, 1):
        box("SoporteRodilloPiso", (0.08, 0.10, 0.35), (sx * (hw + 0.10), yf + 0.18, 0.22), M["blanco"])

    grupo("20b_Torre_de_Control_Embobinadora")
    tx, ty = -(hw + 0.40), yb - 0.75
    box("TorreControl", (0.50, 0.55, 2.20), (tx, ty, 0.12 + 1.10), M["blanco"], 0.01)
    box("PanelTorre", (0.38, 0.01, 0.70), (tx, ty - 0.28, 0.65), M["gris_oscuro"])
    box("PantallaHMI", (0.26, 0.015, 0.18), (tx, ty - 0.283, 1.62), M["negro"])
    for r in range(2):
        for c in range(4):
            cyl("Pulsador", 0.016, 0.02, (tx - 0.12 + c * 0.08, ty - 0.29, 1.38 - r * 0.07),
                M["rojo"] if (r + c) % 2 else M["verde"], axis="Y", verts=16)
    z = 2.34
    cyl("BalizaBase", 0.035, 0.04, (tx, ty, z), M["negro"])
    z += 0.04
    for nm in ("BalizaVerde", "BalizaAmbar", "BalizaRoja"):
        cyl(nm, 0.04, 0.08, (tx, ty, z + 0.04), M["blanco"], bevel=0.004)
        z += 0.082
    gx, gy = -(hw + 0.45), yb + 0.05
    box("GabineteElectrico", (0.55, 0.95, 1.05), (gx, gy, 0.12 + 0.525), M["blanco"], 0.01)
    for k in (-1, 1):
        box("PuertaGabinete", (0.01, 0.40, 0.80), (gx - 0.28, gy + k * 0.22, 0.62), M["negro"])
    box("RejillaGabinete", (0.40, 0.70, 0.01), (gx, gy, 0.12 + 1.055), M["gris_oscuro"])
    mx_, my_ = -(hw + 0.12), yf + 0.45
    box("CajaManometro", (0.08, 0.20, 0.16), (mx_, my_, 0.82), M["blanco"], 0.005)
    cyl("Manometro", 0.045, 0.02, (mx_ - 0.05, my_, 0.84), M["aluminio"], axis="X", verts=24)
    pts = []
    for i in range(80):
        a = i * 0.45
        pts.append(Vector((mx_ - 0.15 + 0.06 * math.cos(a), my_ - 0.05 + 0.06 * math.sin(a), 0.70 - i * 0.0075)))
    curve_tube("MangueraEspiral", pts, 0.006, M["rojo"], res=4)

    grupo("21_Puente_de_Rodillos")
    for sx in (-1, 1):
        beam("VigaPuente", (sx * 0.80, -CY, 2.40), (sx * 0.80, yb - 0.05, 2.40), 0.08, M["negro"], t2=0.14)
    for y in (-1.15, -1.70):
        cyl("RodilloPuente", 0.04, 1.56, (0, y, 2.43), M["acero"], axis="X")


# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------
tower()
upper_tower()
bubble()
extruder()
control_panel()
ladder()
winder()

# Aplicar modificadores (biseles, booleanos) para dejar mallas limpias y
# borrar los objetos auxiliares de corte.
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

# ---------------------------------------------------------------------------
# Nombres descriptivos de cada pieza
# ---------------------------------------------------------------------------
NOMBRES = {
    "TamborGomaE1": "Tambor_Goma_Estacion_1",
    "TapaTamborRojaE1": "Tapa_Tambor_Roja_Estacion_1",
    "EjeVerdeE1": "Eje_Manga_Verde_Estacion_1",
    "MangaVerdeE1": "Manga_Verde_Estacion_1",
    "BobinaE1": "Bobina_Estacion_1",
    "NucleoE1": "Nucleo_Carton_Estacion_1",
    "EjeBobinaE1": "Eje_Bobina_Estacion_1",
    "MandrilE1": "Mandril_Estacion_1",
    "BrazoBobinaE1": "Brazo_Porta_Bobina_Estacion_1",
    "TamborGomaE2": "Tambor_Goma_Estacion_2",
    "TapaTamborRojaE2": "Tapa_Tambor_Roja_Estacion_2",
    "EjeVerdeE2": "Eje_Manga_Verde_Estacion_2",
    "MangaVerdeE2": "Manga_Verde_Estacion_2",
    "BobinaE2": "Bobina_Estacion_2",
    "NucleoE2": "Nucleo_Carton_Estacion_2",
    "EjeBobinaE2": "Eje_Bobina_Estacion_2",
    "MandrilE2": "Mandril_Estacion_2",
    "BrazoBobinaE2": "Brazo_Porta_Bobina_Estacion_2",
    # Extrusora N4: piezas propias
    "Vigueta": "Vigueta_Plataforma", "Descanso": "Descanso_Escalera", "PosteDescanso": "Poste_Descanso",
    "PlataformaEnfriador": "Plataforma_Voladizo_Enfriador", "VigaVoladizo": "Viga_Voladizo",
    "PuntalVoladizo": "Puntal_Diagonal_Voladizo", "ColumnaVoladizo": "Columna_Voladizo",
    "Enfriador": "Enfriador_de_Aire_Chiller", "MarcoEnfriador": "Marco_Enfriador",
    "RejillaEnfriador": "Rejilla_Enfriador", "PanelFiltro": "Panel_Filtro_Enfriador",
    "PantallaEnfriador": "Pantalla_Enfriador", "DuctoAireFrio": "Ducto_Aire_Frio",
    "ColumnaNivel2": "Columna_Nivel_Superior", "VigaNivel2": "Viga_Nivel_Superior",
    "PlataformaSup": "Plataforma_Superior", "BarandaSup": "Baranda_Plataforma_Superior",
    "ParanteSup": "Parante_Plataforma_Superior", "TableroLED": "Tablero_LED_Produccion",
    "FilaLED": "Fila_Digitos_LED", "EtiquetaLED": "Etiqueta_Tablero_LED", "SoporteLED": "Soporte_Tablero_LED",
    "CalibradorViga": "Calibrador_Viga_Azul", "CalibradorRodillo": "Calibrador_Rodillo",
    "CalibradorBrazo": "Calibrador_Brazo_Azul", "PedestalCabezal": "Pedestal_Cabezal",
    "CargadorVacio": "Cargador_al_Vacio",
    "AnilloDistribuidor": "Anillo_Distribuidor_Aire", "MangueraAlimentacion": "Manguera_Alimentacion_Soplador",
    "PosteIntermedio": "Poste_Portico_Intermedio", "TravesanoIntermedio": "Travesano_Portico_Intermedio",
    "RodilloSeparador": "Rodillo_Separador_Hojas", "PortaCuchilla": "Porta_Cuchilla_Corte_Bordes",
    "BarraCuchillas": "Barra_Cuchillas", "RodilloHoja1": "Rodillo_Hoja_1", "RodilloHoja2": "Rodillo_Hoja_2",
    "LaminaEstacion1": "Lamina_Hoja_a_Estacion_1", "LaminaEstacion2": "Lamina_Hoja_a_Estacion_2",
    "BaseNegra": "Base_Embobinadora", "PisoChapaEstriada": "Piso_Chapa_Estriada",
    "BastidorAlto": "Bastidor_Alto", "BastidorBajo": "Bastidor_Bajo", "BastidorPuntera": "Bastidor_Puntera",
    "PanelOscuro": "Panel_Oscuro_Bastidor", "AnilloRojo": "Anillo_Rojo_Rodillo", "EjeVerde": "Eje_Manga_Verde",
    "MangaVerde": "Manga_Verde", "TamborGoma": "Tambor_Goma_Bobinado", "TapaTamborRoja": "Tapa_Tambor_Roja",
    "BrazoBobina": "Brazo_Porta_Bobina", "RodilloPiso": "Rodillo_Piso_Descarga",
    "SoporteRodilloPiso": "Soporte_Rodillo_Piso", "TorreControl": "Torre_Control_Embobinadora",
    "PanelTorre": "Panel_Torre_Control", "PantallaHMI": "Pantalla_Tactil_HMI",
    "BalizaBase": "Baliza_Base", "BalizaRoja": "Baliza_Roja", "BalizaAmbar": "Baliza_Ambar",
    "BalizaVerde": "Baliza_Verde", "GabineteElectrico": "Gabinete_Electrico_Embobinadora",
    "PuertaGabinete": "Puerta_Gabinete_Electrico", "RejillaGabinete": "Rejilla_Gabinete_Electrico",
    "CajaManometro": "Caja_Manometro", "Manometro": "Manometro", "MangueraEspiral": "Manguera_Neumatica_Espiral",
    "VigaPuente": "Viga_Puente_Rodillos", "RodilloPuente": "Rodillo_Puente",
    ("20", "Pulsador"): "Pulsador_Torre_Control", ("20", "Bobina"): "Bobina_de_Film",
    # Extrusora N3: piezas propias
    "PernoAnclaje": "Perno_Anclaje", "VigaInterior": "Viga_Interior_Plataforma",
    "Riostra": "Riostra_Corta", "RiostraLarga": "Riostra_Diagonal_Larga", "Cartela": "Cartela_Columna_Viga",
    "PlataformaSup": "Plataforma_Superior", "CajonPlataformaSup": "Cajon_Plataforma_Superior",
    "BarandaSup": "Baranda_Plataforma_Superior", "ParanteSup": "Parante_Plataforma_Superior",
    "LargueroSup": "Larguero_Escalera_Superior", "PeldanoSup": "Peldano_Escalera_Superior",
    "PasamanoSup": "Pasamano_Escalera_Superior", "ParantePasamanoSup": "Parante_Pasamano_Escalera_Superior",
    "PestanaPeldanoSup": "Pestana_Peldano_Escalera_Superior", "PieSup": "Pie_Escalera_Superior",
    "PestanaPeldano": "Pestana_Peldano_Escalera",
    "PorticoSup": "Portico_Superior", "CarroCabezal": "Carro_Cabezal", "PataCarro": "Pata_Carro_Cabezal",
    "RuedaCarro": "Rueda_Carro_Cabezal", "CajaControlCabezal": "Caja_Control_Cabezal",
    "PataBancada": "Pata_Bancada", "ZocaloBancada": "Zocalo_Bancada", "MangueraRollo": "Manguera_Enrollada",
    "LargueroBase": "Larguero_Base_Embobinadora", "Rodamiento": "Rodamiento_Embobinadora",
    "RodilloEmb": "Rodillo_Embobinadora", "RodilloCromado": "Rodillo_Cromado_Embobinadora",
    "TamborCromado": "Tambor_Cromado", "EjeBobinado": "Eje_Bobinado", "BrazoFrontal": "Brazo_Frontal",
    "ReductorEmb": "Reductor_Embobinadora", "MotorEmb": "Motor_Embobinadora",
    "TapaMotorEmb": "Tapa_Motor_Embobinadora", "ReductorServo": "Reductor_Servomotor",
    "Servomotor": "Servomotor", "TravesanoGuia": "Travesano_Portico_Embobinadora",
    "PosteCaja": "Poste_Caja_Control",
    "TravesanoPortico": "Travesano_Portico_Central", "RodilloSuperior": "Rodillo_Superior_Portico",
    "SoporteRodilloSup": "Soporte_Rodillo_Superior", "BarraExpansora": "Barra_Expansora",
    "RodilloCentral": "Rodillo_Central", "PortaCuchilla": "Porta_Cuchilla_Corte_Bordes",
    "BarraCuchillas": "Barra_Cuchillas", "RodilloGoma": "Rodillo_Goma",
    "ParadaEmergencia": "Parada_Emergencia", "UnidadNeumatica": "Unidad_Neumatica_FRL",
    "MangueraNeumatica": "Manguera_Neumatica", "ConectorServo": "Conector_Servomotor",
    "LaminaDelantera": "Lamina_Hoja_a_Estacion_Delantera", "LaminaTrasera": "Lamina_Hoja_a_Estacion_Trasera",
    "TamborDelantera": "Tambor_Friccion_Delantero", "TamborTrasera": "Tambor_Friccion_Trasero",
    "EjeTamborDelantera": "Eje_Tambor_Delantero", "EjeTamborTrasera": "Eje_Tambor_Trasero",
    "TapaRodamientoTamborDelantera": "Tapa_Rodamiento_Tambor_Delantero",
    "TapaRodamientoTamborTrasera": "Tapa_Rodamiento_Tambor_Trasero",
    "BobinaDelantera": "Bobina_Estacion_Delantera", "BobinaTrasera": "Bobina_Estacion_Trasera",
    "NucleoDelantera": "Nucleo_Carton_Delantero", "NucleoTrasera": "Nucleo_Carton_Trasero",
    "EjeBobinadoDelantera": "Eje_Bobinado_Delantero", "EjeBobinadoTrasera": "Eje_Bobinado_Trasero",
    "MandrilDelantera": "Mandril_Delantero", "MandrilTrasera": "Mandril_Trasero",
    "HorquillaDelantera": "Horquilla_Eje_Delantero", "HorquillaTrasera": "Horquilla_Eje_Trasero",
    "CilindroPresionDelantera": "Cilindro_Presion_Delantero", "CilindroPresionTrasera": "Cilindro_Presion_Trasero", "CanaletaCables": "Canaleta_Flexible_Cables",
    ("20", "PosteGuia"): "Poste_Portico_Embobinadora", ("20", "RodilloGuia"): "Rodillo_Portico_Embobinadora",
    ("20", "BarraGuia"): "Barra_Portico_Embobinadora", ("20", "Pie"): "Pie_Embobinadora",
    ("20", "Pulsador"): "Pulsador_Caja_Control",
    # 01 estructura de la torre
    "Columna": "Columna_Torre", "PlacaBase": "Placa_Base_Columna",
    "VigaX": "Viga_Plataforma_Longitudinal", "VigaY": "Viga_Plataforma_Transversal",
    ("01", "Travesano"): "Travesano_Inferior_Torre",
    # 02 plataforma
    "Plataforma": "Piso_Plataforma", ("02", "Zocalo"): "Zocalo_Plataforma",
    # 03 barandas
    "Baranda": "Baranda_Tubo_Horizontal", "Parante": "Baranda_Parante",
    # 04 letreros
    "Letrero1": "Letrero_Extrusora_Placa", "Letrero1Borde": "Letrero_Extrusora_Marco",
    "TxtExtrusora": "Texto_EXTRUSORA", "TxtN": "Texto_N", "Txt1": "Texto_Numero_1",
    "LetreroCasco": "Letrero_Casco_Placa", "LetreroCascoAzul": "Letrero_Casco_Fondo",
    "Casco": "Letrero_Casco_Pictograma", "CascoVisera": "Letrero_Casco_Visera",
    "Cara": "Letrero_Casco_Cara", "LetreroCascoTxtFondo": "Letrero_Casco_Franja_Texto",
    "TxtCasco": "Texto_UTILIZAR_CASCO",
    # 05 marco torre superior
    "ColSup": "Columna_Torre_Superior", "TravSupX": "Travesano_Superior_Longitudinal",
    "TravSupY": "Travesano_Superior_Transversal", "ChapaNip": "Placa_Lateral_Nip",
    # 06 rodillos nip
    "NipCromo": "Rodillo_Nip_Cromado", "NipGoma": "Rodillo_Nip_Goma", "EjeNip": "Eje_Rodillo_Nip",
    "Neumatico": "Cilindro_Neumatico_Presion", "Vastago": "Vastago_Cilindro_Neumatico",
    "RodilloRetorno": "Rodillo_Retorno_Superior",
    # 07 motorreductor nip
    "Reductor": "Caja_Reductora_Nip", "Brida": "Brida_Motor_Nip", "Motor": "Motor_Electrico_Nip",
    "Aleta": "Aleta_Motor_Nip", "TapaVentilador": "Tapa_Ventilador_Motor_Nip",
    "CajaBornes": "Caja_Bornes_Motor_Nip",
    # 08 canasta colapsadora
    "Liston": "Liston_Madera_Canasta", ("08", "Larguero"): "Larguero_Canasta",
    "GuiaLat": "Guia_Lateral_Canasta",
    # 09 iris
    "Iris": "Anillo_Calibrador_Iris", "SoporteIris": "Brazo_Soporte_Iris",
    # 10 pelicula
    "Burbuja": "Manga_Burbuja_de_Film", "Lamina": "Lamina_Film_Aplanada",
    # 11 rodillo bajo plataforma
    "RodilloPlataforma": "Rodillo_Guia_Bajo_Plataforma", "SoporteRodillo": "Soporte_Rodillo_Plataforma",
    # 12 cabezal
    "BaseCabezal": "Base_Cabezal", "Cabezal": "Cabezal_Dado", "ResistenciaCabezal": "Resistencia_Cabezal",
    "AnilloAire": "Anillo_de_Aire", "LabioAnillo": "Labio_Anillo_de_Aire", "Dado": "Boquilla_Dado",
    "Entrada": "Entrada_Aire_Anillo",
    # 13 extrusora
    "Adaptador": "Adaptador_Cilindro_Cabezal", "Cilindro": "Cilindro_Barril_Tornillo",
    "Resistencia": "Resistencia_Cilindro", "Cubierta": "Cubierta_Resistencias",
    "BancadaExtrusora": "Bancada_Extrusora", "Ventilador": "Ventilador_Enfriamiento_Cilindro",
    # 14 tolva
    "Garganta": "Garganta_Alimentacion", "TolvaCono": "Tolva_Cono", "Tolva": "Tolva_Cuerpo",
    "TapaTolva": "Tolva_Tapa", "Visor": "Tolva_Visor_Nivel",
    # 15 motor principal
    "ReductorPpal": "Reductor_Principal", "MotorPpal": "Motor_Principal",
    "AletaMotor": "Aleta_Motor_Principal", "TapaMotorPpal": "Tapa_Motor_Principal",
    # 16 soplador
    "Voluta": "Soplador_Voluta", "Descarga": "Soplador_Descarga", "MotorSoplador": "Motor_Soplador",
    "BaseSoplador": "Base_Soplador", "Colector": "Colector_Distribuidor_Aire",
    # 17 mangueras
    "Manguera": "Manguera_Aire",
    # 18 tablero electrico
    "Tablero": "Gabinete_Tablero", ("18", "Zocalo"): "Zocalo_Tablero", "Puerta": "Puerta_Tablero",
    "Controlador": "Controlador_Temperatura", "Display": "Display_Temperatura_Real",
    "Display2": "Display_Temperatura_Ajuste", "Piloto": "Luz_Piloto", "Pulsador": "Pulsador",
    "Amperimetro": "Amperimetro", "Voltimetro": "Voltimetro", "Selector": "Selector_Rotativo",
    "RiesgoElectrico": "Senal_Riesgo_Electrico", "RiesgoTexto": "Senal_Riesgo_Electrico_Texto",
    "Rayo": "Senal_Riesgo_Electrico_Rayo", "Manija": "Manija_Puerta_Tablero", "Ducto": "Canaleta_Cables",
    # 19 escalera
    ("19", "Larguero"): "Larguero_Escalera", "Pasamano": "Pasamano_Escalera",
    "ParantePasamano": "Parante_Pasamano_Escalera", "Peldano": "Peldano_Escalera", "Pie": "Pie_Escalera",
    # 20 embobinadora
    "PlacaLateral": "Placa_Lateral_Embobinadora", "Perno": "Perno_Embobinadora",
    "PataLat": "Pata_Embobinadora", "Rueda": "Rueda_Embobinadora",
    ("20", "Travesano"): "Travesano_Embobinadora", "RodilloEntrada": "Rodillo_Entrada_Embobinadora",
    "RodilloTension": "Rodillo_Tension_Embobinadora", "RodilloArrastre": "Rodillo_Arrastre_Embobinadora",
    "NucleoCarton": "Nucleo_Carton_Bobina", "Bobina": "Bobina_de_Film", "EjeBobina": "Eje_Bobina",
    "Mandril": "Mandril_Bobina", "TapaMotor": "Cubierta_Motor_Embobinadora",
    "TapaMotor2": "Cubierta_Transmision_Embobinadora", "CajaControl": "Caja_Control_Embobinadora",
    "Contador": "Contador_de_Metros", "Guia": "Barra_Guia_Embobinadora",
    # 21 soporte guia
    "PosteGuia": "Poste_Soporte_Guia", "PieGuia": "Pie_Soporte_Guia",
    "RodilloGuia": "Rodillo_Guia", "BarraGuia": "Barra_Guia",
}


def base_name(n):
    return n.split(".")[0]


def lado(v, neg, pos, tol=0.05):
    return neg if v < -tol else pos if v > tol else "Centro"


grupos = {}
for ob in bpy.data.objects:
    c = ob.users_collection[0].name
    b = base_name(ob.name)
    nuevo = NOMBRES.get((c[:2], b)) or NOMBRES.get(b) or b
    grupos.setdefault(nuevo, []).append(ob)

for nuevo, obs in grupos.items():
    for ob in obs:
        ob.name = "__tmp__" + ob.name
for nuevo, obs in grupos.items():
    if len(obs) == 1:
        finales = [nuevo]
    else:
        # sufijo por posicion (Izq/Der, Delantera/Trasera); si se repite, numerar
        tags = []
        for ob in obs:
            x, y, _ = ob.matrix_world.translation
            t = []
            if len({round(o.matrix_world.translation.x, 2) for o in obs}) > 1:
                t.append(lado(x, "Izq", "Der"))
            if len({round(o.matrix_world.translation.y, 2) for o in obs}) > 1:
                t.append(lado(y, "Delantero", "Trasero"))
            tags.append("_".join(t))
        if all(tags) and len(set(tags)) == len(tags):
            finales = [f"{nuevo}_{t}" for t in tags]
        else:
            orden = sorted(range(len(obs)), key=lambda i: (round(obs[i].matrix_world.translation.z, 3),
                                                          round(obs[i].matrix_world.translation.x, 3),
                                                          round(obs[i].matrix_world.translation.y, 3)))
            finales = [None] * len(obs)
            for k, i in enumerate(orden):
                finales[i] = f"{nuevo}_{k + 1:02d}"
    for ob, nm in zip(obs, finales):
        ob.name = nm
        if ob.data is not None:
            ob.data.name = nm

# limpiar datos huerfanos
for blocks in (bpy.data.meshes, bpy.data.curves, bpy.data.materials):
    for d in list(blocks):
        if d.users == 0:
            blocks.remove(d)

scene.unit_settings.system = "METRIC"
scene.unit_settings.length_unit = "METERS"
here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
out = os.path.join(here, "extrusora4_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en",
      len(bpy.data.collections) - 1, "grupos", flush=True)
