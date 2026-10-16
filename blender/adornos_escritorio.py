"""
Adornos de escritorio para "Claudio Alvarez S." - Coordinador de I+D.

Tres diseños, todos con dos cadenas de polietileno (-CH2-CH2-)n en esferas y
barras y la paleta negro / rojo / azul / blanco:

  cristal  - bloque de cristal con las dos cadenas dentro, sobre base negra.
  placa    - placa negra inclinada con las cadenas en relieve sobre el nombre.
  trofeo   - base negra con las dos cadenas de pie sobre varillas.

Uso:
  python3 blender/adornos_escritorio.py                      # los tres diseños
  python3 blender/adornos_escritorio.py --disenos placa --samples 64 --res 0.5
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Matrix, Vector

AQUI = os.path.dirname(os.path.abspath(__file__))
FUENTE_NOMBRE = os.path.join(AQUI, "fuentes", "PlayfairDisplay.ttf")
FUENTE_CARGO = os.path.join(AQUI, "fuentes", "Montserrat.ttf")
NOMBRE = "Claudio Alvarez S."
CARGO = "COORDINADOR DE I+D"

NEGRO = (0.008, 0.008, 0.010)
ROJO = (0.62, 0.015, 0.025)
AZUL = (0.010, 0.10, 0.62)
BLANCO = (0.90, 0.90, 0.90)

# Geometría del polietileno en Å: C-C 1.54, C-C-C 112°, C-H 1.09, H-C-H 109.5°
PASO_X = 1.54 * math.sin(math.radians(56))
MEDIO_Z = 1.54 * math.cos(math.radians(56)) / 2
CH = 1.09
H_Y, H_Z = math.sin(math.radians(54.75)), math.cos(math.radians(54.75))
R_C, R_H, R_ENLACE = 0.40, 0.26, 0.11


# ---------------------------------------------------------------- utilidades
def material(nombre, color, rugosidad=0.3, metal=0.0, barniz=0.0, transmision=0.0, ior=1.45):
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1)
    b.inputs["Roughness"].default_value = rugosidad
    b.inputs["Metallic"].default_value = metal
    b.inputs["Coat Weight"].default_value = barniz
    b.inputs["Transmission Weight"].default_value = transmision
    b.inputs["IOR"].default_value = ior
    return m


def suavizar(o, angulo=None):
    for p in o.data.polygons:
        p.use_smooth = True
    if angulo is not None:
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        bpy.ops.object.shade_smooth_by_angle(angle=angulo)
        o.select_set(False)


def caja(nombre, dims, loc, mat, bisel=0.0):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.object
    o.name = nombre
    o.scale = dims
    bpy.ops.object.transform_apply(scale=True)
    if bisel:
        mod = o.modifiers.new("bisel", "BEVEL")
        mod.width = bisel
        mod.segments = 5
        suavizar(o, math.radians(40))
    o.data.materials.append(mat)
    return o


def prisma(nombre, perfil_yz, ancho, mat, bisel=0.0):
    """Extruye un perfil (y, z) a lo largo de X, centrado en x=0."""
    me = bpy.data.meshes.new(nombre)
    n = len(perfil_yz)
    vs = [(-ancho / 2, y, z) for y, z in perfil_yz] + [(ancho / 2, y, z) for y, z in perfil_yz]
    caras = [list(range(n))[::-1], list(range(n, 2 * n))]
    caras += [[i, (i + 1) % n, n + (i + 1) % n, n + i] for i in range(n)]
    me.from_pydata(vs, [], caras)
    me.update()
    o = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(o)
    if bisel:
        mod = o.modifiers.new("bisel", "BEVEL")
        mod.width = bisel
        mod.segments = 5
        suavizar(o, math.radians(40))
    o.data.materials.append(mat)
    return o


def esfera(nombre, centro, radio, mat):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=radio, location=centro)
    o = bpy.context.object
    o.name = nombre
    suavizar(o)
    o.data.materials.append(mat)
    return o


def cilindro_entre(nombre, p1, p2, radio, mat, lados=20):
    p1, p2 = Vector(p1), Vector(p2)
    d = p2 - p1
    bpy.ops.mesh.primitive_cylinder_add(vertices=lados, radius=radio, depth=d.length, location=(p1 + p2) / 2)
    o = bpy.context.object
    o.name = nombre
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = d.to_track_quat("Z", "Y")
    suavizar(o, math.radians(50))
    o.data.materials.append(mat)
    return o


def marco(origen, u, v):
    """Matriz con X=u, Y=v, Z=u×v y traslación en origen."""
    u, v = Vector(u).normalized(), Vector(v).normalized()
    n = u.cross(v)
    m = Matrix((u, v, n)).transposed().to_4x4()
    m.translation = Vector(origen)
    return m


def texto(nombre, cuerpo, fuente, tam, matriz, mat, relieve=0.0006, espaciado=1.0):
    cu = bpy.data.curves.new(nombre, "FONT")
    cu.body = cuerpo
    cu.font = bpy.data.fonts.load(fuente, check_existing=True)
    cu.size = tam
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = relieve / 2
    cu.bevel_depth = relieve * 0.12
    cu.space_character = espaciado
    cu.resolution_u = 8
    o = bpy.data.objects.new(nombre, cu)
    bpy.context.scene.collection.objects.link(o)
    o.matrix_world = matriz @ Matrix.Translation((0, 0, relieve / 2))
    o.data.materials.append(mat)
    return o


# ---------------------------------------------------------------- molécula
def cadena_polietileno(prefijo, n_c, matriz, escala, mat_c, mat_h, mat_enlace):
    """Segmento de polietileno CH3-(CH2)n-CH3 en esferas y barras.

    Coordenadas locales en Å: eje de la cadena en X, zigzag del esqueleto en Z,
    hidrógenos a ±Y. `matriz` lleva el marco local al mundo y `escala` son m/Å.
    """
    carbonos = [Vector(((i - (n_c - 1) / 2) * PASO_X, 0, MEDIO_Z if i % 2 == 0 else -MEDIO_Z)) for i in range(n_c)]
    hidrogenos = []
    for c in carbonos:
        s = 1 if c.z > 0 else -1
        for sy in (1, -1):
            hidrogenos.append((c, c + Vector((0, sy * H_Y, s * H_Z)) * CH))
    for i, j in ((0, 1), (n_c - 1, n_c - 2)):  # metilos terminales
        c, vec = carbonos[i], carbonos[j]
        siguiente = Vector((2 * c.x - vec.x, 0, vec.z))
        hidrogenos.append((c, c + (siguiente - c).normalized() * CH))

    w = lambda p: matriz @ (p * escala)
    for i, c in enumerate(carbonos):
        esfera(f"{prefijo}_C{i + 1}", w(c), R_C * escala, mat_c)
    for i in range(n_c - 1):
        cilindro_entre(f"{prefijo}_CC{i + 1}", w(carbonos[i]), w(carbonos[i + 1]), R_ENLACE * escala, mat_enlace)
    for k, (c, h) in enumerate(hidrogenos):
        esfera(f"{prefijo}_H{k + 1}", w(h), R_H * escala, mat_h)
        cilindro_entre(f"{prefijo}_CH{k + 1}", w(c), w(h), R_ENLACE * 0.8 * escala, mat_enlace)
    return carbonos


# ---------------------------------------------------------------- escena
def escena_base(res, samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 16
    sc.cycles.transmission_bounces = 16
    sc.render.resolution_x = 1600
    sc.render.resolution_y = 1200
    sc.render.resolution_percentage = int(res * 100)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"

    mundo = bpy.data.worlds.new("mundo")
    sc.world = mundo
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.012, 0.014, 1)
    mundo.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0

    # Escritorio: superficie gris grafito satinada con fondo curvo
    escritorio = material("escritorio", (0.012, 0.012, 0.014), rugosidad=0.3)
    bpy.ops.mesh.primitive_plane_add(size=4, location=(0, 0.6, 0))
    piso = bpy.context.object
    piso.name = "escritorio"
    piso.data.materials.append(escritorio)

    def luz(nombre, loc, objetivo, energia, tam, color=(1, 1, 1)):
        d = bpy.data.lights.new(nombre, "AREA")
        d.energy = energia
        d.size = tam
        d.color = color
        o = bpy.data.objects.new(nombre, d)
        sc.collection.objects.link(o)
        o.location = loc
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = (Vector(objetivo) - Vector(loc)).to_track_quat("-Z", "Y")

    luz("clave", (-0.45, -0.55, 0.55), (0, 0, 0.06), 45, 0.6)
    luz("relleno", (0.6, -0.35, 0.25), (0, 0, 0.06), 10, 0.8)
    luz("contra_roja", (-0.35, 0.45, 0.35), (0, 0, 0.08), 25, 0.3, (1.0, 0.25, 0.25))
    luz("contra_azul", (0.35, 0.45, 0.35), (0, 0, 0.08), 25, 0.3, (0.3, 0.45, 1.0))
    luz("cenital", (0, 0.05, 0.8), (0, 0, 0), 18, 0.9)
    return sc


def camara(sc, loc, objetivo, focal, enfoque):
    d = bpy.data.cameras.new("camara")
    d.lens = focal
    d.dof.use_dof = True
    d.dof.aperture_fstop = 5.6
    d.dof.focus_distance = enfoque
    o = bpy.data.objects.new("camara", d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_mode = "QUATERNION"
    o.rotation_quaternion = (Vector(objetivo) - Vector(loc)).to_track_quat("-Z", "Y")
    sc.camera = o


def materiales():
    return {
        "negro": material("laca_negra", NEGRO, rugosidad=0.3, barniz=0.35),
        "letras": material("letras_blancas", BLANCO, rugosidad=0.35),
        "rojo": material("laca_roja", ROJO, rugosidad=0.3, barniz=0.5),
        "azul": material("laca_azul", AZUL, rugosidad=0.3, barniz=0.5),
        "h": material("hidrogeno", BLANCO, rugosidad=0.3, barniz=0.3),
        "enlace": material("enlace", (0.75, 0.75, 0.77), rugosidad=0.15, metal=1.0),
        "cristal": material("cristal", (1, 1, 1), rugosidad=0.0, transmision=1.0, ior=1.5),
    }


FRENTE = ((1, 0, 0), (0, 0, 1))  # marco de una cara que mira a -Y


def rotulo_frontal(m, y_cara, z_nombre, z_cargo, z_linea, tam_nombre, tam_cargo, largo_linea):
    """Nombre, cargo y dos filetes (rojo y azul) en una cara frontal vertical."""
    texto("nombre", NOMBRE, FUENTE_NOMBRE, tam_nombre, marco((0, y_cara, z_nombre), *FRENTE), m["letras"])
    texto("cargo", CARGO, FUENTE_CARGO, tam_cargo, marco((0, y_cara, z_cargo), *FRENTE), m["letras"],
          relieve=0.0004, espaciado=1.35)
    for nombre, signo, mat in (("filete_rojo", -1, m["rojo"]), ("filete_azul", 1, m["azul"])):
        x0 = signo * 0.004
        x1 = signo * (0.004 + largo_linea)
        caja(nombre, (abs(x1 - x0), 0.0008, 0.0012), ((x0 + x1) / 2, y_cara - 0.0004, z_linea), mat)


# ---------------------------------------------------------------- diseños
def diseno_cristal(m):
    """Bloque de cristal con las dos cadenas dentro, sobre base de laca negra."""
    base_h, base_d = 0.048, 0.07
    caja("base", (0.21, base_d, base_h), (0, 0, base_h / 2), m["negro"], bisel=0.003)
    caja("asiento_rojo", (0.19, 0.052, 0.0025), (0, 0, base_h + 0.00125), m["rojo"], bisel=0.0008)
    bloque_h = 0.12
    z0 = base_h + 0.0025
    caja("bloque_cristal", (0.185, 0.046, bloque_h), (0, 0, z0 + bloque_h / 2), m["cristal"], bisel=0.004)
    zc = z0 + bloque_h / 2
    for pref, dz, mat, giro in (("PE_rojo", 0.027, m["rojo"], 20), ("PE_azul", -0.025, m["azul"], -20)):
        M = Matrix.Translation((0, 0, zc + dz)) @ Matrix.Rotation(math.radians(giro), 4, "X")
        cadena_polietileno(pref, 8, M, 0.0128, mat, m["h"], m["enlace"])
    rotulo_frontal(m, -base_d / 2, 0.030, 0.0135, 0.0215, 0.0125, 0.0052, 0.045)
    return dict(loc=(0.16, -0.50, 0.21), objetivo=(0, 0, 0.088), focal=68)


def diseno_placa(m):
    """Placa negra inclinada; cadenas en relieve arriba, nombre y cargo abajo."""
    alto, y_frente_abajo, y_frente_arriba, y_atras = 0.10, -0.048, -0.006, 0.035
    prisma("placa", [(y_frente_abajo, 0), (y_atras, 0), (y_atras, alto), (y_frente_arriba, alto)],
           0.27, m["negro"], bisel=0.0025)
    caja("zocalo_azul", (0.272, 0.086, 0.004), (0, (y_frente_abajo + y_atras) / 2, -0.002), m["azul"], bisel=0.001)
    v = Vector((0, y_frente_arriba - y_frente_abajo, alto)).normalized()
    u = Vector((1, 0, 0))
    n = u.cross(v)  # normal de la cara inclinada, hacia afuera
    pie = Vector((0, y_frente_abajo, 0))
    en_cara = lambda t, x=0.0, sobre=0.0: pie + v * t + u * x + n * sobre

    escala = 0.0102
    sobre = (H_Y * CH + R_H) * escala  # los H de atrás tocan la placa
    for pref, x, mat in (("PE_rojo", -0.063, m["rojo"]), ("PE_azul", 0.063, m["azul"])):
        # X local -> u, Z local (zigzag) -> v, Y local (H) -> normal
        M = Matrix((u, n, v)).transposed().to_4x4()
        M.translation = en_cara(0.080, x, sobre)
        cadena_polietileno(pref, 8, M, escala, mat, m["h"], m["enlace"])

    texto("nombre", NOMBRE, FUENTE_NOMBRE, 0.017, marco(en_cara(0.047), u, v), m["letras"])
    texto("cargo", CARGO, FUENTE_CARGO, 0.0068, marco(en_cara(0.022), u, v), m["letras"],
          relieve=0.0004, espaciado=1.35)
    for nombre, signo, mat in (("filete_rojo", -1, m["rojo"]), ("filete_azul", 1, m["azul"])):
        centro = en_cara(0.0335, signo * 0.034, 0.0003)
        o = caja(nombre, (0.06, 0.0012, 0.0008), (0, 0, 0), mat)
        o.matrix_world = marco(centro, u, v)
    return dict(loc=(0.13, -0.52, 0.22), objetivo=(0, -0.02, 0.05), focal=62)


def diseno_trofeo(m):
    """Base negra con las dos cadenas de pie sobre varillas, como escultura."""
    base_h, base_d = 0.05, 0.085
    caja("base", (0.2, base_d, base_h), (0, 0, base_h / 2), m["negro"], bisel=0.004)
    caja("tapa_blanca", (0.17, 0.06, 0.004), (0, 0.004, base_h + 0.002), m["h"], bisel=0.0012)
    escala = 0.0118
    largo = 7 * PASO_X * escala
    z_pie = base_h + 0.004 + 0.022
    for pref, x, mat, giro, dz in (("PE_rojo", -0.032, m["rojo"], 25, 0.0), ("PE_azul", 0.032, m["azul"], -25, 0.012)):
        centro = Vector((x, 0.004, z_pie + dz + largo / 2))
        # cadena vertical: X local -> +Z mundo, girada sobre su eje para mostrar los H
        M = Matrix.Translation(centro) @ Matrix.Rotation(math.radians(giro), 4, "Z") @ Matrix.Rotation(
            math.radians(-90), 4, "Y")
        carbonos = cadena_polietileno(pref, 8, M, escala, mat, m["h"], m["enlace"])
        primero = M @ (carbonos[0] * escala)
        cilindro_entre(f"{pref}_varilla", (primero.x, primero.y, base_h + 0.004), primero, 0.0018, m["negro"])
    rotulo_frontal(m, -base_d / 2, 0.031, 0.0145, 0.0225, 0.0125, 0.0052, 0.045)
    return dict(loc=(0.17, -0.52, 0.21), objetivo=(0, 0, 0.098), focal=54)


DISENOS = {"cristal": diseno_cristal, "placa": diseno_placa, "trofeo": diseno_trofeo}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--disenos", default=",".join(DISENOS))
    ap.add_argument("--out", default=os.path.join(AQUI, "..", "renders", "adorno"))
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--res", type=float, default=1.0)
    a = ap.parse_args(argv)
    for nombre in a.disenos.split(","):
        sc = escena_base(a.res, a.samples)
        cam = DISENOS[nombre](materiales())
        enfoque = (Vector(cam["objetivo"]) - Vector(cam["loc"])).length
        camara(sc, cam["loc"], cam["objetivo"], cam["focal"], enfoque)
        sc.render.filepath = os.path.abspath(f"{a.out}_{nombre}.png")
        bpy.ops.render.render(write_still=True)
        print("render:", sc.render.filepath)


if __name__ == "__main__":
    main()
