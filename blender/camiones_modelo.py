"""Camion rigido con caja de carga y tractocamion con semirremolque. Sin materiales. Metros, piso z=0,
frente hacia +X. Genera dos archivos: camion_modelo.blend y camion_trailer_modelo.blend.
Uso: python3 blender/camiones_modelo.py"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import *

AQUI = os.path.dirname(os.path.abspath(__file__))


def cabina(pref, xf, ancho=2.40, alto=2.95, largo=1.85, dormitorio=0.0, z0=1.05):
    """Cabina tipo cab-over: caja redondeada con parabrisas, puertas, espejos, parrilla y faros."""
    hw = ancho / 2
    L = largo + dormitorio
    xc = xf - L / 2
    box(f"{pref}_Cabina", (L, ancho, alto - z0), (xc, 0, z0 + (alto - z0) / 2), bevel=0.10)
    box(f"{pref}_Parabrisas", (0.02, ancho - 0.30, 0.85), (xf + 0.005, 0, alto - 0.70),
        rot=(0, math.radians(-6), 0))
    box(f"{pref}_Parrilla", (0.03, ancho - 0.50, 0.55), (xf + 0.01, 0, z0 + 0.55))
    for k in range(5):
        box(f"{pref}_Lama_Parrilla", (0.02, ancho - 0.60, 0.03), (xf + 0.025, 0, z0 + 0.35 + k * 0.10))
    box(f"{pref}_Parachoques", (0.25, ancho + 0.04, 0.35), (xf - 0.02, 0, z0 - 0.10), bevel=0.04)
    for sy, sn in ((1, "Izq"), (-1, "Der")):
        box(f"{pref}_Faro_{sn}", (0.04, 0.35, 0.18), (xf + 0.01, sy * (hw - 0.30), z0 + 0.05), bevel=0.02)
        box(f"{pref}_Intermitente_{sn}", (0.04, 0.10, 0.10), (xf + 0.01, sy * (hw - 0.06), z0 + 0.05))
        box(f"{pref}_Puerta_{sn}", (1.00, 0.02, alto - z0 - 0.35), (xf - 0.75, sy * (hw + 0.005), z0 + (alto - z0) / 2 - 0.10))
        box(f"{pref}_Ventana_Lateral_{sn}", (0.80, 0.02, 0.65), (xf - 0.70, sy * (hw + 0.012), alto - 0.65))
        box(f"{pref}_Manija_{sn}", (0.15, 0.03, 0.04), (xf - 1.10, sy * (hw + 0.02), z0 + 0.95))
        beam(f"{pref}_Brazo_Espejo_{sn}", (xf - 0.15, sy * hw, alto - 0.55), (xf + 0.05, sy * (hw + 0.30), alto - 0.45), 0.04)
        box(f"{pref}_Espejo_{sn}", (0.06, 0.20, 0.45), (xf + 0.08, sy * (hw + 0.35), alto - 0.55), bevel=0.02)
        for k in range(2):
            box(f"{pref}_Escalon_{sn}", (0.40, 0.25, 0.04), (xf - 0.75, sy * (hw - 0.05), z0 - 0.35 - k * 0.30))
    box(f"{pref}_Visera_Parasol", (0.25, ancho - 0.20, 0.05), (xf + 0.05, 0, alto - 0.18))
    for k in range(3):
        box(f"{pref}_Luz_Galibo", (0.04, 0.10, 0.04), (xf - 0.05, -0.30 + k * 0.30, alto + 0.01))
    if dormitorio:
        box(f"{pref}_Deflector_Techo", (1.20, ancho - 0.10, 0.55), (xf - 1.00, 0, alto + 0.25), rot=(0, math.radians(-8), 0), bevel=0.08)
    return xf - L


def chasis(pref, x0, x1, z=0.85, sep=0.45):
    for sy in (-1, 1):
        box(f"{pref}_Larguero_Chasis", (x0 - x1, 0.10, 0.28), ((x0 + x1) / 2, sy * sep, z))
    for k in range(int((x0 - x1) / 1.0) + 1):
        box(f"{pref}_Travesano_Chasis", (0.08, 2 * sep, 0.20), (x0 - k * 1.0, 0, z))


def eje(pref, x, doble=False, r=0.52, w=0.30, track=1.02):
    cyl(f"{pref}_Eje", 0.07, 2 * track, (x, 0, r), axis="Y", verts=16)
    for sy, sn in ((1, "Izq"), (-1, "Der")):
        rueda(f"{pref}_Rueda_{sn}_Ext", (x, sy * track, r), r, w, rayos=8)
        if doble:
            rueda(f"{pref}_Rueda_{sn}_Int", (x, sy * (track - w - 0.02), r), r, w, rayos=8)
        box(f"{pref}_Guardafango_{sn}", (1.10 if not doble else 1.15, 0.55, 0.04), (x, sy * (track - (0.15 if doble else 0)), 2 * r + 0.08))


# ======================================================================= camion rigido
nueva_escena("Camion_Rigido")
grupo("01_Cabina")
xb = cabina("Cabina", 3.80)
grupo("02_Chasis_y_Ejes")
chasis("Chasis", 3.60, -4.20)
eje("Eje_Delantero", 2.95)
eje("Eje_Trasero", -2.40, doble=True)
cyl("Tanque_Combustible", 0.30, 0.90, (0.80, 0.85, 0.80), axis="X", verts=24)
box("Caja_Baterias", (0.60, 0.40, 0.40), (0.0, -0.85, 0.80), bevel=0.02)
cyl("Escape_Vertical", 0.07, 1.80, (1.75, -1.10, 2.10), verts=16)
box("Parachoques_Trasero", (0.12, 2.30, 0.15), (-4.25, 0, 0.75))
for sy in (-1, 1):
    box("Defensa_Lateral", (3.20, 0.05, 0.12), (0.35, sy * 1.15, 0.65))
grupo("03_Caja_de_Carga")
cx0, cx1 = 1.85, -4.30
box("Caja_Carga", (cx0 - cx1, 2.48, 2.60), ((cx0 + cx1) / 2, 0, 1.15 + 1.30), bevel=0.03)
box("Piso_Caja", (cx0 - cx1, 2.48, 0.12), ((cx0 + cx1) / 2, 0, 1.09))
for k in range(9):
    for sy in (-1, 1):
        box("Poste_Lateral_Caja", (0.06, 0.02, 2.55), (cx1 + 0.35 + k * 0.70, sy * 1.25, 2.45))
for sy, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Puerta_Trasera_{sn}", (0.03, 1.22, 2.50), (cx1 - 0.015, sy * 0.62, 2.45))
    for z in (1.6, 2.4, 3.2):
        box(f"Bisagra_Puerta_{sn}", (0.04, 0.08, 0.12), (cx1 - 0.03, sy * 1.20, z))
    beam(f"Barra_Cierre_{sn}", (cx1 - 0.04, sy * 0.30, 1.25), (cx1 - 0.04, sy * 0.30, 3.65), 0.03, round_=True)
    box(f"Calavera_{sn}", (0.04, 0.30, 0.12), (-4.32, sy * 0.95, 0.80))
finalizar("camion_modelo.blend", AQUI)

# ======================================================================= tractocamion + semirremolque
nueva_escena("Tractocamion_con_Semirremolque")
grupo("01_Tracto_Cabina")
cabina("Tracto", 4.90, dormitorio=0.80)
grupo("02_Tracto_Chasis_y_Ejes")
chasis("Tracto_Chasis", 4.70, -0.90)
eje("Tracto_Eje_Delantero", 4.05)
eje("Tracto_Eje_Motriz_1", 0.85, doble=True)
eje("Tracto_Eje_Motriz_2", -0.45, doble=True)
for sy in (1, -1):
    cyl("Tracto_Tanque_Combustible", 0.32, 1.20, (2.30, sy * 0.85, 0.85), axis="X", verts=24)
cyl("Tracto_Escape_Vertical", 0.08, 2.20, (2.15, -1.12, 2.30), verts=16)
box("Tracto_Quinta_Rueda", (0.90, 0.90, 0.12), (0.20, 0, 1.15), bevel=0.04)
box("Tracto_Base_Quinta_Rueda", (0.80, 0.80, 0.10), (0.20, 0, 1.04))
for sy in (-1, 1):
    curve_tube("Tracto_Manguera_Aire_Remolque", [Vector((1.65, sy * 0.30, 1.50)), Vector((1.20, sy * 0.30, 1.70)),
                                                 Vector((0.70, sy * 0.25, 1.45))], 0.015)
grupo("03_Semirremolque")
SX0, SX1 = 1.30, -12.30
SZ = 1.30
box("Semirremolque_Caja", (SX0 - SX1, 2.60, 2.75), ((SX0 + SX1) / 2, 0, SZ + 1.375), bevel=0.03)
box("Semirremolque_Piso", (SX0 - SX1, 2.60, 0.14), ((SX0 + SX1) / 2, 0, SZ - 0.05))
for sy in (-1, 1):
    box("Semirremolque_Viga_Principal", (SX0 - SX1 - 0.4, 0.12, 0.35), ((SX0 + SX1) / 2, sy * 0.45, SZ - 0.30))
    box("Semirremolque_Defensa_Lateral", (5.0, 0.04, 0.12), (-4.5, sy * 1.25, 0.80))
    for k in range(20):
        box("Semirremolque_Poste_Lateral", (0.06, 0.02, 2.70), (SX1 + 0.35 + k * 0.68, sy * 1.31, SZ + 1.375))
cyl("Semirremolque_Perno_Rey", 0.05, 0.12, (0.20, 0, SZ - 0.18), verts=16)
for sy, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Semirremolque_Pata_Apoyo_{sn}", (0.12, 0.12, 0.90), (-1.30, sy * 0.80, 0.70))
    box(f"Semirremolque_Zapata_{sn}", (0.25, 0.25, 0.04), (-1.30, sy * 0.80, 0.25))
    box(f"Semirremolque_Puerta_Trasera_{sn}", (0.03, 1.28, 2.65), (SX1 - 0.015, sy * 0.65, SZ + 1.375))
    beam(f"Semirremolque_Barra_Cierre_{sn}", (SX1 - 0.04, sy * 0.30, SZ + 0.10), (SX1 - 0.04, sy * 0.30, SZ + 2.65), 0.03, round_=True)
    box(f"Semirremolque_Calavera_{sn}", (0.04, 0.30, 0.12), (SX1 - 0.05, sy * 0.95, 1.00))
cyl("Semirremolque_Manivela_Patas", 0.012, 0.35, (-1.30, -1.05, 0.95), axis="Y", verts=8)
box("Semirremolque_Parachoques_Trasero", (0.15, 2.30, 0.15), (SX1 - 0.10, 0, 0.60))
for k, x in enumerate((-9.50, -10.80, -12.0 + 0.85)):
    eje(f"Semirremolque_Eje_{k + 1}", x, doble=True)
finalizar("camion_trailer_modelo.blend", AQUI)
