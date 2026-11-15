// Un solo visor de Mol* para toda la sesión, que pasa de un caso al siguiente.
//
// POR QUÉ (medido el 2026-11-10 en el export, con una instantánea del montón). Antes cada caso creaba su visor y lo
// destruía al salir, y cada cambio de caso dejaba retenidos unos 21 MB:
//
//   · `Viewer.create` monta la interfaz de Mol* con una raíz de React propia y `dispose()` no la desmonta: quien conserve
//     el elemento donde se montó conserva el plugin entero. La biblioteca no da forma de desmontarla desde fuera;
//   · ese elemento era parte de la pantalla del caso, y Ketcher retenía la pantalla entera (`lib/ketcherOyentes.ts`).
//
// Con un único visor no hay nada que destruir: se crea una vez, en un elemento suyo que no pertenece a ningún caso, y ese
// elemento se cuelga de quien lo pide y se descuelga cuando lo devuelve. De paso desaparecen el medio segundo de crear
// Mol* y el contexto WebGL nuevo de cada cambio.
//
// LO QUE ESTO NO PUEDE HACER: enseñar a un caso la estructura de otro. `CaseWorkspace` aísla los casos remontando todo lo
// demás; aquí la instancia es compartida a propósito, así que el aislamiento lo dan tres reglas:
//
//   1. al devolverlo, el elemento se oculta en el acto y sale del documento;
//   2. todo lo que se le pide va en una cola: el vaciado de quien lo devolvió termina antes de la carga del siguiente,
//      y una carga que ya no es la vigente no sigue añadiendo estructuras;
//   3. no vuelve a verse hasta que Mol* ha dibujado un fotograma ya vacío.
//
// Lo comprueba `lib/__tests__/molstarResidente.test.ts`, y en el export, `scripts/resistencia.mjs`.

/** El visor de Mol* (`molstar.Viewer`), que no trae tipos: llega como global de un script aparte. */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type VisorMolstar = any;

export type Prestamo = {
  visor: VisorMolstar;
  /**
   * Pone un trabajo en la cola del visor. Los trabajos van de uno en uno y en orden. `vigente()` deja de ser cierto en
   * cuanto se devuelve el visor o se encola otra carga: el trabajo debe consultarlo entre paso y paso y dejarlo ahí.
   * Antes de `trabajo` el visor siempre se vacía.
   */
  cargar(trabajo: (visor: VisorMolstar, vigente: () => boolean) => Promise<void>): Promise<void>;
  /** Devuelve el visor: se oculta, sale del documento y se vacía. */
  devolver(): void;
  /** El visor no sirve (se quedó sin contexto 3D): se destruye, y el siguiente que lo pida recibe uno nuevo. */
  descartar(): void;
};

type Residente = { visor: VisorMolstar; caja: HTMLDivElement };

let residente: Residente | null = null;
let creando: Promise<Residente> | null = null;
let cola: Promise<void> = Promise.resolve();
/** Quién tiene el visor ahora (0: nadie). Cada préstamo recibe un número nuevo. */
let titular = 0;
let ultimoPrestamo = 0;
/** La carga más reciente que se ha encolado: sólo ésa sigue vigente. */
let ultimaCarga = 0;
/** Falso desde que una carga empieza hasta que un vaciado termina. */
let vacio = true;

/** Cuántos visores se han creado y destruido en esta página. Lo lee la prueba de resistencia. */
export const cuentaDeVisores = { creados: 0, descartados: 0 };

function encolar(paso: () => Promise<void>): Promise<void> {
  const resultado = cola.then(paso, paso);
  cola = resultado.then(() => undefined, () => undefined);
  return resultado;
}

/** Espera a que Mol* dibuje. Sin fotogramas (ventana minimizada) no se espera para siempre. */
function trasDibujar(visor: VisorMolstar): Promise<void> {
  return new Promise<void>((seguir) => {
    let hecho = false;
    let suscripcion: { unsubscribe?: () => void } | undefined;
    const fin = () => {
      if (hecho) return;
      hecho = true;
      try { suscripcion?.unsubscribe?.(); } catch { /* el visor ya no existe */ }
      seguir();
    };
    try {
      const lienzo = visor?.plugin?.canvas3d;
      // `didDraw` repite su último valor a quien se suscribe: ese aviso es del fotograma viejo y no cuenta.
      let alSuscribir = true;
      suscripcion = lienzo?.didDraw?.subscribe?.(() => { if (!alSuscribir) fin(); });
      alSuscribir = false;
      lienzo?.requestDraw?.();
    } catch { /* sin lienzo 3D no hay nada que esperar */ }
    setTimeout(fin, 400);
  });
}

