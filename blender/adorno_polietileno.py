"""
Adorno de escritorio imprimible en 3D: unidad repetitiva del polietileno
-[CH2-CH2]- en esferas y barras sobre una base ovalada, con placa de nombre
"Claudio Alvarez S." / "COORDINADOR DE I+D".

Química correcta: cada carbono tiene exactamente 2 hidrógenos y 2 enlaces C
(el enlace C-C central y un enlace abierto que indica que la cadena continúa),
con ángulos C-C-C 112°, H-C-H 109.5° y conformación trans (zigzag).

Incluye el logo de Polímeros Norte en relieve azul sobre la placa.

Colores de impresión (sin rojo):
  negro  - cuerpo de la base, letras, filetes y carbonos
  azul   - tapa de la base y logo (#36427A, azul del logo)
  blanco - aro de la base, placa, hidrógenos y enlaces

Salida para imprimir en imprimir_3d/: un 3MF multiparte (una parte por color),
un STL por color y un .blend con todo en mallas, en mm y con el mismo origen.

Uso:
  python3 blender/adorno_polietileno.py                 # renders + 3MF + STL + .blend
  python3 blender/adorno_polietileno.py --samples 32 --res 0.4 --sin-stl
"""
import argparse
import json
import math
import os
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from adornos_escritorio import (  # noqa: E402
    AQUI, BLANCO, CARGO, NEGRO, NOMBRE,
    caja, camara, cilindro_entre, esfera, marco, material, prisma, suavizar, texto,
)

MM = 0.001
AZUL_LOGO = (0.018, 0.028, 0.12)  # tono de render del azul del logo (#36427A)
LOGO = os.path.join(AQUI, "logo", "polimeros_norte.json")
# fuentes estáticas sin contornos superpuestos: las letras salen como sólidos cerrados
FUENTE_NOMBRE = os.path.join(AQUI, "fuentes", "PlayfairDisplay-SemiBold.ttf")
FUENTE_CARGO = os.path.join(AQUI, "fuentes", "Montserrat-Medium.ttf")

# Base ovalada (semiejes en mm)
A, B = 95.0, 55.0
EXPONENTE = 4.0
H_CUERPO, H_ARO, H_TAPA = 11.0, 3.4, 2.6   # el aro blanco sobresale 0.8 mm sobre la tapa azul
ANCHO_ARO = 3.2

# Molécula: 1 Å -> 26 mm
ESCALA = 30.0
R_C, R_H, R_ENL = 12.5, 9.0, 3.6
CC, CH = 1.54, 1.09
LARGO_ABIERTO = 0.95  # Å, enlace que continúa la cadena
HUNDIDO = 1.6          # mm que los H inferiores entran en la tapa (pegado firme)
Y_MOLECULA = 10.0      # mm hacia atrás para dejar sitio a la placa


# ---------------------------------------------------------------- geometría
def elipse(a, b, z, n=256, p=None):
    """Superelipse |x/a|^p + |y/b|^p = 1 (p=2 elipse; p≈4 rectángulo de esquinas suaves)."""
    p = p or EXPONENTE
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        pts.append((a * math.copysign(abs(c) ** (2 / p), c), b * math.copysign(abs(s) ** (2 / p), s), z))
    return pts


def solido_lofteado(nombre, anillos, mat):
    """Sólido cerrado a partir de contornos (listas de vértices) apilados."""
    vs, caras = [], []
    n = len(anillos[0])
    for anillo in anillos:
        vs += anillo
    for k in range(len(anillos) - 1):
        o0, o1 = k * n, (k + 1) * n
        caras += [[o0 + i, o0 + (i + 1) % n, o1 + (i + 1) % n, o1 + i] for i in range(n)]
    caras.append(list(range(n))[::-1])
    caras.append(list(range((len(anillos) - 1) * n, len(anillos) * n)))
    return _objeto(nombre, vs, caras, mat)


def anillo_eliptico(nombre, a, b, ancho, z0, z1, mat, n=256):
    """Aro de sección rectangular entre dos elipses."""
    ext0, ext1 = elipse(a, b, z0, n), elipse(a, b, z1, n)
    int0, int1 = elipse(a - ancho, b - ancho, z0, n), elipse(a - ancho, b - ancho, z1, n)
    vs = ext0 + ext1 + int0 + int1
    E0, E1, I0, I1 = 0, n, 2 * n, 3 * n
    caras = []
    for i in range(n):
        j = (i + 1) % n
        caras.append([E0 + i, E0 + j, E1 + j, E1 + i])      # pared exterior
        caras.append([I0 + j, I0 + i, I1 + i, I1 + j])      # pared interior
        caras.append([E1 + i, E1 + j, I1 + j, I1 + i])      # cara superior
        caras.append([E0 + j, E0 + i, I0 + i, I0 + j])      # cara inferior
    return _objeto(nombre, vs, caras, mat)


