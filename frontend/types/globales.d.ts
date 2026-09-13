/**
 * Los globales que el navegador —o un `<script>` externo— pone en `window` y
 * `document`, declarados en un sitio.
 *
 * # Por qué existe
 *
 * Estos accesos estaban escritos como `(window as any).$3Dmol`, y cada uno era
 * un `as any` suelto: trece en cinco archivos. `as any` apaga la comprobación
 * completa de lo que venga detrás, así que un `viewer.addModal(...)` con una
 * letra de más compilaba igual.
 *
 * Declararlos aquí cambia el fallo de sitio: sigue siendo `unknown` o un tipo
 * laxo lo que hay al otro lado —no controlamos $3Dmol ni Molstar—, pero **la
 * existencia** de la propiedad y su opcionalidad quedan tipadas, que es lo que
 * de verdad se comprobaba mal. El `?` no es decorativo: ninguno de estos está
 * garantizado, y varios se cargan por `<script>` después del primer render.
 *
 * Lo que NO se hace aquí es inventar la firma de las librerías. `$3Dmol` y
 * `molstar` se tipan como `any` a propósito: fingir un tipo que no se ha
 * verificado contra la librería real sería peor que `any`, porque además
 * mentiría. Lo que se gana es que `window.$3Dmol` deje de ser un agujero por el
 * que pasa cualquier cosa.
 */

declare global {
  /** El objeto que inyecta el `<script>` de 3Dmol.js. Sin tipos oficiales. */
  type Global3Dmol = any;

  /** El visor de Molstar cargado como global (no el módulo, que sí tiene tipos). */
  type GlobalMolstar = any;

  /**
   * `SpeechRecognition`, aún con prefijo en los navegadores basados en WebKit.
   *
   * Los dos eventos vivían duplicados dentro de `useSpeechRecognition.ts`. Están
   * aquí porque la firma del constructor los necesita: sin ellos los manejadores
   * sólo se podían tipar como `unknown`, y entonces el `as any` volvía por la
   * puerta de atrás para poder leer `event.results`.
   */
  interface EventoDeReconocimientoDeVoz extends Event {
    results: SpeechRecognitionResultList;
    resultIndex: number;
  }

  interface ErrorDeReconocimientoDeVoz extends Event {
    error: string;
    message: string;
  }

  interface InstanciaSpeechRecognition {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    maxAlternatives: number;
    start(): void;
    stop(): void;
    abort(): void;
    onresult: ((evento: EventoDeReconocimientoDeVoz) => void) | null;
    onerror: ((evento: ErrorDeReconocimientoDeVoz) => void) | null;
    onend: (() => void) | null;
    onstart: (() => void) | null;
  }

  type ConstructorSpeechRecognition = new () => InstanciaSpeechRecognition;

  interface Window {
    $3Dmol?: Global3Dmol;
    molstar?: GlobalMolstar;
    SpeechRecognition?: ConstructorSpeechRecognition;
    webkitSpeechRecognition?: ConstructorSpeechRecognition;
    /**
     * Tauri v2 inyecta `__TAURI_INTERNALS__` siempre; `__TAURI__` sólo con
     * `app.withGlobalTauri: true` (por defecto, false). Se comprueban los dos:
     * sin el primero la app de escritorio caía en el flujo web de OAuth.
     */
    __TAURI__?: unknown;
    __TAURI_INTERNALS__?: unknown;
  }

  interface Document {
    /**
     * View Transitions API. No está en todos los navegadores que soportamos, y
     * por eso el llamador comprueba antes de usarla.
     */
    startViewTransition?: (callback: () => void) => {
      finished: Promise<void>;
      ready: Promise<void>;
      updateCallbackDone: Promise<void>;
    };
  }
}

export {};
