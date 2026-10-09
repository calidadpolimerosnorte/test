"""
Escena Blender: Extrusora Nº 1 (linea de pelicula soplada / blown film).

Uso:
    blender -b -P blender/extrusora.py -- --out renders/extrusora --samples 128
    # o con el modulo bpy de PyPI:
    python3 blender/extrusora.py --out renders/extrusora --samples 128

Genera la escena completa de forma procedural, guarda extrusora.blend y
renderiza las camaras definidas con Cycles.
"""
import math
import os
import sys
import argparse

import bpy
import bmesh
from mathutils import Vector, Matrix


# ---------------------------------------------------------------------------
# Argumentos
# ---------------------------------------------------------------------------
argv = sys.argv
argv = argv[argv.index("--") + 1:] if "--" in argv else argv[1:]
ap = argparse.ArgumentParser()
ap.add_argument("--out", default="renders/extrusora")
ap.add_argument("--samples", type=int, default=128)
ap.add_argument("--res", type=float, default=1.0, help="escala de resolucion")
ap.add_argument("--cams", default="principal,frontal,lateral")
ap.add_argument("--blend", default="blender/extrusora.blend")
args = ap.parse_args(argv)


# ---------------------------------------------------------------------------
# Escena limpia
# ---------------------------------------------------------------------------
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
col = scene.collection