def _objeto(nombre, vs, caras, mat):
    me = bpy.data.meshes.new(nombre)
    me.from_pydata([Vector(v) * MM for v in vs], [], caras)
    me.update()
    o = bpy.data.objects.new(nombre, me)
    bpy.context.scene.collection.objects.link(o)
    suavizar(o, math.radians(35))
    o.data.materials.append(mat)
    return o


def base(m):
    """Cuerpo negro con chaflán inferior, aro blanco y tapa azul."""
    z_tapa = H_CUERPO + H_TAPA
    anillos = [elipse(A - 2.0, B - 2.0, 0.0), elipse(A - 0.4, B - 0.4, 0.4), elipse(A, B, 2.0),
               elipse(A, B, H_CUERPO)]
    solido_lofteado("base_cuerpo", anillos, m["negro"])
    anillo_eliptico("base_aro", A, B, ANCHO_ARO, H_CUERPO, H_CUERPO + H_ARO, m["blanco"])
    a, b = A - ANCHO_ARO, B - ANCHO_ARO
    solido_lofteado("base_tapa", [elipse(a, b, H_CUERPO), elipse(a, b, z_tapa)], m["azul"])
    return z_tapa


def unidad_polietileno(m, z_tapa, x0=0.0, espejo=False):
    """-[CH2-CH2]- con el zigzag de carbonos en el plano vertical, de frente al observador.

    C1 tiene sus dos H hacia abajo (adelante y atrás) y C2 los suyos hacia arriba;
    los enlaces abiertos salen arriba-izquierda y abajo-derecha (trans). Se inclina
    unos grados para que la molécula se apoye en tres puntos: los dos H de C1 y la
    punta del enlace abierto de C2, todos hundidos en la tapa.
    """
    t = math.radians(112)
    c1, c2 = Vector((-CC / 2, 0, 0)), Vector((CC / 2, 0, 0))
    abierto1 = Vector((math.cos(t), 0, math.sin(t)))   # 112° respecto de C1->C2
    abierto2 = -abierto1                               # conformación trans
    hs = []
    for c, ab, otro in ((c1, abierto1, c2), (c2, abierto2, c1)):
        bis = ((otro - c).normalized() + ab).normalized()
        for sy in (1, -1):
            d = -bis * math.cos(math.radians(54.75)) + Vector((0, sy, 0)) * math.sin(math.radians(54.75))
            hs.append((c, c + d * CH))
    extremos = [(c1, c1 + abierto1 * LARGO_ABIERTO), (c2, c2 + abierto2 * LARGO_ABIERTO)]

    # inclinación que deja al mismo nivel el fondo de los H de C1 y el de la punta de C2
    h_bajo, punta = hs[0][1], extremos[1][1]
    r_h, r_p = R_H / ESCALA, R_ENL / ESCALA
    ang = 0.0
    for _ in range(60):  # bisección sobre el ángulo de giro en Y
        rot = Matrix.Rotation(ang, 3, "Y")
        dif = (rot @ punta).z - r_p - ((rot @ h_bajo).z - r_h)
        ang += 0.5 * dif / (punta - h_bajo).length
    rot = Matrix.Rotation(ang, 3, "Y")

    todos = [c1, c2] + [h for _, h in hs] + [e for _, e in extremos]
    z_min = (rot @ h_bajo).z * ESCALA - R_H
    dz = z_tapa - HUNDIDO - z_min
    refl = Matrix.Diagonal((-1, 1, 1)) if espejo else Matrix.Identity(3)
    w = lambda p: (refl @ rot @ p * ESCALA + Vector((x0, Y_MOLECULA, dz))) * MM

    for i, c in enumerate((c1, c2)):
        esfera(f"carbono_{i + 1}", w(c), R_C * MM, m["negro"])
    cilindro_entre("enlace_CC", w(c1), w(c2), R_ENL * MM, m["blanco"], lados=32)
    for k, (c, h) in enumerate(hs):
        esfera(f"hidrogeno_{k + 1}", w(h), R_H * MM, m["blanco"])
        cilindro_entre(f"enlace_CH_{k + 1}", w(c), w(h), R_ENL * MM, m["blanco"], lados=32)
    for k, (c, e) in enumerate(extremos):
        cilindro_entre(f"enlace_cadena_{k + 1}", w(c), w(e), R_ENL * MM, m["blanco"], lados=32)
        esfera(f"enlace_cadena_{k + 1}_punta", w(e), R_ENL * MM, m["blanco"])
    print(f"inclinación {math.degrees(ang):.1f}°")
    return [w(p) for p in todos]


