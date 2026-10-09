# Render 3D – Extrusora Nº 1 (película soplada)

Modelo procedural en Blender de la línea de extrusión de película soplada (blown film)
"EXTRUSORA Nº 1", reconstruido a partir de fotos de planta.

## Contenido

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
