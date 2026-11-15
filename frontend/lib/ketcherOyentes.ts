// Lo que Ketcher 3.18.0 deja registrado en `window` y `document` cuando se desmonta, y cómo se retira.
//
// EL FALLO (medido el 2026-11-10 en el export, con una instantánea del montón). Cada editor registra cuatro oyentes
// globales y su propia limpieza no retira ninguno, porque no guarda la referencia:
//
//   · `window.resize`                                  `initResize()`: cierra sobre su almacén, y éste sobre el editor;
//   · `document.mousemove`, `mouseup` y `mouseleave`   `domEventSetup()`: funciones anónimas que reparten a `editor.event`.
//
// Con el editor desmontado, esos cuatro siguen alcanzando su raíz en el DOM. Un subárbol desprendido se conserva entero
// mientras quede vivo uno de sus nodos, así que cada cambio de caso dejaba retenido el DOM completo del caso anterior, y
// con él su visor de Mol* (unos 21 MB por cambio; 3,5 MB sin Mol*). Además cada movimiento del ratón recorría los editores
// muertos de toda la sesión.
//
// POR QUÉ ASÍ. No hay forma de preguntar qué oyentes tiene un destino, así que hay que verlos registrarse. Y no vale
// «todo lo que se registre mientras Ketcher arranca»: en ese mismo medio segundo arrancan el visor 3D y media pantalla,
// y retirar un oyente ajeno rompería a su dueño sin avisar. Cada uno se reconoce por algo que sólo Ketcher hace:
//
//   · el de `resize` es el primero que se registra en la ventana dentro de la misma tarea síncrona en que Ketcher
//     registra el teclado en SU elemento raíz (`initApp` hace las dos cosas seguidas);
//   · los de `document` llevan en su código el nombre `isPolymerEditorTurnedOn`, que es de Ketcher.
//
// HABÍA UN TERCER RETENEDOR, que los oyentes tapaban. Cada Ketcher crea también su «editor central» (`CoreEditor`, el de
// macromoléculas) y éste, su herramienta de selección, que se suscribe a dos conjuntos ESTÁTICOS de la clase
// `RotationView` (`rotationHandleSubscribers` y `rotationCenterSubscribers`). La herramienta sólo se da de baja cuando se
// cambia por otra, nunca al destruir el editor, así que esos conjuntos acumulaban una por caso abierto, y cada una
// alcanzaba su editor y los ~1 200 nodos de su interfaz (medido tras arreglar los oyentes: +1 221 nodos y +484 oyentes de
// elemento por cambio de caso). Aquí se le pide a la herramienta que se dé de baja.
//
// Y UN CUARTO, detrás de ése. El servicio de ajustes de Ketcher es único para toda la página y el constructor de cada
// `Ketcher` se suscribe a su `settings:changed` sin guardar la función para darse de baja. El oyente mantiene viva su
// instancia, ésta su editor y el editor su interfaz (medido tras arreglar lo anterior: siete copias de la pantalla del
// caso tras seis cambios). Los oyentes son anónimos, así que se reconocen por cuándo aparecen: los que se añaden
// mientras arranca un solo editor son suyos.
//
// EN DESARROLLO HAY DOS MÁS, las dos del modo estricto de React, que monta el editor dos veces (medido el 2026-11-11 en
// `next dev`: +1 308 nodos y +540 oyentes por cambio de caso; el export nunca los tuvo):
//
//   · EL AVISO LLEGA TARDE. El `onInit` público de Ketcher no sale cuando una instancia termina de arrancar: lo lanza un
//     efecto de su componente exterior (`Editor`), cuando también está listo el editor de macromoléculas. El aviso de la
//     primera instancia, que Ketcher ya ha destruido, llega cuando la segunda ha registrado el teclado y aún no ha creado
//     su editor. Tomarlo por el de la segunda cerraba la vigilancia antes de tiempo y los tres oyentes de `document` de la
//     que se queda en pantalla se registraban sin que nadie los viera. Un aviso así se reconoce porque el lienzo de su
//     editor ya no está dentro de la raíz;
//   · EL EDITOR CENTRAL NO SABE DE QUIÉN ES. `new CoreEditor()` no recibe el identificador de su Ketcher y toma «el último
//     que se añadió», que en ese momento es la segunda instancia, todavía sin editor: se queda con
//     `micromoleculesEditor = null` y comparar con el editor no lo reconoce. Se le reconoce también por dónde está su
//     raíz (`ketcherRootElement`): en la misma pantalla que la nuestra.
//
// La tercera causa de desarrollo no es de Ketcher sino de React Refresh: `lib/reactRefreshSinFuga.ts`.
//
// Depende de cómo está escrita la versión 3.18.0 (fijada en `package.json`). Si una versión nueva cambia ese orden, esto
// deja de capturar y la fuga vuelve: lo ve `scripts/resistencia.mjs`, que cuenta nodos y oyentes tras cada cambio.