def logo(nombre, matriz, alto, relieve, mat):
    """Logo de Polímeros Norte en relieve (curva 2D rellena a partir de los contornos vectorizados)."""
    with open(LOGO) as f:
        datos = json.load(f)
    cu = bpy.data.curves.new(nombre, "CURVE")
    cu.dimensions = "2D"
    cu.fill_mode = "BOTH"
    cu.extrude = relieve / 2 / alto
    for contorno in datos["contornos"]:
        sp = cu.splines.new("POLY")
        sp.points.add(len(contorno) - 1)
        for pt, (x, y) in zip(sp.points, contorno):
            pt.co = (x, y, 0, 1)
        sp.use_cyclic_u = True
    o = bpy.data.objects.new(nombre, cu)
    bpy.context.scene.collection.objects.link(o)
    o.matrix_world = matriz @ Matrix.Translation((0, 0, relieve / 2)) @ Matrix.Scale(alto, 4)
    o.data.materials.append(mat)
    return o, datos["ancho"] * alto


def placa(m, z_tapa):
    """Placa blanca en cuña al frente: logo azul a la izquierda; nombre y cargo en negro a la derecha."""
    prof_abajo, prof_arriba, alto, ancho = 15.0, 4.0, 18.0, 146.0
    y_frente = -B + ANCHO_ARO + 6.0
    perfil = [(y_frente, 0), (y_frente + prof_abajo, 0), (y_frente + prof_abajo, alto),
              (y_frente + prof_abajo - prof_arriba, alto)]
    perfil = [(y * MM, (z + z_tapa - 0.4) * MM) for y, z in perfil]
    prisma("placa", perfil, ancho * MM, m["blanco"], bisel=0.7 * MM)

    v = Vector((0, prof_abajo - prof_arriba, alto)).normalized()
    u = Vector((1, 0, 0))
    n = u.cross(v)
    largo = math.hypot(prof_abajo - prof_arriba, alto)
    pie = Vector((0, y_frente, z_tapa - 0.4)) * MM
    en_cara = lambda s, x=0.0: pie + v * (s * MM) + u * (x * MM) + n * (-0.15 * MM)

    # logo a la izquierda, separador vertical y bloque de nombre a la derecha
    x_logo, x_sep, x_texto = -47.0, -20.5, 25.0
    _, ancho_logo = logo("logo", marco(en_cara(largo * 0.5, x_logo), u, v), 12.5 * MM, 0.9 * MM, m["azul"])
    print(f"logo: {ancho_logo / MM:.1f} x 12.5 mm")
    sep = caja("filete_vertical", (0.7 * MM, largo * 0.62 * MM, 0.9 * MM), (0, 0, 0), m["letras"])
    sep.matrix_world = marco(en_cara(largo * 0.5, x_sep) + n * (0.45 * MM), u, v)
    nombre = texto("texto_nombre", NOMBRE, FUENTE_NOMBRE, 11.0 * MM, marco(en_cara(largo * 0.66, x_texto), u, v),
                   m["letras"], relieve=0.9 * MM, espaciado=1.03)
    texto("texto_cargo", CARGO, FUENTE_CARGO, 3.9 * MM, marco(en_cara(largo * 0.19, x_texto), u, v),
          m["letras"], relieve=0.9 * MM, espaciado=1.30)
    bpy.context.view_layer.update()
    print(f"nombre: {nombre.dimensions.x / MM:.1f} mm de ancho")
    fil = caja("filete", (80 * MM, 0.7 * MM, 0.9 * MM), (0, 0, 0), m["letras"])
    fil.matrix_world = marco(en_cara(largo * 0.40, x_texto) + n * (0.45 * MM), u, v)


