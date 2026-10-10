# Render 3D – Extrusora Nº 1 (película soplada)

Modelo procedural en Blender de la línea de extrusión de película soplada (blown film)
"EXTRUSORA Nº 1", reconstruido a partir de fotos de planta.

## Contenido

- `blender/selladora_f1_modelo.blend` – **Selladora de fondo F1** (máquina de bolsas) con su mesa de trabajo: mismo formato, piezas nombradas por grupos, sin materiales. Se genera con `python3 blender/selladora_f1_modelo.py`.
- `blender/vehiculo_pickup_modelo.blend` – **Camioneta pickup doble cabina** (tipo JMC Vigus EV): mismo formato, piezas nombradas por grupos, sin materiales. Se genera con `python3 blender/vehiculo_pickup_modelo.py`.
- `blender/vehiculo_suv_modelo.blend` – **SUV compacto** (tipo Chevrolet Tracker): mismo formato, piezas nombradas por grupos, sin materiales. Se genera con `python3 blender/vehiculo_suv_modelo.py`.
- `blender/extrusora7_modelo.blend` – **Extrusora Nº 7**: igual que la Nº 6 pero con impresora y troqueladora más grandes. Mismo formato. Se genera con `python3 blender/extrusora7_modelo.py`.
- `blender/extrusora6_modelo.blend` – **Extrusora Nº 6** (no existe la Nº 5): línea larga con torre, impresora flexográfica, troqueladora con aspiración de recorte, puente aéreo de rodillos y dos embobinadoras en tándem. Mismo formato: solo la máquina, sin materiales ni animación, piezas nombradas por grupos. Se genera con `python3 blender/extrusora6_modelo.py`.
- `blender/extrusora4_modelo.blend` – **Extrusora Nº 4**, mismo formato: solo la máquina, sin materiales ni animación, piezas nombradas por grupos. Se genera con `python3 blender/extrusora4_modelo.py`. Todas las extrusoras usan la misma referencia de planta (piso en z=0, metros).
- `blender/extrusora3_modelo.blend` – **Extrusora Nº 3**, mismo formato: solo la máquina, sin materiales ni animación, piezas nombradas por grupos. Se genera con `python3 blender/extrusora3_modelo.py`.
- `blender/extrusora2_modelo.blend` – **Extrusora Nº 2**, mismo formato que el modelo limpio: solo la máquina, sin materiales ni animación, piezas nombradas por grupos. Se genera con `python3 blender/extrusora2_modelo.py`.
- `blender/extrusora_modelo.blend` – **modelo limpio**: solo la máquina, sin materiales, sin animación, sin galpón/piso/luces/cámaras. 332 piezas con nombre descriptivo, agrupadas en 21 colecciones por sistema (torre, plataforma, barandas, nip, canasta, extrusora, tolva, tablero, embobinadora…). Se genera con `python3 blender/extrusora_modelo.py`.
- `blender/extrusora.py` – script que genera toda la escena (máquina, galpón, luces, cámaras) y renderiza con Cycles.
- `blender/extrusora.blend` – escena guardada, lista para abrir en Blender 4.2+ / 5.x.
- `renders/extrusora_principal.png`, `renders/extrusora_frontal.png`, `renders/extrusora_lateral.png` – renders finales.

## Qué está modelado

- Torre blanca con 4 columnas, plataforma con barandas negras, letreros "EXTRUSORA Nº 1" y "UTILIZAR CASCO".
- Torre superior: canasta colapsadora con listones de madera, rodillos nip (cromo + goma), cilindros neumáticos y motorreductor azul.
- Burbuja de film translúcida (expansión, línea de enfriamiento y aplanado) y recorrido de la lámina hasta la embobinadora.
- Extrusora: cabezal, anillo de aire, mangueras flexibles, soplador, cilindro con resistencias, tolva, reductor y motor.
- Tablero de control con controladores de temperatura, pilotos y señal de riesgo eléctrico.
- Escalera de gato, embobinadora con bobina, soporte de rodillos guía.
- Galpón: piso de concreto, paredes de plancha ondulada, lámparas colgantes, pallets con rollos, sacos de resina.

## Volver a renderizar

```bash
# Con Blender instalado
blender -b -P blender/extrusora.py -- --out renders/extrusora --samples 128

# O con el módulo bpy de PyPI (pip install bpy)
python3 blender/extrusora.py --out renders/extrusora --samples 128
```

Opciones: `--cams principal,frontal,lateral`, `--res 0.5` (escala de resolución), `--samples N`.
