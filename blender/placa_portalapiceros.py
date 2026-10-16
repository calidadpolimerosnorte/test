"""
Placa de escritorio delgada en la que las moléculas son el porta-lapiceros.

  - Piso fino (3 mm) de esquinas redondeadas.
  - Al frente, una placa inclinada de 3 mm (como las placas de nombre de aluminio)
    con rieles azules, logo de Polímeros Norte en azul y "Claudio Alvarez S." /
    "COORDINADOR DE I+D" en negro.
  - Atrás, dos unidades del polietileno -[CH2-CH2]- (cada carbono con 2 H y 2
    enlaces C). Cada carbono es un porta-lapicero: un agujero vertical de Ø 13 mm
    lo atraviesa y baja hasta un rebaje en el piso donde se apoya la punta.
    4 lapiceros en total.

Colores (sin rojo): negro, azul (#36427A) y blanco.
Salida en imprimir_3d/: placa_portalapiceros.3mf (una parte por color), .blend y STL.

Uso:
  python3 blender/placa_portalapiceros.py
  python3 blender/placa_portalapiceros.py --samples 24 --res 0.5 --sin-stl
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adorno_polietileno as ap  # noqa: E402
from adornos_escritorio import AQUI, CARGO, NOMBRE, caja, camara, cilindro_entre, esfera, marco, material, texto  # noqa: E402

MM = ap.MM

# piso
PISO_A, PISO_B, PISO_Y, PISO_E = 90.0, 46.0, 3.0, 3.0   # semiejes, centro en Y y espesor (mm)

# placa inclinada
PLACA_ANCHO, PLACA_ALTO, PLACA_E = 170.0, 30.0, 3.0
PLACA_ANG = 65.0                    # grados sobre la horizontal
PLACA_PIE = (-39.0, 1.5)            # (y, z) del borde inferior de la cara frontal, dentro del piso

# moléculas porta-lapiceros
X_MOLECULAS = 45.0                  # una a cada lado (la derecha en espejo)
R_AGUJERO = 6.5                     # Ø 13 mm: lapiceros y plumones
DESCENTRADO = 5.0                   # el agujero se corre hacia el enlace C-C para no chocar con el enlace abierto
REBAJE = 1.5                        # mm que la punta del lapicero entra en el piso


def piso(m):
    contorno = lambda a, b, z: [(x, y + PISO_Y, zz) for x, y, zz in ap.elipse(a, b, z, p=5.0)]
    return ap.solido_lofteado("piso", [contorno(PISO_A - 0.8, PISO_B - 0.8, 0.0),
                                       contorno(PISO_A, PISO_B, 0.8),
                                       contorno(PISO_A, PISO_B, PISO_E)], m["negro"])


def placa(m):
    """Placa delgada inclinada: panel blanco, rieles azules, logo, nombre y cargo."""
    a = math.radians(PLACA_ANG)
    u = Vector((1, 0, 0))
    v = Vector((0, math.cos(a), math.sin(a)))
    n = u.cross(v)                                     # normal de la cara frontal (hacia adelante-arriba)
    p0 = Vector((0, *PLACA_PIE)) * MM
    en_cara = lambda s, x=0.0, sobre=0.0: p0 + v * (s * MM) + u * (x * MM) + n * (sobre * MM)

    o = caja("placa_panel", (PLACA_ANCHO * MM, PLACA_ALTO * MM, PLACA_E * MM), (0, 0, 0), m["blanco"])
    o.matrix_world = marco(en_cara(PLACA_ALTO / 2, 0, -PLACA_E / 2), u, v)
    for k, s in enumerate((2.4, PLACA_ALTO - 2.4)):
        r = caja(f"riel_{k + 1}", ((PLACA_ANCHO - 6) * MM, 1.4 * MM, 1.0 * MM), (0, 0, 0), m["azul"])
        r.matrix_world = marco(en_cara(s, 0, 0.4), u, v)

    x_logo, x_sep, x_texto = -55.0, -26.0, 29.0
    _, ancho_logo = ap.logo("logo", marco(en_cara(PLACA_ALTO / 2, x_logo, -0.1), u, v), 15.0 * MM, 1.0 * MM,
                            m["azul"])
    sep = caja("filete_vertical", (0.8 * MM, 18 * MM, 1.0 * MM), (0, 0, 0), m["letras"])
    sep.matrix_world = marco(en_cara(PLACA_ALTO / 2, x_sep, 0.4), u, v)
    nombre = texto("texto_nombre", NOMBRE, ap.FUENTE_NOMBRE, 10.5 * MM, marco(en_cara(19.2, x_texto, -0.1), u, v),
                   m["letras"], relieve=1.0 * MM, espaciado=1.03)
    texto("texto_cargo", CARGO, ap.FUENTE_CARGO, 4.3 * MM, marco(en_cara(9.4, x_texto, -0.1), u, v),
          m["letras"], relieve=1.0 * MM, espaciado=1.30)
    fil = caja("filete", (76 * MM, 0.8 * MM, 1.0 * MM), (0, 0, 0), m["letras"])
    fil.matrix_world = marco(en_cara(14.4, x_texto, 0.4), u, v)
    bpy.context.view_layer.update()
    print(f"logo {ancho_logo / MM:.1f} x 15 mm; nombre {nombre.dimensions.x / MM:.1f} mm")


def moleculas(m):
    """Dos unidades -[CH2-CH2]- grandes; devuelve los ejes (x, y) de los 4 agujeros y la altura tope."""
    ap.ESCALA, ap.R_C, ap.R_H, ap.R_ENL = 30.0, 16.0, 9.5, 4.2
    ap.LARGO_ABIERTO, ap.HUNDIDO, ap.Y_MOLECULA = 0.95, 1.0, 10.0
    ejes, z_tope = [], 0.0
    for x0, espejo in ((-X_MOLECULAS, False), (X_MOLECULAS, True)):
        pts = ap.unidad_polietileno(m, PISO_E, x0=x0, espejo=espejo)
        c1, c2 = pts[0] / MM, pts[1] / MM
        for c, otro in ((c1, c2), (c2, c1)):
            dx = math.copysign(DESCENTRADO, otro.x - c.x)
            ejes.append((c.x + dx, c.y))
            z_tope = max(z_tope, c.z + ap.R_C)
    return ejes, z_tope


def agujeros(ejes, z_tope):
    """Resta los 4 agujeros verticales a carbonos, enlaces y piso (rebaje para la punta)."""
    cortes = []
    for x, y in ejes:
        z0, z1 = PISO_E - REBAJE, z_tope + 4
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=R_AGUJERO * MM, depth=(z1 - z0) * MM,
                                            location=(x * MM, y * MM, (z0 + z1) / 2 * MM))
        cortes.append(bpy.context.object)
    bpy.ops.object.select_all(action="DESELECT")
    for c in cortes:
        c.select_set(True)
    bpy.context.view_layer.objects.active = cortes[0]
    bpy.ops.object.join()
    corte = bpy.context.object
    corte.name = "corte_agujeros"
    for o in list(bpy.context.scene.objects):
        if o.type != "MESH" or not o.name.startswith(("piso", "carbono_", "enlace_", "hidrogeno_")):
            continue
        mod = o.modifiers.new("agujeros", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.solver = "EXACT"
        mod.object = corte
        bpy.ops.object.select_all(action="DESELECT")
        bpy.context.view_layer.objects.active = o
        bpy.ops.object.modifier_apply(modifier="agujeros")
    bpy.data.objects.remove(corte)


def lapiceros(ejes):
    """Lapiceros de muestra (solo para el render, no se exportan)."""
    colores = [material("tinta_negra", (0.01, 0.01, 0.012), rugosidad=0.25),
               material("tinta_azul", (0.01, 0.03, 0.25), rugosidad=0.25),
               material("metal", (0.8, 0.8, 0.82), rugosidad=0.2, metal=1.0)]
    largos = (142, 136, 146, 139)
    for k, ((x, y), largo) in enumerate(zip(ejes, largos)):
        z0 = PISO_E - REBAJE
        mat = colores[k % 2]
        cilindro_entre(f"boligrafo_{k}", (x * MM, y * MM, z0 * MM), (x * MM, y * MM, (z0 + largo) * MM),
                       4.6 * MM, mat, lados=32)
        esfera(f"boligrafo_{k}_tapa", (x * MM, y * MM, (z0 + largo) * MM), 4.6 * MM, mat)
        caja(f"boligrafo_{k}_clip", (1.6 * MM, 1.6 * MM, 38 * MM),
             (x * MM, (y - 5.0) * MM, (z0 + largo - 22) * MM), colores[2])


COLORES = {"negro": ("piso", "texto_", "filete", "carbono_"),
           "azul": ("riel_", "logo"),
           "blanco": ("placa_", "hidrogeno_", "enlace_")}

VISTAS = {
    "principal": dict(loc=(0.30, -0.52, 0.30), objetivo=(0, 0.0, 0.07), focal=75),
    "frontal": dict(loc=(0.0, -0.60, 0.16), objetivo=(0, 0.0, 0.075), focal=72),
    "lateral": dict(loc=(-0.42, -0.34, 0.34), objetivo=(0, 0.0, 0.065), focal=75),
}


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    a_p = argparse.ArgumentParser()
    a_p.add_argument("--vistas", default=",".join(VISTAS))
    a_p.add_argument("--out", default=os.path.join(AQUI, "..", "renders", "placa_portalapiceros"))
    a_p.add_argument("--stl", default=os.path.join(AQUI, "..", "imprimir_3d"))
    a_p.add_argument("--sin-stl", action="store_true")
    a_p.add_argument("--samples", type=int, default=160)
    a_p.add_argument("--res", type=float, default=1.0)
    a = a_p.parse_args(argv)

    sc = ap.escena(a.res, a.samples)
    m = ap.materiales()
    piso(m)
    placa(m)
    ejes, z_tope = moleculas(m)
    agujeros(ejes, z_tope)
    print("agujeros (x, y) mm:", [(round(x, 1), round(y, 1)) for x, y in ejes], "tope", round(z_tope, 1))
    lapiceros(ejes)

    for nombre in filter(None, a.vistas.split(",")):
        v = VISTAS[nombre]
        camara(sc, v["loc"], v["objetivo"], v["focal"], (Vector((0, -0.01, 0.04)) - Vector(v["loc"])).length)
        sc.camera.data.dof.aperture_fstop = 11.0
        sc.render.filepath = os.path.abspath(f"{a.out}_{nombre}.png")
        bpy.ops.render.render(write_still=True)
        print("render:", sc.render.filepath)
        bpy.data.objects.remove(sc.camera)

    if not a.sin_stl:
        for o in [o for o in sc.objects if o.name.startswith("boligrafo")]:
            bpy.data.objects.remove(o)
        ap.COLORES = COLORES
        ap.curvas_a_malla()
        carpeta = os.path.abspath(a.stl)
        ap.exportar_stl(carpeta, "placa_portalapiceros")
        ap.exportar_3mf(os.path.join(carpeta, "placa_portalapiceros.3mf"), "Placa porta-lapiceros")
        for color in COLORES:
            col = bpy.data.collections.new(f"imprimir_{color}")
            sc.collection.children.link(col)
            for o in ap.piezas(color):
                for c in o.users_collection:
                    c.objects.unlink(o)
                col.objects.link(o)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(carpeta, "placa_portalapiceros.blend"))


if __name__ == "__main__":
    main()
