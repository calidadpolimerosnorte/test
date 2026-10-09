"""
Modelo Blender limpio de la Extrusora Nº 6: linea larga con torre, impresora
flexografica, troqueladora y doble embobinado en tandem.

Solo la maquina: sin materiales/colores, sin animacion, sin galpon, piso,
luces ni camaras. Cada pieza tiene un nombre descriptivo y esta agrupada en
colecciones por sistema (torre, plataforma, extrusora, tablero, etc.).

Uso:
    python3 blender/extrusora6_modelo.py           # con bpy de PyPI
    blender -b -P blender/extrusora6_modelo.py     # con Blender

Guarda blender/extrusora6_modelo.blend.
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
ROOT = bpy.data.collections.new("Extrusora_N6")
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
# Mismas referencias de planta que las demas (piso en z=0, metros).
# La linea avanza hacia -Y: torre -> impresora -> troqueladora -> 2 embobinadoras.
PZ = 3.00            # plataforma principal (negra)
PX, PY = 1.35, 1.10
CX, CY = 1.15, 0.95
DIE_Z = 1.15
TZ = 5.40            # plataforma superior (negra)
NIP_Z = TZ + 0.55
CAN_Z0 = PZ + 0.90
R_BUB = 0.30
IMP_Y = -2.40        # centro de la impresora
TRQ_Y = -4.80        # centro de la troqueladora
EMB_Y = (-6.90, -8.90)   # extremo trasero de cada embobinadora
OVZ = 2.65           # altura del puente aereo de rodillos
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
            box("Columna", (0.20, 0.20, PZ - 0.12), (x, y, (PZ - 0.12) / 2), M["blanco"], 0.006)
            box("PlacaBase", (0.40, 0.40, 0.025), (x, y, 0.0125), M["blanco"], 0.004)
            for k in range(4):
                cyl("PernoAnclaje", 0.016, 0.04, (x + (k % 2 - 0.5) * 0.28, y + (k // 2 - 0.5) * 0.28, 0.045),
                    M["acero"], verts=6)
    # marco blanco con riostras en "A" bajo la plataforma (como en las fotos)
    FZ = 2.10
    for sy in (-1, 1):
        box("Viga_Marco_Intermedio", (2 * CX, 0.14, 0.14), (0, sy * CY, FZ), M["blanco"], 0.004)
        for sx in (-1, 1):
            beam("Riostra_A", (sx * CX, sy * CY, 0.95), (sx * 0.35, sy * CY, FZ - 0.07), 0.10, M["blanco"])
            beam("Riostra_Superior", (sx * CX, sy * CY, FZ + 0.07), (sx * 0.35, sy * CY, PZ - 0.25), 0.09, M["blanco"])
    for sx in (-1, 1):
        box("Viga_Marco_Intermedio", (0.14, 2 * CY, 0.14), (sx * CX, 0, FZ), M["blanco"], 0.004)
        for sy in (-1, 1):
            beam("Riostra_A", (sx * CX, sy * CY, 0.95), (sx * CX, sy * 0.30, FZ - 0.07), 0.10, M["blanco"])
    for sy in (-1, 1):
        box("VigaX", (2 * PX, 0.16, 0.24), (0, sy * CY, PZ - 0.22), M["negro"], 0.004)
    for sx in (-1, 1):
        box("VigaY", (0.16, 2 * PY, 0.24), (sx * CX, 0, PZ - 0.22), M["negro"], 0.004)

    grupo("02_Plataforma")
    H = 0.50
    t = 0.10
    zc = PZ - t / 2
    box("Plataforma", (2 * PX, PY - H, t), (0, -(PY + H) / 2, zc), M["negro"], 0.006)
    box("Plataforma", (2 * PX, PY - H, t), (0, (PY + H) / 2, zc), M["negro"], 0.006)
    box("Plataforma", (PX - H, 2 * H, t), (-(PX + H) / 2, 0, zc), M["negro"], 0.006)
    box("Plataforma", (PX - H, 2 * H, t), ((PX + H) / 2, 0, zc), M["negro"], 0.006)
    # descanso de la escalera (lado izquierdo)
    LX0, LX1, LY0, LY1 = -PX - 0.80, -PX, -0.30, 0.90
    box("Descanso_Escalera", (LX1 - LX0, LY1 - LY0, t), ((LX0 + LX1) / 2, (LY0 + LY1) / 2, zc), M["negro"], 0.006)
    for y in (LY0 + 0.07, LY1 - 0.07):
        box("Poste_Descanso", (0.12, 0.12, PZ - 0.10), (LX0 + 0.07, y, (PZ - 0.10) / 2), M["blanco"], 0.004)
        box("PlacaBase", (0.26, 0.26, 0.02), (LX0 + 0.07, y, 0.01), M["blanco"])

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
    rail_segment((ex, -ey, 0), (ex, ey, 0))
    rail_segment((-ex, -ey, 0), (-ex, LY0, 0))
    rail_segment((-ex, LY1, 0), (-ex, ey, 0))
    rail_segment((LX0 + 0.02, LY0 + 0.02, 0), (LX0 + 0.02, LY1 - 0.02, 0))
    rail_segment((LX0 + 0.02, LY1 - 0.02, 0), (-ex, LY1 - 0.02, 0))


# ---------------------------------------------------------------------------
# Torre superior: marco, canasta colapsadora de madera, rodillos nip, motor
# ---------------------------------------------------------------------------
def upper_tower():
    grupo("05_Torre_Superior_Marco")
    fx, fy = 0.70, 0.50
    top = NIP_Z + 0.45
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("ColSup", (0.08, 0.08, top - PZ), (sx * fx, sy * fy, (top + PZ) / 2), M["blanco"], 0.004)
    for z in (PZ + 1.20, TZ - 0.10, top - 0.04):
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
    ox, oy = CX, CY
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("Columna_Nivel_Superior", (0.16, 0.16, TZ - PZ), (sx * ox, sy * oy, (TZ + PZ) / 2), M["blanco"], 0.004)
    for sy in (-1, 1):
        box("Viga_Nivel_Superior", (2 * PX, 0.14, 0.18), (0, sy * oy, TZ - 0.17), M["negro"], 0.004)
    for sx in (-1, 1):
        box("Viga_Nivel_Superior", (0.14, 2 * PY, 0.18), (sx * ox, 0, TZ - 0.17), M["negro"], 0.004)
    # plataforma superior negra: hueco central y hueco de la escalera (atras)
    t = 0.08
    zc = TZ - t / 2
    for (x0, x1, y0, y1) in [(-PX, PX, -PY, -0.50), (-PX, -0.50, -0.50, PY), (0.50, PX, -0.50, 0.62),
                             (-0.50, 0.50, 0.50, 0.62)]:
        box("Plataforma_Superior", (x1 - x0, y1 - y0, t), ((x0 + x1) / 2, (y0 + y1) / 2, zc), M["negro"], 0.004)
    rh = 1.05

    def rail(p1, p2):
        p1, p2 = Vector(p1), Vector(p2)
        for z in (TZ + rh, TZ + 0.55):
            beam("Baranda_Superior", (p1.x, p1.y, z), (p2.x, p2.y, z), 0.04, M["negro"])
        n = max(1, round((p2 - p1).length / 0.6))
        for k in range(n + 1):
            p = p1.lerp(p2, k / n)
            box("Parante_Superior", (0.04, 0.04, rh), (p.x, p.y, TZ + rh / 2), M["negro"])

    ex, ey = PX - 0.02, PY - 0.02
    rail((-ex, -ey, 0), (ex, -ey, 0))
    rail((-ex, -ey, 0), (-ex, ey, 0))
    rail((ex, -ey, 0), (ex, 0.62, 0))
    rail((-ex, ey, 0), (-0.50, ey, 0))
    rail((-0.50, 0.64, 0), (ex, 0.64, 0))      # protege el hueco de la escalera
    # escalera metalica de la plataforma principal a la superior (sube hacia -X por detras)
    stair((0.95, 0.86, PZ), (-0.62, 0.86, TZ), 0.36, tag="Sup")

    grupo("05d_Tablero_LED")
    bx_, by_, bz_ = -0.45, -PY - 0.06, TZ + 1.35
    box("Tablero_LED", (0.80, 0.08, 0.50), (bx_, by_, bz_), M["negro"], 0.006)
    for k in range(4):
        box("Fila_Digitos_LED", (0.45, 0.01, 0.07), (bx_ + 0.12, by_ - 0.045, bz_ + 0.16 - k * 0.11), M["rojo_led"])
        box("Etiqueta_LED", (0.18, 0.01, 0.06), (bx_ - 0.24, by_ - 0.045, bz_ + 0.16 - k * 0.11), M["blanco"])
    for sx in (-1, 1):
        box("Soporte_Tablero_LED", (0.05, 0.05, 0.75), (bx_ + sx * 0.32, by_ + 0.05, TZ + 0.75), M["negro"])

    grupo("04b_Letrero")
    sx_, sz_ = CX, TZ - 0.45
    box("Letrero1", (0.15, 0.008, 0.26), (sx_, -CY - 0.085, sz_), M["blanco"], 0.002)
    text("Txt1", "6", 0.16, (sx_, -CY - 0.091, sz_), M["negro_mate"])

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
    path = [
        (0.0, NIP_Z + 0.08),
        (-0.30, NIP_Z + 0.17),
        (-0.47, NIP_Z + 0.10),
        (-0.50, PZ + 0.40),
        (-0.52, PZ - 0.32),
        (-0.62, PZ - 0.42),
        (IMP_Y + 0.55, 2.30),      # entra por arriba a la impresora
        (IMP_Y + 0.40, 2.20),
        (IMP_Y + 0.35, 1.55),      # grupo de impresion superior
        (IMP_Y + 0.15, 1.42),
        (IMP_Y + 0.10, 0.88),      # grupo de impresion inferior
        (IMP_Y - 0.15, 0.78),
        (IMP_Y - 0.70, 0.74),      # sale hacia la troqueladora
        (TRQ_Y + 0.90, 0.95),
        (TRQ_Y - 0.80, 0.97),      # troquelado
        (TRQ_Y - 1.15, 0.97),
        (TRQ_Y - 1.18, OVZ - 0.06),   # sube al puente aereo
    ]
    ramas = []
    for k, y0 in enumerate((EMB_Y[0], EMB_Y[1]), start=1):
        ramas.append((f"Lamina_a_Embobinadora_{k}", [(TRQ_Y - 1.18, OVZ - 0.06), (TRQ_Y - 1.10, OVZ + 0.02),
                     (y0 - 0.05, OVZ + 0.02), (y0 - 0.15, 1.58), (y0 - 0.45, 1.30), (y0 - 0.80, 0.97),
                     (y0 - 1.02, 1.04), (y0 - 1.18, 1.18)]))
    verts, faces = [], []
    for (y, z) in path:
        verts += [(-w, y, z), (w, y, z)]
    for i in range(len(path) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    mesh_from("Lamina", verts, faces, M["film_doble"], smooth=True)
    for nombre, pth in ramas:
        vv, ff = [], []
        # (las dos hojas comparten el tramo del puente; se desplazan un poco en altura)
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
    box("Pedestal_Cabezal", (0.60, 0.60, 0.30), (0, 0, 0.15), M["negro"], 0.01)
    cyl("Rotador_Cabezal", 0.30, 0.18, (0, 0, 0.42), M["acero"], bevel=0.01)
    for k in range(6):
        cyl("Aleta_Rotador", 0.32, 0.012, (0, 0, 0.36 + k * 0.025), M["aluminio"])
    cyl("Cabezal", 0.22, 0.40, (0, 0, DIE_Z - 0.32), M["acero"], bevel=0.01)
    for k in range(5):
        cyl("Resistencia_Cabezal", 0.245, 0.04, (0, 0, DIE_Z - 0.48 + k * 0.08), M["aluminio"], bevel=0.003)
    cyl("Anillo_de_Aire", 0.42, 0.12, (0, 0, DIE_Z - 0.03), M["negro"], verts=64, bevel=0.01)
    cyl("Labio_Anillo_de_Aire", 0.26, 0.09, (0, 0, DIE_Z + 0.06), M["aluminio"], verts=64, r2=0.21)
    cyl("Boquilla_Dado", 0.17, 0.02, (0, 0, DIE_Z + 0.02), M["cromo"], verts=64)
    box("Caja_Control_Cabezal", (0.24, 0.20, 0.28), (0.44, 0.44, 0.95), M["aluminio"], 0.008)
    nh = 4
    angs = [math.radians(a) for a in (200, 250, 300, 345)]
    for a in angs:
        cyl("Entrada_Aire_Anillo", 0.05, 0.10, (math.cos(a) * 0.45, math.sin(a) * 0.45, DIE_Z - 0.03),
            M["negro"], axis="X").rotation_euler = (0, 0, a)

    grupo("13_Extrusora_Cilindro_y_Bancada")
    bz = 0.80
    cyl("Adaptador_Cilindro_Cabezal", 0.07, 0.45, (0, 0.40, bz), M["acero"], axis="Y")
    cyl("Cilindro_Barril_Tornillo", 0.08, 1.9, (0, 1.55, bz), M["acero"], axis="Y")
    box("Cubierta_Resistencias", (0.36, 1.75, 0.30), (0, 1.55, bz + 0.02), M["negro"], 0.02)
    box("Bancada_Extrusora", (0.62, 2.55, 0.55), (0, 1.95, 0.32), M["negro"], 0.02)
    for k in range(3):
        cyl(f"Tapa_Calefactor_{k + 1}", 0.11, 0.18, (0, 0.95 + k * 0.40, bz + 0.22), M["negro"], verts=4,
            r2=0.11).rotation_euler = (0, 0, math.pi / 4)
        # ventiladores blancos de enfriamiento al costado
        cyl(f"Ventilador_Enfriamiento_{k + 1}", 0.10, 0.08, (0.36, 0.95 + k * 0.40, 0.55), M["blanco"], axis="X")
        cyl(f"Motor_Ventilador_{k + 1}", 0.05, 0.12, (0.46, 0.95 + k * 0.40, 0.55), M["blanco"], axis="X")

    grupo("14_Tolva_y_Alimentador")
    hx, hy = 0, 2.40
    box("Caja_Alimentador", (0.50, 0.45, 0.62), (hx, hy, bz + 0.56), M["blanco"], 0.02)
    box("Ventana_Alimentador", (0.30, 0.01, 0.40), (hx, hy - 0.23, bz + 0.56), M["negro"])
    cyl("Garganta_Tolva", 0.06, 0.10, (hx, hy, bz + 0.92), M["negro"])
    cyl("Tolva_Conica", 0.08, 0.45, (hx, hy, bz + 1.20), M["negro"], r2=0.42, bevel=0.005)
    cyl("Tolva_Borde", 0.42, 0.18, (hx, hy, bz + 1.51), M["negro"], bevel=0.005)

    grupo("15_Reductor_y_Motor_Principal")
    box("Reductor_Principal", (0.50, 0.45, 0.50), (0, 3.45, 0.75), M["aluminio"], 0.03)
    cyl("Motor_Principal", 0.22, 0.55, (0, 3.95, 0.72), M["aluminio"], axis="Y", bevel=0.02)
    for k in range(14):
        a = k * math.tau / 14
        box("Aleta_Motor_Principal", (0.015, 0.45, 0.04),
            (math.cos(a) * 0.225, 3.95, 0.72 + math.sin(a) * 0.225), M["aluminio"], rot=(0, -a, 0))
    cyl("Tapa_Motor_Principal", 0.20, 0.08, (0, 4.26, 0.72), M["aluminio"], axis="Y", bevel=0.02)

    grupo("16_Soplador_de_Aire")
    bx, by = -0.95, -0.85
    cyl("Soplador_Voluta", 0.26, 0.20, (bx, by, 0.32), M["gris_oscuro"], axis="X", bevel=0.02)
    cyl("Motor_Soplador", 0.12, 0.25, (bx - 0.22, by, 0.32), M["gris_oscuro"], axis="X", bevel=0.01)
    box("Base_Soplador", (0.50, 0.40, 0.06), (bx - 0.08, by, 0.03), M["negro"], 0.01)

    grupo("17_Mangueras_de_Aire")
    RD, ZD = 0.55, 0.62
    dist = bpy.data.curves.new("Anillo_Distribuidor_Aire", "CURVE")
    dist.dimensions = "3D"
    dist.bevel_depth = 0.05
    sp = dist.splines.new("NURBS")
    sp.points.add(31)
    for i in range(32):
        a = i * math.tau / 32
        sp.points[i].co = (RD * math.cos(a), RD * math.sin(a), ZD, 1)
    sp.use_cyclic_u = True
    link(bpy.data.objects.new("Anillo_Distribuidor_Aire", dist), None)
    for a in angs:
        c, sn = math.cos(a), math.sin(a)
        curve_tube("Manguera_Aire", [Vector((RD * c, RD * sn, ZD + 0.04)), Vector((0.78 * c, 0.78 * sn, 0.85)),
                                     Vector((0.66 * c, 0.66 * sn, DIE_Z - 0.05)),
                                     Vector((0.50 * c, 0.50 * sn, DIE_Z - 0.03))], 0.045, M["manguera"])
    a = math.radians(225)
    curve_tube("Manguera_Alimentacion_Soplador", [Vector((bx, by + 0.12, 0.45)), Vector((bx + 0.30, by + 0.35, 0.55)),
                                                  Vector((RD * math.cos(a), RD * math.sin(a), ZD - 0.04))],
               0.07, M["manguera"])


# ---------------------------------------------------------------------------
# Tablero de control
# ---------------------------------------------------------------------------
def control_panel():
    grupo("18_Tablero_Electrico")
    x, y = -1.45, 2.90
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
    beam("Ducto", (x - 0.2, y, 2.55), (x - 0.2, CY, 2.55), 0.08, M["gris_panel"])


# ---------------------------------------------------------------------------
# Escalera de gato (negra) al costado derecho
# ---------------------------------------------------------------------------
def ladder():
    grupo("19_Escalera")
    x = -(PX + 0.40)
    stair((x, -2.55, 0.0), (x, -0.32, PZ), 0.70)


# ---------------------------------------------------------------------------
# Embobinadora (frente)
# ---------------------------------------------------------------------------
def winder():
    # ============================ IMPRESORA FLEXOGRAFICA ============================
    grupo("22_Impresora_Flexografica")
    y0, hw = IMP_Y, 0.85
    box("Impresora_Base", (2 * hw + 0.2, 1.40, 0.12), (0, y0, 0.06), M["negro"], 0.005)
    for sx in (-1, 1):
        box("Impresora_Bastidor", (0.12, 1.10, 2.05), (sx * hw, y0, 0.12 + 1.025), M["gris_panel"], 0.01)
    # viga superior en voladizo con rodillos guia y aspirador
    box("Impresora_Viga_Superior", (2 * hw + 0.30, 1.75, 0.32), (0, y0 + 0.25, 2.33), M["gris_panel"], 0.01)
    for dy in (0.80, 0.45, 0.05):
        cyl("Impresora_Rodillo_Guia_Superior", 0.04, 2 * hw + 0.1, (0, y0 + dy, 2.55), M["cromo"], axis="X")
    cyl("Impresora_Aspirador", 0.16, 0.18, (hw - 0.25, y0 - 0.35, 2.58), M["gris_panel"], bevel=0.01)
    curve_tube("Impresora_Ducto_Aspiracion", [Vector((hw - 0.25, y0 - 0.35, 2.67)), Vector((hw - 0.25, y0 - 0.2, 3.05)),
                                               Vector((hw - 0.25, y0 + 1.6, 3.10))], 0.06, M["aluminio"])
    # gabinete lateral del operador con puertas oscuras y panel de mandos
    xc = hw + 0.30
    box("Impresora_Gabinete", (0.45, 0.95, 2.05), (xc, y0 - 0.05, 0.12 + 1.025), M["gris_panel"], 0.01)
    for k in (-1, 1):
        box("Impresora_Puerta", (0.01, 0.42, 1.50), (xc + 0.23, y0 - 0.05 + k * 0.22, 0.95), M["gris_oscuro"])
    box("Impresora_Panel_Mandos", (0.01, 0.30, 0.45), (xc + 0.235, y0 + 0.30, 1.75), M["blanco"])
    for r in range(4):
        for c in range(3):
            cyl("Impresora_Pulsador", 0.014, 0.02, (xc + 0.24, y0 + 0.21 + c * 0.09, 1.88 - r * 0.08),
                M["rojo"] if (r + c) % 2 else M["verde"], axis="X", verts=12)
    # dos grupos de impresion (arriba y abajo): cilindro portaclise, anilox, rodillo tintero y bandeja
    for nm, zg, yg in (("Superior", 1.55, IMP_Y + 0.35), ("Inferior", 0.88, IMP_Y + 0.10)):
        g = f"Grupo_Impresion_{nm}"
        cyl(f"{g}_Cilindro_Impresion", 0.09, 2 * hw - 0.12, (0, yg - 0.10, zg), M["cromo"], axis="X")
        cyl(f"{g}_Cilindro_Portaclise", 0.08, 2 * hw - 0.12, (0, yg + 0.08, zg), M["negro"], axis="X")
        cyl(f"{g}_Rodillo_Anilox", 0.06, 2 * hw - 0.12, (0, yg + 0.22, zg - 0.04), M["cromo"], axis="X")
        cyl(f"{g}_Rodillo_Tintero", 0.05, 2 * hw - 0.12, (0, yg + 0.33, zg - 0.10), M["goma"], axis="X")
        box(f"{g}_Bandeja_Tinta", (2 * hw - 0.2, 0.18, 0.08), (0, yg + 0.33, zg - 0.19), M["negro"], 0.005)
        for sx in (-1, 1):
            box(f"{g}_Soporte", (0.10, 0.30, 0.22), (sx * (hw - 0.10), yg + 0.15, zg), M["negro"], 0.01)
            beam(f"{g}_Brazo_Ajuste", (sx * (hw + 0.07), yg + 0.30, zg - 0.05), (sx * (hw + 0.07), yg + 0.70, zg - 0.45),
                 0.03, M["aluminio"])
    cyl("Impresora_Rodillo_Salida", 0.04, 2 * hw - 0.12, (0, IMP_Y - 0.15, 0.78), M["cromo"], axis="X")
    cyl("Impresora_Motor", 0.10, 0.25, (-hw - 0.10, y0 + 0.35, 0.30), M["aluminio"], axis="X", bevel=0.01)

    # ============================ TROQUELADORA ============================
    grupo("23_Troqueladora")
    y0, hw = TRQ_Y, 0.85
    L = 1.80
    box("Troqueladora_Cuerpo", (2 * hw, L, 0.85), (0, y0, 0.10 + 0.425), M["blanco"], 0.012)
    for sx in (-1, 1):
        box("Troqueladora_Panel_Negro", (0.01, L - 0.30, 0.62), (sx * (hw + 0.006), y0, 0.50), M["negro"])
    box("Troqueladora_Zocalo", (2 * hw - 0.04, L - 0.04, 0.10), (0, y0, 0.05), M["gris_oscuro"])
    box("Troqueladora_Mesa", (2 * hw - 0.10, L - 0.10, 0.04), (0, y0, 0.97), M["aluminio"])
    # unidad de troquel: viga con cilindros neumaticos
    box("Troqueladora_Viga_Troquel", (2 * hw - 0.10, 0.16, 0.12), (0, y0 + 0.40, 1.12), M["gris_panel"], 0.005)
    for k in range(6):
        cyl("Troqueladora_Cilindro_Neumatico", 0.035, 0.16, (-0.55 + k * 0.22, y0 + 0.40, 1.26), M["aluminio"], verts=16)
    # bandeja blanca curva (cubierta de malla) sobre postes
    prof = [(-0.70, 1.20), (-0.35, 1.36), (0.0, 1.40), (0.35, 1.36), (0.70, 1.20)]
    for sx in (-1, 1):
        verts = [(sx * (hw - 0.05) - 0.02, y0 + py * 0.9, pz) for py, pz in prof]
        verts += [(sx * (hw - 0.05) + 0.02, y0 + py * 0.9, pz) for py, pz in prof]
        vv = verts + [(x, y, z - 0.06) for (x, y, z) in verts]
        n = len(prof)
        faces = []
        for i in range(n - 1):
            a, b = i, i + 1
            faces += [(a, b, n + b, n + a), (2 * n + a, 3 * n + a, 3 * n + b, 2 * n + b),
                      (a, 2 * n + a, 2 * n + b, b), (n + a, n + b, 3 * n + b, 3 * n + a)]
        mesh_from("Troqueladora_Arco_Bandeja", vv, faces, M["blanco"], smooth=False)
    for py, pz in prof:
        box("Troqueladora_Liston_Bandeja", (2 * hw - 0.10, 0.10, 0.025), (0, y0 + py * 0.9, pz - 0.02), M["blanco"])
    for sx in (-1, 1):
        for py in (-0.35, 0.35):
            cyl("Troqueladora_Poste_Bandeja", 0.018, 0.30, (sx * 0.55, y0 + py, 1.12), M["acero"], verts=12)
    # rodillos de entrada (verdes) y de salida
    cyl("Troqueladora_Rodillo_Entrada", 0.05, 2 * hw - 0.06, (0, y0 + L / 2 - 0.05, 0.98), M["verde"], axis="X")
    cyl("Troqueladora_Rodillo_Salida", 0.05, 2 * hw - 0.06, (0, y0 - L / 2 + 0.05, 0.98), M["cromo"], axis="X")
    # gabinete de control aparte (HMI, botonera, senal de riesgo electrico)
    cx_, cy_ = hw + 0.32, y0 - 0.55
    box("Troqueladora_Gabinete_Control", (0.55, 0.50, 1.05), (cx_, cy_, 0.06 + 0.525), M["blanco"], 0.01)
    box("Troqueladora_Puerta_Gabinete", (0.01, 0.40, 0.70), (cx_ + 0.28, cy_, 0.48), M["negro"])
    box("Troqueladora_Pantalla_HMI", (0.18, 0.13, 0.012), (cx_ - 0.08, cy_, 1.115), M["negro"])
    for c in range(4):
        cyl("Troqueladora_Pulsador", 0.015, 0.02, (cx_ + 0.12, cy_ - 0.12 + c * 0.08, 1.12), M["rojo"], verts=12)
    mesh_from("Troqueladora_Senal_Riesgo",
              [(cx_ + 0.287, cy_ - 0.08, 0.80), (cx_ + 0.287, cy_ + 0.08, 0.80), (cx_ + 0.287, cy_, 0.94)],
              [(0, 1, 2)], M["amarillo"], smooth=False)
    # aspiracion del recorte: soplador, filtro negro, codo de PVC y manga de malla
    ax_, ay_ = -(hw + 0.45), y0 + 0.35
    cyl("Aspirador_Recorte_Voluta", 0.22, 0.18, (ax_, ay_, 0.30), M["gris_oscuro"], axis="X", bevel=0.01)
    cyl("Aspirador_Recorte_Filtro", 0.17, 1.05, (ax_, ay_, 0.95), M["negro"], bevel=0.01)
    cyl("Aspirador_Recorte_Tapa", 0.19, 0.06, (ax_, ay_, 1.50), M["negro"])
    curve_tube("Aspirador_Recorte_Codo_PVC", [Vector((ax_, ay_, 1.52)), Vector((ax_, ay_, 1.78)),
                                              Vector((ax_, ay_ - 0.20, 1.86)), Vector((ax_, ay_ - 0.48, 1.78))],
               0.10, M["blanco"])
    cyl("Aspirador_Recorte_Manga_Malla", 0.36, 1.70, (ax_, ay_ - 0.48, 0.88), M["verde"], r2=0.10, verts=32)
    for k, yy in enumerate((y0 - 0.20, y0 - 0.55)):
        curve_tube("Aspirador_Recorte_Manguera_Azul",
                   [Vector((ax_ + 0.10, ay_ - 0.05, 0.22)), Vector((ax_ + 0.25, (ay_ + yy) / 2, 0.12 + 0.05 * k)),
                    Vector((-hw - 0.05, yy, 0.55))], 0.05, M["azul"])
    # poste de salida con rodillo que sube la lamina al puente
    for sx in (-1, 1):
        box("Poste_Salida_Troqueladora", (0.08, 0.08, OVZ), (sx * 0.85, y0 - 1.18, OVZ / 2), M["blanco"], 0.004)
    cyl("Rodillo_Salida_Alto", 0.045, 1.62, (0, y0 - 1.18, OVZ - 0.06), M["cromo"], axis="X")
    cyl("Rodillo_Salida_Bajo", 0.045, 1.62, (0, y0 - 1.15, 0.97), M["cromo"], axis="X")

    # ============================ PUENTE AEREO DE RODILLOS ============================
    grupo("24_Puente_Aereo_Rodillos")
    ya, yz = TRQ_Y - 1.18, EMB_Y[1] - 1.75
    for sx in (-1, 1):
        beam("Puente_Tubo_Longitudinal", (sx * 0.80, ya, OVZ + 0.10), (sx * 0.80, yz, OVZ + 0.10), 0.07, M["acero"],
             round_=True)
        for yp in (EMB_Y[0] - 1.85, yz):
            box("Puente_Poste", (0.08, 0.08, OVZ + 0.10), (sx * 0.80, yp, (OVZ + 0.10) / 2), M["negro"], 0.004)
    for yp in (EMB_Y[0] - 1.85, yz):
        box("Puente_Travesano", (1.68, 0.08, 0.08), (0, yp, OVZ + 0.14), M["negro"], 0.004)
    for y0 in EMB_Y:
        cyl("Puente_Rodillo", 0.04, 1.56, (0, y0 - 0.05, OVZ + 0.0), M["cromo"], axis="X")
    cyl("Puente_Rodillo", 0.04, 1.56, (0, (ya + EMB_Y[0]) / 2, OVZ + 0.0), M["cromo"], axis="X")

    # ============================ DOS EMBOBINADORAS EN TANDEM ============================
    for k, y0 in enumerate(EMB_Y, start=1):
        grupo(f"2{4 + k}_Embobinadora_{k}")
        tg = f"Embobinadora_{k}"
        hw = 0.75
        Lw = 1.70
        yc = y0 - Lw / 2
        box(f"{tg}_Base", (2 * hw + 0.10, Lw, 0.10), (0, yc, 0.05), M["negro"], 0.005)
        for sx in (-1, 1):
            # costado alto atras y bajo adelante, con paneles oscuros
            box(f"{tg}_Bastidor_Alto", (0.14, 0.70, 1.55), (sx * hw, y0 - 0.35, 0.10 + 0.775), M["blanco"], 0.01)
            box(f"{tg}_Bastidor_Bajo", (0.14, Lw - 0.70, 0.75), (sx * hw, y0 - 0.70 - (Lw - 0.70) / 2, 0.10 + 0.375),
                M["blanco"], 0.01)
            box(f"{tg}_Panel_Oscuro", (0.01, 0.55, 0.60), (sx * (hw + 0.075), y0 - 0.35, 0.50), M["gris_oscuro"])
            box(f"{tg}_Panel_Oscuro", (0.01, 0.80, 0.50), (sx * (hw + 0.075), y0 - 1.20, 0.40), M["gris_oscuro"])
        # columna de control con HMI y botonera (lado izquierdo, atras)
        tx = -(hw + 0.27)
        box(f"{tg}_Columna_Control", (0.40, 0.45, 1.80), (tx, y0 - 0.35, 0.10 + 0.90), M["blanco"], 0.01)
        box(f"{tg}_Panel_Control", (0.01, 0.32, 0.75), (tx - 0.205, y0 - 0.35, 1.30), M["negro"])
        box(f"{tg}_Pantalla_HMI", (0.012, 0.20, 0.14), (tx - 0.212, y0 - 0.35, 1.55), M["gris_oscuro"])
        for r in range(3):
            for c in range(3):
                cyl(f"{tg}_Pulsador", 0.014, 0.02, (tx - 0.215, y0 - 0.43 + c * 0.08, 1.32 - r * 0.07),
                    M["rojo"] if (r + c) % 2 else M["verde"], axis="X", verts=12)
        box(f"{tg}_Gabinete_Bajo", (0.40, 0.45, 0.70), (tx, y0 - 0.80, 0.10 + 0.35), M["blanco"], 0.01)
        box(f"{tg}_Puerta_Gabinete", (0.01, 0.36, 0.55), (tx - 0.205, y0 - 0.80, 0.45), M["gris_oscuro"])
        # rodillos de entrada, tambor de goma marron, bobina
        cyl(f"{tg}_Rodillo_Entrada", 0.045, 2 * hw - 0.12, (0, y0 - 0.15, 1.58), M["cromo"], axis="X")
        cyl(f"{tg}_Rodillo_Tension", 0.05, 2 * hw - 0.12, (0, y0 - 0.45, 1.30), M["cromo"], axis="X")
        cyl(f"{tg}_Barra_Ajuste", 0.03, 2 * hw - 0.12, (0, y0 - 0.30, 1.42), M["negro"], axis="X")
        cyl(f"{tg}_Tambor_Goma", 0.16, 2 * hw - 0.12, (0, y0 - 0.85, 0.82), M["goma"], axis="X", verts=64)
        rr = 0.22
        yb_, zb_ = y0 - 0.85 - (0.16 + rr) * 0.80, 0.82 + (0.16 + rr) * 0.60
        cyl(f"{tg}_Bobina", rr, 2 * LAYFLAT + 0.02, (0, yb_, zb_), M["bobina"], axis="X", verts=96, bevel=0.01)
        cyl(f"{tg}_Nucleo_Carton", 0.045, 2 * LAYFLAT + 0.08, (0, yb_, zb_), M["carton"], axis="X")
        cyl(f"{tg}_Eje_Bobina", 0.032, 2 * hw + 0.50, (0, yb_, zb_), M["acero"], axis="X")
        for sx in (-1, 1):
            cyl(f"{tg}_Mandril", 0.055, 0.07, (sx * (hw + 0.14), yb_, zb_), M["negro"], axis="X", verts=6)
            beam(f"{tg}_Brazo_Bobina", (sx * (hw + 0.08), y0 - 0.70, 0.80), (sx * (hw + 0.08), yb_, zb_ - 0.04),
                 0.05, M["blanco"], t2=0.09)
        cyl(f"{tg}_Rodillo_Piso", 0.05, 2 * hw + 0.05, (0, y0 - Lw + 0.10, 0.25), M["acero"], axis="X")
        # manguera neumatica naranja en espiral (frente)
        mx_, my_ = hw + 0.10, y0 - Lw + 0.20
        pts = []
        for i in range(60):
            a = i * 0.45
            pts.append(Vector((mx_ + 0.05 * math.cos(a), my_ + 0.05 * math.sin(a), 0.65 - i * 0.008)))
        curve_tube(f"{tg}_Manguera_Espiral", pts, 0.006, M["rojo"], res=4)


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
    "TamborGomaTrasera": "Tambor_Goma_Estacion_Trasera",
    "TapaTamborRojaTrasera": "Tapa_Tambor_Roja_Estacion_Trasera",
    "EjeVerdeTrasera": "Eje_Manga_Verde_Estacion_Trasera",
    "MangaVerdeTrasera": "Manga_Verde_Estacion_Trasera",
    "BobinaTrasera": "Bobina_Estacion_Trasera",
    "NucleoTrasera": "Nucleo_Carton_Estacion_Trasera",
    "EjeBobinaTrasera": "Eje_Bobina_Estacion_Trasera",
    "MandrilTrasera": "Mandril_Estacion_Trasera",
    "BrazoBobinaTrasera": "Brazo_Porta_Bobina_Estacion_Trasera",
    "TamborGomaDelantera": "Tambor_Goma_Estacion_Delantera",
    "TapaTamborRojaDelantera": "Tapa_Tambor_Roja_Estacion_Delantera",
    "EjeVerdeDelantera": "Eje_Manga_Verde_Estacion_Delantera",
    "MangaVerdeDelantera": "Manga_Verde_Estacion_Delantera",
    "BobinaDelantera": "Bobina_Estacion_Delantera",
    "NucleoDelantera": "Nucleo_Carton_Estacion_Delantera",
    "EjeBobinaDelantera": "Eje_Bobina_Estacion_Delantera",
    "MandrilDelantera": "Mandril_Estacion_Delantera",
    "BrazoBobinaDelantera": "Brazo_Porta_Bobina_Estacion_Delantera",
    "BastidorBajoTrasero": "Bastidor_Bajo_Trasero", "BastidorBajoDelantero": "Bastidor_Bajo_Delantero",
    "GuardaNegra": "Guarda_Negra_Frontal", "TravesanoAlto": "Travesano_Cuerpo_Alto",
    "PostePuente": "Poste_Puente_Rodillos", "LaminaEstacionTrasera": "Lamina_Hoja_a_Estacion_Trasera",
    "LaminaEstacionDelantera": "Lamina_Hoja_a_Estacion_Delantera",
    ("20", "RodilloGuia"): "Rodillo_Guia_Embobinadora", ("20", "TorreControl"): "Columna_Control_Embobinadora",
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
out = os.path.join(here, "extrusora6_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en",
      len(bpy.data.collections) - 1, "grupos", flush=True)
