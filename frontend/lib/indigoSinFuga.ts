// La fuga del worker de Indigo (ketcher-standalone 3.18.0) y cómo se le quita casi todo su peso.
//
// EL FALLO (medido el 2026-11-10). El worker de Indigo es uno para toda la página. Por cada mensaje crea un mapa de
// opciones de C++ (`new indigo.MapStringString()`) y no lo libera nunca (`.delete()`): los objetos de embind viven en la
// memoria de WebAssembly y el recolector de basura no los ve. Y en las opciones de cada conversión
// (`setMolecule`, `getSmiles`, `getMolfile`…) Ketcher copia la biblioteca de monómeros del editor entera, ~1,3 MB de
// JSON. Cada conversión dejaba ~1,3 MB atrapados en el worker. Un cambio de caso hace unas tres; una evaluación, decenas.
// Medido en el export: la página crecía 5–6 MB por cambio de caso, y al cerrar el worker se liberaban 216–325 MB.
//
// EL ARREGLO. No se puede liberar el mapa desde fuera, pero sí no meterle la biblioteca. Sólo la necesitan las
// macromoléculas: el modo de macromoléculas del editor, los formatos de secuencia (FASTA, HELM, IDT…) y los KET que
// contienen monómeros. Para todo lo demás —las moléculas pequeñas de MolDesign— se quita del mensaje antes de enviarlo,
// y el mapa que se pierde pasa a pesar unos cientos de bytes. Comprobado reenviando a un segundo worker las conversiones
// reales de una sesión, con y sin biblioteca: las mismas respuestas, byte a byte.
//
// Depende de la forma de los mensajes de ketcher-standalone 3.18.0 (fijada en `package.json`). Si cambia, la envoltura
// deja de reconocerlos y no toca nada: la fuga volvería, y la vería `scripts/resistencia.mjs`.

/** `Command.Convert` del worker de Indigo. */
const CONVERTIR = 1;

/** Los formatos de `SupportedFormat` que no son de macromoléculas. */
const FORMATOS_DE_MOLECULA_PEQUENA = new Set([
  "rxnfile", "molfile", "smiles", "smarts", "cml", "inchi", "inchi-aux", "inchi-key", "ket", "cdx", "cdxml", "sdf", "rdf",
]);

type DatosDeConversion = { struct?: unknown; format?: unknown; options?: Record<string, unknown> };

/** ¿Necesita esta conversión la biblioteca de monómeros? Ante la duda, sí: quitarla de más cambiaría un resultado. */
export function necesitaLaBibliotecaDeMonomeros(datos: DatosDeConversion, modoMacromoleculas: boolean): boolean {
  if (modoMacromoleculas) return true;
  if (!FORMATOS_DE_MOLECULA_PEQUENA.has(String(datos.format ?? ""))) return true;
  const entrada = datos.options?.["input-format"];
  if (entrada != null && !FORMATOS_DE_MOLECULA_PEQUENA.has(String(entrada))) return true;
  // Un KET con monómeros (los deja el editor de macromoléculas en la estructura) sí la necesita.
  if (typeof datos.struct !== "string" || /monomer/i.test(datos.struct)) return true;
  return false;
}

/** Lo que ha hecho la envoltura en esta página. Lo leen las pruebas y el guion de resistencia. */
export const cuentaDeIndigo = { conversiones: 0, sinBiblioteca: 0, mbNoEnviados: 0 };

const protegidos = new WeakSet<object>();
const modoMacromoleculas = () => (globalThis as { isPolymerEditorTurnedOn?: boolean }).isPolymerEditorTurnedOn === true;

/**
 * Envuelve un `postMessage` para que las conversiones que no la necesitan no lleven la biblioteca de monómeros. Acepta
 * un worker o `Worker.prototype`. Una vez por objeto.
 *
 * POR QUÉ EL PROTOTIPO. El worker de Indigo es interno a ketcher-standalone y no se alcanza desde fuera:
 * `ketcher.structService` es un envoltorio de métodos ya enlazados, sin `.worker` (la primera versión de este arreglo lo
 * buscaba ahí y no se instalaba nunca; lo vio la medida, no las pruebas). Envolver el prototipo es seguro porque sólo
 * se toca un mensaje con la forma exacta de una conversión de Indigo (`type: 1` y `data.options.monomerLibrary` como
 * texto), que ningún otro worker de la aplicación envía.
 */
export function protegerWorkerDeIndigo(worker: unknown): void {
  if (!worker || typeof worker !== "object" || protegidos.has(worker)) return;
  const w = worker as { postMessage?: (mensaje: unknown, ...resto: unknown[]) => void };
  if (typeof w.postMessage !== "function") return;
  protegidos.add(worker);
  const original = w.postMessage;
  w.postMessage = function (this: unknown, mensaje: unknown, ...resto: unknown[]) {
    const m = mensaje as { type?: unknown; data?: DatosDeConversion } | null;
    const opciones = m?.data?.options;
    if (m && m.type === CONVERTIR && opciones && typeof opciones.monomerLibrary === "string") {
      cuentaDeIndigo.conversiones++;
      if (!necesitaLaBibliotecaDeMonomeros(m.data!, modoMacromoleculas())) {
        const { monomerLibrary, ...demas } = opciones;
        cuentaDeIndigo.sinBiblioteca++;
        cuentaDeIndigo.mbNoEnviados += (monomerLibrary as string).length / 1048576;
        // Un mensaje nuevo: el de Ketcher no se toca.
        mensaje = { ...m, data: { ...m.data, options: demas } };
      }
    }
    return original.call(this, mensaje, ...resto);
  };
}