async function vaciar(visor: VisorMolstar) {
  try {
    await visor.plugin.clear();
  } catch { /* un visor a medio destruir no se puede vaciar, ni hace falta */ }
  vacio = true;
}

/** Arranca el bucle de dibujo si está parado. `start()` dos veces seguidas dejaría dos bucles dibujando a la vez. */
function reanudar(visor: VisorMolstar) {
  try {
    const bucle = visor?.plugin?.animationLoop;
    if (bucle && bucle.isAnimating === false) bucle.start();
  } catch { /* sin bucle que arrancar */ }
}

function ajustarTamano(visor: VisorMolstar) {
  try {
    visor.handleResize?.();
    visor.plugin?.canvas3d?.handleResize?.();
  } catch { /* se ajustará con el siguiente cambio de tamaño */ }
}

function prestar(propio: Residente, destino: HTMLElement): Prestamo {
  const { visor, caja } = propio;
  const turno = ++ultimoPrestamo;
  titular = turno;
  const esMio = () => titular === turno && residente === propio;

  // Lo que quedara dibujado es del caso anterior: no se enseña hasta que haya un fotograma vacío.
  if (!vacio) caja.style.visibility = "hidden";
  destino.appendChild(caja);
  reanudar(visor);
  ajustarTamano(visor);
  if (!vacio) {
    void encolar(async () => {
      if (!esMio()) return;
      await trasDibujar(visor);
      if (esMio()) caja.style.visibility = "";
    });
  } else {
    caja.style.visibility = "";
  }

  return {
    visor,
    cargar(trabajo) {
      const carga = ++ultimaCarga;
      const vigente = () => esMio() && ultimaCarga === carga;
      return encolar(async () => {
        if (!vigente()) return;
        // Siempre se parte de un visor vacío: lo que hubiera dejado una carga anterior, completa o a medias, se va.
        if (!vacio) await vaciar(visor);
        if (!vigente()) return;
        vacio = false;
        await trabajo(visor, vigente);
      });
    },
    devolver() {
      if (!esMio()) return;
      titular = 0;
      ultimaCarga++;
      caja.style.visibility = "hidden";
      caja.remove();
      void encolar(async () => {
        if (residente !== propio) return;
        if (!vacio) await vaciar(visor);
        // Aparcado no dibuja: nadie lo ve. Si alguien lo pidió mientras se vaciaba, sigue en marcha.
        if (titular === 0) { try { visor.plugin?.animationLoop?.stop?.(); } catch { /* sin bucle que parar */ } }
        // Y si lo pidieron justo antes de parar, el bucle tiene que seguir.
        else reanudar(visor);
      });
    },
    descartar() {
      if (residente !== propio) return;
      if (titular === turno) titular = 0;
      ultimaCarga++;
      residente = null;
      vacio = true;
      cuentaDeVisores.descartados++;
      caja.remove();
      try { visor.dispose(); } catch { /* ya estaba roto */ }
    },
  };
}

/**
 * Pide el visor de Mol* y lo cuelga de `destino`. Lo crea con `crear` si todavía no existe.
 *
 * `crear` recibe el elemento propio del visor, ya dentro de `destino` (Mol* mide su contenedor al arrancar), y devuelve
 * el `molstar.Viewer`. Si falla, la promesa falla y no queda ningún visor a medias.
 *
 * Quien lo pide puede haberse desmontado mientras se creaba: debe comprobarlo al recibirlo y, en ese caso, devolverlo.
 */
export async function pedirMolstar(destino: HTMLElement, crear: (caja: HTMLElement) => Promise<VisorMolstar>): Promise<Prestamo> {
  if (!residente) {
    creando ??= (async () => {
      const caja = document.createElement("div");
      caja.dataset.molstarResidente = "";
      caja.style.cssText = "position:relative;width:100%;height:100%";
      destino.appendChild(caja);
      try {
        const visor = await crear(caja);
        cuentaDeVisores.creados++;
        vacio = true;
        residente = { visor, caja };
        return residente;
      } catch (fallo) {
        caja.remove();
        throw fallo;
      } finally {
        creando = null;
      }
    })();
    await creando;
  }
  // Entre tanto pudo descartarse (un visor recién creado que no consiguió contexto): se intenta de nuevo.
  if (!residente) return pedirMolstar(destino, crear);
  return prestar(residente, destino);
}

/** Sólo para las pruebas: olvida el visor sin destruirlo. */
export function olvidarResidente() {
  residente = null;
  creando = null;
  cola = Promise.resolve();
  titular = 0;
  ultimoPrestamo = 0;
  ultimaCarga = 0;
  vacio = true;
  cuentaDeVisores.creados = 0;
  cuentaDeVisores.descartados = 0;
}
