"use client";

// =====================================================================
// CaseSidebarShell — el panel de casos se pliega y se redimensiona
// =====================================================================
//
// POR QUÉ. Medido a 1440 px: el panel ocupaba 272 px FIJOS, el 19% del ancho,
// para una lista que casi siempre cabe en un tercio de su altura. Enfrente, el
// editor químico y el visor 3D se reparten lo que sobra. En una pantalla de
// portátil esa proporción decide si una pose se ve o no.
//
// DOS GESTOS, NO UNO. El panel se pliega a un raíl y también se estira: un
// investigador con treinta casos y nombres largos necesita lo contrario que
// uno que está mirando una pose. Las dos preferencias se recuerdan.
//
// LO QUE EL RAÍL CONSERVA. Plegado NO desaparece: quedan el botón de abrir y
// el de caso nuevo, y el número de casos. Un panel que se esfuma sin dejar
// rastro obliga a buscar cómo recuperarlo, y esa búsqueda cuesta más que los
// 48 px que ahorra.

import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { useLanguage } from "../../context/LanguageContext";
import { PanelLeftOpen, Plus } from "lucide-react";

/** Lo que ocupa el raíl plegado. Cabe un botón de 44 px con su margen. */
export const ANCHO_PLEGADO = 48;
export const ANCHO_MINIMO = 220;
export const ANCHO_MAXIMO = 480;
export const ANCHO_POR_DEFECTO = 272;

const CLAVE_ANCHO = "moldesign_casos_ancho";
const CLAVE_PLEGADO = "moldesign_casos_plegado";

function leerNumero(clave: string, porDefecto: number): number {
  if (typeof window === "undefined") return porDefecto;
  try {
    const crudo = window.localStorage.getItem(clave);
    if (!crudo) return porDefecto;
    const valor = Number.parseInt(crudo, 10);
    if (!Number.isFinite(valor)) return porDefecto;
    return Math.min(ANCHO_MAXIMO, Math.max(ANCHO_MINIMO, valor));
  } catch {
    return porDefecto;
  }
}

function leerBooleano(clave: string): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(clave) === "1";
  } catch {
    return false;
  }
}

function guarda(clave: string, valor: string): void {
  try {
    window.localStorage.setItem(clave, valor);
  } catch {
    // Un almacenamiento bloqueado no puede impedir usar el panel.
  }
}

export interface CaseSidebarShellProps {
  /**
   * El panel, al que se le entrega la acción de plegar.
   *
   * Es una función y no un `ReactNode` porque el botón de plegar vive DENTRO
   * de la cabecera del panel: flotando encima tapaba «Nuevo caso», medido en
   * pantalla. Y el mismo panel se usa en el cajón móvil, donde no hay nada que
   * plegar; allí simplemente no se le pasa.
   */
  readonly children: (api: { readonly plegar: () => void }) => ReactNode;
  /** Se muestra en el raíl para que plegado siga informando. */
  readonly totalCasos: number;
  /** {t("ca_crear_boton")} desde el raíl, sin tener que desplegarlo antes. */
  readonly onCreate: () => void;
  readonly createDisabled?: boolean;
  readonly createDisabledReason?: string;
}

