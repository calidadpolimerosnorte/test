"""Montacargas contrapesado (gas/electrico) con mastil, horquillas, techo protector y contrapeso.
Sin materiales. Metros, piso z=0, horquillas hacia +X. Uso: python3 blender/montacargas_modelo.py"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import *

nueva_escena("Montacargas")
HW = 0.55

grupo("01_Chasis_y_Contrapeso")
box("Chasis_Inferior", (1.60, 1.10, 0.35), (0.0, 0, 0.42), bevel=0.04)
box("Carroceria_Motor", (1.10, 1.05, 0.40), (-0.30, 0, 0.78), bevel=0.06)
box("Capot_Asiento", (0.70, 0.90, 0.10), (-0.25, 0, 1.02), bevel=0.04)
box("Contrapeso", (0.45, 1.12, 0.75), (-0.95, 0, 0.62), bevel=0.10)
cyl("Faro_Trasero_Izq", 0.04, 0.03, (-1.18, 0.40, 0.90), axis="X", verts=16)
cyl("Faro_Trasero_Der", 0.04, 0.03, (-1.18, -0.40, 0.90), axis="X", verts=16)
box("Escalon_Acceso", (0.30, 0.12, 0.04), (0.30, 0.58, 0.30))
cyl("Tanque_Gas_GLP", 0.16, 0.75, (-0.80, 0, 1.22), axis="Y", verts=24)
box("Soporte_Tanque", (0.20, 0.80, 0.06), (-0.80, 0, 1.04))

grupo("02_Ruedas")
for x, r, w, nm in ((0.55, 0.33, 0.22, "Delantera"), (-0.70, 0.27, 0.18, "Trasera")):
    for sy, sn in ((1, "Izq"), (-1, "Der")):
        rueda(f"Rueda_{nm}_{sn}", (x, sy * (HW - 0.02), r), r, w, rayos=6)
    box(f"Guardafango_{nm}", (0.70, 1.12, 0.04), (x, 0, 2 * r + 0.05), bevel=0.01)

grupo("03_Cabina_Techo_Protector")
for x in (0.45, -0.75):
    for sy in (-1, 1):
        beam("Pilar_Techo_Protector", (x, sy * 0.45, 0.85), (x - 0.05 if x < 0 else x - 0.10, sy * 0.45, 2.15), 0.06)
box("Techo_Protector_Marco", (1.30, 0.98, 0.06), (-0.12, 0, 2.17), bevel=0.01)
for k in range(6):
    box("Techo_Protector_Barra", (1.25, 0.04, 0.03), (-0.12, -0.40 + k * 0.16, 2.15))
box("Asiento_Operador", (0.45, 0.45, 0.10), (-0.25, 0, 1.12), bevel=0.04)
box("Respaldo_Operador", (0.10, 0.45, 0.45), (-0.47, 0, 1.38), rot=(0, math.radians(-10), 0), bevel=0.04)
box("Tablero_Instrumentos", (0.20, 0.60, 0.30), (0.30, 0, 1.08), rot=(0, math.radians(-20), 0), bevel=0.03)
beam("Columna_Direccion", (0.28, 0, 1.15), (0.15, 0, 1.45), 0.05, round_=True)
cyl("Volante", 0.18, 0.03, (0.13, 0, 1.47), verts=24, rot=(0, math.radians(-25), 0))
for k in range(3):
    beam("Palanca_Mando_Hidraulico", (0.32, -0.25 + k * 0.08, 1.20), (0.30, -0.25 + k * 0.08, 1.38), 0.015, round_=True)
    esfera("Pomo_Palanca", 0.02, (0.30, -0.25 + k * 0.08, 1.39))
cyl("Baliza_Ambar", 0.05, 0.08, (-0.75, 0.40, 2.24), verts=16)
box("Espejo_Retrovisor", (0.03, 0.18, 0.10), (0.42, 0.50, 2.05))
cyl("Pedal_Acelerador", 0.03, 0.08, (0.40, -0.12, 0.85), axis="X", verts=12)
cyl("Pedal_Freno", 0.03, 0.08, (0.40, 0.05, 0.85), axis="X", verts=12)

grupo("04_Mastil_y_Horquillas")
MX = 0.92
for sy in (-1, 1):
    box("Mastil_Exterior_Riel", (0.08, 0.10, 2.20), (MX, sy * 0.35, 1.25), bevel=0.005)
    box("Mastil_Interior_Riel", (0.07, 0.08, 2.10), (MX + 0.06, sy * 0.28, 1.35), bevel=0.005)
    beam("Cilindro_Inclinacion", (0.55, sy * 0.38, 0.75), (MX - 0.04, sy * 0.38, 1.00), 0.06, round_=True)
for z in (0.25, 1.30, 2.32):
    box("Travesano_Mastil", (0.06, 0.78, 0.08), (MX, 0, z))
cyl("Cilindro_Elevacion", 0.045, 1.80, (MX - 0.02, 0, 1.10), verts=16)
cyl("Vastago_Elevacion", 0.025, 0.40, (MX - 0.02, 0, 2.10), verts=12)
for sy in (-1, 1):
    cyl("Polea_Cadena", 0.05, 0.04, (MX + 0.02, sy * 0.12, 2.33), axis="Y", verts=16)
    beam("Cadena_Elevacion", (MX + 0.04, sy * 0.12, 2.33), (MX + 0.10, sy * 0.12, 0.55), 0.02, t2=0.015)
CZ = 0.35
box("Placa_Porta_Horquillas", (0.06, 1.00, 0.40), (MX + 0.14, 0, CZ + 0.20), bevel=0.005)
box("Rejilla_Respaldo_Carga", (0.03, 1.00, 0.60), (MX + 0.13, 0, CZ + 0.70))
for k in range(5):
    box("Barra_Rejilla_Respaldo", (0.03, 0.03, 0.60), (MX + 0.13, -0.40 + k * 0.20, CZ + 0.70))
for sy, sn in ((1, "Izq"), (-1, "Der")):
    box(f"Horquilla_Vertical_{sn}", (0.05, 0.12, 0.45), (MX + 0.19, sy * 0.30, CZ + 0.20))
    box(f"Horquilla_Pala_{sn}", (1.10, 0.12, 0.045), (MX + 0.19 + 0.55, sy * 0.30, CZ - 0.01))

finalizar("montacargas_modelo.blend", os.path.dirname(os.path.abspath(__file__)))
