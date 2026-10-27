// Copia la colección 'configuracion_formatos' (solo documentos y campos, sin subcolecciones)
// del proyecto polimeros-del-norte-ce0c2 al proyecto polplast.
//
// Uso:
//   npm install
//   node copiar-coleccion.js            -> simulación (no escribe nada)
//   node copiar-coleccion.js --ejecutar -> copia de verdad

const admin = require("firebase-admin");

const COLECCION = "configuracion_formatos";
const ORIGEN_KEY = "./origen-key.json";   // cuenta de servicio de polimeros-del-norte-ce0c2
const DESTINO_KEY = "./destino-key.json"; // cuenta de servicio de polplast
const EJECUTAR = process.argv.includes("--ejecutar");

const origenApp = admin.initializeApp(
  { credential: admin.credential.cert(require(ORIGEN_KEY)) },
  "origen"
);
const destinoApp = admin.initializeApp(
  { credential: admin.credential.cert(require(DESTINO_KEY)) },
  "destino"
);
const origen = origenApp.firestore();
const destino = destinoApp.firestore();

// Las referencias a documentos apuntan al proyecto de origen; se reescriben
// para que apunten a la misma ruta en el proyecto de destino.
function convertir(valor) {
  if (valor instanceof admin.firestore.DocumentReference) {
    return destino.doc(valor.path);
  }
  if (Array.isArray(valor)) return valor.map(convertir);
  if (
    valor &&
    typeof valor === "object" &&
    !(valor instanceof admin.firestore.Timestamp) &&
    !(valor instanceof admin.firestore.GeoPoint) &&
    !Buffer.isBuffer(valor)
  ) {
    const out = {};
    for (const [k, v] of Object.entries(valor)) out[k] = convertir(v);
    return out;
  }
  return valor;
}

async function main() {
  console.log(`Origen : ${origenApp.options.credential.projectId}`);
  console.log(`Destino: ${destinoApp.options.credential.projectId}`);
  console.log(`Modo   : ${EJECUTAR ? "EJECUTAR (escribe en destino)" : "SIMULACIÓN"}\n`);

  // get() de una colección trae solo los documentos y sus campos, nunca subcolecciones.
  const snap = await origen.collection(COLECCION).get();
  console.log(`Documentos encontrados en '${COLECCION}': ${snap.size}`);

  const existentes = await destino.collection(COLECCION).get();
  if (existentes.size > 0) {
    console.log(`Aviso: el destino ya tiene ${existentes.size} documentos en '${COLECCION}'.`);
    console.log("Los que tengan el mismo ID serán reemplazados; los demás se mantienen.\n");
  }

  if (!EJECUTAR) {
    snap.docs.forEach((d) => console.log(`  - ${d.id} (${Object.keys(d.data()).length} campos)`));
    console.log("\nSimulación terminada. Ejecuta con --ejecutar para copiar.");
    return;
  }

  const writer = destino.bulkWriter();
  let errores = 0;
  writer.onWriteError((err) => {
    errores++;
    console.error(`  Error en ${err.documentRef.path}: ${err.message}`);
    return false;
  });
  for (const d of snap.docs) {
    writer.set(destino.collection(COLECCION).doc(d.id), convertir(d.data()));
  }
  await writer.close();

  const verif = await destino.collection(COLECCION).get();
  console.log(`\nCopiados: ${snap.size - errores} / ${snap.size}. Errores: ${errores}.`);
  console.log(`Documentos ahora en destino: ${verif.size}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
