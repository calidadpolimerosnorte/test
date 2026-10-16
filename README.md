# Render 3D – Extrusora Nº 1 (película soplada)

Modelo procedural en Blender de la línea de extrusión de película soplada (blown film)
"EXTRUSORA Nº 1", reconstruido a partir de fotos de planta.

## Contenido

- `blender/adornos_escritorio.py` – **adornos de escritorio** para "Claudio Alvarez S. – Coordinador de I+D", en negro, rojo, azul y blanco, cada uno con dos cadenas de polietileno (–CH2–CH2–) en esferas y barras: bloque de cristal sobre base negra (`renders/adorno_cristal.png`), placa inclinada (`renders/adorno_placa.png`) y escultura con las cadenas de pie (`renders/adorno_trofeo.png`). Fuentes Playfair Display y Montserrat (OFL) en `blender/fuentes/`. Se genera con `python3 blender/adornos_escritorio.py` (opciones `--disenos cristal,placa,trofeo`, `--samples N`, `--res 0.5`).
- `blender/comun.py` – funciones comunes (primitivas con nombre, colecciones, ruedas, guardar) usadas por los modelos siguientes.
- `blender/personas_modelo.blend` – **8 personas realistas y articuladas** hechas con la malla humana de MakeHuman (CC0): hombres y mujeres de distinta tez (mestiza, clara, afroperuana, trigueña), rasgos de rostro, edad y color de cabello; camisa celeste manga corta o polo plomo, jean, correa y zapatos de seguridad; con casco o cofia. Cabello, cejas y pestañas con curvas de pelo, ojos con textura. Esqueleto completo de 163 huesos (dedos, cara, ojos) con pesos: cuerpo y ropa se deforman al posar en Pose Mode. Se genera con `python3 blender/personas_modelo.py` (usa `blender/mh_humano.py` y los datos de `blender/makehuman_cc0/`). Vista previa: `renders/personas_preview.png`.
- `blender/autos_modelo.blend` – **5 autos basados en modelos reales** con sus medidas: Toyota Corolla sedán, Suzuki Swift, Toyota RAV4, Toyota Hilux doble cabina y Toyota Hiace techo alto; cada uno en su colección, sin materiales. Se genera con `python3 blender/autos_modelo.py`. Vista previa: `renders/autos_preview.png`.
- `blender/camion_modelo.blend` y `blender/camion_trailer_modelo.blend` – **camión rígido con furgón** y **tracto con semirremolque de 13.6 m** (quinta rueda, patas de apoyo, 3 ejes dobles). Se generan con `python3 blender/camiones_modelo.py`.
- `blender/montacargas_modelo.blend` – **montacargas contrapesado a GLP**: mástil, cadenas, horquillas, techo protector, asiento y mandos. Se genera con `python3 blender/montacargas_modelo.py`.
- `blender/parihuelas_racks_modelo.blend` – **rack selectivo de 3 cuerpos** (parantes azules, vigas plomas) con parihuelas de madera y de plástico cargadas con sacos, más parihuelas en el piso y una ruma de vacías. Se genera con `python3 blender/parihuelas_racks_modelo.py`.
- `blender/escritorio_laptop_modelo.blend` – **escritorio con laptop**, mouse, lámpara, taza, cuaderno, cajonera y silla de oficina. Se genera con `python3 blender/escritorio_laptop_modelo.py`.
- `blender/laminadora_modelo.blend` – **Laminadora** de dos láminas: pasillo central con la bobina 1 y la bobina final, recubrimiento en el extremo izquierdo, laminado con la bobina 2 exterior en el extremo derecho. Se genera con `python3 blender/laminadora_modelo.py`.
- `blender/impresora_ci6_modelo.blend` – **Impresora flexográfica de tambor central CHCI6-800J** (6 colores) con plataforma, escalera, desbobinador/rebobinador, columna de mando y gabinetes. Se genera con `python3 blender/impresora_ci6_modelo.py`.
- `blender/selladora_p1_modelo.blend` – **Selladora P1** (línea larga de ~22 m): entrada negra con desbobinador, torre de acumulación y corte/plegado; tramo inoxidable con vigas de sellado, aplicador de cierre, 8 estaciones transversales y troquel; salida con apilador y tablero. Se genera con `python3 blender/selladora_p1_modelo.py`.
- `blender/cortadora_1_modelo.blend` – **Cortadora Nº 1**: mismo formato, piezas nombradas por grupos, sin materiales. Se genera con `python3 blender/cortadora_1_modelo.py`.
- `blender/selladora_lateral_l1_modelo.blend` – **Selladora Lateral L1**: mismo formato, piezas nombradas por grupos, sin materiales. Se genera con `python3 blender/selladora_lateral_l1_modelo.py`.
- `blender/selladora_2_modelo.blend` – **Selladora con desbobinador doble** (sin mesa): mismo formato, piezas nombradas por grupos, sin materiales. Se genera con `python3 blender/selladora_2_modelo.py`.
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