const FIRMA_DE_KETCHER = "isPolymerEditorTurnedOn";
const TIPOS_DE_DOCUMENTO = new Set(["mousemove", "mouseup", "mouseleave"]);
/** Un editor desmontado antes de terminar de arrancar: cuánto se le espera para retirar lo que registre tarde. */
const ESPERA_DE_UN_ARRANQUE_ABANDONADO_MS = 30_000;

type Registrado = { tipo: string; oyente: EventListenerOrEventListenerObject; opciones?: boolean | AddEventListenerOptions };
/** Lo que se usa del editor central de Ketcher (`CoreEditor`). Todo opcional: es de otra biblioteca. */
type EditorCentral = {
  micromoleculesEditor?: unknown;
  /** La raíz de su interfaz (`.Ketcher-polymer-editor-root`). */
  ketcherRootElement?: unknown;
  tool?: unknown;
  selectedTool?: unknown;
  destroy?: () => void;
};
type Herramienta = { rotationHandleUnsubscribe?: () => void; rotationCenterUnsubscribe?: () => void };

type Emisor = { listeners?: (evento: string) => unknown[]; off?: (evento: string, oyente: unknown) => unknown };
type ServicioDeAjustes = { emitter?: Emisor };
const EVENTO_DE_AJUSTES = "settings:changed";

type Instancia = {
  deVentana: Registrado[];
  deDocumento: Registrado[];
  /** Los oyentes de ajustes que había cuando empezó a arrancar. */
  ajustesAntes: Set<unknown>;
  /** Los que añadió este editor (su `Ketcher` y su interfaz). */
  deAjustes: unknown[];
  /** Otro editor arrancó a la vez: no se sabe de quién es cada oyente de ajustes. */
  solapada: boolean;
  lista: boolean;
  desmontada: boolean;
  limpia: boolean;
  editor: unknown;
  central: EditorCentral | null;
};

/** El servicio de ajustes de Ketcher: uno para toda la página. Se conoce en cuanto arranca el primer editor. */
let servicioDeAjustes: ServicioDeAjustes | null = null;
/** Los editores vigilados que no se han limpiado todavía. Todo editor de la aplicación pasa por aquí. */
const vivas = new Set<Instancia>();

function oyentesDeAjustes(servicio: ServicioDeAjustes | null): unknown[] {
  try { return servicio?.emitter?.listeners?.(EVENTO_DE_AJUSTES) ?? []; } catch { return []; }
}

export type OpcionesDelVigia = {
  /** El editor central vigente de Ketcher (`provideEditorInstance` de `ketcher-core`). Ketcher sólo guarda el último. */
  editorCentral?: () => unknown;
};

/** Los editores que todavía no han avisado de que están listos. */
const arrancando = new Set<Instancia>();
/** El oyente de documento de Ketcher que se está ejecutando ahora mismo, para que un editor muerto sepa cuál retirar. */
let enCurso: Registrado | null = null;
let envoltorioDeDocumento: typeof document.addEventListener | null = null;

function esDeKetcher(oyente: unknown): oyente is (...args: unknown[]) => unknown {
  if (typeof oyente !== "function") return false;
  try { return Function.prototype.toString.call(oyente).includes(FIRMA_DE_KETCHER); } catch { return false; }
}

