# Adorno de escritorio – Polietileno (Claudio Alvarez S., Coordinador de I+D)

## Archivo principal: `adorno_polietileno.3mf`

Un solo objeto con **3 partes, una por color**, en milímetros:

| Parte  | Filamento | Contiene |
|--------|-----------|----------|
| negro  | Negro     | cuerpo de la base, nombre, cargo, filetes y los 2 carbonos |
| azul   | Azul (#36427A, azul del logo) | tapa de la base y logo de Polímeros Norte |
| blanco | Blanco    | aro de la base, placa, 4 hidrógenos y enlaces |

En Bambu Studio / OrcaSlicer / PrusaSlicer: *Abrir* el 3MF → en la lista de objetos
aparecen las 3 partes → asignar a cada una su filamento → laminar.

Medidas: base 190 × 110 mm, altura total ≈ 67 mm.

## Otros archivos

- `adorno_polietileno.blend` – el modelo en Blender, todo en mallas, una colección por color
  (`imprimir_negro`, `imprimir_azul`, `imprimir_blanco`). Se puede exportar desde Blender.
- `adorno_polietileno_negro.stl`, `_azul.stl`, `_blanco.stl` – los mismos cuerpos por separado y con
  el mismo origen; si se cargan juntos, responder **Sí** a "¿cargar como un objeto con varias partes?".

## Química

Unidad repetitiva –[CH2–CH2]–: cada carbono tiene exactamente **2 hidrógenos** y
2 enlaces a carbono (el C–C central y un enlace abierto que indica que la cadena
continúa). Conformación trans (zigzag), C–C–C 112°, H–C–H 109.5°.

## Impresión sugerida

- Capa 0.12–0.16 mm (letras y logo con 0.9 mm de relieve), boquilla 0.4 mm.
- Soportes *tree* solo para la molécula (se apoya en tres puntos que entran 1.6 mm en la tapa).
- El enlace fino del logo se engrosó para que quede imprimible (~0.4 mm).
