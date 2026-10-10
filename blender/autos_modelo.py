"""Cinco autos genericos (sedan, hatchback, SUV, camioneta pickup y minivan), sin marcas.
Sin materiales. Metros, piso z=0, frente hacia +X; cada auto en su coleccion, separados en Y.
Uso: python3 blender/autos_modelo.py"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import *

nueva_escena("Autos")
AQUI = os.path.dirname(os.path.abspath(__file__))

# Cada tabla va de adelante (+X) hacia atras; lerp_table interpola.
AUTOS = [
    dict(tag="Sedan", L=4.60, hw=0.90, eje=2.70, xf=1.40, r=0.32, tw=0.21,
         bot=[(2.30, 0.36), (2.05, 0.20), (-1.95, 0.20), (-2.30, 0.40)],
         top=[(2.30, 0.60), (2.18, 0.74), (1.10, 0.86), (0.80, 0.92), (-1.50, 0.96), (-2.20, 0.95), (-2.30, 0.72)],
         gh=(0.85, -1.55), techo=[(0.85, 0.94), (0.05, 1.43), (-0.75, 1.44), (-1.55, 0.98)], belt=0.93),
    dict(tag="Hatchback", L=4.05, hw=0.87, eje=2.55, xf=1.25, r=0.31, tw=0.20,
         bot=[(2.02, 0.36), (1.80, 0.20), (-1.75, 0.20), (-2.02, 0.42)],
         top=[(2.02, 0.60), (1.90, 0.74), (0.90, 0.88), (0.65, 0.93), (-1.85, 0.97), (-2.02, 0.95)],
         gh=(0.70, -1.90), techo=[(0.70, 0.95), (-0.10, 1.46), (-1.55, 1.44), (-1.90, 1.00)], belt=0.94),
    dict(tag="SUV", L=4.70, hw=0.95, eje=2.80, xf=1.45, r=0.37, tw=0.24,
         bot=[(2.35, 0.48), (2.15, 0.30), (-2.05, 0.30), (-2.35, 0.50)],
         top=[(2.35, 0.78), (2.22, 0.95), (1.20, 1.05), (0.90, 1.10), (-2.20, 1.13), (-2.35, 1.10)],
         gh=(0.95, -2.25), techo=[(0.95, 1.11), (0.20, 1.70), (-1.95, 1.70), (-2.25, 1.15)], belt=1.10,
         barras=True),
    dict(tag="Pickup", L=5.30, hw=0.95, eje=3.10, xf=1.45, r=0.38, tw=0.25,
         bot=[(2.65, 0.50), (2.45, 0.34), (-2.45, 0.34), (-2.65, 0.50)],
         top=[(2.65, 0.82), (2.52, 0.98), (1.50, 1.08), (1.20, 1.12), (-0.40, 1.14)],
         gh=(1.22, -0.40), techo=[(1.22, 1.13), (0.50, 1.80), (-0.30, 1.80), (-0.40, 1.15)], belt=1.12,
         caja=(-0.45, -2.65)),
    dict(tag="Minivan", L=5.00, hw=0.97, eje=3.00, xf=1.25, r=0.34, tw=0.23,
         bot=[(2.50, 0.38), (2.30, 0.22), (-2.20, 0.22), (-2.50, 0.42)],
         top=[(2.50, 0.66), (2.40, 0.82), (1.75, 0.94), (1.45, 1.00), (-2.35, 1.03), (-2.50, 1.00)],
         gh=(1.50, -2.42), techo=[(1.50, 1.01), (0.55, 1.76), (-2.10, 1.78), (-2.42, 1.08)], belt=1.00,
         barras=True, corrediza=True),
]


def estaciones(x0, x1, n):
    return [x0 + (x1 - x0) * k / (n - 1) for k in range(n)]


def auto(c, Y):
    t, hw, r, L = c["tag"], c["hw"], c["r"], c["L"]
    xfa = L / 2 - c["xf"]            # eje delantero
    xra = xfa - c["eje"]             # eje trasero
    xb = c["caja"][0] if "caja" in c else -L / 2

    def ancho(x):                    # medio ancho que se afina en los extremos
        e = min(L / 2 - x, x + L / 2)
        return hw * (0.86 + 0.14 * min(1.0, e / 0.45))

    def perfil_bajo(x):
        zb, = lerp_table(c["bot"], x)
        zt, = lerp_table(c["top"], x)
        w = ancho(x)
        return [(0, zb), (w * 0.90, zb), (w, zb + 0.10), (w, zt - 0.07), (w * 0.94, zt), (0, zt)]

    def perfil_alto(x):
        zr, = lerp_table(c["techo"], x)
        zb = c["belt"] - 0.04
        w = ancho(x) * 0.97
        return [(0, zb), (w, zb), (w * 0.84, zr - 0.05), (w * 0.72, zr), (0, zr)]

    cuerpo = loft(f"{t}_Carroceria", estaciones(L / 2, xb, 40), perfil_bajo)
    cuerpo.location.y = Y
    for x in (xfa, xra):
        cut = cyl(f"{t}_Corte_Guardafango", r + 0.05, 2 * hw + 0.4, (x, Y, r), axis="Y", verts=32)
        cut.hide_render = True
        cut.hide_viewport = True
        md = cuerpo.modifiers.new("Arco", "BOOLEAN")
        md.object = cut
        md.operation = "DIFFERENCE"
    g0, g1 = c["gh"]
    hab = loft(f"{t}_Habitaculo_Techo", estaciones(g0, g1, 60), perfil_alto)
    hab.location.y = Y

    # Vidrios: placas delgadas pegadas a la superficie del habitaculo
    tech = c["techo"]
    xs_top0, xs_top1 = tech[1][0], tech[-2][0]           # inicio y fin del techo plano
    zb = c["belt"]
    def pto_lado(x, z, s):
        zr, = lerp_table(tech, x)
        w = ancho(x) * 0.97
        frac = max(0.0, min(1.0, (z - (zb - 0.04)) / max(0.05, zr - 0.05 - (zb - 0.04))))
        return (x, Y + s * (w - 0.16 * w * frac + 0.014), z)

    def ventana(nombre, xa, xc, s):
        z0 = zb + 0.05
        n = 24
        top = []
        for k in range(n + 1):
            x = xa + (xc - xa) * k / n
            zt = lerp_table(tech, x)[0] - 0.09
            if zt > z0 + 0.18:
                top.append(pto_lado(x, zt, s))
        if len(top) < 2:
            return
        pts = [pto_lado(top[0][0], z0, s), pto_lado(top[-1][0], z0, s)] + top[::-1]
        face = tuple(range(len(pts)))
        from_pydata(nombre, pts, [face if s > 0 else face[::-1]], smooth=False, solidify=0.005)

    wf0 = (ancho(g0) * 0.80, zb + 0.03)
    p = [(g0 - 0.06, Y - wf0[0], wf0[1]), (g0 - 0.06, Y + wf0[0], wf0[1]),
         (xs_top0 + 0.06, Y + ancho(xs_top0) * 0.66, tech[1][1] - 0.03),
         (xs_top0 + 0.06, Y - ancho(xs_top0) * 0.66, tech[1][1] - 0.03)]
    fr = Vector((g0 - xs_top0, 0, tech[1][1] - zb)).normalized()
    nrm = Vector((fr.z, 0, -fr.x)) * -0.008
    from_pydata(f"{t}_Parabrisas", [Vector(q) + nrm for q in p], [(0, 1, 2, 3)], smooth=False, solidify=0.006)
    zr1 = tech[-2][1]
    q = [(g1 + 0.06, Y + ancho(g1) * 0.78, zb + 0.06), (g1 + 0.06, Y - ancho(g1) * 0.78, zb + 0.06),
         (xs_top1 - 0.05, Y - ancho(xs_top1) * 0.66, zr1 - 0.04), (xs_top1 - 0.05, Y + ancho(xs_top1) * 0.66, zr1 - 0.04)]
    br = Vector((xs_top1 - g1, 0, zr1 - zb)).normalized()
    nrm = Vector((-br.z, 0, br.x)) * 0.008
    from_pydata(f"{t}_Luneta_Trasera", [Vector(v) + nrm for v in q], [(0, 1, 2, 3)], smooth=False, solidify=0.006)
    # ventanas laterales separadas por pilares
    largo = g0 - g1
    n_v = 2 if "caja" in c else 3 if largo > 2.6 else 2
    cortes = estaciones(g0 - 0.10, g1 + 0.10, n_v + 1)
    for s, sn in ((1, "Izq"), (-1, "Der")):
        for k in range(n_v):
            xa, xc = cortes[k], cortes[k + 1]
            ventana(f"{t}_Ventana_Lateral_{k + 1}_{sn}", xa - 0.04, xc + 0.04, s)
        # puertas: lineas como tiras delgadas y manijas
        n_p = 2 if c.get("corrediza") else n_v if "caja" in c else 2
        xp = estaciones(g0 + 0.05, g1 + (0.55 if n_v == 3 else 0.10), n_p + 1)
        zt_door = zb - 0.05
        for k, x in enumerate(xp):
            box(f"{t}_Junta_Puerta_{sn}", (0.006, 0.006, zt_door - 0.30), (x, Y + s * (ancho(x) + 0.002), (zt_door + 0.30) / 2))
        for k in range(n_p):
            xm = xp[k + 1] + 0.12
            box(f"{t}_Manija_Puerta_{sn}", (0.16, 0.025, 0.035), (xm, Y + s * (ancho(xm) + 0.012), zb - 0.12), bevel=0.008)
        if c.get("corrediza"):
            box(f"{t}_Riel_Puerta_Corrediza_{sn}", (1.10, 0.02, 0.025), (xp[-1] - 0.50, Y + s * (ancho(xp[-1]) + 0.01), zb - 0.05))
        # espejo retrovisor
        xe = g0 - 0.15
        box(f"{t}_Brazo_Espejo_{sn}", (0.10, 0.10, 0.04), (xe, Y + s * (ancho(xe) + 0.05), zb + 0.04))
        box(f"{t}_Espejo_Retrovisor_{sn}", (0.08, 0.20, 0.14), (xe - 0.03, Y + s * (ancho(xe) + 0.17), zb + 0.08), bevel=0.03)
        # luces
        xl = L / 2 - 0.10
        zl, = lerp_table(c["top"], xl)
        box(f"{t}_Faro_Delantero_{sn}", (0.12, 0.30, 0.10), (xl, Y + s * (ancho(xl) - 0.20), zl - 0.10), bevel=0.02)
        xt = xb + 0.04
        zt2, = lerp_table(c["top"], xt) if "caja" not in c else (1.10,)
        box(f"{t}_Faro_Posterior_{sn}", (0.10, 0.22, 0.16), (xt, Y + s * (ancho(xt) - 0.14 if "caja" not in c else hw - 0.05), zt2 - 0.16), bevel=0.02)
        box(f"{t}_Estribo_Faldon_{sn}", (c["eje"] - 2 * r - 0.25, 0.06, 0.08), ((xfa + xra) / 2, Y + s * (hw - 0.02), lerp_table(c["bot"], 0)[0] + 0.05), bevel=0.02)
        for x, nm in ((xfa, "Delantera"), (xra, "Trasera")):
            rueda(f"{t}_Rueda_{nm}_{sn}", (x, Y + s * (hw - c["tw"] / 2 - 0.02), r), r, c["tw"], rayos=5)

    # frente y parte trasera
    zf, = lerp_table(c["top"], L / 2)
    zbf, = lerp_table(c["bot"], L / 2)
    box(f"{t}_Parrilla", (0.04, hw * 0.95, (zf - zbf) * 0.40), (L / 2 + 0.005, Y, zbf + (zf - zbf) * 0.55), bevel=0.01)
    box(f"{t}_Parachoque_Delantero", (0.16, 2 * hw * 0.97, 0.16), (L / 2 - 0.02, Y, zbf + 0.06), bevel=0.05)
    box(f"{t}_Placa_Delantera", (0.01, 0.34, 0.12), (L / 2 + 0.065, Y, zbf + 0.07))
    box(f"{t}_Neblinero_Izq", (0.03, 0.10, 0.05), (L / 2 + 0.065, Y + hw * 0.70, zbf + 0.07))
    box(f"{t}_Neblinero_Der", (0.03, 0.10, 0.05), (L / 2 + 0.065, Y - hw * 0.70, zbf + 0.07))
    zbr, = lerp_table(c["bot"], -L / 2)
    box(f"{t}_Parachoque_Posterior", (0.16, 2 * hw * 0.97, 0.18), (-L / 2 + 0.02, Y, zbr + 0.04), bevel=0.05)
    box(f"{t}_Placa_Posterior", (0.01, 0.34, 0.12), (-L / 2 - 0.065, Y, zbr + 0.20))
    cyl(f"{t}_Tubo_Escape", 0.03, 0.20, (-L / 2 + 0.02, Y - hw * 0.55, zbr - 0.04), axis="X", verts=16)
    # capo, limpiaparabrisas, antena, tapa de combustible
    xg = g0 + 0.05
    for s in (1, -1):
        beam(f"{t}_Limpiaparabrisas", (xg, Y + s * 0.05, zb + 0.03), (xg - 0.10, Y + s * 0.50, zb + 0.06), 0.018, t2=0.012)
    beam(f"{t}_Antena", (g1 + 0.25, Y, lerp_table(tech, g1 + 0.25)[0] - 0.01), (g1 + 0.05, Y, lerp_table(tech, g1 + 0.25)[0] + 0.07), 0.02, round_=True)
    xc = xra + r + 0.25
    cyl(f"{t}_Tapa_Combustible", 0.07, 0.01, (xc, Y - ancho(xc) - 0.003, zb - 0.20), axis="Y", verts=20)
    if c.get("barras"):
        for s, sn in ((1, "Izq"), (-1, "Der")):
            a, b = tech[1][0] - 0.10, tech[-2][0] + 0.05
            zr = tech[1][1]
            for x in (a, b):
                box(f"{t}_Soporte_Barra_Techo_{sn}", (0.08, 0.04, 0.05), (x, Y + s * ancho(x) * 0.62, zr + 0.02))
            box(f"{t}_Barra_Techo_{sn}", (a - b + 0.05, 0.035, 0.03), ((a + b) / 2, Y + s * ancho(a) * 0.62, zr + 0.06), bevel=0.01)
    if "caja" in c:     # caja de carga de la camioneta
        x0, x1 = c["caja"]
        lc, zp, zr = x0 - x1, lerp_table(c["bot"], -1.0)[0] + 0.30, 1.10
        cx = (x0 + x1) / 2
        caja = box(f"{t}_Caja_Carga_Piso", (lc, 2 * hw, zp - 0.34), (cx, Y, (zp + 0.34) / 2), bevel=0.02)
        md = caja.modifiers.new("Arco", "BOOLEAN")
        cutc = cyl(f"{t}_Corte_Caja", r + 0.05, 2 * hw + 0.4, (xra, Y, r), axis="Y", verts=32)
        cutc.hide_render = cutc.hide_viewport = True
        md.object, md.operation = cutc, "DIFFERENCE"
        for s, sn in ((1, "Izq"), (-1, "Der")):
            pared = box(f"{t}_Caja_Pared_Lateral_{sn}", (lc, 0.05, zr - zp), (cx, Y + s * (hw - 0.025), (zr + zp) / 2), bevel=0.01)
            md = pared.modifiers.new("Arco", "BOOLEAN")
            md.object, md.operation = cutc, "DIFFERENCE"
            box(f"{t}_Caja_Borde_Superior_{sn}", (lc, 0.08, 0.03), (cx, Y + s * (hw - 0.04), zr + 0.015), bevel=0.01)
            box(f"{t}_Guardafango_Interior_{sn}", (2 * r + 0.15, 0.25, r * 0.6), (xra, Y + s * (hw - 0.17), zp + r * 0.3), bevel=0.04)
        box(f"{t}_Caja_Pared_Frontal", (0.05, 2 * hw, zr - zp), (x0 - 0.025, Y, (zr + zp) / 2))
        box(f"{t}_Compuerta_Trasera", (0.05, 2 * hw, zr - zp + 0.08), (x1 + 0.025, Y, (zr + zp) / 2 - 0.04), bevel=0.01)
        box(f"{t}_Manija_Compuerta", (0.03, 0.22, 0.05), (x1 - 0.005, Y, zr - 0.12), bevel=0.01)
        box(f"{t}_Barra_Antivuelco", (0.06, 2 * hw - 0.20, 0.06), (x0 - 0.10, Y, 1.55), bevel=0.01)
        for s in (1, -1):
            beam(f"{t}_Parante_Antivuelco", (x0 - 0.10, Y + s * (hw - 0.13), zr), (x0 - 0.10, Y + s * (hw - 0.13), 1.55), 0.06, round_=True)


for i, c in enumerate(AUTOS):
    grupo(f"{i + 1:02d}_{c['tag']}")
    auto(c, i * 3.0)

finalizar("autos_modelo.blend", AQUI)