function vigilarElDocumento() {
  if (envoltorioDeDocumento || typeof document === "undefined") return;
  const original = document.addEventListener;
  const envoltorio = function (this: Document, tipo: string, oyente: EventListenerOrEventListenerObject | null, opciones?: boolean | AddEventListenerOptions) {
    if (!TIPOS_DE_DOCUMENTO.has(tipo) || !esDeKetcher(oyente)) return original.call(document, tipo, oyente as EventListenerOrEventListenerObject, opciones);
    const suyo = oyente;
    const registrado: Registrado = { tipo, opciones, oyente: () => {} };
    registrado.oyente = function (this: unknown, ...args: unknown[]) {
      const previo = enCurso;
      enCurso = registrado;
      try { return suyo.apply(this, args); } finally { enCurso = previo; }
    } as EventListener;
    // Sólo se atribuye cuando no hay duda de quién es: con dos editores arrancando a la vez no se sabe, y retirar los de
    // un editor vivo lo dejaría sin ratón. Los que quedan sin dueño se retiran solos (ver `retirarElQueLlama`).
    if (arrancando.size === 1) for (const instancia of arrancando) instancia.deDocumento.push(registrado);
    return original.call(document, tipo, registrado.oyente, opciones);
  } as typeof document.addEventListener;
  envoltorioDeDocumento = envoltorio;
  document.addEventListener = envoltorio;
}

function dejarDeVigilarElDocumento() {
  if (arrancando.size > 0 || !envoltorioDeDocumento) return;
  // Sólo se quita si sigue siendo el nuestro: si alguien puso el suyo encima, quitarlo lo borraría a él.
  if (document.addEventListener === envoltorioDeDocumento) delete (document as { addEventListener?: unknown }).addEventListener;
  envoltorioDeDocumento = null;
}

/** El siguiente `resize` que se registre en la ventana, dentro de esta misma tarea síncrona, es el de `instancia`. */
const MARCA_DE_CAPTURA = Symbol("captura del resize de Ketcher");

function capturarElResizeDeEstaTarea(instancia: Instancia) {
  if ((window.addEventListener as { [MARCA_DE_CAPTURA]?: true })[MARCA_DE_CAPTURA]) return;
  const original = window.addEventListener;
  // En el navegador el método es heredado; si alguien lo hubiera puesto en la propia ventana, se le devuelve el suyo.
  const propio = Object.getOwnPropertyDescriptor(window, "addEventListener");
  const soltar = () => {
    if (window.addEventListener !== envoltorio) return;
    if (propio) Object.defineProperty(window, "addEventListener", propio);
    else delete (window as { addEventListener?: unknown }).addEventListener;
  };
  const envoltorio = function (this: Window, tipo: string, oyente: EventListenerOrEventListenerObject | null, opciones?: boolean | AddEventListenerOptions) {
    const resultado = original.call(window, tipo, oyente as EventListenerOrEventListenerObject, opciones);
    if (tipo === "resize" && oyente) {
      soltar();
      if (instancia.limpia) window.removeEventListener("resize", oyente, opciones);
      else instancia.deVentana.push({ tipo, oyente, opciones });
    }
    return resultado;
  } as typeof window.addEventListener;
  (envoltorio as { [MARCA_DE_CAPTURA]?: true })[MARCA_DE_CAPTURA] = true;
  Object.defineProperty(window, "addEventListener", { value: envoltorio, configurable: true, writable: true });
  // Si Ketcher no registra ninguno (otra versión), la ventana no se queda envuelta.
  queueMicrotask(soltar);
}

/** Lo que hace `dispatch` en un editor muerto: retirar el oyente de documento que lo ha llamado. */
function retirarElQueLlama() {
  if (enCurso) document.removeEventListener(enCurso.tipo, enCurso.oyente, enCurso.opciones);
}

/**
 * El editor central de `editor`, si es el vigente. Sólo el vigente se puede reconocer: Ketcher no guarda los demás.
 *
 * Es el suyo si apunta a `editor` o, cuando Ketcher lo creó sin saber de quién era (modo estricto: ver la cabecera), si
 * su raíz está dentro de `marco`, la pantalla de este Ketcher.
 */
