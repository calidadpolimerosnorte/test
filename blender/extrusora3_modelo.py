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
LAD_Y = (0.28, 0.86)  # escalera principal: atras-derecha
R_BUB = 0.36         # radio de la burbuja estabilizada
LAYFLAT = math.pi * R_BUB / 2  # semi-ancho de la lamina aplanada


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
    # escalera de gato desde la plataforma principal a la plataforma superior derecha
    lx0, lx1 = fx + 0.15, fx + 0.55
    for x in (lx0, lx1):
        beam("LargueroSup", (x, 0.95, PZ), (x, 0.50, MZ), 0.04, M["negro"], t2=0.08)
    for i in range(1, 8):
        f = i / 8
        box("PeldanoSup", (lx1 - lx0, 0.04, 0.03), ((lx0 + lx1) / 2, 0.95 - 0.45 * f, PZ + (MZ - PZ) * f), M["negro"])
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
        (-1.98, 2.22),
        (-2.06, 2.16),
        (-2.12, 1.80),
        (-2.30, 1.18),
        (-2.62, 1.05),
        (-2.92, 1.14),
        (-3.20, 1.00),
        (-3.55, 1.06),
        (-3.82, 0.98),
        (-4.12, 1.01),
        (-4.45, 0.95),
        (-4.88, 1.08),
    ]
    verts, faces = [], []
    for (y, z) in path:
        verts += [(-w, y, z), (w, y, z)]
    for i in range(len(path) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    mesh_from("Lamina", verts, faces, M["film_doble"], smooth=True)
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
    y0, y1 = LAD_Y
    top = Vector((PX + 0.02, 0, PZ + 0.02))
    bot = Vector((PX + 0.85, 0, 0.0))
    for y in (y0, y1):
        beam("Larguero", (bot.x, y, bot.z), (top.x, y, top.z), 0.05, M["negro"], t2=0.12)
        # pasamanos que sube por encima de la plataforma
        beam("Pasamano", (bot.x + 0.06, y, 0.95), (top.x + 0.06, y, top.z + 0.95), 0.035, M["negro"])
        beam("Pasamano", (top.x + 0.06, y, top.z + 0.95), (top.x - 0.05, y, top.z + 1.05), 0.035, M["negro"])
        beam("ParantePasamano", (top.x + 0.04, y, top.z), (top.x + 0.06, y, top.z + 0.95), 0.035, M["negro"])
    n = 11
    for i in range(1, n + 1):
        p = bot.lerp(top, i / (n + 0.4))
        box("Peldano", (0.16, y1 - y0, 0.03), (p.x, (y0 + y1) / 2, p.z), M["negro"])
    # ruedas/topes al pie
    for y in (y0, y1):
        box("Pie", (0.12, 0.06, 0.03), (bot.x, y, 0.015), M["goma"])


# ---------------------------------------------------------------------------
# Embobinadora (frente)
# ---------------------------------------------------------------------------
def winder():
    grupo("20_Embobinadora")
    hw = 0.72
    ya, yb = -2.00, -4.95          # fondo (portico) y frente
    # largueros de base y travesanos
    for sx in (-1, 1):
        box("LargueroBase", (0.12, ya - yb + 0.2, 0.12), (sx * hw, (ya + yb) / 2, 0.06), M["blanco"], 0.005)
        box("Pie", (0.16, 0.16, 0.02), (sx * hw, ya + 0.05, 0.01), M["blanco"])
        box("Pie", (0.16, 0.16, 0.02), (sx * hw, yb + 0.20, 0.01), M["blanco"])
    for y in (ya + 0.1, (ya + yb) / 2, yb + 0.3):
        cyl("Travesano", 0.045, 2 * hw, (0, y, 0.20), M["blanco"], axis="X")
    # placas laterales con ventanas rectangulares
    prof = [(ya, 0.12), (yb + 0.35, 0.12), (yb - 0.05, 0.50), (yb + 0.25, 1.10),
            (-3.30, 1.22), (-2.35, 1.28), (ya, 1.28)]
    cutters = []
    for k, yy in enumerate((-2.45, -2.95, -3.45, -3.95, -4.40)):
        c = box("Ventana", (0.3, 0.28, 0.22), (0, yy, 0.42), None)
        c.hide_render = c.hide_viewport = True
        cutters.append(c)
    for sx in (-1, 1):
        x = sx * hw
        verts = [(x - 0.018, py, pz) for py, pz in prof] + [(x + 0.018, py, pz) for py, pz in prof]
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
            md = pl.modifiers.new("Ventana", "BOOLEAN")
            md.object = c2
            md.operation = "DIFFERENCE"
        for (py, pz) in [(-2.3, 1.12), (-2.62, 0.98), (-2.92, 1.08), (-3.2, 0.92), (-3.55, 1.0),
                         (-3.82, 0.84), (-4.12, 0.95), (-4.45, 0.80)]:
            cyl("Rodamiento", 0.05, 0.05, (x + sx * 0.04, py, pz), M["negro"], axis="X", verts=16)
    # rodillos (y, z, radio, tipo)
    rolls = [(-2.30, 1.12, 0.05, "RodilloEmb"), (-2.62, 0.98, 0.06, "RodilloEmb"),
             (-2.92, 1.08, 0.05, "RodilloEmb"), (-3.20, 0.92, 0.07, "RodilloCromado"),
             (-3.55, 1.00, 0.05, "RodilloEmb"), (-3.82, 0.84, 0.13, "TamborCromado"),
             (-4.12, 0.95, 0.05, "RodilloEmb"), (-4.45, 0.80, 0.14, "TamborCromado"),
             (-4.20, 0.55, 0.05, "RodilloEmb")]
    for py, pz, r, nm in rolls:
        cyl(nm, r, 2 * hw - 0.04, (0, py, pz), M["cromo"], axis="X")
    # ejes de bobinado al frente (dos estaciones) con mandriles
    for (py, pz) in ((-4.85, 0.95), (-4.92, 0.36)):
        cyl("EjeBobinado", 0.04, 2 * hw + 0.55, (0, py, pz), M["acero"], axis="X")
        for sx in (-1, 1):
            cyl("Mandril", 0.06, 0.08, (sx * (hw + 0.12), py, pz), M["negro"], axis="X", verts=6)
            cyl("Mandril", 0.05, 0.05, (sx * (hw + 0.22), py, pz), M["acero"], axis="X", verts=12)
    # brazos delanteros inclinados
    for sx in (-1, 1):
        beam("BrazoFrontal", (sx * (hw + 0.05), yb + 0.25, 0.70), (sx * (hw + 0.05), yb - 0.15, 1.00),
             0.05, M["blanco"], t2=0.10)
    # motorreductor azul (lado derecho) y servomotores negros (lado izquierdo)
    xr = hw + 0.10
    box("ReductorEmb", (0.16, 0.22, 0.22), (xr, -3.20, 0.62), M["azul"], 0.015)
    cyl("MotorEmb", 0.09, 0.30, (xr + 0.02, -3.20, 0.88), M["azul"], bevel=0.008)
    cyl("TapaMotorEmb", 0.09, 0.05, (xr + 0.02, -3.20, 1.05), M["azul"], bevel=0.008)
    xl = -(hw + 0.12)
    for yy in (-3.05, -3.55):
        box("ReductorServo", (0.16, 0.18, 0.18), (xl, yy, 0.40), M["negro"], 0.012)
        cyl("Servomotor", 0.08, 0.30, (xl, yy + 0.22, 0.40), M["negro"], axis="Y", bevel=0.01)
    # portico trasero con rodillos de entrada
    for sx in (-1, 1):
        box("PosteGuia", (0.10, 0.10, 1.05), (sx * hw, ya, 1.28 + 0.52), M["blanco"], 0.004)
    box("TravesanoGuia", (2 * hw + 0.10, 0.10, 0.10), (0, ya, 2.30), M["blanco"], 0.004)
    cyl("RodilloGuia", 0.045, 2 * hw - 0.06, (0, ya + 0.04, 2.18), M["cromo"], axis="X")
    cyl("RodilloGuia", 0.045, 2 * hw - 0.06, (0, ya - 0.08, 1.80), M["cromo"], axis="X")
    cyl("BarraGuia", 0.03, 2 * hw - 0.06, (0, ya - 0.06, 1.55), M["negro"], axis="X")
    # caja de control blanca sobre un poste (lado izquierdo, atras)
    box("PosteCaja", (0.06, 0.06, 0.55), (-(hw + 0.18), ya - 0.30, 1.55), M["blanco"])
    box("CajaControl", (0.45, 0.26, 0.42), (-(hw + 0.18), ya - 0.30, 2.02), M["blanco"], 0.01)
    fy = ya - 0.30 - 0.135
    for r in range(3):
        for c in range(4):
            cyl("Pulsador", 0.016, 0.02, (-(hw + 0.18) - 0.135 + c * 0.09, fy, 2.10 - r * 0.07),
                M["rojo"], axis="Y", verts=16)
    box("Contador", (0.12, 0.005, 0.04), (-(hw + 0.18), fy, 2.18), M["rojo_led"])
    # canaleta flexible de cables desde la torre
    curve_tube("CanaletaCables", [Vector((-(hw + 0.18), ya - 0.30, 2.23)), Vector((-0.6, -1.4, 2.6)),
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
    "PorticoSup": "Portico_Superior", "CarroCabezal": "Carro_Cabezal", "PataCarro": "Pata_Carro_Cabezal",
    "RuedaCarro": "Rueda_Carro_Cabezal", "CajaControlCabezal": "Caja_Control_Cabezal",
    "PataBancada": "Pata_Bancada", "ZocaloBancada": "Zocalo_Bancada", "MangueraRollo": "Manguera_Enrollada",
    "LargueroBase": "Larguero_Base_Embobinadora", "Rodamiento": "Rodamiento_Embobinadora",
    "RodilloEmb": "Rodillo_Embobinadora", "RodilloCromado": "Rodillo_Cromado_Embobinadora",
    "TamborCromado": "Tambor_Cromado", "EjeBobinado": "Eje_Bobinado", "BrazoFrontal": "Brazo_Frontal",
    "ReductorEmb": "Reductor_Embobinadora", "MotorEmb": "Motor_Embobinadora",
    "TapaMotorEmb": "Tapa_Motor_Embobinadora", "ReductorServo": "Reductor_Servomotor",
    "Servomotor": "Servomotor", "TravesanoGuia": "Travesano_Portico_Embobinadora",
    "PosteCaja": "Poste_Caja_Control", "CanaletaCables": "Canaleta_Flexible_Cables",
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