export function CaseSidebarShell({
  children,
  totalCasos,
  onCreate,
  createDisabled = false,
  createDisabledReason,
}: CaseSidebarShellProps) {
  const { t } = useLanguage();
  // El primer render debe coincidir con el del servidor o la hidratación se
  // queja; las preferencias se leen después, ya en el cliente.
  const [montado, setMontado] = useState(false);
  const [plegado, setPlegado] = useState(false);
  const [ancho, setAncho] = useState(ANCHO_POR_DEFECTO);
  const [arrastrando, setArrastrando] = useState(false);
  const anchoRef = useRef(ancho);
  anchoRef.current = ancho;

  useEffect(() => {
    setPlegado(leerBooleano(CLAVE_PLEGADO));
    setAncho(leerNumero(CLAVE_ANCHO, ANCHO_POR_DEFECTO));
    setMontado(true);
  }, []);

  const alternar = useCallback(() => {
    setPlegado((previo) => {
      const siguiente = !previo;
      guarda(CLAVE_PLEGADO, siguiente ? "1" : "0");
      return siguiente;
    });
  }, []);

  // ── Arrastre del borde ────────────────────────────────────────────────
  //
  // Los listeners van en `window` y no en el tirador: si el puntero sale del
  // elemento mientras se arrastra —y sale siempre, porque el borde se mueve—
  // el arrastre se quedaría colgado con el ratón ya soltado.
  const empiezaArrastre = useCallback(
    (evento: React.PointerEvent<HTMLDivElement>) => {
      if (plegado) return;
      evento.preventDefault();
      const xInicial = evento.clientX;
      const anchoInicial = anchoRef.current;
      setArrastrando(true);

      const mueve = (e: PointerEvent) => {
        const propuesto = anchoInicial + (e.clientX - xInicial);
        setAncho(Math.min(ANCHO_MAXIMO, Math.max(ANCHO_MINIMO, propuesto)));
      };
      const suelta = () => {
        setArrastrando(false);
        guarda(CLAVE_ANCHO, String(anchoRef.current));
        window.removeEventListener("pointermove", mueve);
        window.removeEventListener("pointerup", suelta);
        window.removeEventListener("pointercancel", suelta);
      };
      window.addEventListener("pointermove", mueve);
      window.addEventListener("pointerup", suelta);
      window.addEventListener("pointercancel", suelta);
    },
    [plegado],
  );

  /** El teclado también redimensiona: arrastrar no puede ser la única vía. */
  const teclaEnTirador = useCallback((evento: React.KeyboardEvent<HTMLDivElement>) => {
    const paso = evento.shiftKey ? 48 : 16;
    let siguiente: number | null = null;
    if (evento.key === "ArrowLeft") siguiente = anchoRef.current - paso;
    else if (evento.key === "ArrowRight") siguiente = anchoRef.current + paso;
    else if (evento.key === "Home") siguiente = ANCHO_MINIMO;
    else if (evento.key === "End") siguiente = ANCHO_MAXIMO;
    if (siguiente === null) return;
    evento.preventDefault();
    const acotado = Math.min(ANCHO_MAXIMO, Math.max(ANCHO_MINIMO, siguiente));
    setAncho(acotado);
    guarda(CLAVE_ANCHO, String(acotado));
  }, []);

  const anchoActual = plegado ? ANCHO_PLEGADO : ancho;

  return (
    <div
      className="relative hidden shrink-0 lg:block"
      style={{
        width: anchoActual,
        // Mientras se arrastra no hay transición: animar cada píxel del
        // arrastre lo vuelve pastoso y desincroniza el borde del puntero.
        transition: arrastrando || !montado ? undefined : "width 140ms ease",
      }}
    >
      {plegado ? (
        <div className="flex h-full flex-col items-center gap-2 border-r border-surface-800 bg-surface-950 py-3">
          <button
            type="button"
            onClick={alternar}
            aria-expanded={false}
            aria-controls="case-sidebar-panel"
            title={t("ca_mostrar_casos")}
            aria-label={t("ca_mostrar_panel")}
            className="grid h-9 w-9 place-items-center rounded-md text-zinc-400 transition-colors hover:bg-surface-800 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400"
          >
            <PanelLeftOpen className="h-4 w-4" aria-hidden="true" />
          </button>
          <button
            type="button"
            onClick={onCreate}
            disabled={createDisabled}
            title={createDisabled ? createDisabledReason : "Caso nuevo"}
            aria-label={t("ca_crear_boton")}
            className="grid h-9 w-9 place-items-center rounded-md text-zinc-400 transition-colors hover:bg-surface-800 hover:text-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
          >
            <Plus className="h-4 w-4" aria-hidden="true" />
          </button>
          {/* Plegado sigue diciendo cuántos casos hay: un panel oculto que no
              informa de nada invita a abrirlo sólo para comprobarlo. */}
          <span
            className="mt-1 rounded bg-surface-900 px-1.5 py-0.5 font-mono text-[10px] text-zinc-500"
            title={`${totalCasos} ${totalCasos === 1 ? "caso" : "casos"}`}
          >
            {totalCasos}
          </span>
          <span
            aria-hidden="true"
            className="mt-2 select-none font-mono text-[10px] uppercase tracking-[0.25em] text-zinc-600"
            style={{ writingMode: "vertical-rl" }}
          >
            Casos
          </span>
        </div>
      ) : (
        <>
          <div id="case-sidebar-panel" className="h-full min-w-0">
            {children({ plegar: alternar })}
          </div>

          {/* Separador redimensionable. `separator` con `aria-valuenow` es lo
              que un lector de pantalla entiende como «esto se puede mover». */}
          <div
            role="separator"
            aria-orientation="vertical"
            aria-label={t("ca_ancho_panel")}
            aria-valuenow={ancho}
            aria-valuemin={ANCHO_MINIMO}
            aria-valuemax={ANCHO_MAXIMO}
            tabIndex={0}
            onPointerDown={empiezaArrastre}
            onKeyDown={teclaEnTirador}
            className={`absolute inset-y-0 right-0 z-20 w-1.5 cursor-col-resize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-400 ${
              arrastrando ? "bg-brand-500/60" : "bg-transparent hover:bg-brand-500/35"
            }`}
          />
        </>
      )}
    </div>
  );
}

export default CaseSidebarShell;