function centralDe(editor: unknown, opciones: OpcionesDelVigia, marco: Node | null = null): EditorCentral | null {
  if (!editor || !opciones.editorCentral) return null;
  try {
    const central = opciones.editorCentral() as EditorCentral | null | undefined;
    if (!central) return null;
    if (central.micromoleculesEditor === editor) return central;
    const suRaiz = central.ketcherRootElement;
    return marco && suRaiz instanceof Node && marco.contains(suRaiz) ? central : null;
  } catch { return null; }
}

/** El lienzo de un editor de Ketcher (`render.clientArea`), si esta versión lo expone. */
function lienzoDe(editor: unknown): Node | null {
  try {
    const lienzo = (editor as { render?: { clientArea?: unknown } } | null)?.render?.clientArea;
    return lienzo instanceof Node ? lienzo : null;
  } catch { return null; }
}

/**
 * Deja a `editor` sin nada que atender: sus manejadores alcanzan el editor y su lienzo. Los oyentes de `document` que
 * sigan registrados se retiran a sí mismos la próxima vez que el navegador los llame.
 */
function apagar(editor: unknown) {
  const eventos = (editor as { event?: Record<string, { handlers?: unknown; dispatch?: unknown }> } | null)?.event;
  if (!eventos || typeof eventos !== "object") return;
  for (const nombre of Object.keys(eventos)) {
    const suscripcion = eventos[nombre];
    if (!suscripcion || typeof suscripcion !== "object" || !Array.isArray(suscripcion.handlers)) continue;
    suscripcion.handlers = [];
    if (TIPOS_DE_DOCUMENTO.has(nombre)) suscripcion.dispatch = retirarElQueLlama;
  }
}

/** La herramienta de selección del editor central deja los conjuntos estáticos de `RotationView`. */
function soltarElCentral(central: EditorCentral, opciones: OpcionesDelVigia) {
  const vistas = new Set<unknown>();
  for (const clave of ["tool", "selectedTool"] as const) {
    let herramienta: unknown;
    try { herramienta = central[clave]; } catch { continue; }
    if (!herramienta || typeof herramienta !== "object" || vistas.has(herramienta)) continue;
    vistas.add(herramienta);
    const h = herramienta as Herramienta;
    try { h.rotationHandleUnsubscribe?.(); } catch { /* ya estaba de baja */ }
    try { h.rotationCenterUnsubscribe?.(); } catch { /* ya estaba de baja */ }
  }
  // `destroy()` borra el editor central GLOBAL de Ketcher: sólo si sigue siendo éste, o se lo quitaría al editor vivo.
  try {
    if (opciones.editorCentral?.() === central) central.destroy?.();
  } catch { /* a medio destruir: lo que importa ya se soltó */ }
}

function limpiar(instancia: Instancia, opciones: OpcionesDelVigia) {
  if (instancia.limpia) return;
  instancia.limpia = true;
  for (const oyente of instancia.deAjustes) {
    try { servicioDeAjustes?.emitter?.off?.(EVENTO_DE_AJUSTES, oyente); } catch { /* ya no estaba */ }
  }
  instancia.deAjustes.length = 0;
  instancia.ajustesAntes.clear();
  vivas.delete(instancia);
  const central = instancia.central ?? centralDe(instancia.editor, opciones);
  if (central) soltarElCentral(central, opciones);
  instancia.central = null;
  for (const r of instancia.deVentana) window.removeEventListener(r.tipo, r.oyente, r.opciones);
  for (const r of instancia.deDocumento) document.removeEventListener(r.tipo, r.oyente, r.opciones);
  instancia.deVentana.length = 0;
  instancia.deDocumento.length = 0;
  // Lo que no se pudo atribuir sigue registrado. Se le quita lo que alcanzaba (el editor y su lienzo), y la próxima
  // vez que el navegador lo llame se retira a sí mismo.
  apagar(instancia.editor);
  instancia.editor = null;
}

export type VigiaDeKetcher = {
  /** Ketcher avisó de que está listo (`onInit`): ya registró lo suyo. `editor` es `ketcher.editor`. */
  listo(editor: unknown, ketcher?: unknown): void;
  /** El editor se desmontó de verdad: se retira lo que dejó registrado. */
  soltar(): void;
};