# ---------------------------------------------------------------- escena
def escena(res, samples):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = 1600, 1200
    sc.render.resolution_percentage = int(res * 100)
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Punchy"

    mundo = bpy.data.worlds.new("mundo")
    sc.world = mundo
    mundo.use_nodes = True
    mundo.node_tree.nodes["Background"].inputs["Color"].default_value = (0.02, 0.018, 0.016, 1)

    # escritorio de piedra oscura satinada
    piedra = bpy.data.materials.new("piedra")
    piedra.use_nodes = True
    nt = piedra.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.28
    ruido = nt.nodes.new("ShaderNodeTexNoise")
    ruido.inputs["Scale"].default_value = 140.0
    ruido.inputs["Detail"].default_value = 8.0
    rampa = nt.nodes.new("ShaderNodeValToRGB")
    rampa.color_ramp.elements[0].position = 0.35
    rampa.color_ramp.elements[0].color = (0.012, 0.012, 0.013, 1)
    rampa.color_ramp.elements[1].position = 0.75
    rampa.color_ramp.elements[1].color = (0.06, 0.06, 0.065, 1)
    nt.links.new(ruido.outputs["Fac"], rampa.inputs["Fac"])
    nt.links.new(rampa.outputs["Color"], bsdf.inputs["Base Color"])
    bpy.ops.mesh.primitive_plane_add(size=3, location=(0, 0.6, 0))
    bpy.context.object.data.materials.append(piedra)

    def luz(nombre, loc, objetivo, energia, tam, color=(1, 1, 1)):
        d = bpy.data.lights.new(nombre, "AREA")
        d.energy, d.size, d.color = energia, tam, color
        o = bpy.data.objects.new(nombre, d)
        sc.collection.objects.link(o)
        o.location = loc
        o.rotation_mode = "QUATERNION"
        o.rotation_quaternion = (Vector(objetivo) - Vector(loc)).to_track_quat("-Z", "Y")

    luz("clave", (-0.5, -0.6, 0.6), (0, 0, 0.03), 70, 0.7, (1.0, 0.96, 0.9))
    luz("relleno", (0.7, -0.4, 0.3), (0, 0, 0.03), 18, 0.9)
    luz("contra", (0.2, 0.7, 0.5), (0, 0, 0.04), 40, 0.5, (0.85, 0.9, 1.0))
    return sc


def materiales():
    pla = dict(rugosidad=0.38, barniz=0.15)
    return {
        "negro": material("PLA_negro", NEGRO, **pla),
        "azul": material("PLA_azul", AZUL_LOGO, rugosidad=0.45),
        "blanco": material("PLA_blanco", BLANCO, **pla),
        "letras": material("PLA_negro_mate", NEGRO, rugosidad=0.7),
    }


COLORES = {"negro": ("base_cuerpo", "texto_", "filete", "carbono_"),
           "azul": ("base_tapa", "logo"),
           "blanco": ("base_aro", "placa", "hidrogeno_", "enlace_")}
COLOR_HEX = {"negro": "#141414FF", "azul": "#36427AFF", "blanco": "#F2F2F2FF"}


def curvas_a_malla():
    """Convierte letras y logo en mallas cerradas (sin vértices duplicados)."""
    for o in list(bpy.context.scene.objects):
        if o.type in ("FONT", "CURVE"):
            if o.type == "FONT":
                o.data.bevel_depth = 0.0  # sin redondeo: letras cerradas y de bordes nítidos
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.convert(target="MESH")
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-7)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            bm.to_mesh(o.data)
            bm.free()


def piezas(color):
    return [o for o in bpy.context.scene.objects if o.type == "MESH" and o.name.startswith(COLORES[color])]


def exportar_stl(carpeta, prefijo="adorno_polietileno"):
    os.makedirs(carpeta, exist_ok=True)
    for color in COLORES:
        bpy.ops.object.select_all(action="DESELECT")
        sel = piezas(color)
        for o in sel:
            o.select_set(True)
        bpy.context.view_layer.objects.active = sel[0]
        ruta = os.path.join(carpeta, f"{prefijo}_{color}.stl")
        bpy.ops.wm.stl_export(filepath=ruta, export_selected_objects=True, global_scale=1000.0,
                              apply_modifiers=True, ascii_format=False)
        print("stl:", ruta, len(sel), "piezas")


