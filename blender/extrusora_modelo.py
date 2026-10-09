"""
Modelo Blender limpio de la Extrusora Nº 1 (linea de pelicula soplada).

Solo la maquina: sin materiales/colores, sin animacion, sin galpon, piso,
luces ni camaras. Cada pieza tiene un nombre descriptivo y esta agrupada en
colecciones por sistema (torre, plataforma, extrusora, tablero, etc.).

Uso:
    python3 blender/extrusora_modelo.py            # con bpy de PyPI
    blender -b -P blender/extrusora_modelo.py      # con Blender

Guarda blender/extrusora_modelo.blend.
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
ROOT = bpy.data.collections.new("Extrusora_N1")
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
PZ = 2.80            # cota superior de la plataforma
PX, PY = 1.20, 0.90  # semi-dimensiones de la plataforma
CX, CY = 0.78, 0.62  # columnas inferiores
DIE_Z = 0.98         # parte superior del cabezal / anillo de aire
NIP_Z = 5.05         # rodillos de arrastre (nip)
R_BUB = 0.33         # radio de la burbuja estabilizada
LAYFLAT = math.pi * R_BUB / 2  # semi-ancho de la lamina aplanada


# ---------------------------------------------------------------------------
# Torre: columnas, plataforma, barandas
# ---------------------------------------------------------------------------
def tower():
    grupo("01_Estructura_Torre")
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * CX, sy * CY
            box("Columna", (0.16, 0.16, PZ - 0.12), (x, y, (PZ - 0.12) / 2), M["blanco"], 0.006)
            box("PlacaBase", (0.32, 0.32, 0.02), (x, y, 0.01), M["blanco"], 0.004)
    # vigas bajo plataforma
    for sy in (-1, 1):
        box("VigaX", (2 * PX, 0.14, 0.18), (0, sy * CY, PZ - 0.21), M["blanco"], 0.004)
    for sx in (-1, 1):
        box("VigaY", (0.14, 2 * PY, 0.18), (sx * CX, 0, PZ - 0.21), M["blanco"], 0.004)
    # arriostres en la parte baja (travesanos a 0.5 m)
    box("Travesano", (0.08, 2 * CY, 0.08), (-CX, 0, 0.55), M["blanco"])
    box("Travesano", (0.08, 2 * CY, 0.08), (CX, 0, 0.55), M["blanco"])
    grupo("02_Plataforma")
    # Plataforma con hueco central para la burbuja
    H = 0.48
    t = 0.10
    zc = PZ - t / 2
    box("Plataforma", (2 * PX, PY - H, t), (0, -(PY + H) / 2, zc), M["blanco"], 0.008)
    box("Plataforma", (2 * PX, PY - H, t), (0, (PY + H) / 2, zc), M["blanco"], 0.008)
    box("Plataforma", (PX - H, 2 * H, t), (-(PX + H) / 2, 0, zc), M["blanco"], 0.008)
    box("Plataforma", (PX - H, 2 * H, t), ((PX + H) / 2, 0, zc), M["blanco"], 0.008)
    # canto negro de la plataforma (zocalo)
    for sy in (-1, 1):
        box("Zocalo", (2 * PX + 0.02, 0.02, 0.12), (0, sy * (PY + 0.01), PZ + 0.04), M["negro"])
    for sx in (-1, 1):
        box("Zocalo", (0.02, 2 * PY, 0.12), (sx * (PX + 0.01), 0, PZ + 0.04), M["negro"])

    grupo("03_Barandas")
    # Barandas negras (tubo cuadrado 40 mm)
    rh = 1.05
    tt = 0.04
    gap = (-0.80, -0.20)  # hueco en el lado derecho para la escalera

    def rail_segment(p1, p2, posts=True):
        p1, p2 = Vector(p1), Vector(p2)
        for z in (PZ + rh, PZ + 0.55):
            beam("Baranda", (p1.x, p1.y, z), (p2.x, p2.y, z), tt, M["negro"])
        if posts:
            L = (p2 - p1).length
            n = max(1, round(L / 0.55))
            for i in range(n + 1):
                p = p1.lerp(p2, i / n)
                box("Parante", (tt, tt, rh), (p.x, p.y, PZ + rh / 2), M["negro"])

    ex, ey = PX - 0.02, PY - 0.02
    rail_segment((-ex, -ey, 0), (ex, -ey, 0))
    rail_segment((-ex, ey, 0), (ex, ey, 0))
    rail_segment((-ex, -ey, 0), (-ex, ey, 0))
    rail_segment((ex, -ey, 0), (ex, gap[0], 0))
    rail_segment((ex, gap[1], 0), (ex, ey, 0))

    grupo("04_Letreros")
    # Letrero "EXTRUSORA Nº 1"
    sx, sz = -0.78, PZ + 0.62
    box("Letrero1", (0.34, 0.012, 0.44), (sx, -ey - 0.035, sz), M["blanco"], 0.003)
    box("Letrero1Borde", (0.36, 0.008, 0.46), (sx, -ey - 0.027, sz), M["negro"])
    text("TxtExtrusora", "EXTRUSORA", 0.055, (sx, -ey - 0.043, sz + 0.15), M["negro_mate"])
    text("TxtN", "Nº", 0.05, (sx - 0.11, -ey - 0.043, sz - 0.04), M["negro_mate"])
    text("Txt1", "1", 0.26, (sx + 0.04, -ey - 0.043, sz - 0.06), M["negro_mate"])

    # Letrero azul "UTILIZAR CASCO"
    bx, bz = 0.88, PZ + 0.55
    box("LetreroCasco", (0.26, 0.012, 0.40), (bx, -ey - 0.035, bz), M["blanco"], 0.003)
    box("LetreroCascoAzul", (0.24, 0.006, 0.24), (bx, -ey - 0.043, bz + 0.06), M["azul_letrero"])
    # pictograma del casco (semiesfera simplificada)
    helm = cyl("Casco", 0.06, 0.01, (bx, -ey - 0.048, bz + 0.04), M["blanco"], axis="Y")
    helm.scale = (1, 1, 0.8)
    box("CascoVisera", (0.15, 0.006, 0.015), (bx, -ey - 0.048, bz + 0.0), M["blanco"])
    cyl("Cara", 0.045, 0.006, (bx, -ey - 0.049, bz + 0.07), M["azul_letrero"], axis="Y")
    box("LetreroCascoTxtFondo", (0.24, 0.006, 0.12), (bx, -ey - 0.043, bz - 0.12), M["azul_letrero"])
    text("TxtCasco", "UTILIZAR\nCASCO", 0.04, (bx, -ey - 0.05, bz - 0.12), M["blanco"])


# ---------------------------------------------------------------------------
# Torre superior: marco, canasta colapsadora de madera, rodillos nip, motor
# ---------------------------------------------------------------------------
def upper_tower():
    grupo("05_Torre_Superior_Marco")
    fx, fy = 0.62, 0.42
    top = NIP_Z + 0.32
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
        (-1.62, 1.82),
        (-1.72, 1.75),
        (-1.75, 1.20),
        (-1.82, 1.12),
        (-2.38, 1.10),
        (-2.55, 1.07),
        (-2.82, 0.99),
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
    # Cabezal (dado) y anillo de aire
    cyl("BaseCabezal", 0.20, 0.30, (0, 0, 0.35), M["negro"], bevel=0.01)
    cyl("Cabezal", 0.22, 0.32, (0, 0, DIE_Z - 0.26), M["acero"], bevel=0.01)
    for z in (DIE_Z - 0.34, DIE_Z - 0.24, DIE_Z - 0.14):
        cyl("ResistenciaCabezal", 0.235, 0.06, (0, 0, z), M["aluminio"], bevel=0.005)
    ring = cyl("AnilloAire", 0.40, 0.11, (0, 0, DIE_Z - 0.04), M["gris_oscuro"], verts=64, bevel=0.01)
    lip = cyl("LabioAnillo", 0.24, 0.09, (0, 0, DIE_Z + 0.03), M["aluminio"], verts=64, r2=0.19)
    cyl("Dado", 0.17, 0.02, (0, 0, DIE_Z + 0.0), M["cromo"], verts=64)
    # entradas de mangueras en el anillo
    nh = 6
    for k in range(nh):
        a = k * math.tau / nh + 0.3
        cyl("Entrada", 0.05, 0.10, (math.cos(a) * 0.43, math.sin(a) * 0.43, DIE_Z - 0.04),
            M["gris_oscuro"], axis="X").rotation_euler = (0, 0, a)

    grupo("13_Extrusora_Cilindro_y_Bancada")
    # Husillo / cilindro horizontal hacia atras (+Y)
    bz = 0.62
    cyl("Adaptador", 0.07, 0.4, (0, 0.30, bz), M["acero"], axis="Y")
    cyl("Cilindro", 0.075, 1.7, (0, 1.30, bz), M["acero"], axis="Y")
    for i in range(6):
        cyl("Resistencia", 0.12, 0.14, (0, 0.62 + i * 0.22, bz), M["aluminio"], axis="Y", bevel=0.006)
    box("Cubierta", (0.34, 1.4, 0.06), (0, 1.15, bz + 0.17), M["negro"], 0.01)
    box("BancadaExtrusora", (0.6, 2.3, 0.45), (0, 1.55, 0.225), M["negro"], 0.01)
    # ventiladores de enfriamiento bajo el cilindro
    for i in range(4):
        cyl("Ventilador", 0.08, 0.06, (0, 0.70 + i * 0.3, bz - 0.2), M["negro_mate"])
    grupo("14_Tolva")
    # Tolva
    hx, hy = 0, 2.12
    cyl("Garganta", 0.11, 0.25, (hx, hy, bz + 0.2), M["negro"], bevel=0.005)
    cyl("TolvaCono", 0.12, 0.35, (hx, hy, bz + 0.5), M["negro"], r2=0.30, bevel=0.005)
    cyl("Tolva", 0.30, 0.50, (hx, hy, bz + 0.92), M["negro"], bevel=0.01)
    cyl("TapaTolva", 0.31, 0.03, (hx, hy, bz + 1.18), M["negro"], bevel=0.005)
    cyl("Visor", 0.032, 0.30, (hx + 0.298, hy, bz + 0.92), M["film"], verts=16)
    grupo("15_Reductor_y_Motor_Principal")
    # Reductor + motor principal
    box("ReductorPpal", (0.55, 0.45, 0.55), (0, 2.85, 0.55), M["negro"], 0.03)
    cyl("MotorPpal", 0.22, 0.6, (0, 3.35, 0.5), M["negro"], axis="Y", bevel=0.02)
    for k in range(16):
        a = k * math.tau / 16
        box("AletaMotor", (0.015, 0.5, 0.04),
            (math.cos(a) * 0.225, 3.35, 0.5 + math.sin(a) * 0.225), M["negro"], rot=(0, -a, 0))
    cyl("TapaMotorPpal", 0.2, 0.08, (0, 3.69, 0.5), M["negro"], axis="Y", bevel=0.02)

    grupo("16_Soplador_de_Aire")
    # Soplador centrifugo (detras-derecha)
    bx, by = 0.95, 0.55
    cyl("Voluta", 0.34, 0.24, (bx, by, 0.42), M["negro"], axis="X", bevel=0.02)
    box("Descarga", (0.24, 0.3, 0.22), (bx, by - 0.28, 0.66), M["negro"], 0.02)
    cyl("MotorSoplador", 0.15, 0.3, (bx + 0.27, by, 0.42), M["negro"], axis="X", bevel=0.01)
    box("BaseSoplador", (0.6, 0.5, 0.08), (bx + 0.1, by, 0.04), M["negro"], 0.01)
    cyl("Colector", 0.16, 0.2, (bx, by - 0.45, 0.7), M["negro"], bevel=0.01)

    grupo("17_Mangueras_de_Aire")
    # Mangueras flexibles (gris, corrugadas) desde el colector al anillo
    src = Vector((bx, by - 0.45, 0.72))
    for k in range(nh):
        a = k * math.tau / nh + 0.3
        end = Vector((math.cos(a) * 0.48, math.sin(a) * 0.48, DIE_Z - 0.04))
        out = Vector((math.cos(a) * 0.75, math.sin(a) * 0.75, 0.35))
        st = src + Vector((math.cos(a) * 0.12, math.sin(a) * 0.12, 0.0))
        mid = (st + out) / 2 + Vector((0, 0, -0.15))
        curve_tube("Manguera", [st, mid, out, end], 0.045, M["manguera"])


# ---------------------------------------------------------------------------
# Tablero de control
# ---------------------------------------------------------------------------
def control_panel():
    grupo("18_Tablero_Electrico")
    x, y = 1.95, 0.55
    w, d, h = 0.85, 0.42, 1.75
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
    beam("Ducto", (x - 0.2, y, 2.55), (0.7, y, 2.55), 0.08, M["gris_panel"])


# ---------------------------------------------------------------------------
# Escalera de gato (negra) al costado derecho
# ---------------------------------------------------------------------------
def ladder():
    grupo("19_Escalera")
    y0, y1 = -0.78, -0.22
    top = Vector((PX + 0.02, 0, PZ + 0.02))
    bot = Vector((PX + 0.95, 0, 0.0))
    for y in (y0, y1):
        beam("Larguero", (bot.x, y, bot.z), (top.x, y, top.z), 0.05, M["negro"], t2=0.12)
        # pasamanos que sube por encima de la plataforma
        beam("Pasamano", (bot.x + 0.06, y, 0.95), (top.x + 0.06, y, top.z + 0.95), 0.035, M["negro"])
        beam("Pasamano", (top.x + 0.06, y, top.z + 0.95), (top.x - 0.05, y, top.z + 1.05), 0.035, M["negro"])
        beam("ParantePasamano", (top.x + 0.04, y, top.z), (top.x + 0.06, y, top.z + 0.95), 0.035, M["negro"])
    n = 10
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
    yc = -2.62
    hw = 0.62
    for sx in (-1, 1):
        x = sx * hw
        # placas laterales con forma (perfil poligonal extruido)
        prof = [(-0.42, 0.0), (0.32, 0.0), (0.32, 1.15), (0.10, 1.22), (-0.28, 1.05), (-0.42, 0.75)]
        verts = [(x - 0.015, yc + py, pz) for py, pz in prof] + [(x + 0.015, yc + py, pz) for py, pz in prof]
        n = len(prof)
        faces = [tuple(range(n))[::-1], tuple(range(n, 2 * n))]
        for i in range(n):
            j = (i + 1) % n
            faces.append((i, j, n + j, n + i))
        mesh_from("PlacaLateral", verts, faces, M["blanco"], smooth=False)
        # pernos
        for (py, pz) in [(0.2, 1.05), (0.0, 0.9), (-0.2, 0.8), (0.25, 0.45), (-0.3, 0.3), (0.1, 0.62)]:
            cyl("Perno", 0.015, 0.05, (x, yc + py, pz), M["acero"], axis="X", verts=12)
        box("PataLat", (0.08, 0.84, 0.04), (x, yc - 0.05, 0.02), M["blanco"])
        cyl("Rueda", 0.04, 0.04, (x, yc - 0.42, 0.04), M["goma"], axis="X")
        cyl("Rueda", 0.04, 0.04, (x, yc + 0.32, 0.04), M["goma"], axis="X")
    # travesanos y rodillos
    for (py, pz, r, m) in [(-0.3, 0.22, 0.035, M["blanco"]), (0.2, 0.22, 0.035, M["blanco"]),
                           (0.25, 0.48, 0.035, M["blanco"]), (-0.32, 0.42, 0.035, M["blanco"])]:
        cyl("Travesano", r, 2 * hw, (0, yc + py, pz), m, axis="X")
    cyl("RodilloEntrada", 0.045, 2 * hw, (0, yc + 0.24, 1.07), M["acero"], axis="X")
    cyl("RodilloTension", 0.035, 2 * hw, (0, yc + 0.10, 1.18), M["acero"], axis="X")
    cyl("RodilloArrastre", 0.10, 2 * hw - 0.04, (0, yc + 0.0, 0.96), M["cromo"], axis="X")
    cyl("NucleoCarton", 0.045, 1.15, (0, yc - 0.2, 0.75), M["carton"], axis="X")
    # bobina de film
    cyl("Bobina", 0.23, 2 * LAYFLAT + 0.02, (0, yc - 0.2, 0.75), M["bobina"], axis="X", verts=96, bevel=0.01)
    cyl("EjeBobina", 0.025, 1.6, (0, yc - 0.2, 0.75), M["negro"], axis="X")
    for sx in (-1, 1):
        cyl("Mandril", 0.04, 0.08, (sx * 0.72, yc - 0.2, 0.75), M["negro"], axis="X")
    # cubierta negra del motor/embrague
    cyl("TapaMotor", 0.16, 0.18, (hw + 0.12, yc + 0.0, 0.96), M["negro"], axis="X", bevel=0.02)
    box("TapaMotor2", (0.18, 0.3, 0.28), (hw + 0.12, yc + 0.15, 0.82), M["negro"], 0.03)
    # caja de control de la embobinadora
    box("CajaControl", (0.12, 0.3, 0.42), (hw + 0.08, yc + 0.1, 0.42), M["blanco"], 0.01)
    box("Contador", (0.005, 0.08, 0.04), (hw + 0.142, yc + 0.1, 0.55), M["rojo_led"])
    # cuchilla/guia
    cyl("Guia", 0.02, 2 * hw, (0, yc - 0.05, 1.16), M["negro"], axis="X")

    grupo("21_Soporte_Rodillos_Guia")
    # Soporte de rodillos intermedio (entre torre y embobinadora)
    sy = -1.72
    for sx in (-1, 1):
        x = sx * 0.66
        box("PosteGuia", (0.05, 0.05, 1.9), (x, sy, 0.95), M["acero"], 0.003)
        box("PieGuia", (0.08, 0.5, 0.04), (x, sy, 0.02), M["acero"])
    cyl("RodilloGuia", 0.04, 1.32, (0, sy + 0.08, 1.80), M["acero"], axis="X")
    cyl("RodilloGuia", 0.04, 1.32, (0, sy - 0.07, 1.17), M["acero"], axis="X")
    cyl("BarraGuia", 0.02, 1.32, (0, sy, 1.5), M["acero"], axis="X")


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
out = os.path.join(here, "extrusora_modelo.blend")
bpy.ops.wm.save_as_mainfile(filepath=out)
print("Guardado", out, "-", len(bpy.data.objects), "piezas en",
      len(bpy.data.collections) - 1, "grupos", flush=True)