# ---------------------------------------------------------------------------
# Materiales
# ---------------------------------------------------------------------------
def principled(name, color, rough=0.5, metal=0.0, emission=None, strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if emission:
        b.inputs["Emission Color"].default_value = (*emission, 1)
        b.inputs["Emission Strength"].default_value = strength
    return m


def film_material(name, opacity):
    """Pelicula plastica translucida: mezcla de transparente + lechoso brillante."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (0.97, 0.98, 1.0, 1)
    pb = nt.nodes.new("ShaderNodeBsdfPrincipled")
    pb.inputs["Base Color"].default_value = (0.92, 0.94, 0.95, 1)
    pb.inputs["Roughness"].default_value = 0.18
    pb.inputs["Coat Weight"].default_value = 0.6
    pb.inputs["Coat Roughness"].default_value = 0.05
    # el borde (angulo rasante) se ve mas opaco, como el film real
    fres = nt.nodes.new("ShaderNodeLayerWeight")
    fres.inputs["Blend"].default_value = 0.35
    mr = nt.nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = opacity
    mr.inputs["To Max"].default_value = min(1.0, opacity + 0.45)
    nt.links.new(fres.outputs["Facing"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(pb.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return m


def noise_material(name, c1, c2, rough=0.6, scale=8.0, bump=0.05, detail=8.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = detail
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*c1, 1)
    ramp.color_ramp.elements[1].color = (*c2, 1)
    ramp.color_ramp.elements[0].position = 0.35
    ramp.color_ramp.elements[1].position = 0.7
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = bump
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], b.inputs["Base Color"])
    nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


def concrete_material():
    m = noise_material("Concreto", (0.36, 0.36, 0.35), (0.55, 0.55, 0.53),
                       rough=0.4, scale=2.0, bump=0.02)
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    # juntas del piso (losas de 3 m) con textura de ladrillo
    tc = nt.nodes.new("ShaderNodeTexCoord")
    br = nt.nodes.new("ShaderNodeTexBrick")
    br.inputs["Scale"].default_value = 1.0 / 3.0
    br.inputs["Mortar Size"].default_value = 0.008
    br.inputs["Brick Width"].default_value = 1.0
    br.inputs["Row Height"].default_value = 1.0
    br.offset = 0.0
    br.inputs["Color1"].default_value = (1, 1, 1, 1)
    br.inputs["Color2"].default_value = (1, 1, 1, 1)
    br.inputs["Mortar"].default_value = (0.35, 0.35, 0.35, 1)
    ramp = [n for n in nt.nodes if n.type == "VALTORGB"][0]
    mul = nt.nodes.new("ShaderNodeMix")
    mul.data_type = "RGBA"
    mul.blend_type = "MULTIPLY"
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(tc.outputs["Object"], br.inputs["Vector"])
    nt.links.new(ramp.outputs["Color"], mul.inputs["A"])
    nt.links.new(br.outputs["Color"], mul.inputs["B"])
    nt.links.new(mul.outputs["Result"], b.inputs["Base Color"])
    return m


def corrugated_material():
    """Plancha metalica ondulada (TR4) de las paredes."""
    m = bpy.data.materials.new("PlanchaOndulada")
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.42, 0.45, 0.49, 1)
    b.inputs["Metallic"].default_value = 0.55
    b.inputs["Roughness"].default_value = 0.38
    tc = nt.nodes.new("ShaderNodeTexCoord")
    wv = nt.nodes.new("ShaderNodeTexWave")
    wv.wave_type = "BANDS"
    wv.bands_direction = "X"
    wv.wave_profile = "SIN"
    wv.inputs["Scale"].default_value = 1.0
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    mth = nt.nodes.new("ShaderNodeMath")
    mth.operation = "MULTIPLY"
    mth.inputs[1].default_value = 1.0 / 0.25  # nervio cada 25 cm
    comb = nt.nodes.new("ShaderNodeCombineXYZ")
    bp = nt.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 1.0
    bp.inputs["Distance"].default_value = 0.05
    nt.links.new(tc.outputs["UV"], sep.inputs[0])
    nt.links.new(sep.outputs["X"], mth.inputs[0])
    nt.links.new(mth.outputs[0], comb.inputs["X"])
    nt.links.new(comb.outputs[0], wv.inputs["Vector"])
    nt.links.new(wv.outputs["Fac"], bp.inputs["Height"])
    nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
    return m


M = {
    "blanco": principled("PinturaBlanca", (0.82, 0.84, 0.83), 0.32),
    "negro": principled("PinturaNegra", (0.018, 0.018, 0.02), 0.38),
    "negro_mate": principled("NegroMate", (0.03, 0.03, 0.03), 0.7),
    "acero": principled("Acero", (0.80, 0.80, 0.82), 0.18, 1.0),
    "cromo": principled("Cromo", (0.92, 0.92, 0.93), 0.06, 1.0),
    "aluminio": principled("Aluminio", (0.75, 0.76, 0.78), 0.35, 1.0),
    "gris_panel": principled("GrisTablero", (0.70, 0.71, 0.70), 0.4),
    "gris_oscuro": principled("GrisOscuro", (0.12, 0.13, 0.14), 0.5),
    "manguera": noise_material("Manguera", (0.30, 0.31, 0.32), (0.55, 0.56, 0.57),
                               rough=0.55, scale=40, bump=0.3),
    "madera": noise_material("Madera", (0.28, 0.15, 0.06), (0.52, 0.33, 0.16),
                             rough=0.6, scale=12, bump=0.05),
    "azul": principled("AzulMotor", (0.03, 0.14, 0.55), 0.3),
    "azul_letrero": principled("AzulLetrero", (0.02, 0.08, 0.32), 0.35),
    "amarillo": principled("Amarillo", (0.95, 0.72, 0.02), 0.35),
    "rojo_led": principled("RojoLED", (0.6, 0.02, 0.01), 0.3, 0, (1.0, 0.05, 0.02), 6),
    "verde_led": principled("VerdeLED", (0.02, 0.5, 0.05), 0.3, 0, (0.1, 1.0, 0.15), 4),
    "rojo": principled("Rojo", (0.55, 0.02, 0.02), 0.3),
    "verde": principled("Verde", (0.02, 0.35, 0.05), 0.3),
    "goma": principled("Goma", (0.02, 0.02, 0.02), 0.85),
    "bobina": noise_material("Bobina", (0.86, 0.87, 0.88), (0.94, 0.95, 0.96),
                             rough=0.35, scale=60, bump=0.02),
    "carton": principled("Carton", (0.55, 0.38, 0.2), 0.7),
    "saco": noise_material("Saco", (0.80, 0.81, 0.82), (0.92, 0.92, 0.93),
                           rough=0.75, scale=25, bump=0.15),
    "film": film_material("PeliculaBurbuja", 0.16),
    "film_doble": film_material("PeliculaDoble", 0.32),
    "concreto": concrete_material(),
    "pared": corrugated_material(),
    "techo": principled("Techo", (0.88, 0.88, 0.88), 0.7),
    "estructura": principled("EstructuraGris", (0.22, 0.24, 0.26), 0.45, 0.4),
    "luz": principled("Lampara", (1, 1, 1), 0.5, 0, (1.0, 0.97, 0.92), 25),
    "verde_salida": principled("VerdeSalida", (0.02, 0.45, 0.12), 0.4),
    "pallet": noise_material("Pallet", (0.40, 0.28, 0.15), (0.6, 0.45, 0.28),
                             rough=0.7, scale=6, bump=0.1),
    "azul_tacho": principled("AzulTacho", (0.02, 0.10, 0.45), 0.35),
}


# ---------------------------------------------------------------------------
# Utilidades de geometria
# ---------------------------------------------------------------------------
def link(obj, mat):
    col.objects.link(obj)
    if mat is not None:
        obj.data.materials.append(mat)
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
    # rodillo guia bajo la plataforma
    cyl("RodilloPlataforma", 0.05, 2 * 0.62, (0, -0.56, PZ - 0.37), M["acero"], axis="X")
    for sx in (-1, 1):
        box("SoporteRodillo", (0.03, 0.12, 0.22), (sx * 0.64, -0.56, PZ - 0.26), M["blanco"])


# ---------------------------------------------------------------------------
# Extrusora (planta baja): cabezal, anillo de aire, husillo, tolva, soplador
# ---------------------------------------------------------------------------
def extruder():
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
    # Tolva
    hx, hy = 0, 2.12
    cyl("Garganta", 0.11, 0.25, (hx, hy, bz + 0.2), M["negro"], bevel=0.005)
    cyl("TolvaCono", 0.12, 0.35, (hx, hy, bz + 0.5), M["negro"], r2=0.30, bevel=0.005)
    cyl("Tolva", 0.30, 0.50, (hx, hy, bz + 0.92), M["negro"], bevel=0.01)
    cyl("TapaTolva", 0.31, 0.03, (hx, hy, bz + 1.18), M["negro"], bevel=0.005)
    cyl("Visor", 0.032, 0.30, (hx + 0.298, hy, bz + 0.92), M["film"], verts=16)
    # Reductor + motor principal
    box("ReductorPpal", (0.55, 0.45, 0.55), (0, 2.85, 0.55), M["negro"], 0.03)
    cyl("MotorPpal", 0.22, 0.6, (0, 3.35, 0.5), M["negro"], axis="Y", bevel=0.02)
    for k in range(16):
        a = k * math.tau / 16
        box("AletaMotor", (0.015, 0.5, 0.04),
            (math.cos(a) * 0.225, 3.35, 0.5 + math.sin(a) * 0.225), M["negro"], rot=(0, -a, 0))
    cyl("TapaMotorPpal", 0.2, 0.08, (0, 3.69, 0.5), M["negro"], axis="Y", bevel=0.02)

    # Soplador centrifugo (detras-derecha)
    bx, by = 0.95, 0.55
    cyl("Voluta", 0.34, 0.24, (bx, by, 0.42), M["negro"], axis="X", bevel=0.02)
    box("Descarga", (0.24, 0.3, 0.22), (bx, by - 0.28, 0.66), M["negro"], 0.02)
    cyl("MotorSoplador", 0.15, 0.3, (bx + 0.27, by, 0.42), M["negro"], axis="X", bevel=0.01)
    box("BaseSoplador", (0.6, 0.5, 0.08), (bx + 0.1, by, 0.04), M["negro"], 0.01)
    cyl("Colector", 0.16, 0.2, (bx, by - 0.45, 0.7), M["negro"], bevel=0.01)

    # Mangueras flexibles (gris, corrugadas) desde el colector al anillo
    src = Vector((bx, by - 0.45, 0.72))
    for k in range(nh):
        a = k * math.tau / nh + 0.3
        end = Vector((math.cos(a) * 0.48, math.sin(a) * 0.48, DIE_Z - 0.04))
        out = Vector((math.cos(a) * 0.75, math.sin(a) * 0.75, 0.35))
        st = src + Vector((math.cos(a) * 0.12, math.sin(a) * 0.12, 0.0))
        mid = (st + out) / 2 + Vector((0, 0, -0.15))
        curve_tube("Manguera", [st, mid, out, end], 0.045, M["manguera"])
        # anillos de la manguera (corrugado)
    # Tacho azul y sacos de resina al pie
    cyl("Tacho", 0.24, 0.62, (-1.55, 0.55, 0.31), M["azul_tacho"], r2=0.27, bevel=0.01)
    for i, (x, y, rz) in enumerate([(-0.9, -0.95, 0.2), (-0.55, -1.15, -0.25), (-1.05, -1.4, 0.4),
                                     (0.55, -1.0, 0.1), (-0.75, -1.2, -0.1)]):
        s = box("Saco", (0.48, 0.75, 0.13), (x, y, 0.065 + (0.12 if i == 4 else 0)), M["saco"], 0.05,
                rot=(0, 0, rz))
        s.modifiers.new("Sub", "SUBSURF").levels = 2


# ---------------------------------------------------------------------------
# Tablero de control
# ---------------------------------------------------------------------------
def control_panel():
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
# Galpon: piso, paredes de plancha ondulada, techo, luces, utileria
# ---------------------------------------------------------------------------
def building():
    W, D, H = 26.0, 22.0, 9.0
    bpy.ops.mesh.primitive_plane_add(size=1)
    fl = bpy.context.active_object
    fl.name = "Piso"
    fl.scale = (W, D, 1)
    fl.location = (2, 3, 0)
    fl.data.materials.append(M["concreto"])

    def wall(name, loc, size, rot):
        bpy.ops.mesh.primitive_plane_add(size=1)
        w = bpy.context.active_object
        w.name = name
        w.location = loc
        w.rotation_euler = rot
        w.scale = (size[0], size[1], 1)
        w.data.materials.append(M["pared"])
        # UV en metros para el ondulado
        for lp in w.data.loops:
            uv = w.data.uv_layers.active.data[lp.index].uv
            uv.x *= size[0]
            uv.y *= size[1]
        return w

    back_y = 4.2
    wall("ParedFondo", (2, back_y, H / 2), (W, H), (math.pi / 2, 0, 0))
    wall("ParedDerecha", (8.5, 3, H / 2), (D, H), (math.pi / 2, 0, math.pi / 2))
    wall("ParedIzq", (-6.5, 3, H / 2), (D, H), (math.pi / 2, 0, -math.pi / 2))
    # estructura de la fachada: vigas horizontales y columnas
    for z in (0.9, 3.4, 6.2, 8.4):
        box("VigaPared", (W, 0.08, 0.12), (2, back_y - 0.05, z), M["estructura"])
        box("VigaPared", (0.08, D, 0.12), (8.45, 3, z), M["estructura"])
        box("VigaPared", (0.08, D, 0.12), (-6.45, 3, z), M["estructura"])
    for x in (-5.0, -2.5, 0.0, 2.5, 5.0, 7.5):
        box("MontantePared", (0.08, 0.08, H), (x, back_y - 0.05, H / 2), M["estructura"])
    for y in (-6, -3.5, -1.0, 1.5, 4.0):
        box("MontantePared", (0.08, 0.08, H), (8.45, y, H / 2), M["estructura"])
        box("MontantePared", (0.08, 0.08, H), (-6.45, y, H / 2), M["estructura"])
    # columnas de concreto blancas del galpon
    for x in (-3.6, 4.2):
        box("ColumnaGalpon", (0.5, 0.45, H), (x, back_y - 0.25, H / 2), M["techo"], 0.01)
    # tuberias de aire comprimido (azules) a lo largo de la pared
    beam("TuboAire", (-6.4, back_y - 0.35, 3.6), (8.4, back_y - 0.35, 3.6), 0.04, M["azul"], round_=True)
    beam("TuboAire", (-6.4, back_y - 0.5, 3.75), (8.4, back_y - 0.5, 3.75), 0.05, M["gris_oscuro"], round_=True)
    beam("TuboAire", (1.1, back_y - 0.35, 3.6), (1.1, 0.4, 3.0), 0.035, M["aluminio"], round_=True)
    # techo
    bpy.ops.mesh.primitive_plane_add(size=1, location=(2, 3, H))
    ce = bpy.context.active_object
    ce.name = "Techo"
    ce.scale = (W, D, 1)
    ce.rotation_euler = (math.pi, 0, 0)
    ce.data.materials.append(M["techo"])
    # lamparas LED colgantes (visibles) + luces de area
    for (x, y) in [(-2.5, -1.5), (2.5, -1.5), (-2.5, 2.5), (2.5, 2.5), (7, 0.5), (7, -4), (-2.5, -5.5), (2.5, -5.5)]:
        cyl("Lampara", 0.22, 0.08, (x, y, H - 1.2), M["luz"], verts=32)
        cyl("Campana", 0.25, 0.10, (x, y, H - 1.12), M["gris_oscuro"], verts=32)
        beam("Cable", (x, y, H - 1.05), (x, y, H), 0.008, M["negro"], round_=True)
        ld = bpy.data.lights.new("LuzArea", "AREA")
        ld.shape = "DISK"
        ld.size = 0.5
        ld.energy = 500
        ld.color = (1.0, 0.97, 0.92)
        lo = bpy.data.objects.new("LuzArea", ld)
        lo.location = (x, y, H - 1.26)
        col.objects.link(lo)
    # relleno suave (luz de las ventanas/techo)
    for (loc, rot, e, s) in [((-4, -8, 6), (math.radians(70), 0, math.radians(-25)), 1600, 8),
                             ((6, -6, 7), (math.radians(60), 0, math.radians(35)), 800, 6)]:
        ld = bpy.data.lights.new("Relleno", "AREA")
        ld.size = s
        ld.energy = e
        lo = bpy.data.objects.new("Relleno", ld)
        lo.location = loc
        lo.rotation_euler = rot
        col.objects.link(lo)

    # senales verdes de "SALIDA" y botiquin
    for (x, z) in [(-0.9, 2.2), (3.2, 2.2)]:
        box("Salida", (0.3, 0.01, 0.16), (x, back_y - 0.02, z), M["verde_salida"])
        text("TxtSalida", "← SALIDA", 0.045, (x, back_y - 0.03, z), M["blanco"])
    box("Botiquin", (0.36, 0.12, 0.42), (5.4, back_y - 0.07, 1.5), M["blanco"], 0.01)
    box("Cruz", (0.12, 0.01, 0.04), (5.4, back_y - 0.135, 1.6), M["rojo"])
    box("Cruz", (0.04, 0.01, 0.12), (5.4, back_y - 0.135, 1.6), M["rojo"])
    cyl("Extintor", 0.08, 0.5, (4.8, back_y - 0.15, 0.95), M["rojo"], bevel=0.02)

    # Pallets con bobinas/rollos de producto (derecha)
    for (px, py) in [(3.6, -0.6), (3.6, 0.9), (4.9, -0.6), (4.9, 0.9), (3.6, 2.4), (6.2, 0.2)]:
        box("Pallet", (1.15, 1.15, 0.14), (px, py, 0.07), M["pallet"], 0.005)
        for (dx, dy) in [(-0.28, -0.28), (0.28, -0.28), (-0.28, 0.28), (0.28, 0.28)]:
            hgt = 0.62
            nlev = 2 if (px + py) % 2 > 0.5 else 1
            for lev in range(nlev):
                cyl("Rollo", 0.27, hgt, (px + dx, py + dy, 0.14 + hgt / 2 + lev * hgt), M["bobina"],
                    verts=48, bevel=0.03)
    # rollos grandes acostados (primer plano izquierdo)
    cyl("RolloGrande", 0.55, 1.3, (-4.3, -2.2, 0.55), M["bobina"], axis="X", verts=96, bevel=0.04)


# ---------------------------------------------------------------------------
# Camaras
# ---------------------------------------------------------------------------
def add_camera(name, loc, target, lens):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    ob = bpy.data.objects.new(name, cd)
    ob.location = loc
    d = Vector(target) - Vector(loc)
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    col.objects.link(ob)
    return ob


tower()
upper_tower()
bubble()
extruder()
control_panel()
ladder()
winder()
building()

cams = {
    "principal": (add_camera("CamPrincipal", (-3.4, -6.4, 1.75), (0.35, -0.2, 2.55), 22), (1200, 1600)),
    "frontal": (add_camera("CamFrontal", (0.6, -7.2, 1.65), (0.2, 0, 2.6), 24), (1200, 1600)),
    "lateral": (add_camera("CamLateral", (4.6, -5.6, 2.1), (0.2, 0.0, 2.6), 22), (1200, 1600)),
}

# Mundo: gris claro tenue
world = bpy.data.worlds.new("Mundo")
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.75, 0.78, 0.8, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.2
scene.world = world

# Render
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 8
scene.cycles.transparent_max_bounces = 24
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -1.6
scene.render.image_settings.file_format = "PNG"

os.makedirs(os.path.dirname(os.path.abspath(args.blend)), exist_ok=True)
scene.camera = cams["principal"][0]
scene.render.resolution_x, scene.render.resolution_y = cams["principal"][1]
bpy.ops.wm.save_as_mainfile(filepath=os.path.abspath(args.blend))

os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
for name in [c for c in args.cams.split(",") if c]:
    cam, (rx, ry) = cams[name]
    scene.camera = cam
    scene.render.resolution_x = int(rx * args.res)
    scene.render.resolution_y = int(ry * args.res)
    scene.render.filepath = os.path.abspath(f"{args.out}_{name}.png")
    print(f"Renderizando {name} -> {scene.render.filepath}", flush=True)
    bpy.ops.render.render(write_still=True)
