"""
Vectoriza el logo de Polímeros Norte (azul sobre fondo gris) a polígonos.

Salida: polimeros_norte.json con una lista de contornos en coordenadas
normalizadas (alto del logo = 1, origen en el centro, Y hacia arriba).
Los agujeros (interior de la "o", "e", "P"...) son contornos más, y Blender
los resta al rellenar la curva 2D.

Uso: python3 blender/logo/vectorizar_logo.py
"""
import json
import os

import cv2
import numpy as np
from PIL import Image

AQUI = os.path.dirname(os.path.abspath(__file__))
ENGROSAR_PX = 4  # el enlace fino del logo queda imprimible (~0.4 mm a 40 mm de ancho)

im = np.array(Image.open(os.path.join(AQUI, "polimeros_norte.webp")).convert("RGB")).astype(int)
r, b = im[..., 0], im[..., 2]
mascara = (((b - r) > 35) & (r < 140)).astype(np.uint8) * 255
nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * ENGROSAR_PX + 1, 2 * ENGROSAR_PX + 1))
mascara = cv2.dilate(mascara, nucleo)

contornos, _ = cv2.findContours(mascara, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
ys, xs = np.nonzero(mascara)
cx, cy = (xs.min() + xs.max()) / 2, (ys.min() + ys.max()) / 2
alto = ys.max() - ys.min()
salida = []
for c in contornos:
    if cv2.contourArea(c) < 30:
        continue
    c = cv2.approxPolyDP(c, 0.8, True)[:, 0, :]
    salida.append([[round((x - cx) / alto, 5), round((cy - y) / alto, 5)] for x, y in c])
with open(os.path.join(AQUI, "polimeros_norte.json"), "w") as f:
    json.dump({"ancho": round((xs.max() - xs.min()) / alto, 4), "contornos": salida}, f)
print(len(salida), "contornos, relación ancho/alto", round((xs.max() - xs.min()) / alto, 3))