def exportar_3mf(ruta, titulo="Adorno polietileno"):
    """3MF de un solo objeto con una parte por color (negro, azul, blanco), en mm.

    Bambu Studio / OrcaSlicer / PrusaSlicer lo abren como un objeto multiparte:
    solo hay que asignar un filamento a cada parte.
    """
    import zipfile
    dg = bpy.context.evaluated_depsgraph_get()
    mats = "".join(f'<base name="{c.capitalize()}" displaycolor="{COLOR_HEX[c]}"/>' for c in COLORES)
    objetos, comps = [], []
    for k, color in enumerate(COLORES):
        vs, ts = [], []
        for o in piezas(color):
            ev = o.evaluated_get(dg)
            me = ev.to_mesh()
            me.calc_loop_triangles()
            base = len(vs)
            mw = o.matrix_world
            vs += [mw @ vt.co / MM for vt in me.vertices]
            ts += [tuple(base + i for i in tri.vertices) for tri in me.loop_triangles]
            ev.to_mesh_clear()
        xml_v = "".join(f'<vertex x="{p.x:.4f}" y="{p.y:.4f}" z="{p.z:.4f}"/>' for p in vs)
        xml_t = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in ts)
        oid = k + 2
        objetos.append(f'<object id="{oid}" type="model" name="{color}" pid="1" pindex="{k}">'
                       f'<mesh><vertices>{xml_v}</vertices><triangles>{xml_t}</triangles></mesh></object>')
        comps.append(f'<component objectid="{oid}"/>')
        print(f"3mf: parte {color}: {len(vs)} vértices, {len(ts)} triángulos")
    padre = len(COLORES) + 2
    modelo = ('<?xml version="1.0" encoding="UTF-8"?>'
              '<model unit="millimeter" xml:lang="es-PE" '
              'xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02">'
              f'<metadata name="Title">{titulo} - Claudio Alvarez S.</metadata>'
              '<metadata name="Designer">Polímeros Norte - I+D</metadata>'
              f'<resources><basematerials id="1">{mats}</basematerials>{"".join(objetos)}'
              f'<object id="{padre}" type="model" name="{titulo}"><components>{"".join(comps)}'
              f'</components></object></resources><build><item objectid="{padre}"/></build></model>')
    tipos = ('<?xml version="1.0" encoding="UTF-8"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>'
             '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Target="/3D/3dmodel.model" Id="rel0" '
            'Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/></Relationships>')
    with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", tipos)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", modelo)
    print("3mf:", ruta)


VISTAS = {
    "principal": dict(loc=(0.18, -0.34, 0.21), objetivo=(0, 0.002, 0.036), focal=58),
    "frontal": dict(loc=(0.0, -0.40, 0.14), objetivo=(0, 0.0, 0.036), focal=60),
    "superior": dict(loc=(-0.17, -0.22, 0.30), objetivo=(0, 0.005, 0.03), focal=52),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    ap = argparse.ArgumentParser()
    ap.add_argument("--vistas", default=",".join(VISTAS))
    ap.add_argument("--out", default=os.path.join(AQUI, "..", "renders", "adorno_polietileno"))
    ap.add_argument("--stl", default=os.path.join(AQUI, "..", "imprimir_3d"))
    ap.add_argument("--sin-stl", action="store_true")
    ap.add_argument("--samples", type=int, default=160)
    ap.add_argument("--res", type=float, default=1.0)
    a = ap.parse_args(argv)

    sc = escena(a.res, a.samples)
    m = materiales()
    z_tapa = base(m)
    puntos = unidad_polietileno(m, z_tapa)
    placa(m, z_tapa)
    xs, ys, zs = zip(*[(p.x / MM, p.y / MM, p.z / MM) for p in puntos])
    print(f"molécula (centros) x {min(xs):.1f}..{max(xs):.1f}  y {min(ys):.1f}..{max(ys):.1f}  z {min(zs):.1f}..{max(zs):.1f} mm")

    for nombre in filter(None, a.vistas.split(",")):
        v = VISTAS[nombre]
        enfoque = (Vector((0, -0.025, 0.025)) - Vector(v["loc"])).length  # nítido desde la placa
        camara(sc, v["loc"], v["objetivo"], v["focal"], enfoque)
        sc.camera.data.dof.aperture_fstop = 11.0
        sc.render.filepath = os.path.abspath(f"{a.out}_{nombre}.png")
        bpy.ops.render.render(write_still=True)
        print("render:", sc.render.filepath)
        bpy.data.objects.remove(sc.camera)

    if not a.sin_stl:
        curvas_a_malla()
        carpeta = os.path.abspath(a.stl)
        exportar_stl(carpeta)
        exportar_3mf(os.path.join(carpeta, "adorno_polietileno.3mf"))
        # .blend listo para imprimir: todo en mallas, una colección por color
        for color in COLORES:
            col = bpy.data.collections.new(f"imprimir_{color}")
            bpy.context.scene.collection.children.link(col)
            for o in piezas(color):
                for c in o.users_collection:
                    c.objects.unlink(o)
                col.objects.link(o)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(carpeta, "adorno_polietileno.blend"))


if __name__ == "__main__":
    main()
