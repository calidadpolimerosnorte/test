"""Escritorio de oficina con laptop, silla, cajonera, mouse y lampara. Sin materiales. Metros, piso z=0.
Uso: python3 blender/escritorio_laptop_modelo.py  ->  blender/escritorio_laptop_modelo.blend"""
import math, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from comun import *

nueva_escena("Escritorio_con_Laptop")
W, D, H = 1.40, 0.70, 0.75

grupo("01_Escritorio")
box("Tablero_Escritorio", (W, D, 0.03), (0, 0, H - 0.015), bevel=0.004)
for sx in (-1, 1):
    box("Pata_Lateral_Panel", (0.03, D - 0.06, H - 0.03), (sx * (W / 2 - 0.03), 0, (H - 0.03) / 2))
    box("Pie_Nivelador", (0.06, D - 0.04, 0.02), (sx * (W / 2 - 0.03), 0, 0.01))
box("Faldon_Trasero", (W - 0.10, 0.02, 0.30), (0, D / 2 - 0.04, H - 0.18))
# cajonera con 3 cajones a la derecha
cx = W / 2 - 0.26
box("Cajonera_Cuerpo", (0.42, D - 0.10, 0.58), (cx, -0.02, 0.32), bevel=0.003)
for k in range(3):
    z = 0.15 + k * 0.19
    box("Frente_Cajon", (0.40, 0.015, 0.17), (cx, -D / 2 + 0.035, z), bevel=0.003)
    box("Tirador_Cajon", (0.12, 0.02, 0.015), (cx, -D / 2 + 0.02, z + 0.05))
box("Pasacable_Escritorio", (0.08, 0.08, 0.005), (-0.45, 0.22, H + 0.001))

grupo("02_Laptop")
lx, ly = -0.10, -0.05
box("Laptop_Base", (0.34, 0.24, 0.018), (lx, ly, H + 0.009), bevel=0.004)
box("Laptop_Teclado", (0.29, 0.10, 0.002), (lx, ly + 0.03, H + 0.019))
for r in range(5):
    for c in range(12):
        box("Tecla", (0.019, 0.016, 0.003), (lx - 0.128 + c * 0.0233, ly - 0.012 + r * 0.019, H + 0.0205))
box("Laptop_Touchpad", (0.10, 0.06, 0.002), (lx, ly - 0.075, H + 0.019))
ang = math.radians(105)
hx, hz = 0.24 / 2, H + 0.018
pant = box("Laptop_Pantalla_Tapa", (0.34, 0.008, 0.23), (0, 0, 0), bevel=0.003)
pant.rotation_euler = (math.radians(90) - ang + math.radians(90), 0, 0)
pant.rotation_euler = (-(ang - math.radians(90)), 0, 0)
pant.location = (lx, ly + hx + 0.115 * math.cos(ang - math.radians(90)) * 0 + 0.115 * math.sin(ang - math.radians(90)),
                 hz + 0.115 * math.cos(ang - math.radians(90)))
disp = box("Laptop_Pantalla_Display", (0.30, 0.002, 0.19), (0, 0, 0))
disp.rotation_euler = pant.rotation_euler
disp.location = (pant.location.x, pant.location.y - 0.005 * math.cos(ang - math.radians(90)),
                 pant.location.z + 0.005 * math.sin(ang - math.radians(90)))
cyl("Laptop_Bisagra", 0.006, 0.30, (lx, ly + hx, hz), axis="X", verts=12)
box("Mouse", (0.06, 0.10, 0.03), (lx + 0.30, ly - 0.02, H + 0.015), bevel=0.012)
box("Mousepad", (0.24, 0.20, 0.003), (lx + 0.30, ly - 0.02, H + 0.0015))
cyl("Cable_Cargador", 0.004, 0.40, (lx - 0.25, ly + 0.10, H + 0.005), axis="X", verts=8)

grupo("03_Accesorios")
cyl("Lampara_Base", 0.08, 0.02, (-0.55, 0.20, H + 0.01), verts=24)
beam("Lampara_Brazo_Inferior", (-0.55, 0.20, H + 0.02), (-0.55, 0.12, H + 0.35), 0.015, round_=True)
beam("Lampara_Brazo_Superior", (-0.55, 0.12, H + 0.35), (-0.40, 0.02, H + 0.42), 0.015, round_=True)
cyl("Lampara_Pantalla", 0.06, 0.10, (-0.38, 0.0, H + 0.38), verts=24, r2=0.03, rot=(math.radians(-30), 0, 0))
cyl("Taza", 0.04, 0.10, (0.25, 0.15, H + 0.05), verts=24)
box("Cuaderno", (0.21, 0.29, 0.015), (0.40, -0.10, H + 0.0075), rot=(0, 0, math.radians(10)))
cyl("Lapicero", 0.004, 0.14, (0.36, -0.12, H + 0.02), axis="Y", verts=8)

grupo("04_Silla_Oficina")
sy = -0.75
box("Silla_Asiento", (0.48, 0.46, 0.08), (lx, sy, 0.47), bevel=0.03)
box("Silla_Respaldo", (0.46, 0.06, 0.55), (lx, sy - 0.26, 0.82), rot=(math.radians(-8), 0, 0), bevel=0.03)
beam("Silla_Soporte_Respaldo", (lx, sy - 0.18, 0.44), (lx, sy - 0.28, 0.62), 0.05, t2=0.02)
for sx in (-1, 1):
    beam("Silla_Brazo_Vertical", (lx + sx * 0.25, sy - 0.05, 0.47), (lx + sx * 0.25, sy - 0.05, 0.66), 0.03)
    box("Silla_Apoyabrazos", (0.06, 0.25, 0.03), (lx + sx * 0.25, sy, 0.67), bevel=0.01)
cyl("Silla_Piston", 0.025, 0.30, (lx, sy, 0.27), verts=16)
cyl("Silla_Funda_Piston", 0.035, 0.12, (lx, sy, 0.17), verts=16)
for k in range(5):
    a = k * math.tau / 5
    p2 = (lx + 0.30 * math.cos(a), sy + 0.30 * math.sin(a), 0.07)
    beam("Silla_Pata_Estrella", (lx, sy, 0.10), p2, 0.04, t2=0.03)
    cyl("Silla_Rueda", 0.025, 0.02, (p2[0], p2[1], 0.025), axis="X", verts=16)

finalizar("escritorio_laptop_modelo.blend", os.path.dirname(os.path.abspath(__file__)))
