"""
Placa de escritorio con porta-lapiceros, imprimible en 3D.

  - Frente: placa inclinada (como las placas de nombre de aluminio) con panel
    blanco, rieles azules, logo de Polímeros Norte en azul y
    "Claudio Alvarez S." / "COORDINADOR DE I+D" en negro.
  - Atrás: bloque con 4 agujeros para lapiceros (Ø 13 mm, 64 mm de profundidad).
  - Arriba, al centro: la unidad del polietileno -[CH2-CH2]- (2 carbonos, cada
    uno con 2 H) sobre un pedestal azul.

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
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adorno_polietileno as ap  # noqa: E402
from adornos_escritorio import AQUI, CARGO, NOMBRE, caja, camara, marco, prisma, texto  # noqa: E402

MM = ap.MM
ANCHO = 200.0

# perfil del cuerpo (y, z) en mm: placa inclinada al frente y bloque porta-lapiceros atrás
PIE_PLACA = (-58.0, 0.0)
TOPE_PLACA = (-30.0, 48.0)
Y_BLOQUE, Y_ATRAS, ALTO_BLOQUE = -20.0, 45.0, 76.0

# agujeros para lapiceros
AGUJEROS_X = (-84.0, -62.0, 62.0, 84.0)
R_AGUJERO, PROF_AGUJERO = 6.5, 64.0
Y_CENTRO_BLOQUE = (Y_BLOQUE + Y_ATRAS) / 2

PEDESTAL = (92.0, 56.0, 1.6)  # mm, rectángulo redondeado azul bajo la molécula


def cuerpo(m):
    perfil = [PIE_PLACA, (Y_ATRAS, 0.0), (Y_ATRAS, ALTO_BLOQUE), (Y_BLOQUE, ALTO_BLOQUE),
              (Y_BLOQUE, TOPE_PLACA[1]), TOPE_PLACA]
    o = prisma("cuerpo", [(y * MM, z * MM) for y, z in perfil], ANCHO * MM, m["negro"], bisel=1.2 * MM)
    bpy.context.view_layer.objects.active = o
    o.select_set(True)
    bpy.ops.object.modifier_apply(modifier="bisel")
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()

    # agujeros: un solo objeto con los 4 cilindros, restado con el solver exacto
    cortes = []
    for x in AGUJEROS_X:
        bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=R_AGUJERO * MM, depth=(PROF_AGUJERO + 2) * MM,
                                            location=(x * MM, Y_CENTRO_BLOQUE * MM,
                                                      (ALTO_BLOQUE - PROF_AGUJERO / 2 + 1) * MM))
        cortes.append(bpy.context.object)
    bpy.ops.object.select_all(action="DESELECT")
    for c in cortes:
        c.select_set(True)
    bpy.context.view_layer.objects.active = cortes[0]
    bpy.ops.object.join()
    corte = bpy.context.object
    mod = o.modifiers.new("agujeros", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.solver = "EXACT"
    mod.object = corte
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.modifier_apply(modifier="agujeros")
    bpy.data.objects.remove(corte)
    ap.suavizar(o, math.radians(35))
    return o


def pedestal(m):
    a, b, h = PEDESTAL
    z0 = ALTO_BLOQUE - 0.4
    contorno = lambda z: [(x, y + Y_CENTRO_BLOQUE, zz) for x, y, zz in ap.elipse(a / 2, b / 2, z, p=4.0)]
    ap.solido_lofteado("pedestal", [contorno(z0), contorno(z0 + h)], m["azul"])
    return z0 + h


def frente(m):
    """Panel blanco, rieles azules, logo, nombre y cargo sobre la cara inclinada."""
    p0 = Vector((0, *PIE_PLACA)) * MM
    p1 = Vector((0, *TOPE_PLACA)) * MM
    v = (p1 - p0).normalized()
    u = Vector((1, 0, 0))
    n = u.cross(v)
    largo = (p1 - p0).length / MM
    en_cara = lambda s, x=0.0, sobre=0.0: p0 + v * (s * MM) + u * (x * MM) + n * (sobre * MM)

    panel_ancho, panel_alto, panel_e = 186.0, 40.0, 1.2
    o = caja("placa_panel", (panel_ancho * MM, panel_alto * MM, panel_e * MM), (0, 0, 0), m["blanco"])
    o.matrix_world = marco(en_cara(largo / 2, 0, panel_e / 2 - 0.2), u, v)
    for k, signo in enumerate((-1, 1)):
        r = caja(f"riel_{k + 1}", ((panel_ancho + 6) * MM, 2.6 * MM, 2.2 * MM), (0, 0, 0), m["azul"])
        r.matrix_world = marco(en_cara(largo / 2 + signo * (panel_alto / 2 + 1.3), 0, 1.1 - 0.2), u, v)

    sup = panel_e - 0.2  # superficie del panel
    x_logo, x_sep, x_texto = -58.0, -21.0, 38.0
    _, ancho_logo = ap.logo("logo", marco(en_cara(largo / 2, x_logo, sup - 0.1), u, v), 19.0 * MM, 1.0 * MM,
                            m["azul"])
    sep = caja("filete_vertical", (0.8 * MM, 28 * MM, 1.0 * MM), (0, 0, 0), m["letras"])
    sep.matrix_world = marco(en_cara(largo / 2, x_sep, sup + 0.4), u, v)
    nombre = texto("texto_nombre", NOMBRE, ap.FUENTE_NOMBRE, 12.5 * MM,
                   marco(en_cara(largo / 2 + 7.5, x_texto, sup - 0.1), u, v), m["letras"], relieve=1.0 * MM,
                   espaciado=1.03)
    texto("texto_cargo", CARGO, ap.FUENTE_CARGO, 5.0 * MM, marco(en_cara(largo / 2 - 10.5, x_texto, sup - 0.1), u, v),
          m["letras"], relieve=1.0 * MM, espaciado=1.30)
    fil = caja("filete", (88 * MM, 0.8 * MM, 1.0 * MM), (0, 0, 0), m["letras"])
    fil.matrix_world = marco(en_cara(largo / 2 - 2.5, x_texto, sup + 0.4), u, v)
    bpy.context.view_layer.update()
    print(f"cara inclinada {largo:.1f} mm; logo {ancho_logo / MM:.1f} x 19 mm; nombre {nombre.dimensions.x / MM:.1f} mm")


def molecula(m, z_apoyo):
    # misma unidad -[CH2-CH2]- del adorno anterior, a escala del bloque
    ap.ESCALA, ap.R_C, ap.R_H, ap.R_ENL = 26.0, 11.0, 7.8, 3.2
    ap.LARGO_ABIERTO, ap.HUNDIDO, ap.Y_MOLECULA = 0.95, 1.2, Y_CENTRO_BLOQUE
    return ap.unidad_polietileno(m, z_apoyo)


COLORES = {"negro": ("cuerpo", "texto_", "filete", "carbono_"),
           "azul": ("riel_", "logo", "pedestal"),
           "blanco": ("placa_", "hidrogeno_", "enlace_")}

VISTAS = {
    "principal": dict(loc=(0.24, -0.42, 0.27), objetivo=(0, -0.008, 0.055), focal=55),
    "frontal": dict(loc=(0.0, -0.50, 0.17), objetivo=(0, -0.01, 0.055), focal=58),
    "lateral": dict(loc=(-0.36, -0.30, 0.30), objetivo=(0, 0.0, 0.06), focal=55),
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
    cuerpo(m)
    z_apoyo = pedestal(m)
    frente(m)
    pts = molecula(m, z_apoyo)
    print("molécula: z máx centros", round(max(p.z for p in pts) / MM, 1), "mm")

    for nombre in filter(None, a.vistas.split(",")):
        v = VISTAS[nombre]
        camara(sc, v["loc"], v["objetivo"], v["focal"], (Vector((0, -0.04, 0.03)) - Vector(v["loc"])).length)
        sc.camera.data.dof.aperture_fstop = 11.0
        sc.render.filepath = os.path.abspath(f"{a.out}_{nombre}.png")
        bpy.ops.render.render(write_still=True)
        print("render:", sc.render.filepath)
        bpy.data.objects.remove(sc.camera)

    if not a.sin_stl:
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
