"""
Animacion Blender: Extrusora Nº 1 (linea de pelicula soplada), solo la maquina.

Estados:
    encendida -> burbuja y lamina en movimiento, rodillos/tornillo/bobina
                 girando, pilotos y baliza parpadeando.
    apagada   -> todo detenido, sin burbuja, luces apagadas.

Uso:
    python3 blender/extrusora_animada.py --estado encendida
    python3 blender/extrusora_animada.py --estado apagada
    # o: blender -b -P blender/extrusora_animada.py -- --estado encendida

Guarda blender/extrusora_<estado>.blend, renderiza los cuadros con Cycles y
arma renders/extrusora_<estado>.mp4 con ffmpeg (si esta disponible).
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
ap.add_argument("--estado", choices=["encendida", "apagada"], default="encendida")
ap.add_argument("--samples", type=int, default=32)
ap.add_argument("--res", type=float, default=1.0, help="escala de resolucion")
ap.add_argument("--segundos", type=float, default=6.0)
ap.add_argument("--fps", type=int, default=24)
ap.add_argument("--frames", default="", help="rango a renderizar, p.ej. 1-10 (vacio = todos)")
ap.add_argument("--still", type=int, default=0, help="renderiza solo este cuadro como PNG")
ap.add_argument("--no-render", action="store_true")
args = ap.parse_args(argv)
ON = args.estado == "encendida"


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
    # irregularidades del film (calibre/tratamiento) que viajan con la lamina:
    # UV.y = distancia recorrida; el Mapping se anima para que el patron avance.
    uv = nt.nodes.new("ShaderNodeUVMap")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (5.0, 2.2, 1.0)
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 1.0
    nz.inputs["Detail"].default_value = 4.0
    rmp = nt.nodes.new("ShaderNodeMapRange")
    rmp.inputs["From Min"].default_value = 0.42
    rmp.inputs["From Max"].default_value = 0.72
    rmp.inputs["To Min"].default_value = 0.0
    rmp.inputs["To Max"].default_value = 0.30
    add = nt.nodes.new("ShaderNodeMath")
    add.operation = "ADD"
    add.use_clamp = True
    nt.links.new(uv.outputs["UV"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], nz.inputs["Vector"])
    nt.links.new(nz.outputs["Fac"], rmp.inputs["Value"])
    nt.links.new(mr.outputs["Result"], add.inputs[0])
    nt.links.new(rmp.outputs["Result"], add.inputs[1])
    nt.links.new(add.outputs[0], mix.inputs["Fac"])
    nt.links.new(tr.outputs[0], mix.inputs[1])
    nt.links.new(pb.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    FILM_MAPS.append(mp)
    return m


FILM_MAPS = []   # nodos Mapping del film a animar
ROTORS = []      # (objeto, eje, velocidad angular rad/s)
BLINKS = []      # (material, intensidad, periodo s, fase s); periodo 0 = fijo
LEDS = []        # materiales emisivos que se apagan con la maquina
LIGHT_BLINKS = []  # (luz, energia, periodo s, fase s)
GROWERS = []     # (objeto, escala inicial, escala final) en ejes radiales


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


def led(name, color, emis, strength, period=0.0, phase=0.0):
    """Material emisivo propio (para poder animarlo) de piloto/display."""
    m = principled(name, color, 0.3, 0, emis, strength)
    LEDS.append(m)
    BLINKS.append((m, strength, period, phase))
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
    "rojo": principled("Rojo", (0.55, 0.02, 0.02), 0.3),
    "verde": principled("Verde", (0.02, 0.35, 0.05), 0.3),
    "goma": principled("Goma", (0.02, 0.02, 0.02), 0.85),
    "bobina": noise_material("Bobina", (0.80, 0.82, 0.84), (0.95, 0.96, 0.97),
                             rough=0.35, scale=18, bump=0.04),
    "carton": principled("Carton", (0.55, 0.38, 0.2), 0.7),
    "film": film_material("PeliculaBurbuja", 0.16),
    "film_doble": film_material("PeliculaDoble", 0.32),
}
D_ROJO = led("DisplayRojo", (0.6, 0.02, 0.01), (1.0, 0.05, 0.02), 6)
D_VERDE = led("DisplayVerde", (0.02, 0.5, 0.05), (0.1, 1.0, 0.15), 4)


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


def mesh_from(name, verts, faces, mat, smooth=True, solidify=0.0, uvs=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    if uvs is not None:
        # uvs: un (u, v) por vertice (o funcion poligono/indice -> uv)
        layer = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                layer.data[li].uv = uvs(poly, vi) if callable(uvs) else uvs[vi]
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
V_FILM = 0.45        # velocidad de la lamina (m/s) en la animacion
V_LAMINA0 = 0.0
ANIM_EMPTIES = []    # empties que suben con el film (ondulacion de la burbuja)


def rotor(ob, radius=None, axis=0, omega=None, marks=True, mark_mat=None):
    """Registra un objeto que gira. Si se da el radio, gira a la velocidad del film.
    Agrega pequenas marcas en las puntas para que el giro se note."""
    w = omega if omega is not None else V_FILM / radius
    ROTORS.append((ob, axis, w))
    if marks and radius:
        L = 2 * max(abs(v.co[axis]) for v in ob.data.vertices)
        for sgn in (-1, 1):
            m = box("MarcaGiro", (0.004, radius * 0.25, radius * 0.6), (0, 0, 0), mark_mat or M["negro"])
            m.location = (sgn * (L / 2 + 0.002), 0, radius * 0.45)
            m.parent = ob
    return ob


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
    rail_segment((ex, -ey, 0), (ex, ey, 0))

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
    rotor(cyl("NipCromo", 0.085, 2 * fx + 0.1, (0, -0.088, NIP_Z), M["cromo"], axis="X"), 0.085)
    nip2 = rotor(cyl("NipGoma", 0.085, 2 * fx - 0.05, (0, 0.088, NIP_Z), M["goma"], axis="X"), 0.085,
                 mark_mat=M["amarillo"])
    ROTORS[-1] = (nip2, 0, -V_FILM / 0.085)
    for sx in (-1, 1):
        cyl("EjeNip", 0.03, 0.25, (sx * (fx + 0.06), -0.088, NIP_Z), M["acero"], axis="X")
        cyl("EjeNip", 0.03, 0.25, (sx * (fx + 0.06), 0.088, NIP_Z), M["acero"], axis="X")
        # cilindros neumaticos de presion
        cyl("Neumatico", 0.035, 0.28, (sx * (fx + 0.06), 0.22, NIP_Z + 0.36), M["aluminio"])
        cyl("Vastago", 0.01, 0.12, (sx * (fx + 0.06), 0.22, NIP_Z + 0.16), M["cromo"])
    # rodillo de retorno arriba-adelante
    rotor(cyl("RodilloRetorno", 0.05, 2 * fx, (0, -0.42, NIP_Z + 0.12), M["acero"], axis="X"), 0.05)
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
    # UV: u alrededor de la burbuja, v = longitud de arco recorrida (m)
    vlen = [0.0]
    for i in range(1, len(prof)):
        dz = prof[i][0] - prof[i - 1][0]
        da = (prof[i][1] + prof[i][2]) / 2 - (prof[i - 1][1] + prof[i - 1][2]) / 2
        vlen.append(vlen[-1] + math.hypot(dz, da))

    def bub_uv(poly, vi):
        ring, k = divmod(vi, seg)
        if k == 0 and any(v % seg == seg - 1 for v in poly.vertices):
            k = seg
        return (2.0 * k / seg, vlen[ring])

    global V_LAMINA0
    V_LAMINA0 = vlen[-1]
    if ON:
        bub = mesh_from("Burbuja", verts, faces, M["film"], uvs=bub_uv)
        # ondulacion suave de la burbuja que sube con el aire
        tex = bpy.data.textures.new("OndaBurbuja", "CLOUDS")
        tex.noise_scale = 0.35
        drv = bpy.data.objects.new("OndaBurbujaCtrl", None)
        col.objects.link(drv)
        ANIM_EMPTIES.append(drv)
        md = bub.modifiers.new("Onda", "DISPLACE")
        md.texture = tex
        md.texture_coords = "OBJECT"
        md.texture_coords_object = drv
        md.strength = 0.018
        md.mid_level = 0.5

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
    verts, faces, uvs = [], [], []
    acc = V_LAMINA0
    for i, (y, z) in enumerate(path):
        if i:
            acc += math.hypot(y - path[i - 1][0], z - path[i - 1][1])
        verts += [(-w, y, z), (w, y, z)]
        uvs += [(0.0, acc), (2 * w, acc)]
    for i in range(len(path) - 1):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    mesh_from("Lamina", verts, faces, M["film_doble"], smooth=True, uvs=uvs)
    # rodillo guia bajo la plataforma
    rotor(cyl("RodilloPlataforma", 0.05, 2 * 0.62, (0, -0.56, PZ - 0.37), M["acero"], axis="X"), 0.05)
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

    # Cilindro (barril) horizontal hacia la izquierda (-X) con un corte de
    # seccion al frente para ver el tornillo girando adentro.
    bz = 0.62
    cyl("Adaptador", 0.08, 0.4, (-0.30, 0, bz), M["acero"], axis="X")
    barrel = cyl("Cilindro", 0.10, 1.7, (-1.30, 0, bz), M["acero"], axis="X", verts=64)
    bore = cyl("Agujero", 0.066, 1.9, (-1.30, 0, bz), None, axis="X", verts=64)
    win = box("Ventana", (1.18, 0.4, 0.4), (-1.28, -0.2, bz + 0.17), None)
    for h in (bore, win):
        h.hide_render = h.hide_viewport = True
    cut_parts = [barrel]
    for i in range(6):
        cut_parts.append(cyl("Resistencia", 0.135, 0.14, (-(0.62 + i * 0.22), 0, bz), M["aluminio"],
                             axis="X", bevel=0.006, verts=64))
    for ob in cut_parts:
        for h in (bore, win):
            md = ob.modifiers.new("Corte", "BOOLEAN")
            md.object = h
            md.operation = "DIFFERENCE"
    box("BancadaExtrusora", (2.3, 0.6, 0.45), (-1.55, 0, 0.225), M["negro"], 0.01)
    for i in range(4):
        cyl("Ventilador", 0.08, 0.06, (-(0.70 + i * 0.3), 0.12, bz - 0.2), M["negro_mate"])

    # Tornillo (husillo): eje + filete helicoidal, gira en eje X
    x0, x1 = 0.48, 2.10
    shaft = cyl("Tornillo", 0.036, x1 - x0, (-(x0 + x1) / 2, 0, bz), M["cromo"], axis="X", verts=32)
    pitch, steps_per_turn = 0.12, 40
    L = x1 - x0 - 0.08
    n = int(L / pitch * steps_per_turn)
    verts, faces = [], []
    for i in range(n + 1):
        th = i / steps_per_turn * math.tau
        xx = -L / 2 + pitch * th / math.tau
        c, si = math.cos(th), math.sin(th)
        verts += [(xx, 0.034 * c, 0.034 * si), (xx, 0.063 * c, 0.063 * si)]
    for i in range(n):
        faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    flight = mesh_from("Filete", verts, faces, M["cromo"], solidify=0.014)
    flight.parent = shaft
    rotor(shaft, axis=0, omega=math.tau * 1.0, marks=False)  # 60 rpm

    # Tolva
    hx, hy = -2.12, 0
    cyl("Garganta", 0.11, 0.25, (hx, hy, bz + 0.2), M["negro"], bevel=0.005)
    cyl("TolvaCono", 0.12, 0.35, (hx, hy, bz + 0.5), M["negro"], r2=0.30, bevel=0.005)
    cyl("Tolva", 0.30, 0.50, (hx, hy, bz + 0.92), M["negro"], bevel=0.01)
    cyl("TapaTolva", 0.31, 0.03, (hx, hy, bz + 1.18), M["negro"], bevel=0.005)
    cyl("Visor", 0.032, 0.30, (hx, hy - 0.298, bz + 0.92), M["film"], verts=16)
    # Reductor + motor principal
    box("ReductorPpal", (0.45, 0.55, 0.55), (-2.85, 0, 0.55), M["negro"], 0.03)
    cyl("MotorPpal", 0.22, 0.6, (-3.35, 0, 0.5), M["negro"], axis="X", bevel=0.02)
    for k in range(16):
        a = k * math.tau / 16
        box("AletaMotor", (0.5, 0.04, 0.015),
            (-3.35, math.cos(a) * 0.225, 0.5 + math.sin(a) * 0.225), M["negro"], rot=(a, 0, 0))
    cyl("TapaMotorPpal", 0.2, 0.08, (-3.69, 0, 0.5), M["negro"], axis="X", bevel=0.02)
    # ventilador trasero del motor principal (gira)
    mfan = cyl("VentiladorMotor", 0.16, 0.01, (-3.74, 0, 0.5), M["gris_oscuro"], axis="X", verts=8)
    for k in range(6):
        bl = box("AspaMotor", (0.006, 0.28, 0.05), (0, 0, 0), M["aluminio"], rot=(k * math.tau / 6, 0, 0))
        bl.location = (-0.008, 0, 0)
        bl.parent = mfan
    rotor(mfan, axis=0, omega=math.tau * 4.0, marks=False)

    # Soplador centrifugo (detras)
    bx, by = 0.55, 1.15
    cyl("Voluta", 0.34, 0.24, (bx, by, 0.42), M["negro"], axis="X", bevel=0.02)
    box("Descarga", (0.24, 0.3, 0.22), (bx, by - 0.28, 0.66), M["negro"], 0.02)
    cyl("MotorSoplador", 0.15, 0.3, (bx + 0.27, by, 0.42), M["negro"], axis="X", bevel=0.01)
    box("BaseSoplador", (0.6, 0.5, 0.08), (bx + 0.1, by, 0.04), M["negro"], 0.01)
    fan = cyl("AspasSoplador", 0.11, 0.01, (bx + 0.43, by, 0.42), M["gris_oscuro"], axis="X", verts=6)
    for k in range(5):
        bl = box("Aspa", (0.006, 0.2, 0.035), (0, 0, 0), M["aluminio"], rot=(k * math.tau / 5, 0, 0))
        bl.location = (0.008, 0, 0)
        bl.parent = fan
    rotor(fan, axis=0, omega=math.tau * 3.0, marks=False)
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
            box("Display", (0.07, 0.005, 0.025), (px, fy - 0.022, pz + 0.018), D_ROJO)
            box("Display2", (0.07, 0.005, 0.018), (px, fy - 0.022, pz - 0.015), D_VERDE)
            # el 2do digito de cada controlador parpadea como si actualizara la lectura
            box("Digito", (0.012, 0.004, 0.02), (px + 0.024, fy - 0.025, pz + 0.018),
                led(f"DigitoRojo{row}{c}", (0.6, 0.02, 0.01), (1.0, 0.08, 0.02), 9,
                    0.6 + 0.17 * c + 0.11 * row, 0.07 * c))
    # pilotos: verdes fijos (marcha), ambar y rojos intermitentes
    pil = [((0.02, 0.5, 0.05), (0.1, 1.0, 0.15), 0.0, 0.0),
           ((0.6, 0.35, 0.0), (1.0, 0.55, 0.0), 1.0, 0.0),
           ((0.02, 0.5, 0.05), (0.1, 1.0, 0.15), 0.0, 0.0),
           ((0.6, 0.02, 0.01), (1.0, 0.05, 0.02), 0.5, 0.25),
           ((0.6, 0.35, 0.0), (1.0, 0.55, 0.0), 1.0, 0.5)]
    for c in range(5):
        px = x - 0.30 + c * 0.15
        col_, em, per, ph = pil[c]
        mat = led(f"Piloto{c}", col_, em, 12, per, ph)
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
    # baliza / torre de senalizacion sobre el tablero
    bx_, by_ = x + 0.28, y - 0.05
    top = 0.12 + h
    cyl("BalizaBase", 0.04, 0.05, (bx_, by_, top + 0.025), M["negro"])
    cyl("BalizaPoste", 0.012, 0.12, (bx_, by_, top + 0.11), M["aluminio"])
    z = top + 0.17
    for nm, c_, em, per, ph, st in [("Verde", (0.02, 0.45, 0.05), (0.1, 1.0, 0.15), 0.0, 0.0, 25),
                                    ("Ambar", (0.7, 0.35, 0.0), (1.0, 0.5, 0.0), 0.8, 0.0, 40),
                                    ("Roja", (0.55, 0.02, 0.01), (1.0, 0.04, 0.02), 0.0, 0.0, 0.0)]:
        mat = led(f"Baliza{nm}", c_, em, st, per, ph)
        mat.node_tree.nodes["Principled BSDF"].inputs["Transmission Weight"].default_value = 0.3
        cyl(f"Baliza{nm}", 0.042, 0.09, (bx_, by_, z + 0.045), mat, bevel=0.004)
        if st > 0:
            # luz real para que ilumine el entorno al parpadear
            ld = bpy.data.lights.new(f"LuzBaliza{nm}", "POINT")
            ld.color = em
            ld.energy = st * 0.6
            ld.shadow_soft_size = 0.04
            lo = bpy.data.objects.new(f"LuzBaliza{nm}", ld)
            lo.location = (bx_, by_, z + 0.045)
            col.objects.link(lo)
            LIGHT_BLINKS.append((ld, ld.energy, per, ph))
        z += 0.092
    cyl("BalizaTapa", 0.043, 0.02, (bx_, by_, z + 0.01), M["negro"])

    # canaleta de cables hacia la maquina
    beam("Ducto", (x - 0.2, y, 0.12 + h), (x - 0.2, y, 2.55), 0.08, M["gris_panel"])
    beam("Ducto", (x - 0.2, y, 2.55), (0.7, y, 2.55), 0.08, M["gris_panel"])


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
    rotor(cyl("RodilloEntrada", 0.045, 2 * hw, (0, yc + 0.24, 1.07), M["acero"], axis="X"), 0.045)
    rotor(cyl("RodilloTension", 0.035, 2 * hw, (0, yc + 0.10, 1.18), M["acero"], axis="X"), 0.035)
    rotor(cyl("RodilloArrastre", 0.10, 2 * hw - 0.04, (0, yc + 0.0, 0.96), M["cromo"], axis="X"), 0.10)
    ROTORS[-1] = (ROTORS[-1][0], 0, -V_FILM / 0.10)
    rotor(cyl("NucleoCarton", 0.045, 1.15, (0, yc - 0.2, 0.75), M["carton"], axis="X"),
          omega=V_FILM / 0.23, marks=False)
    # bobina de film
    roll = cyl("Bobina", 0.23, 2 * LAYFLAT + 0.02, (0, yc - 0.2, 0.75), M["bobina"], axis="X",
               verts=96, bevel=0.01)
    rotor(roll, 0.23, mark_mat=M["azul"])
    # cinta de inicio de bobina en las caras (se ve girar)
    for sgn in (-1, 1):
        t_ = box("CintaBobina", (0.003, 0.03, 0.17), (0, 0, 0), M["azul"])
        t_.location = (sgn * (LAYFLAT + 0.012), 0, -0.13)
        t_.parent = roll
    GROWERS.append((roll, 0.90, 1.0))
    rotor(cyl("EjeBobina", 0.025, 1.6, (0, yc - 0.2, 0.75), M["negro"], axis="X"),
          omega=V_FILM / 0.23, marks=False)
    for sx in (-1, 1):
        rotor(cyl("Mandril", 0.04, 0.08, (sx * 0.72, yc - 0.2, 0.75), M["negro"], axis="X", verts=6),
              0.04, mark_mat=M["amarillo"])
        ROTORS[-1] = (ROTORS[-1][0], 0, V_FILM / 0.23)
    # cubierta negra del motor/embrague
    cyl("TapaMotor", 0.16, 0.18, (hw + 0.12, yc + 0.0, 0.96), M["negro"], axis="X", bevel=0.02)
    box("TapaMotor2", (0.18, 0.3, 0.28), (hw + 0.12, yc + 0.15, 0.82), M["negro"], 0.03)
    # caja de control de la embobinadora
    box("CajaControl", (0.12, 0.3, 0.42), (hw + 0.08, yc + 0.1, 0.42), M["blanco"], 0.01)
    box("Contador", (0.005, 0.08, 0.04), (hw + 0.142, yc + 0.1, 0.55), D_ROJO)
    # cuchilla/guia
    cyl("Guia", 0.02, 2 * hw, (0, yc - 0.05, 1.16), M["negro"], axis="X")

    # Soporte de rodillos intermedio (entre torre y embobinadora)
    sy = -1.72
    for sx in (-1, 1):
        x = sx * 0.66
        box("PosteGuia", (0.05, 0.05, 1.9), (x, sy, 0.95), M["acero"], 0.003)
        box("PieGuia", (0.08, 0.5, 0.04), (x, sy, 0.02), M["acero"])
    rotor(cyl("RodilloGuia", 0.04, 1.32, (0, sy + 0.08, 1.80), M["acero"], axis="X"), 0.04)
    rotor(cyl("RodilloGuia", 0.04, 1.32, (0, sy - 0.07, 1.17), M["acero"], axis="X"), 0.04)
    ROTORS[-1] = (ROTORS[-1][0], 0, -V_FILM / 0.04)
    cyl("BarraGuia", 0.02, 1.32, (0, sy, 1.5), M["acero"], axis="X")


# ---------------------------------------------------------------------------
# Estudio: fondo degradado, luces de estudio y sombra en el piso (sin piso visible)
# ---------------------------------------------------------------------------
def studio():
    world = bpy.data.worlds.new("Estudio")
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputWorld")
    mix = nt.nodes.new("ShaderNodeMixShader")
    lp = nt.nodes.new("ShaderNodeLightPath")
    bg_light = nt.nodes.new("ShaderNodeBackground")
    bg_light.inputs["Color"].default_value = (0.8, 0.82, 0.85, 1)
    bg_light.inputs["Strength"].default_value = 0.35
    # fondo visto por la camara: degradado vertical gris azulado oscuro
    tc = nt.nodes.new("ShaderNodeTexCoord")
    sep = nt.nodes.new("ShaderNodeSeparateXYZ")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.035, 0.040, 0.048, 1)
    ramp.color_ramp.elements[1].color = (0.20, 0.22, 0.25, 1)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[1].position = 1.0
    bg_cam = nt.nodes.new("ShaderNodeBackground")
    bg_cam.inputs["Strength"].default_value = 1.0
    nt.links.new(tc.outputs["Window"], sep.inputs[0])
    nt.links.new(sep.outputs["Y"], ramp.inputs["Fac"])
    nt.links.new(ramp.outputs["Color"], bg_cam.inputs["Color"])
    nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs["Fac"])
    nt.links.new(bg_light.outputs[0], mix.inputs[1])
    nt.links.new(bg_cam.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    scene.world = world

    # plano que solo recibe sombras (no se ve como piso)
    bpy.ops.mesh.primitive_plane_add(size=16, location=(0, 0, 0))
    sc = bpy.context.active_object
    sc.name = "AtrapaSombras"
    sc.is_shadow_catcher = True

    def area(name, loc, target, energy, size, color=(1, 1, 1)):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.size = size
        ld.color = color
        lo = bpy.data.objects.new(name, ld)
        lo.location = loc
        d = Vector(target) - Vector(loc)
        lo.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        col.objects.link(lo)
        return lo

    area("Principal", (-5.0, -6.5, 7.5), (0, 0, 2.2), 4500, 5.0, (1.0, 0.97, 0.93))
    area("Relleno", (7.0, -4.5, 3.5), (0, 0, 2.0), 1600, 6.0, (0.9, 0.95, 1.0))
    area("Contra", (2.0, 6.0, 7.0), (0, 0, 3.0), 3000, 4.0, (0.85, 0.9, 1.0))
    area("Cenital", (0.0, -1.0, 9.0), (0, -1.0, 0), 1500, 4.0)


# ---------------------------------------------------------------------------
# Construccion
# ---------------------------------------------------------------------------
tower()
upper_tower()
bubble()
extruder()
control_panel()
winder()
studio()

fps = args.fps
nframes = int(round(args.segundos * fps))
scene.render.fps = fps
scene.frame_start = 1
scene.frame_end = nframes
T = (nframes - 1) / fps   # duracion entre el primer y ultimo cuadro (s)

# Camara: arco lento alrededor de la maquina (igual en ambos estados)
target = bpy.data.objects.new("ObjetivoCamara", None)
target.location = (0.25, -0.35, 2.62)
col.objects.link(target)
pivot = bpy.data.objects.new("PivoteCamara", None)
pivot.location = target.location
col.objects.link(pivot)
cd = bpy.data.cameras.new("Camara")
cd.lens = 34
cd.sensor_width = 36
cam = bpy.data.objects.new("Camara", cd)
cam.parent = pivot
cam.location = (0.0, -12.0, 0.0)   # relativo al pivote (frente)
col.objects.link(cam)
tr = cam.constraints.new("TRACK_TO")
tr.target = target
tr.track_axis = "TRACK_NEGATIVE_Z"
tr.up_axis = "UP_Y"
scene.camera = cam

prefs = bpy.context.preferences.edit
prefs.keyframe_new_interpolation_type = "BEZIER"
# arranca de frente-izquierda (tornillo) y gira hacia el tablero (derecha)
for f, az, h in [(1, math.radians(-24), 0.2), (nframes, math.radians(22), 0.6)]:
    pivot.rotation_euler = (0, 0, az)
    pivot.keyframe_insert("rotation_euler", index=2, frame=f)
    cam.location.z = h
    cam.keyframe_insert("location", index=2, frame=f)

prefs.keyframe_new_interpolation_type = "LINEAR"
if ON:
    # rodillos, tornillo, ventilador y bobina girando a velocidad constante
    for ob, axis, w in ROTORS:
        ob.rotation_euler[axis] = 0.0
        ob.keyframe_insert("rotation_euler", index=axis, frame=1)
        ob.rotation_euler[axis] = w * T
        ob.keyframe_insert("rotation_euler", index=axis, frame=nframes)
    # bobina creciendo (se enrolla el film)
    for ob, s0, s1 in GROWERS:
        for f, sc_ in ((1, s0), (nframes, s1)):
            ob.scale = (1.0, sc_, sc_)
            ob.keyframe_insert("scale", frame=f)
    # el patron del film avanza con la lamina
    for mp in FILM_MAPS:
        loc = mp.inputs["Location"]
        loc.default_value[1] = 0.0
        loc.keyframe_insert("default_value", index=1, frame=1)
        loc.default_value[1] = -V_FILM * T
        loc.keyframe_insert("default_value", index=1, frame=nframes)
    # la ondulacion de la burbuja sube con el aire
    for e in ANIM_EMPTIES:
        e.location.z = 0.0
        e.keyframe_insert("location", index=2, frame=1)
        e.location.z = 0.9 * T
        e.keyframe_insert("location", index=2, frame=nframes)

    # parpadeos (interpolacion constante)
    prefs.keyframe_new_interpolation_type = "CONSTANT"

    def blink_keys(sock, value, period, phase):
        if period <= 0:
            sock.default_value = value
            return
        half = period / 2
        t = -phase
        on = True
        while t < T + period:
            f = max(1, int(round(1 + t * fps)))
            sock.default_value = value if on else 0.0
            sock.keyframe_insert("default_value", frame=f)
            t += half
            on = not on

    for mat, strength, period, phase in BLINKS:
        sock = mat.node_tree.nodes["Principled BSDF"].inputs["Emission Strength"]
        blink_keys(sock, strength, period, phase)

    class _LightSock:
        """Adaptador para animar la energia de una luz con el mismo codigo."""
        def __init__(self, ld):
            self.ld = ld

        @property
        def default_value(self):
            return self.ld.energy

        @default_value.setter
        def default_value(self, v):
            self.ld.energy = v

        def keyframe_insert(self, _path, frame):
            self.ld.keyframe_insert("energy", frame=frame)

    for ld, energy, period, phase in LIGHT_BLINKS:
        blink_keys(_LightSock(ld), energy, period, phase)
    prefs.keyframe_new_interpolation_type = "BEZIER"
else:
    # maquina apagada: sin emision ni luces de senalizacion
    for mat in LEDS:
        b = mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Emission Strength"].default_value = 0.0
        c = b.inputs["Base Color"].default_value
        b.inputs["Base Color"].default_value = (c[0] * 0.35, c[1] * 0.35, c[2] * 0.35, 1)
    for ld, _e, _p, _ph in LIGHT_BLINKS:
        ld.energy = 0.0

# Render
scene.render.engine = "CYCLES"
scene.cycles.device = "CPU"
scene.cycles.samples = args.samples
scene.cycles.use_denoising = True
scene.cycles.max_bounces = 6
scene.cycles.transparent_max_bounces = 24
scene.cycles.caustics_reflective = False
scene.cycles.caustics_refractive = False
scene.view_settings.view_transform = "AgX"
scene.view_settings.look = "AgX - Medium High Contrast"
scene.view_settings.exposure = -1.1
scene.render.resolution_x = int(1280 * args.res)
scene.render.resolution_y = int(720 * args.res)
scene.render.image_settings.file_format = "PNG"

here = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
root = os.path.dirname(here)
blend = os.path.join(here, f"extrusora_{args.estado}.blend")
scene.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=blend)
print("Guardado", blend, flush=True)

if not args.no_render:
    frames_dir = os.path.join(root, "renders", f"cuadros_{args.estado}")
    os.makedirs(frames_dir, exist_ok=True)
    if args.still:
        scene.frame_set(args.still)
        scene.render.filepath = os.path.join(root, "renders", f"extrusora_{args.estado}.png")
        bpy.ops.render.render(write_still=True)
    else:
        f0, f1 = 1, nframes
        if args.frames:
            f0, f1 = (int(v) for v in args.frames.split("-"))
        for f in range(f0, f1 + 1):
            path = os.path.join(frames_dir, f"{f:04d}.png")
            if os.path.exists(path):
                continue
            scene.frame_set(f)
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            print(f"cuadro {f}/{nframes}", flush=True)
        if not args.frames:
            mp4 = os.path.join(root, "renders", f"extrusora_{args.estado}.mp4")
            os.system(f'ffmpeg -y -loglevel error -framerate {fps} -i "{frames_dir}/%04d.png" '
                      f'-c:v libx264 -pix_fmt yuv420p -crf 18 "{mp4}"')
            print("Video", mp4, flush=True)
