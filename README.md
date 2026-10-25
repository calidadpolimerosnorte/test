# Render 3D – Extrusora Nº 1 (película soplada)

Modelo procedural en Blender de la línea de extrusión de película soplada (blown film)
"EXTRUSORA Nº 1", reconstruido a partir de fotos de planta.

## Contenido

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

## Recorrido 3D en el navegador (`recorrido/`)

- `recorrido/index.html` – vista en primera persona de Piura Futura y Planta 1 (three.js), publicada como artifact. Los modelos de Blender exportados están en `recorrido/modelos/*.glb.wasm` (son .glb; la extensión es por el hosting).
- Vista a **1,70 m** del piso. Las máquinas van a **tamaño real** del modelo de Blender: solo se achican si no caben en su huella del plano 2D más 1 m de holgura, y se corren hacia adentro si atraviesan el muro de la nave.
- **Montacargas manejable**: <kbd>E</kbd> subir/bajar, <kbd>W</kbd>/<kbd>S</kbd> avanzar y retroceder, <kbd>A</kbd>/<kbd>D</kbd> girar (dirección trasera, como uno real), <kbd>R</kbd>/<kbd>F</kbd> horquillas (mástil dúplex, hasta 3,6 m). Para cargar una parihuela se le meten las horquillas abajo y se suben; se dejan bajando hasta el piso, sobre otra parihuela o en un nivel del rack. Choca con muros, máquinas y parihuelas. En táctil: botones «Subir», ▲ y ▼.
- Pisos con textura (concreto con juntas cada 6 m, asfalto, vereda) y sonido del motor, pito de retroceso e hidráulica.
- **Piura Futura sale del plano a escala** `planos/PLANO POLIMEROS DEL NORTE.zip` (DXF en metros): cerco, naves y ejes de tijerales, muros de concreto, termopanel y drywall con sus vanos y portones enrollables, columnas, cuartos de laminado/laboratorio (h = 4,2 m) e impresión (h = 5,0 m) con cielo raso, máquinas en su posición y medida (cada modelo se ajusta a su huella del DXF con 0,6 m de tolerancia; largo y fondo por separado, la altura sigue al largo), racks del almacén (3 filas de 3 cuerpos, niveles a 1,55 y 3,10 m), parihuelas, mesas de envasado, escritorios y autos. Planta 1 sigue con el plano 2D aproximado.
- **Segundos pisos caminables** del plano: oficinas sobre laminado/laboratorio (+4,30, escalera de 22 peldaños y pasarela), módulo de oficinas (+2,85, escalera en U) y comedor sobre SS.HH. (+3,35).
- **Mobiliario por capa** del DXF (sillas, casilleros, bancas, mesas, estantes, cocina, refrigerador, sanitarios, duchas, tableros, desinfección), puertas abiertas en sus vanos y ventanas.
- **Plano eléctrico**: 125 luminarias con su circuito y los interruptores del plano (<kbd>E</kbd> junto a uno); <kbd>N</kbd> turno de noche.
- **Gente**: operadores animados en las máquinas en marcha y caminantes con rutas A*; rodillos que giran y balizas que muestran el estado de cada máquina.
- **Choques** con una grilla de 10 cm y 96 franjas de altura hecha con la geometría real; resolución adaptable para sostener 60 fps.
- `recorrido/dxf/`: scripts con los que se leyó el DXF (`dxf_muebles.py` mobiliario y muros de 2.º piso, `dxf_luces.py` luminarias e interruptores); (`dxf_capas.py` lista capas y rects, `dxf_muros.py` genera `MUROS_PF` y `COLUMNAS_PF`, `dxf_dibujo.py` dibuja el plano: `renders/plano_dxf_piura_futura.png`). Requieren `pip install ezdxf pillow`.

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