/** Arranques de Ketcher empezados en toda la página: si entre dos momentos empezó más de uno, no se sabe de quién es qué. */
let arranquesEmpezados = 0;

/**
 * Empieza a mirar lo que registra el editor de Ketcher montado en `raiz` (su elemento `.Ketcher-root`).
 *
 * Hay que llamarlo antes de que Ketcher arranque: en un efecto del componente que lo monta, que React ejecuta antes de
 * que continúe el arranque asíncrono de Ketcher.
 *
 * UNA RAÍZ PUEDE TENER VARIOS ARRANQUES. En el modo estricto de React (desarrollo) el editor se monta dos veces, y
 * Ketcher, al ver el segundo montaje, destruye su primera instancia y crea otra en la misma raíz. Cada arranque empieza
 * cuando Ketcher registra el teclado en la raíz (`initApp`). Si el anterior ya había avisado, está muerto y se limpia; si
 * no (lo normal: su aviso llega tarde, ver la cabecera), los dos se vigilan juntos y lo que registren se retira a la vez,
 * al desmontar. En producción hay uno solo.
 */
export function vigilarKetcher(raiz: HTMLElement, opciones: OpcionesDelVigia = {}): VigiaDeKetcher {
  const deEstaRaiz: Instancia[] = [];
  /** La que está arrancando: entre que Ketcher registra el teclado y avisa con `listo`. */
  let actual: Instancia | null = null;
  let desmontado = false;
  let abandono: ReturnType<typeof setTimeout> | null = null;
  // Lo que había antes del próximo arranque. El constructor de `Ketcher` se suscribe a los ajustes ANTES de registrar el
  // teclado, así que esta foto se toma antes: al empezar a vigilar y, después, en cada `listo`.
  const foto = () => ({
    ajustes: new Set(oyentesDeAjustes(servicioDeAjustes)),
    servicioConocido: servicioDeAjustes !== null,
    solo: vivas.size === 0,
    arranques: arranquesEmpezados,
  });
  let referencia = foto();

  // Se suelta en cuanto deja de hacer falta: esta misma función no debe ser la que retenga la raíz de un editor muerto.
  let raizVigilada: HTMLElement | null = raiz;
  const dejarDeVigilarLaRaiz = () => {
    if (raizVigilada && Object.prototype.hasOwnProperty.call(raizVigilada, "addEventListener")) {
      delete (raizVigilada as { addEventListener?: unknown }).addEventListener;
    }
    raizVigilada = null;
  };
  const terminar = (instancia: Instancia) => {
    arrancando.delete(instancia);
    dejarDeVigilarElDocumento();
    if (actual === instancia) actual = null;
  };
  const quedaAlgoPendiente = () => deEstaRaiz.some((i) => !i.limpia);
  const cerrar = () => {
    if (abandono) clearTimeout(abandono);
    abandono = null;
    dejarDeVigilarLaRaiz();
    deEstaRaiz.length = 0;
  };
  /** Desmontado y con todo lo que arrancó ya limpio. Si nunca arrancó nada, se sigue esperando (ver `soltar`). */
  const cerrarSiNoQuedaNada = () => {
    if (desmontado && deEstaRaiz.length > 0 && !quedaAlgoPendiente()) cerrar();
  };

  const abrir = (): Instancia => {
    // La instancia anterior de esta raíz ya no existe: Ketcher la ha sustituido.
    for (const vieja of deEstaRaiz) {
      if (vieja.limpia) continue;
      if (vieja.lista) limpiar(vieja, opciones);
      else { vieja.desmontada = true; terminar(vieja); }
    }
    const instancia: Instancia = {
      deVentana: [], deDocumento: [], ajustesAntes: referencia.ajustes, deAjustes: [], solapada: false,
      lista: false, desmontada: false, limpia: false, editor: null, central: null,
    };
    arranquesEmpezados++;
    for (const otra of arrancando) { otra.solapada = true; instancia.solapada = true; }
    arrancando.add(instancia);
    vivas.add(instancia);
    vigilarElDocumento();
    deEstaRaiz.push(instancia);
    actual = instancia;
    return instancia;
  };

  const registrarEnLaRaiz = raiz.addEventListener;
  raiz.addEventListener = function (this: HTMLElement, tipo: string, oyente: EventListenerOrEventListenerObject | null, opcionesDelOyente?: boolean | AddEventListenerOptions) {
    // También después de desmontar: Ketcher termina de arrancar aunque ya no esté en pantalla, y eso hay que limpiarlo.
    if (tipo === "keydown") capturarElResizeDeEstaTarea(actual && !actual.lista ? actual : abrir());
    return registrarEnLaRaiz.call(this, tipo, oyente as EventListenerOrEventListenerObject, opcionesDelOyente);
  } as typeof raiz.addEventListener;

  return {
    listo(editor, ketcher) {
      const instancia = actual && !actual.lista ? actual : null;
      if (!instancia) return;
      // El aviso de una instancia que Ketcher ya sustituyó (modo estricto): su lienzo no está en la raíz. La que se
      // queda todavía no ha creado su editor, así que la vigilancia sigue abierta hasta SU aviso. Con el editor ya
      // desmontado de verdad no puede venir ningún otro: ése sí cierra.
      const lienzo = desmontado ? null : lienzoDe(editor);
      if (lienzo && raizVigilada && !raizVigilada.contains(lienzo)) { apagar(editor); return; }
      instancia.editor = editor ?? null;
      let servicio: ServicioDeAjustes | null = null;
      try { servicio = ((ketcher as { settingsService?: ServicioDeAjustes } | null)?.settingsService) ?? null; } catch { /* instancia destruida */ }
      if (servicio) {
        servicioDeAjustes = servicio;
        // Sólo si desde la foto no empezó ningún otro arranque, en esta raíz ni en ninguna.
        const unico = arranquesEmpezados - referencia.arranques === 1 && !instancia.solapada;
        if (unico && (referencia.servicioConocido || referencia.solo)) {
          instancia.deAjustes = oyentesDeAjustes(servicio).filter((o) => !instancia.ajustesAntes.has(o));
        }
      }
      instancia.ajustesAntes = new Set();
      // La pantalla de este Ketcher: lo que contiene sus dos cajas, la de moléculas (con la raíz) y la de macromoléculas.
      const marco = raizVigilada?.closest("[data-ketcher-editor]")?.parentElement ?? null;
      instancia.central = centralDe(instancia.editor, opciones, marco);
      instancia.lista = true;
      terminar(instancia);
      referencia = foto();
      // Se desmontó mientras arrancaba (o ya la había sustituido otro arranque): lo que acaba de registrar no tiene dueño.
      if (desmontado || instancia.desmontada) limpiar(instancia, opciones);
      cerrarSiNoQuedaNada();
    },
    soltar() {
      if (desmontado) return;
      desmontado = true;
      for (const instancia of deEstaRaiz) {
        instancia.desmontada = true;
        if (instancia.lista) limpiar(instancia, opciones);
      }
      if (deEstaRaiz.length > 0 && !quedaAlgoPendiente()) { cerrar(); return; }
      // Uno no ha avisado, o Ketcher ni siquiera llegó a registrar nada. Termina de arrancar aunque ya no esté en
      // pantalla y entonces registra: se espera a ese aviso para limpiar. Si no llega (el arranque falló), no se deja la
      // página vigilada para siempre.
      abandono = setTimeout(() => {
        abandono = null;
        for (const instancia of deEstaRaiz) { terminar(instancia); limpiar(instancia, opciones); }
        cerrar();
      }, ESPERA_DE_UN_ARRANQUE_ABANDONADO_MS);
    },
  };
}

/** Sólo para las pruebas: cuántos editores siguen arrancando y si el documento está envuelto. */
export function estadoDeLaVigilancia() {
  return { arrancando: arrancando.size, documentoEnvuelto: envoltorioDeDocumento !== null };
}

/** Sólo para las pruebas: olvida el servicio de ajustes recordado. */
export function olvidarServicioDeAjustes() {
  servicioDeAjustes = null;
  vivas.clear();
}
