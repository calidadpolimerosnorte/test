"""
Modelo Blender limpio de la Extrusora Nº 3 (linea de pelicula soplada).

Solo la maquina: sin materiales/colores, sin animacion, sin galpon, piso,
luces ni camaras. Cada pieza tiene un nombre descriptivo y esta agrupada en
colecciones por sistema (torre, plataforma, extrusora, tablero, etc.).

Uso:
    python3 blender/extrusora3_modelo.py           # con bpy de PyPI
    blender -b -P blender/extrusora3_modelo.py     # con Blender

Guarda blender/extrusora3_modelo.blend.
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
ROOT = bpy.data.collections.new("Extrusora_N3")
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
PZ = 3.10            # cota superior de la plataforma (mas alta que la Nº 1)
PX, PY = 1.45, 1.10  # semi-dimensiones de la plataforma
CX, CY = 1.28, 0.93  # columnas inferiores (casi en las esquinas)
DIE_Z = 1.05         # parte superior del cabezal / anillo de aire
NIP_Z = PZ + 2.55    # rodillos de arrastre (nip)
MZ = PZ + 2.05       # plataformas laterales superiores (servicio del nip)
LAD_Y = (0.28, 0.86)
WC = -3.40           # centro de la embobinadora doble (frente hacia -Y)
WL = 1.45            # semilargo de la embobinadora  # escalera principal: atras-derecha
R_BUB = 0.36         # radio de la burbuja estabilizada
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
            box("Columna", (0.20, 0.20, PZ - 0.14), (x, y, (PZ - 0.14) / 2), M["blanco"], 0.006)
            box("PlacaBase", (0.42, 0.42, 0.025), (x, y, 0.0125), M["blanco"], 0.004)
            for k in range(4):
                cyl("PernoAnclaje", 0.018, 0.04, (x + (k % 2 - 0.5) * 0.3, y + (k // 2 - 0.5) * 0.3, 0.045),
                    M["acero"], verts=6)
    # vigas perimetrales de canto alto bajo la plataforma
    for sy in (-1, 1):
        box("VigaX", (2 * PX, 0.16, 0.30), (0, sy * CY, PZ - 0.29), M["blanco"], 0.004)
    for sx in (-1, 1):
        box("VigaY", (0.16, 2 * PY, 0.30), (sx * CX, 0, PZ - 0.29), M["blanco"], 0.004)
    # vigas interiores que cargan la torre superior
    for sx in (-1, 1):
        box("VigaInterior", (0.12, 2 * CY, 0.22), (sx * 0.72, 0, PZ - 0.25), M["blanco"], 0.004)
    # riostras: cartabones cortos y diagonales largas hacia el centro (cercha)
    zb = PZ - 1.15
    for sy in (-1, 1):
        for sx in (-1, 1):
            beam("Riostra", (sx * CX, sy * CY, zb + 0.45), (sx * (CX - 0.55), sy * CY, PZ - 0.45),
                 0.09, M["blanco"])
            beam("RiostraLarga", (sx * CX, sy * CY, zb), (sx * 0.30, sy * CY, PZ - 0.45), 0.09, M["blanco"])
    for sx in (-1, 1):
        for sy in (-1, 1):
            beam("Riostra", (sx * CX, sy * CY, zb + 0.45), (sx * CX, sy * (CY - 0.55), PZ - 0.45),
                 0.09, M["blanco"])
    # cartelas triangulares en los encuentros columna-viga
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * CX, sy * CY
            for (dx, dy) in ((-sx, 0), (0, -sy)):
                t = 0.006
                ox, oy = -dy * t, dx * t
                p0 = (x + dx * 0.10, y + dy * 0.10)
                p1 = (x + dx * 0.40, y + dy * 0.40)
                zt = PZ - 0.44
                v = [(p0[0], p0[1], zt), (p1[0], p1[1], zt), (p0[0], p0[1], zt - 0.30)]
                verts = [(a + ox, b + oy, c) for a, b, c in v] + [(a - ox, b - oy, c) for a, b, c in v]
                faces = [(0, 1, 2), (5, 4, 3), (0, 3, 4, 1), (1, 4, 5, 2), (2, 5, 3, 0)]
                mesh_from("Cartela", verts, faces, M["blanco"], smooth=False)

    grupo("02_Plataforma")
    H = 0.50
    t = 0.12
    zc = PZ - t / 2
    box("Plataforma", (2 * PX, PY - H, t), (0, -(PY + H) / 2, zc), M["blanco"], 0.008)
    box("Plataforma", (2 * PX, PY - H, t), (0, (PY + H) / 2, zc), M["blanco"], 0.008)
    box("Plataforma", (PX - H, 2 * H, t), (-(PX + H) / 2, 0, zc), M["blanco"], 0.008)
    box("Plataforma", (PX - H, 2 * H, t), ((PX + H) / 2, 0, zc), M["blanco"], 0.008)
    for sy in (-1, 1):
        box("Zocalo", (2 * PX + 0.02, 0.02, 0.12), (0, sy * (PY + 0.01), PZ + 0.04), M["negro"])
    for sx in (-1, 1):
        box("Zocalo", (0.02, 2 * PY, 0.12), (sx * (PX + 0.01), 0, PZ + 0.04), M["negro"])

    grupo("03_Barandas")
    rh = 1.05
    tt = 0.04

    def rail_segment(p1, p2, z0=PZ, posts=True):
        p1, p2 = Vector(p1), Vector(p2)
        for z in (z0 + rh, z0 + 0.55):
            beam("Baranda", (p1.x, p1.y, z), (p2.x, p2.y, z), tt, M["negro"])
        if posts:
            L = (p2 - p1).length
            n = max(1, round(L / 0.6))
            for i in range(n + 1):
                p = p1.lerp(p2, i / n)
                box("Parante", (tt, tt, rh), (p.x, p.y, z0 + rh / 2), M["negro"])

    ex, ey = PX - 0.02, PY - 0.02
    rail_segment((-ex, -ey, 0), (ex, -ey, 0))
    rail_segment((-ex, ey, 0), (ex, ey, 0))
    rail_segment((-ex, -ey, 0), (-ex, ey, 0))
    rail_segment((ex, -ey, 0), (ex, LAD_Y[0], 0))      # hueco para la escalera (atras-derecha)
    rail_segment((ex, LAD_Y[1], 0), (ex, ey, 0))

    grupo("04_Letreros")
    # letrero "EXTRUSORA Nº 3" en la cara frontal de la columna delantera derecha
    sx, sz, sy = CX, PZ - 0.62, -CY - 0.105
    box("Letrero1", (0.19, 0.008, 0.28), (sx, sy, sz), M["blanco"], 0.002)
    text("TxtExtrusora", "EXTRUSORA", 0.03, (sx, sy - 0.006, sz + 0.10), M["negro_mate"])
    text("TxtN", "Nº", 0.03, (sx - 0.06, sy - 0.006, sz - 0.01), M["negro_mate"])
    text("Txt1", "3", 0.16, (sx + 0.02, sy - 0.006, sz - 0.03), M["negro_mate"])


# ---------------------------------------------------------------------------
# Torre superior: marco, canasta colapsadora de madera, rodillos nip, motor
# ---------------------------------------------------------------------------
def upper_tower():
    grupo("05_Torre_Superior_Marco")
    fx, fy = 0.72, 0.48
    top = NIP_Z + 0.70   # portico alto
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("ColSup", (0.08, 0.08, top - PZ), (sx * fx, sy * fy, (top + PZ) / 2), M["blanco"], 0.004)
    for z in (PZ + 1.05, top - 0.04):
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

    grupo("05c_Plataformas_Superiores")
    # dos plataformas laterales de servicio a la altura del nip, con barandas
    for sx in (-1, 1):
        x0, x1 = sx * (fx + 0.04), sx * (fx + 0.70)
        xc, w = (x0 + x1) / 2, abs(x1 - x0)
        box("PlataformaSup", (w, 0.95, 0.06), (xc, 0, MZ - 0.03), M["blanco"], 0.004)
        box("CajonPlataformaSup", (w, 0.95, 0.38), (xc, 0, MZ - 0.25), M["negro"], 0.006)
        for z in (MZ + 0.5, MZ + 0.95):
            beam("BarandaSup", (x1, -0.46, z), (x1, 0.46, z), 0.035, M["negro"])
            for sy in (-1, 1):
                beam("BarandaSup", (x0, sy * 0.46, z), (x1, sy * 0.46, z), 0.035, M["negro"])
        for sy in (-1, 1):
            box("ParanteSup", (0.035, 0.035, 0.95), (x1, sy * 0.46, MZ + 0.475), M["negro"])
            box("ParanteSup", (0.035, 0.035, 0.95), (x0, sy * 0.46, MZ + 0.475), M["negro"])
    # escalera metalica desde la plataforma principal a la plataforma superior derecha
    stair(((fx + 0.36), 1.05, PZ), ((fx + 0.36), 0.42, MZ), 0.40, tag="Sup")
    # portico superior alto
    beam("PorticoSup", (-fx, -fy, top + 0.02), (fx, -fy, top + 0.02), 0.10, M["blanco"])

    grupo("08_Canasta_Colapsadora")
    # Canasta colapsadora (dos planos de listones de madera en V)
    z0, z1 = PZ + 0.55, NIP_Z - 0.16
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
    z_frost, z_col0 = DIE_Z + 0.75, PZ + 0.55
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
        (-0.48, PZ + 0.40),
        (-0.50, PZ - 0.32),
        (-0.62, PZ - 0.42),
        (WC + 0.14, 1.80),
        (WC + 0.06, 1.74),
        (WC + 0.02, 1.30),
        (WC, 1.06),
    ]
    # al llegar al centro la manga aplanada se corta por los bordes y cada
    # hoja va a una estacion: delantera (-Y) y trasera (+Y)
    ramas = []
    for sg, nombre in ((-1, "LaminaDelantera"), (1, "LaminaTrasera")):
        ramas.append((nombre, [(WC, 1.06), (WC + sg * 0.30, 0.96), (WC + sg * 0.52, 0.89),
                               (WC + sg * 0.80, 0.82), (WC + sg * 1.10, 0.78), (WC + sg * 1.22, 0.86)]))
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
    # carro con ruedas que sostiene el cabezal
    box("CarroCabezal", (0.75, 0.75, 0.06), (0, 0, 0.30), M["blanco"], 0.005)
    for sx in (-1, 1):
        for sy in (-1, 1):
            box("PataCarro", (0.05, 0.05, 0.22), (sx * 0.33, sy * 0.33, 0.17), M["blanco"])
            cyl("RuedaCarro", 0.045, 0.03, (sx * 0.33, sy * 0.33, 0.045), M["goma"], axis="X", verts=24)
    cyl("BaseCabezal", 0.24, 0.20, (0, 0, 0.43), M["negro"], bevel=0.01)
    cyl("Cabezal", 0.25, 0.42, (0, 0, DIE_Z - 0.30), M["acero"], bevel=0.01)
    # cabezal con aletas (resistencias ceramicas)
    for k in range(8):
        cyl("ResistenciaCabezal", 0.285, 0.022, (0, 0, DIE_Z - 0.48 + k * 0.05), M["aluminio"], bevel=0.003)
    cyl("AnilloAire", 0.52, 0.13, (0, 0, DIE_Z - 0.03), M["negro"], verts=64, bevel=0.01)
    cyl("LabioAnillo", 0.30, 0.10, (0, 0, DIE_Z + 0.06), M["negro"], verts=64, r2=0.24)
    cyl("Dado", 0.20, 0.02, (0, 0, DIE_Z + 0.02), M["cromo"], verts=64)
    box("CajaControlCabezal", (0.30, 0.20, 0.16), (0.05, 0.30, DIE_Z + 0.10), M["gris_panel"], 0.006)
    nh = 6
    for k in range(nh):
        a = k * math.tau / nh + 0.3
        cyl("Entrada", 0.065, 0.12, (math.cos(a) * 0.56, math.sin(a) * 0.56, DIE_Z - 0.03),
            M["negro"], axis="X").rotation_euler = (0, 0, a)

    grupo("13_Extrusora_Cilindro_y_Bancada")
    # extrusora negra hacia atras (+Y), cilindro cubierto por carcasa
    bz = 0.78
    cyl("Adaptador", 0.08, 0.45, (0, 0.40, bz), M["acero"], axis="Y")
    cyl("Cilindro", 0.09, 1.9, (0, 1.55, bz), M["acero"], axis="Y")
    box("Cubierta", (0.40, 1.75, 0.38), (0, 1.55, bz + 0.02), M["negro"], 0.03)
    box("BancadaExtrusora", (0.75, 2.9, 0.50), (0, 2.05, 0.30), M["negro"], 0.02)
    for sy in (-1, 1):
        box("PataBancada", (0.70, 0.10, 0.05), (0, 2.05 + sy * 1.35, 0.025), M["negro"])
    box("ZocaloBancada", (0.77, 2.6, 0.06), (0, 2.05, 0.20), M["aluminio"])

    grupo("14_Tolva")
    # tolva de chapa (tronco de piramide) con tapa de madera
    hx, hy = 0, 2.40
    cyl("Garganta", 0.13, 0.25, (hx, hy, bz + 0.30), M["negro"], verts=4, bevel=0.005).rotation_euler = (0, 0, math.pi / 4)
    cyl("TolvaCono", 0.18, 0.40, (hx, hy, bz + 0.62), M["negro"], verts=4, r2=0.45).rotation_euler = (0, 0, math.pi / 4)
    box("Tolva", (0.64, 0.64, 0.30), (hx, hy, bz + 0.97), M["negro"], 0.01)
    box("TapaTolva", (0.68, 0.68, 0.025), (hx, hy, bz + 1.135), M["madera"], 0.004)

    grupo("15_Reductor_y_Motor_Principal")
    box("ReductorPpal", (0.60, 0.50, 0.55), (0, 3.15, 0.85), M["negro"], 0.03)
    cyl("MotorPpal", 0.24, 0.65, (0, 3.70, 0.82), M["negro"], axis="Y", bevel=0.02)
    for k in range(16):
        a = k * math.tau / 16
        box("AletaMotor", (0.015, 0.55, 0.04),
            (math.cos(a) * 0.245, 3.70, 0.82 + math.sin(a) * 0.245), M["negro"], rot=(0, -a, 0))
    cyl("TapaMotorPpal", 0.22, 0.08, (0, 4.06, 0.82), M["negro"], axis="Y", bevel=0.02)

    grupo("16_Soplador_de_Aire")
    bx, by = -1.00, 0.85
    cyl("Voluta", 0.40, 0.28, (bx, by, 0.48), M["negro"], axis="X", bevel=0.02)
    box("Descarga", (0.28, 0.34, 0.26), (bx, by - 0.32, 0.76), M["negro"], 0.02)
    cyl("MotorSoplador", 0.17, 0.34, (bx - 0.31, by, 0.48), M["negro"], axis="X", bevel=0.01)
    box("BaseSoplador", (0.7, 0.6, 0.08), (bx - 0.1, by, 0.04), M["negro"], 0.01)
    cyl("Colector", 0.20, 0.22, (bx, by - 0.55, 0.82), M["negro"], bevel=0.01)

    grupo("17_Mangueras_de_Aire")
    # mangueras corrugadas negras grandes del colector al anillo
    src = Vector((bx, by - 0.55, 0.84))
    for k in range(nh):
        a = k * math.tau / nh + 0.3
        end = Vector((math.cos(a) * 0.62, math.sin(a) * 0.62, DIE_Z - 0.03))
        out = Vector((math.cos(a) * 0.95, math.sin(a) * 0.95, 0.45))
        st = src + Vector((math.cos(a) * 0.14, math.sin(a) * 0.14, 0.0))
        mid = (st + out) / 2 + Vector((0, 0, -0.30))
        curve_tube("Manguera", [st, mid, out, end], 0.06, M["manguera"])
    # manguera de reserva enrollada en el piso
    for k in range(2):
        ring = bpy.data.curves.new("MangueraRollo", "CURVE")
        ring.dimensions = "3D"
        ring.bevel_depth = 0.055
        sp = ring.splines.new("NURBS")
        n = 24
        sp.points.add(n - 1)
        for i in range(n):
            a = i * math.tau / n
            sp.points[i].co = (0.55 * math.cos(a), 0.40 * math.sin(a), 0.0, 1)
        sp.use_cyclic_u = True
        ob = bpy.data.objects.new("MangueraRollo", ring)
        ob.location = (-0.95 + k * 0.18, -0.45 - k * 0.10, 0.06 + k * 0.08)
        link(ob, None)


# ---------------------------------------------------------------------------
# Tablero de control
# ---------------------------------------------------------------------------
def control_panel():
    grupo("18_Tablero_Electrico")
    x, y = -2.45, 0.55
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
    beam("Ducto", (x - 0.2, y, 2.55), (-CX, y, 2.55), 0.08, M["gris_panel"])


# ---------------------------------------------------------------------------
# Escalera de gato (negra) al costado derecho
# ---------------------------------------------------------------------------
def ladder():
    grupo("19_Escalera")
    # escalera metalica principal (lado derecho, atras): baja hacia +X
    yc = (LAD_Y[0] + LAD_Y[1]) / 2
    stair((PX + 1.55, yc, 0.0), (PX + 0.02, yc, PZ), LAD_Y[1] - LAD_Y[0] - 0.04)


# ---------------------------------------------------------------------------
# Embobinadora (frente)
# ---------------------------------------------------------------------------
def winder():
    grupo("20_Embobinadora_Doble")
    hw = 0.72
    # placas laterales: bajas en los extremos (estaciones) y altas al centro (portico)
    prof = [(WL, 0.40), (WL - 0.20, 0.12), (-WL + 0.20, 0.12), (-WL, 0.40), (-WL + 0.10, 0.80),
            (-0.55, 0.95), (-0.14, 1.82), (0.14, 1.82), (0.55, 0.95), (WL - 0.10, 0.80)]
    cutters = []
    for u in (-0.95, -0.55, 0.55, 0.95):
        c = box("Ventana", (0.3, 0.24, 0.20), (0, WC + u, 0.42), None)
        c.hide_render = c.hide_viewport = True
        cutters.append(c)
    for u, z in ((-0.20, 1.35), (0.20, 1.35), (0.0, 1.05)):
        c = cyl("Agujero", 0.06, 0.3, (0, WC + u, z), None, axis="X", verts=24)
        c.hide_render = c.hide_viewport = True
        cutters.append(c)
    for sx in (-1, 1):
        x = sx * hw
        verts = [(x - 0.02, WC + u, z) for u, z in prof] + [(x + 0.02, WC + u, z) for u, z in prof]
        n = len(prof)
        faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        pl = mesh_from("PlacaLateral", verts, faces, M["blanco"], smooth=False)
        for c in cutters:
            c2 = c.copy()
            c2.location.x = x
            col.objects.link(c2)
            c2.hide_render = c2.hide_viewport = True
            md = pl.modifiers.new("Corte", "BOOLEAN")
            md.object = c2
            md.operation = "DIFFERENCE"
        for u in (-WL + 0.25, 0.0, WL - 0.25):
            box("Pie", (0.14, 0.18, 0.12), (x, WC + u, 0.06), M["blanco"], 0.005)
        for u, z in ((-0.5, 0.82), (0.5, 0.82), (-0.8, 0.75), (0.8, 0.75), (-0.3, 0.92), (0.3, 0.92),
                     (0.0, 1.06), (0.06, 1.74)):
            cyl("Rodamiento", 0.045, 0.05, (x + sx * 0.04, WC + u, z), M["negro"], axis="X", verts=16)
    for u in (-WL + 0.3, -0.6, 0.6, WL - 0.3):
        cyl("Travesano", 0.04, 2 * hw, (0, WC + u, 0.22), M["blanco"], axis="X")
    # portico central: travesano superior, rodillo negro arriba y rodillos de entrada
    box("TravesanoPortico", (2 * hw + 0.04, 0.12, 0.10), (0, WC, 1.86), M["blanco"], 0.005)
    cyl("RodilloSuperior", 0.05, 2 * hw - 0.06, (0, WC + 0.06, 1.98), M["goma"], axis="X")
    for sx in (-1, 1):
        box("SoporteRodilloSup", (0.04, 0.08, 0.14), (sx * (hw - 0.05), WC + 0.06, 1.93), M["blanco"])
    cyl("RodilloEntrada", 0.05, 2 * hw - 0.06, (0, WC + 0.06, 1.74), M["cromo"], axis="X")
    cyl("BarraExpansora", 0.03, 2 * hw - 0.06, (0, WC + 0.02, 1.30), M["negro"], axis="X")
    cyl("RodilloCentral", 0.06, 2 * hw - 0.06, (0, WC, 1.00), M["cromo"], axis="X")
    # cuchillas que cortan los bordes de la manga (separan las dos hojas)
    for sx in (-1, 1):
        box("PortaCuchilla", (0.05, 0.10, 0.12), (sx * (LAYFLAT + 0.01), WC - 0.10, 1.14), M["aluminio"], 0.004)
    beam("BarraCuchillas", (-hw, WC - 0.10, 1.20), (hw, WC - 0.10, 1.20), 0.03, M["acero"], round_=True)
    # rodillos de cada lado (simetricos hacia las dos estaciones)
    for sg in (-1, 1):
        cyl("RodilloGoma", 0.055, 2 * hw - 0.06, (0, WC + sg * 0.30, 0.92), M["goma"], axis="X")
        cyl("RodilloCromado", 0.06, 2 * hw - 0.06, (0, WC + sg * 0.52, 0.82), M["cromo"], axis="X")
        cyl("RodilloCromado", 0.06, 2 * hw - 0.06, (0, WC + sg * 0.80, 0.75), M["cromo"], axis="X")

    # dos estaciones de bobinado: tambor de friccion + eje con bobina apoyada
    for sg, est in ((-1, "Delantera"), (1, "Trasera")):
        grupo(f"21_Estacion_Bobinado_{est}")
        yt = WC + sg * 1.10
        cyl(f"Tambor{est}", 0.15, 2 * hw - 0.04, (0, yt, 0.62), M["cromo"], axis="X", verts=64)
        for sx in (-1, 1):
            cyl(f"EjeTambor{est}", 0.035, 0.12, (sx * (hw + 0.06), yt, 0.62), M["acero"], axis="X")
            cyl(f"TapaRodamientoTambor{est}", 0.07, 0.03, (sx * (hw + 0.035), yt, 0.62), M["negro"], axis="X")
        ys, zs, rr = WC + sg * 1.36, 0.88, 0.20 if sg < 0 else 0.14
        # la bobina descansa sobre el tambor (centro desplazado segun su radio)
        d = 0.15 + rr
        ang = math.atan2(zs - 0.62, abs(ys - yt))
        yb_ = yt + sg * d * math.cos(ang)
        zb_ = 0.62 + d * math.sin(ang)
        cyl(f"Bobina{est}", rr, 2 * LAYFLAT + 0.02, (0, yb_, zb_), M["bobina"], axis="X", verts=96, bevel=0.01)
        cyl(f"Nucleo{est}", 0.045, 2 * LAYFLAT + 0.08, (0, yb_, zb_), M["carton"], axis="X")
        cyl(f"EjeBobinado{est}", 0.035, 2 * hw + 0.60, (0, yb_, zb_), M["acero"], axis="X")
        for sx in (-1, 1):
            cyl(f"Mandril{est}", 0.06, 0.07, (sx * (hw + 0.13), yb_, zb_), M["negro"], axis="X", verts=6)
            cyl(f"Mandril{est}", 0.045, 0.05, (sx * (hw + 0.22), yb_, zb_), M["acero"], axis="X", verts=12)
            # brazo de apoyo del eje (horquilla al extremo de la placa)
            beam(f"Horquilla{est}", (sx * (hw + 0.05), WC + sg * (WL - 0.15), 0.40),
                 (sx * (hw + 0.05), yb_, zb_ - 0.06), 0.05, M["blanco"], t2=0.08)
        # brazo pivotante neumatico que presiona la bobina
        for sx in (-1, 1):
            beam(f"CilindroPresion{est}", (sx * (hw + 0.09), WC + sg * 0.70, 0.35),
                 (sx * (hw + 0.09), yb_ - sg * 0.05, zb_ - 0.12), 0.04, M["aluminio"], round_=True)

    grupo("20_Embobinadora_Doble")
    # caja de control sobre el poste izquierdo del portico, botonera hacia el costado
    xcb = -hw - 0.02
    box("CajaControl", (0.30, 0.48, 0.44), (xcb, WC, 2.10), M["blanco"], 0.01)
    fx_ = xcb - 0.155
    for r in range(3):
        for c in range(4):
            cyl("Pulsador", 0.017, 0.02, (fx_, WC - 0.135 + c * 0.09, 2.15 - r * 0.07), M["rojo"], axis="X", verts=16)
    cyl("ParadaEmergencia", 0.03, 0.03, (fx_ - 0.005, WC - 0.135, 2.24), M["rojo"], axis="X", verts=24)
    box("Contador", (0.005, 0.12, 0.04), (fx_, WC + 0.10, 2.25), M["rojo_led"])
    # unidad de mantenimiento neumatica (filtro-regulador) en la placa izquierda
    for k in range(3):
        box("UnidadNeumatica", (0.06, 0.06, 0.12), (-hw - 0.06, WC + 0.18 + k * 0.07, 1.22), M["aluminio"], 0.004)
    curve_tube("MangueraNeumatica", [Vector((-hw - 0.06, WC + 0.25, 1.15)), Vector((-hw - 0.15, WC + 0.3, 0.8)),
                                     Vector((-hw - 0.10, WC + 0.7, 0.5))], 0.008, M["azul"])
    # servomotores negros con reductores en linea (lado izquierdo, abajo)
    xl = -(hw + 0.13)
    for k, u in enumerate((-0.55, 0.10)):
        box("ReductorServo", (0.18, 0.20, 0.20), (xl, WC + u, 0.42), M["negro"], 0.012)
        cyl("Servomotor", 0.085, 0.34, (xl, WC + u + 0.28, 0.42), M["negro"], axis="Y", bevel=0.01)
        box("ConectorServo", (0.05, 0.08, 0.06), (xl - 0.06, WC + u + 0.40, 0.48), M["negro"], 0.005)
    # motorreductor azul (lado derecho)
    xr = hw + 0.10
    box("ReductorEmb", (0.16, 0.22, 0.22), (xr, WC + 0.35, 0.60), M["azul"], 0.015)
    cyl("MotorEmb", 0.09, 0.30, (xr + 0.02, WC + 0.35, 0.86), M["azul"], bevel=0.008)
    cyl("TapaMotorEmb", 0.09, 0.05, (xr + 0.02, WC + 0.35, 1.03), M["azul"], bevel=0.008)
    # canaleta flexible de cables desde la torre
    curve_tube("CanaletaCables", [Vector((xcb, WC + 0.24, 2.25)), Vector((-0.6, -1.6, 2.7)),
                                  Vector((-0.2, -0.9, PZ - 0.35))], 0.03, M["gris_panel"])


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
out = os.path.join(here, "extrusora3_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en",
      len(bpy.data.collections) - 1, "grupos", flush=True)
