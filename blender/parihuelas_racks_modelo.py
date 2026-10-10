"""Racks selectivos (parantes azules, vigas grises) con parihuelas de madera y de plastico,
en los niveles del rack y en el suelo, con y sin carga (sacos). Sin materiales. Metros, piso z=0.
Uso: python3 blender/parihuelas_racks_modelo.py"""
import math, os, sys, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import *

random.seed(7)
nueva_escena("Parihuelas_y_Racks")
PL, PW, PH = 1.20, 1.00, 0.144   # parihuela estandar (largo x ancho x alto)


def parihuela_madera(tag, x, y, z, rot=0.0):
    """Parihuela de madera: 7 tablas superiores, 3 largueros con 9 tacos, 3 tablas inferiores."""
    c, s_ = math.cos(rot), math.sin(rot)
    P = lambda dx, dy, dz: (x + dx * c - dy * s_, y + dx * s_ + dy * c, z + dz)
    for k in range(7):
        box(f"{tag}_Tabla_Superior", (PL, 0.10, 0.022), P(0, -PW / 2 + 0.05 + k * (PW - 0.10) / 6, PH - 0.011), rot=(0, 0, rot))
    for j, dy in enumerate((-PW / 2 + 0.05, 0, PW / 2 - 0.05)):
        box(f"{tag}_Larguero", (PL, 0.10, 0.022), P(0, dy, PH - 0.033), rot=(0, 0, rot))
        for dx in (-PL / 2 + 0.05, 0, PL / 2 - 0.05):
            box(f"{tag}_Taco", (0.10, 0.10, 0.078), P(dx, dy, 0.022 + 0.039), rot=(0, 0, rot))
    for dx in (-PL / 2 + 0.05, 0, PL / 2 - 0.05):
        box(f"{tag}_Tabla_Inferior", (0.10, PW, 0.022), P(dx, 0, 0.011), rot=(0, 0, rot))


def parihuela_plastico(tag, x, y, z, rot=0.0):
    """Parihuela de plastico: cubierta reticulada con aberturas y 9 patines."""
    c, s_ = math.cos(rot), math.sin(rot)
    P = lambda dx, dy, dz: (x + dx * c - dy * s_, y + dx * s_ + dy * c, z + dz)
    top = box(f"{tag}_Cubierta", (PL, PW, 0.04), P(0, 0, PH - 0.02), rot=(0, 0, rot))
    for i in range(4):
        for j in range(3):
            cut = box(f"{tag}_Corte", (0.18, 0.18, 0.10), P(-0.42 + i * 0.28, -0.30 + j * 0.30, PH - 0.02), rot=(0, 0, rot))
            cut.hide_render = cut.hide_viewport = True
            md = top.modifiers.new("Abertura", "BOOLEAN")
            md.object = cut
            md.operation = "DIFFERENCE"
    for dx in (-PL / 2 + 0.07, 0, PL / 2 - 0.07):
        for dy in (-PW / 2 + 0.07, 0, PW / 2 - 0.07):
            box(f"{tag}_Patin", (0.14, 0.14, PH - 0.06), P(dx, dy, 0.02 + (PH - 0.06) / 2), rot=(0, 0, rot), bevel=0.01)
        box(f"{tag}_Riel_Inferior", (0.14, PW, 0.02), P(dx, 0, 0.01), rot=(0, 0, rot))


def carga_sacos(tag, x, y, z, capas=4, rot=0.0):
    """Sacos apilados (5 por capa, trabados) sobre una parihuela."""
    for capa in range(capas):
        alt = capa % 2
        for k in range(5):
            if alt:
                dx, dy, sx, sy = -0.40 + k * 0.20, 0, 0.19, 0.95
            else:
                dx, dy, sx, sy = (-0.30 if k < 3 else 0.30), (-0.32 + (k % 3) * 0.32 if k < 3 else -0.16 + (k - 3) * 0.32), 0.58, 0.30
            ob = box(f"{tag}_Saco", (sx, sy, 0.13), (x + dx, y + dy, z + PH + 0.065 + capa * 0.13),
                     rot=(0, 0, rot + random.uniform(-0.03, 0.03)), bevel=0.04)


# ---------------------------------------------------------------- racks
grupo("01_Racks_Selectivos")
BAYS = 3
BL = 2.70          # largo de cada vano (2 parihuelas)
RD = 1.10          # profundidad del bastidor
LEVELS = (0.0, 1.55, 3.10)   # nivel suelo + 2 niveles de vigas
RH = 4.20
x0 = -BAYS * BL / 2
for i in range(BAYS + 1):
    x = x0 + i * BL
    for sy in (-1, 1):
        box(f"Parante_Azul", (0.09, 0.07, RH), (x, sy * RD / 2, RH / 2), bevel=0.003)
        box(f"Placa_Base_Parante", (0.15, 0.13, 0.008), (x, sy * RD / 2, 0.004))
    # diagonales y horizontales del bastidor
    zs = [0.15, 1.0, 1.9, 2.8, 3.7, 4.10]
    for k in range(len(zs) - 1):
        a, b = (x, -RD / 2, zs[k]), (x, RD / 2, zs[k + 1])
        if k % 2:
            a, b = (x, RD / 2, zs[k]), (x, -RD / 2, zs[k + 1])
        beam("Diagonal_Bastidor", a, b, 0.035, t2=0.025)
    for z in (0.15, RH - 0.10):
        beam("Horizontal_Bastidor", (x, -RD / 2, z), (x, RD / 2, z), 0.035, t2=0.025)
for i in range(BAYS):
    xc = x0 + (i + 0.5) * BL
    for z in LEVELS[1:]:
        for sy in (-1, 1):
            box("Viga_Gris_Carga", (BL - 0.09, 0.05, 0.12), (xc, sy * (RD / 2 + 0.035), z - 0.06), bevel=0.003)
        for dx in (-0.6, 0.6):
            box("Travesano_Seguridad", (0.04, RD + 0.08, 0.03), (xc + dx, 0, z + 0.015))

# ---------------------------------------------------------------- parihuelas en el rack
grupo("02_Parihuelas_en_Rack")
n = 0
for i in range(BAYS):
    xc = x0 + (i + 0.5) * BL
    for li, z in enumerate(LEVELS):
        for j, dx in enumerate((-0.65, 0.65)):
            if li == 2 and i == 2 and j == 1:
                continue                     # hueco libre arriba
            n += 1
            tag = f"Parihuela_Rack_{n:02d}"
            zz = z + (0.03 if li else 0.0)
            if (i + j + li) % 4 == 3:
                parihuela_plastico(tag, xc + dx, 0, zz, rot=math.pi / 2)
            else:
                parihuela_madera(tag, xc + dx, 0, zz, rot=math.pi / 2)
            if not (li == 1 and i == 0 and j == 0):
                carga_sacos(tag, xc + dx, 0, zz, capas=4 if li < 2 else 3, rot=math.pi / 2)

# ---------------------------------------------------------------- parihuelas en el suelo
grupo("03_Parihuelas_en_Suelo")
suelo = [("madera", -2.2, -2.2, 0.05, 4), ("plastico", -0.6, -2.4, -0.10, 0), ("madera", 1.0, -2.2, 0.0, 3),
         ("plastico", 2.6, -2.3, 0.08, 2)]
for k, (tipo, x, y, r, capas) in enumerate(suelo, start=1):
    tag = f"Parihuela_Suelo_{k:02d}"
    (parihuela_madera if tipo == "madera" else parihuela_plastico)(tag, x, y, 0, rot=r)
    if capas:
        carga_sacos(tag, x, y, 0, capas=capas, rot=r)
# ruma de parihuelas vacias apiladas
for k in range(6):
    parihuela_madera(f"Ruma_Parihuelas_Vacias_{k + 1:02d}", 4.3, -0.5, k * PH, rot=math.radians(90 + random.uniform(-3, 3)))

finalizar("parihuelas_racks_modelo.blend", os.path.dirname(os.path.abspath(__file__)))
