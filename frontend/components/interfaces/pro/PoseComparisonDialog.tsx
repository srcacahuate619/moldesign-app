"use client";

import { presentError } from "../../../lib/frontendError";


import { useLanguage } from "@/context/LanguageContext";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useScrollLock } from "@/hooks/useScrollLock";
import { AlertTriangle, ArrowLeftRight, Check, Copy, Loader2, Target, X } from "lucide-react";
import { getEvaluationResult, getPoseFile, getProteinFile } from "../../../lib/api";
import { CARBONO_DE_LIGANDO, CONTACTO_COMPARTIDO } from "../../../lib/visor3d";
import {
  coincidenciasDePoses,
  compararContactos,
  lineasDeContactos,
  medirDistancia,
  posesDeLaCorrida,
  resumenDeLaComparacion,
  textoSinDistancia,
  type CoincidenciasDelLado,
  type ComparacionDeContactos,
  type ContactoComparado,
  type FuenteDeCorrida,
  type LadoDePose,
  type MedidaDeDistancia,
  type PoseDeLaLista,
} from "../../../lib/comparadorDePoses";
import { MoleculeViewer3D, type LineaDeContacto } from "../../MoleculeViewer3D";

export interface PoseComparisonDialogProps {
  readonly moleculeId: string;
  /** Identidad de la corrida inspeccionada; no caer a la última proyección. */
  readonly taskId?: string | null;
  readonly leftRank: number;
  readonly rightRank: number;
  readonly onClose: () => void;
  /**
   * Otras corridas del MISMO caso con las que se puede comparar (mismo receptor sellado). Cada lado elige su
   * corrida y su pose; sin ellas el comparador sigue siendo el de dos poses de una misma corrida.
   */
  readonly runs?: readonly FuenteDeCorrida[];
  /** Corrida con la que arranca el lado derecho; por defecto, la misma que el izquierdo. */
  readonly rightSource?: FuenteDeCorrida;
  /**
   * Información de quien abre el comparador que no es 3D (en el SAR, la ficha del análogo: SMILES, cambio clave,
   * Δ afinidad, QED y Lipinski). Se pinta bajo los visores y antes de las medidas, dentro del mismo diálogo.
   */
  readonly ficha?: ReactNode;
}

/**
 * El endpoint devuelve el SDF completo de una corrida. Este extractor conserva
 * un registro por pose y usa la misma convención 1-indexada que el backend
 * (`pose_rank=1` es la primera pose del archivo); nunca inventa coordenadas.
 */
export function extractPoseFromSdf(sdf: string, rank: number): string | null {
  if (!Number.isInteger(rank) || rank < 1) return null;
  const records = sdf
    .split(/\$\$\$\$\s*/)
    .map((record) => record.trim())
    .filter((record) => record.includes("M  END"));
  const record = records[rank - 1];
  return record ? `${record}\n$$$$\n` : null;
}

interface DatosDeLaCorrida {
  readonly sdf: string;
  readonly protein: string;
  readonly poses: readonly PoseDeLaLista[];
}

type EstadoDelLado =
  | { kind: "loading" }
  | { kind: "ready"; datos: DatosDeLaCorrida }
  | { kind: "error"; message: string };

class CorridaSinArchivos extends Error {}

/** El resultado sólo aporta la energía y los controles de cada pose: si no llega, las poses salen sin ellos. */
async function leerResultado(fuente: FuenteDeCorrida): Promise<unknown | null> {
  try {
    return await getEvaluationResult(fuente.moleculeId, fuente.taskId);
  } catch {
    return null;
  }
}

async function cargarCorrida(fuente: FuenteDeCorrida): Promise<DatosDeLaCorrida> {
  const [sdf, protein, resultado] = await Promise.all([
    getPoseFile(fuente.moleculeId, fuente.taskId),
    getProteinFile(fuente.moleculeId, fuente.taskId),
    leerResultado(fuente),
  ]);
  if (!sdf || !protein) throw new CorridaSinArchivos();
  return { sdf, protein, poses: posesDeLaCorrida(sdf, resultado) };
}

/** Un lado: su corrida elegida y su pose. Cada uno carga lo suyo y una respuesta tardía no pisa a la vigente. */
function useLado(
  fuente: FuenteDeCorrida,
  cache: React.MutableRefObject<Map<string, Promise<DatosDeLaCorrida>>>,
  t: (key: string, params?: Record<string, string | number>) => string,
): EstadoDelLado {
  const [estado, setEstado] = useState<EstadoDelLado>({ kind: "loading" });
  useEffect(() => {
    let disposed = false;
    setEstado({ kind: "loading" });
    const clave = `${fuente.moleculeId}|${fuente.taskId}`;
    let promesa = cache.current.get(clave);
    if (!promesa) {
      promesa = cargarCorrida(fuente);
      cache.current.set(clave, promesa);
    }
    promesa
      .then((datos) => { if (!disposed) setEstado({ kind: "ready", datos }); })
      .catch((error) => {
        cache.current.delete(clave);
        if (disposed) return;
        setEstado({
          kind: "error",
          message: error instanceof CorridaSinArchivos
            ? t("auto_990cc7b4b8ec")
            : error instanceof Error ? presentError(error, t) : t("pr_frontend_089"),
        });
      });
    return () => { disposed = true; };
    // `fuente` es un objeto nuevo en cada render del padre: la identidad de la corrida es lo que cuenta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fuente.moleculeId, fuente.taskId, cache, t]);
  return estado;
}

/**
 * ¿Comparten receptor preparado las dos poses? Es lo único que hace honesta una superposición: las coordenadas de
 * Vina están en el marco del receptor con el que se calcularon, y dibujar dos de marcos distintos en una escena
 * produciría una imagen bonita y sin sentido. Lo decide el backend (hash del receptor de cada corrida), no el visor.
 *   misma corrida              → el mismo receptor por construcción
 *   `frame: "same"`            → los dos hashes declarados coinciden
 *   `different` / `undeclared` → no se superpone
 */
type Receptor = "mismo" | "distinto" | "desconocido";

function receptorDeLaMedida(medida: MedidaDeDistancia): Receptor {
  if (medida.tipo === "misma_corrida" || medida.marco === "same") return "mismo";
  if (medida.marco === "different") return "distinto";
  return "desconocido";
}

type EstadoDeMedida =
  | { kind: "loading" }
  | { kind: "ready"; medida: MedidaDeDistancia }
  | { kind: "error" };

/**
 * La medida de distancia entre los dos lados, y de paso si comparten receptor. El receptor depende de las dos
 * CORRIDAS, no de las poses: al cambiar sólo de pose la medida se repite pero la respuesta sobre el receptor sigue
 * valiendo, así que la vista superpuesta no parpadea a lado a lado en cada clic.
 */
type AtomosDelNucleo = NonNullable<MedidaDeDistancia["atomosDelNucleo"]>;

function useMedida(izquierda: LadoDePose, derecha: LadoDePose): {
  estado: EstadoDeMedida;
  receptor: Receptor | "comprobando";
  /** Los átomos del núcleo común del par, mientras se repite la medida por un cambio de pose se conservan. */
  nucleo: AtomosDelNucleo | null;
} {
  const [estado, setEstado] = useState<EstadoDeMedida>({ kind: "loading" });
  const [receptor, setReceptor] = useState<{ clave: string; valor: Receptor; nucleo: AtomosDelNucleo | null } | null>(null);
  const clave = `${izquierda.fuente.moleculeId}|${izquierda.fuente.taskId}>${derecha.fuente.moleculeId}|${derecha.fuente.taskId}`;

  useEffect(() => {
    let disposed = false;
    setEstado({ kind: "loading" });
    medirDistancia(izquierda, derecha)
      .then((medida) => {
        if (disposed) return;
        setEstado({ kind: "ready", medida });
        setReceptor({ clave, valor: receptorDeLaMedida(medida), nucleo: medida.atomosDelNucleo });
      })
      .catch(() => {
        if (disposed) return;
        setEstado({ kind: "error" });
        // Sin medida no se sabe si comparten receptor: no se superpone a ciegas.
        setReceptor({ clave, valor: "desconocido", nucleo: null });
      });
    return () => { disposed = true; };
    // Lo que identifica la medida son las dos corridas y sus rangos, no los objetos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [izquierda.fuente.taskId, izquierda.fuente.moleculeId, izquierda.rank, derecha.fuente.taskId, derecha.fuente.moleculeId, derecha.rank]);

  const vigente = receptor?.clave === clave ? receptor : null;
  return { estado, receptor: vigente ? vigente.valor : "comprobando", nucleo: vigente?.nucleo ?? null };
}

/**
 * Las distancias de la pose elegida en un lado contra cada pose del otro (cuál de las del otro lado se le parece
 * más). Sólo con el mismo receptor y entre evaluaciones distintas; si el backend se abstiene o falla no se enseña
 * nada. Cambiar la pose elegida invalida lo anterior: una distancia de otra pose sería una etiqueta equivocada.
 */
function useCoincidencias(elegida: LadoDePose, otro: FuenteDeCorrida, activo: boolean): CoincidenciasDelLado | null {
  const [estado, setEstado] = useState<{ clave: string; datos: CoincidenciasDelLado | null } | null>(null);
  const clave = `${elegida.fuente.taskId}#${elegida.rank}>${otro.taskId}`;
  useEffect(() => {
    if (!activo) return;
    let disposed = false;
    coincidenciasDePoses(elegida, otro)
      .then((datos) => { if (!disposed) setEstado({ clave, datos }); })
      .catch(() => { if (!disposed) setEstado({ clave, datos: null }); });
    return () => { disposed = true; };
    // La identidad del cálculo son las dos corridas y el rango elegido, no los objetos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clave, activo]);
  return activo && estado?.clave === clave ? estado.datos : null;
}

type Vista = "lado" | "superpuesta";

type EstadoDeContactos =
  | { clave: string; kind: "loading" }
  | { clave: string; kind: "ready"; datos: ComparacionDeContactos }
  | { clave: string; kind: "error" };

export function PoseComparisonDialog({
  moleculeId,
  taskId = null,
  leftRank,
  rightRank,
  onClose,
  runs = [],
  rightSource,
  ficha,
}: PoseComparisonDialogProps) {
  const { t } = useLanguage();
  // DOC 71, DEFECTO E4, SEGUNDA VUELTA. El bloqueo de la pagina de detras se
  // arreglo con este hook —el mismo que usan los otros seis modales— pero el
  // sintoma seguia: una barra de desplazamiento pegada al borde derecho de la
  // pantalla, justo donde estaba la de la pagina. No era la de detras: era la
  // de este overlay.
  //
  // La diferencia con los otros seis, mirada una por una:
  //
  //     AboutModal, LegalModal, TargetSelectorModal,
  //     ProOptionsModal y otros modales de configuracion
  //         fixed inset-0 flex items-center justify-center   -> sin scroll
  //         el panel:  flex flex-col overflow-hidden  + cuerpo overflow-y-auto
  //
  //     este                                       ANTES
  //         fixed inset-0 ... overflow-y-auto   -> barra a lo alto del VIEWPORT
  //
  // Un contenedor `fixed inset-0` ocupa la ventana entera, asi que su barra se
  // dibuja en el mismo sitio que la de la pagina y se lee como una duplicada.
  // Dentro de la tarjeta —que es mas estrecha— la barra pertenece visiblemente
  // a la tarjeta y no puede confundirse con nada.
  useScrollLock(true);

  const actual: FuenteDeCorrida = { moleculeId, taskId: taskId ?? "", etiqueta: t("pn_cmp3d_actual") };
  const [izquierda, setIzquierda] = useState<LadoDePose>({ fuente: actual, rank: leftRank });
  const [derecha, setDerecha] = useState<LadoDePose>({ fuente: rightSource ?? actual, rank: rightRank });

  // Si el que abre el comparador cambia de corrida o de poses pedidas, los dos lados vuelven a lo pedido.
  useEffect(() => {
    const base: FuenteDeCorrida = { moleculeId, taskId: taskId ?? "", etiqueta: t("pn_cmp3d_actual") };
    setIzquierda({ fuente: base, rank: leftRank });
    setDerecha({ fuente: rightSource ?? base, rank: rightRank });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [moleculeId, taskId, leftRank, rightRank, rightSource?.taskId]);

  const cache = useRef(new Map<string, Promise<DatosDeLaCorrida>>());
  const estadoIzq = useLado(izquierda.fuente, cache, t);
  const estadoDer = useLado(derecha.fuente, cache, t);

  // Las corridas que se pueden elegir: la actual, la del lado derecho si venía de fuera y las del caso.
  const opciones = (() => {
    const vistas = new Set<string>();
    return [actual, ...(rightSource ? [rightSource] : []), ...runs].filter((fuente) => {
      if (vistas.has(fuente.taskId)) return false;
      vistas.add(fuente.taskId);
      return true;
    });
  })();
  const elegirFuente = (lado: "izq" | "der", taskIdElegido: string) => {
    const fuente = opciones.find((opcion) => opcion.taskId === taskIdElegido);
    if (!fuente) return;
    // La pose elegida deja de valer al cambiar de corrida: se vuelve a la primera.
    (lado === "izq" ? setIzquierda : setDerecha)({ fuente, rank: 1 });
  };

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [onClose]);

  const mismaCorrida = izquierda.fuente.taskId === derecha.fuente.taskId;

  const { estado: estadoMedida, receptor, nucleo } = useMedida(izquierda, derecha);
  const [vista, setVista] = useState<Vista>("lado");
  const [visibles, setVisibles] = useState({ izquierda: true, derecha: true });
  // Si se sabe que no comparten receptor, la preferencia por superponer se olvida: no vuelve sola al elegir otra cosa.
  useEffect(() => {
    if (receptor === "distinto" || receptor === "desconocido") setVista("lado");
  }, [receptor]);
  // Nunca se dibuja una superposición sin haber comprobado el receptor: mientras se comprueba, lado a lado.
  const superpuesta = vista === "superpuesta" && receptor === "mismo";

  // El núcleo sólo se dibuja distinto cuando se midió en el mismo receptor; el usuario puede apagarlo.
  const [resaltarNucleo, setResaltarNucleo] = useState(true);
  const nucleoVisible = resaltarNucleo && receptor === "mismo" ? nucleo : null;

  // Qué pose del otro lado se parece más a la elegida: sólo entre evaluaciones distintas y con el mismo receptor.
  const puedeCoincidir = receptor === "mismo" && izquierda.fuente.taskId !== derecha.fuente.taskId;
  const coincidenciasDeLaDerecha = useCoincidencias(izquierda, derecha.fuente, puedeCoincidir);
  const coincidenciasDeLaIzquierda = useCoincidencias(derecha, izquierda.fuente, puedeCoincidir);

  // Los contactos se calculan cuando se piden (tardan unos segundos) y valen para esas dos poses, no para otras.
  const claveDeContactos = `${izquierda.fuente.taskId}#${izquierda.rank}|${derecha.fuente.taskId}#${derecha.rank}`;
  const [contactos, setContactos] = useState<EstadoDeContactos | null>(null);
  const contactosVigentes = contactos?.clave === claveDeContactos ? contactos : null;
  const [dibujarContactos, setDibujarContactos] = useState(true);
  const compararLosContactos = () => {
    const clave = claveDeContactos;
    setContactos({ clave, kind: "loading" });
    compararContactos(izquierda, derecha)
      .then((datos) => setContactos((previo) => (previo?.clave === clave ? { clave, kind: "ready", datos } : previo)))
      .catch(() => setContactos((previo) => (previo?.clave === clave ? { clave, kind: "error" } : previo)));
  };
  const comparados = contactosVigentes?.kind === "ready" && contactosVigentes.datos.disponible ? contactosVigentes.datos.contactos : null;
  const lineasIzquierda = useMemo(() => (dibujarContactos && comparados ? lineasDeContactos(comparados, "izquierda", COLORES_DE_CONTACTO) : undefined), [dibujarContactos, comparados]);
  const lineasDerecha = useMemo(() => (dibujarContactos && comparados ? lineasDeContactos(comparados, "derecha", COLORES_DE_CONTACTO) : undefined), [dibujarContactos, comparados]);
  const lineasDeAmbas = useMemo(() => (dibujarContactos && comparados ? lineasDeContactos(comparados, "ambos", COLORES_DE_CONTACTO) : undefined), [dibujarContactos, comparados]);

  const poseIzquierda = estadoIzq.kind === "ready" ? extractPoseFromSdf(estadoIzq.datos.sdf, izquierda.rank) : null;
  const poseDerecha = estadoDer.kind === "ready" ? extractPoseFromSdf(estadoDer.datos.sdf, derecha.rank) : null;
  const avisoDeSuperposicion =
    receptor === "comprobando" ? { clase: "text-zinc-400", rol: "status" as const, texto: t("pn_cmp3d_sup_comprobando") }
    : receptor === "distinto" ? { clase: "text-amber-300", rol: "note" as const, texto: t("pn_cmp3d_sup_distinto") }
    : receptor === "desconocido" ? { clase: "text-amber-300", rol: "note" as const, texto: t("pn_cmp3d_sup_desconocido") }
    : null;

  return (
    <div
      className="fixed inset-0 z-[135] flex items-center justify-center overflow-hidden bg-black/80 p-4 backdrop-blur-sm"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="pose-comparison-title"
        className="flex max-h-full w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-surface-700 bg-surface-950 shadow-2xl"
      >
        <header className="flex shrink-0 items-start justify-between gap-4 border-b border-surface-800 px-5 py-4">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-purple-300">
              <ArrowLeftRight size={17} aria-hidden="true" />
              <h2 id="pose-comparison-title" className="font-sans text-base font-bold uppercase tracking-[0.14em]">
                {t("pr_pose_comparison_3d")}
              </h2>
            </div>
            <p className="mt-1.5 text-base leading-6 text-zinc-300 font-sans">
              {mismaCorrida
                ? t("pr_pose_pair", { left: izquierda.rank, right: derecha.rank })
                : t("pn_cmp3d_subtitulo")}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-white/[0.08] text-zinc-400 transition-colors hover:border-white/20 hover:text-white focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
            aria-label={t("pn_cerrar_comparador")}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </header>

        {/* El cuerpo es lo unico que se desplaza. `min-h-0` es obligatorio: sin
            el, un hijo flex no se encoge por debajo de su contenido y la tarjeta
            desborda la ventana en vez de dejar que este div haga scroll. */}
        <div className="min-h-0 flex-1 overflow-y-auto">
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 pt-4">
            <div
              role="group"
              aria-label={t("pn_cmp3d_modo")}
              className="inline-flex rounded-lg border border-zinc-700 bg-zinc-950 p-0.5 font-sans text-sm font-semibold"
            >
              <button
                type="button"
                aria-pressed={!superpuesta}
                onClick={() => setVista("lado")}
                className={`min-h-9 rounded-md px-3 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400 ${
                  !superpuesta ? "bg-purple-500/20 text-white" : "text-zinc-400 hover:text-white"
                }`}
              >
                {t("pn_cmp3d_modo_lado")}
              </button>
              <button
                type="button"
                aria-pressed={superpuesta}
                disabled={receptor !== "mismo"}
                aria-describedby={avisoDeSuperposicion ? "pose-comparison-superponer" : undefined}
                onClick={() => setVista("superpuesta")}
                className={`min-h-9 rounded-md px-3 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-50 ${
                  superpuesta ? "bg-purple-500/20 text-white" : "text-zinc-400 hover:text-white"
                }`}
              >
                {t("pn_cmp3d_modo_sup")}
              </button>
            </div>
            {nucleo && receptor === "mismo" && (
              <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 font-sans text-base text-zinc-200">
                <input
                  type="checkbox"
                  checked={resaltarNucleo}
                  onChange={(event) => setResaltarNucleo(event.target.checked)}
                  className="h-4 w-4 accent-purple-500"
                />
                {t("pn_cmp3d_nucleo_resaltar")}
              </label>
            )}
            {avisoDeSuperposicion && (
              <p
                id="pose-comparison-superponer"
                role={avisoDeSuperposicion.rol}
                className={`min-w-0 flex-1 font-sans text-base leading-6 ${avisoDeSuperposicion.clase}`}
              >
                {avisoDeSuperposicion.texto}
              </p>
            )}
            {nucleoVisible && (
              <p className="basis-full font-sans text-base leading-6 text-zinc-400">{t("pn_cmp3d_nucleo_leyenda")}</p>
            )}
          </div>

          {superpuesta ? (
            <div className="grid gap-4 p-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,24rem)]">
              <article className="overflow-hidden rounded-xl border border-surface-800 bg-black">
                {estadoIzq.kind === "ready" && estadoDer.kind === "ready" && poseIzquierda && poseDerecha ? (
                  <MoleculeViewer3D
                    poseData={poseIzquierda}
                    overlayPoseData={poseDerecha}
                    proteinData={estadoIzq.datos.protein}
                    showPrimaryLigand={visibles.izquierda}
                    showOverlayLigand={visibles.derecha}
                    primaryCoreAtoms={nucleoVisible?.izquierda}
                    overlayCoreAtoms={nucleoVisible?.derecha}
                    contactLines={lineasDeAmbas}
                    height={440}
                    hideLegend
                  />
                ) : estadoIzq.kind === "loading" || estadoDer.kind === "loading" ? (
                  <AvisoDelLado estado={{ kind: "loading" }} hayPose />
                ) : (
                  // Lo que falta lo dice la tarjeta de cada lado, a la derecha; aquí sólo queda el recuadro vacío.
                  <div className="min-h-72" aria-hidden="true" />
                )}
                <p role="note" className="border-t border-surface-800 px-4 py-3 font-sans text-base leading-6 text-zinc-300">
                  {t("pn_cmp3d_sup_nota")}
                </p>
              </article>
              <div role="group" aria-label={t("pn_cmp3d_sup_leyenda")} className="space-y-4">
                {([
                  { id: "izquierda", lado: izquierda, estado: estadoIzq, color: CARBONO_DE_LIGANDO.primero, nombre: t("pn_cmp3d_izquierda") },
                  { id: "derecha", lado: derecha, estado: estadoDer, color: CARBONO_DE_LIGANDO.superpuesto, nombre: t("pn_cmp3d_derecha") },
                ] as const).map((lado) => (
                  <section key={lado.id} className="overflow-hidden rounded-xl border border-surface-800 bg-black">
                    <ControlesDelLado
                      lado={lado.lado}
                      estado={lado.estado}
                      opciones={opciones}
                      onFuente={(id) => elegirFuente(lado.id === "izquierda" ? "izq" : "der", id)}
                      onPose={(rank) => (lado.id === "izquierda" ? setIzquierda({ ...izquierda, rank }) : setDerecha({ ...derecha, rank }))}
                      coincidencias={lado.id === "izquierda" ? coincidenciasDeLaIzquierda : coincidenciasDeLaDerecha}
                      superpuesto={{
                        nombre: lado.nombre,
                        color: lado.color,
                        visible: visibles[lado.id],
                        onVisible: (visible) => setVisibles((previos) => ({ ...previos, [lado.id]: visible })),
                      }}
                    />
                    <AvisoDelLado estado={lado.estado} hayPose={lado.estado.kind !== "ready" || Boolean(lado.id === "izquierda" ? poseIzquierda : poseDerecha)} />
                  </section>
                ))}
              </div>
            </div>
          ) : (
            <div className="grid gap-4 p-4 lg:grid-cols-2">
              <LadoDelComparador
                lado={izquierda}
                estado={estadoIzq}
                opciones={opciones}
                onFuente={(id) => elegirFuente("izq", id)}
                onPose={(rank) => setIzquierda({ ...izquierda, rank })}
                coincidencias={coincidenciasDeLaIzquierda}
                nucleo={nucleoVisible?.izquierda}
                lineas={lineasIzquierda}
              />
              <LadoDelComparador
                lado={derecha}
                estado={estadoDer}
                opciones={opciones}
                onFuente={(id) => elegirFuente("der", id)}
                onPose={(rank) => setDerecha({ ...derecha, rank })}
                coincidencias={coincidenciasDeLaDerecha}
                nucleo={nucleoVisible?.derecha}
                lineas={lineasDerecha}
              />
            </div>
          )}
          {(coincidenciasDeLaIzquierda || coincidenciasDeLaDerecha) && (
            <p role="note" className="px-5 font-sans text-base leading-6 text-zinc-400">{t("pn_cmp3d_coincidencias_nota")}</p>
          )}
          {ficha}
          <MedidasDeLaComparacion estado={estadoMedida} />
          <ContactosDeLasPoses
            puede={receptor === "mismo"}
            estado={contactosVigentes}
            onComparar={compararLosContactos}
            dibujar={dibujarContactos}
            onDibujar={setDibujarContactos}
          />
          <CopiarResumen
            resumen={() => resumenDeLaComparacion({
              t,
              izquierda: ladoParaElResumen(izquierda, estadoIzq),
              derecha: ladoParaElResumen(derecha, estadoDer),
              medida: estadoMedida.kind === "ready" ? estadoMedida.medida : null,
              contactos: contactosVigentes?.kind === "ready" ? contactosVigentes.datos : null,
            })}
          />
        </div>
      </section>
    </div>
  );
}

interface PropsDelLado {
  lado: LadoDePose;
  estado: EstadoDelLado;
  opciones: readonly FuenteDeCorrida[];
  onFuente: (taskId: string) => void;
  onPose: (rank: number) => void;
  /** Distancia de cada pose de este lado a la pose elegida del otro, cuando se pudo medir. */
  coincidencias?: CoincidenciasDelLado | null;
}

/** Un lado en la vista lado a lado: sus controles, lo que falte si falta algo, y su visor. */
function LadoDelComparador(props: PropsDelLado & { nucleo?: readonly number[]; lineas?: ReadonlyArray<LineaDeContacto> }) {
  const { lado, estado, nucleo, lineas, ...controles } = props;
  const pose = estado.kind === "ready" ? extractPoseFromSdf(estado.datos.sdf, lado.rank) : null;
  return (
    <article className="overflow-hidden rounded-xl border border-surface-800 bg-black">
      <ControlesDelLado lado={lado} estado={estado} {...controles} conBorde />
      <AvisoDelLado estado={estado} hayPose={Boolean(pose)} />
      {estado.kind === "ready" && pose && (
        <MoleculeViewer3D
          poseData={pose}
          proteinData={estado.datos.protein}
          primaryCoreAtoms={nucleo}
          contactLines={lineas}
          height={360}
          hideLegend
        />
      )}
    </article>
  );
}

/** Cómo se identifica un ligando cuando hay dos en la misma escena: su color, su nombre y si se dibuja. */
interface Superpuesto {
  readonly nombre: string;
  readonly color: string;
  readonly visible: boolean;
  readonly onVisible: (visible: boolean) => void;
}

/** La cabecera de un lado: pose y energía, la evaluación elegida y las poses que esa evaluación conservó. */
function ControlesDelLado({
  lado,
  estado,
  opciones,
  onFuente,
  onPose,
  coincidencias = null,
  conBorde = false,
  superpuesto,
}: PropsDelLado & { conBorde?: boolean; superpuesto?: Superpuesto }) {
  const { t } = useLanguage();
  const fila = estado.kind === "ready" ? estado.datos.poses.find((p) => p.rank === lado.rank) : undefined;

  return (
    <header className={`space-y-2 px-3 py-2 ${conBorde ? "border-b border-surface-800" : ""}`}>
      <div className="flex items-center justify-between gap-3">
        <h3 className="flex min-w-0 items-center gap-2 font-sans text-base font-bold uppercase tracking-wider text-zinc-200">
          {superpuesto && (
            <span
              aria-hidden="true"
              className="inline-block h-3 w-3 shrink-0 rounded-full border border-white/30"
              style={{ backgroundColor: superpuesto.color }}
            />
          )}
          <span>
            {superpuesto ? `${superpuesto.nombre} · ` : ""}
            {t("ev_mmgbsa_pose_numero", { rank: lado.rank })}
          </span>
        </h3>
        <span className="font-mono text-sm text-zinc-400">
          {typeof fila?.affinity === "number" ? `${fila.affinity.toFixed(2)} kcal/mol` : t("pr_pose_coordinates_recorded")}
        </span>
      </div>
      {opciones.length > 1 && (
        <label className="block text-sm text-zinc-400">
          <span className="sr-only">{t("pn_cmp3d_evaluacion")}</span>
          <select
            value={lado.fuente.taskId}
            onChange={(event) => onFuente(event.target.value)}
            className="min-h-9 w-full rounded-lg border border-zinc-700 bg-zinc-950 px-2 text-sm text-zinc-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400"
          >
            {opciones.map((opcion) => (
              <option key={opcion.taskId} value={opcion.taskId}>{opcion.etiqueta}</option>
            ))}
          </select>
        </label>
      )}
      {estado.kind === "ready" && estado.datos.poses.length > 0 && (
        <div role="group" aria-label={t("pn_cmp3d_poses")} className="flex flex-wrap gap-1.5">
          {estado.datos.poses.map((p) => {
            const cerca = coincidencias?.poses.find((c) => c.rank === p.rank)?.rmsd ?? null;
            const esLaMasCercana = coincidencias?.masCercana === p.rank && cerca !== null;
            const nombre = (typeof p.affinity === "number"
              ? t("pn_cmp3d_pose_chip", { rank: p.rank, kcal: p.affinity.toFixed(2) })
              : t("ev_mmgbsa_pose_numero", { rank: p.rank }))
              + (cerca !== null ? t("pn_cmp3d_chip_rmsd", { rmsd: cerca.toFixed(2) }) : "")
              + (esLaMasCercana ? t("pn_cmp3d_chip_cercana") : "");
            return (
              <button
                key={p.rank}
                type="button"
                aria-pressed={p.rank === lado.rank}
                aria-label={nombre}
                onClick={() => onPose(p.rank)}
                className={`inline-flex min-h-9 min-w-12 flex-col items-center justify-center rounded-lg border px-2 py-0.5 font-mono text-xs transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-purple-400 ${
                  p.rank === lado.rank
                    ? "border-purple-400 bg-purple-500/15 text-white"
                    : esLaMasCercana
                      ? "border-emerald-400/70 text-zinc-300 hover:bg-zinc-800"
                      : "border-zinc-700 text-zinc-300 hover:bg-zinc-800"
                }`}
              >
                <span className="flex items-center gap-1 font-bold">
                  {p.rank}
                  {p.physicallyValid && <Check size={11} className="text-emerald-400" aria-hidden="true" />}
                </span>
                {typeof p.affinity === "number" && <span className="text-zinc-400">{p.affinity.toFixed(1)}</span>}
                {cerca !== null && (
                  <span className="flex items-center gap-0.5 text-[10px] text-emerald-300">
                    {esLaMasCercana && <Target size={9} aria-hidden="true" />}
                    {cerca.toFixed(2)} Å
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
      {superpuesto && (
        <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 font-sans text-sm text-zinc-300">
          <input
            type="checkbox"
            checked={superpuesto.visible}
            onChange={(event) => superpuesto.onVisible(event.target.checked)}
            aria-label={t("pn_cmp3d_sup_mostrar", { lado: superpuesto.nombre })}
            className="h-4 w-4 accent-purple-500"
          />
          <span aria-hidden="true">{t("pn_cmp3d_sup_visible")}</span>
        </label>
      )}
    </header>
  );
}

/** Lo que se ve en lugar del visor cuando la evaluación carga, falló o no conserva la pose pedida. */
function AvisoDelLado({ estado, hayPose }: { estado: EstadoDelLado; hayPose: boolean }) {
  const { t } = useLanguage();
  if (estado.kind === "loading") {
    return (
      <div className="flex min-h-72 flex-col items-center justify-center gap-3 px-5 text-zinc-400" role="status">
        <Loader2 className="h-6 w-6 animate-spin text-purple-300" aria-hidden="true" />
        <p className="text-base font-sans leading-6">{t("pn_recuperando_poses")}</p>
      </div>
    );
  }
  if (estado.kind === "error" || (estado.kind === "ready" && !hayPose)) {
    return (
      <div className="m-4 flex items-start gap-3 rounded-xl border border-amber-500/25 bg-amber-500/[0.05] p-4 text-amber-100" role="alert">
        <AlertTriangle size={18} className="mt-0.5 shrink-0 text-amber-300" aria-hidden="true" />
        <p className="text-base leading-6 font-sans">{estado.kind === "error" ? estado.message : t("auto_91d8ff3aff6a")}</p>
      </div>
    );
  }
  return null;
}

/** La distancia y las energías que acompañan a lo que se ve. Todo lo mide el backend; aquí sólo se lee. */
function MedidasDeLaComparacion({ estado }: { estado: EstadoDeMedida }) {
  const { t } = useLanguage();
  if (estado.kind === "error") return null;
  if (estado.kind === "loading") {
    return (
      <p role="status" className="flex items-center gap-2 px-5 pb-4 text-base text-zinc-400">
        <Loader2 size={16} className="animate-spin text-purple-300" aria-hidden="true" />{t("pn_cmp_cargando")}
      </p>
    );
  }

  const { medida } = estado;
  const kcal = (valor: number | null) => (valor === null ? "—" : valor.toFixed(2));
  const pct = medida.nucleo?.fraccion != null ? Math.round(medida.nucleo.fraccion * 100) : "—";
  const motivo = textoSinDistancia(medida, t);

  return (
    <section aria-label={t("pn_cmp3d_medidas")} className="space-y-2 border-t border-surface-800 px-5 py-4 font-sans">
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        <div>
          <span className="block text-sm uppercase tracking-wider text-zinc-400">
            {t(medida.tipo === "nucleo_comun" ? "pn_ana_nucleo" : "pn_cmp3d_rmsd")}
          </span>
          <span className="font-mono text-2xl font-black text-white">
            {medida.disponible && medida.rmsd !== null ? `${medida.rmsd.toFixed(2)} Å` : "—"}
          </span>
        </div>
        <div className="font-mono text-base text-zinc-200">
          <span className="block font-sans text-sm uppercase tracking-wider text-zinc-400">{t("pn_cmp3d_vina")}</span>
          {kcal(medida.vinaIzquierda)} → {kcal(medida.vinaDerecha)}
          {medida.diferenciaComparable && medida.diferenciaVina !== null && (
            <span className="ml-2 text-zinc-400">
              ({medida.diferenciaVina > 0 ? "+" : ""}{medida.diferenciaVina.toFixed(2)})
            </span>
          )}
        </div>
      </div>
      {medida.tipo === "nucleo_comun" && (
        <p className="text-base leading-6 text-zinc-300">
          {t("pn_cmp3d_otro_ligando")}
          {medida.disponible && ` ${t("pn_ana_nucleo_tamano", { core: medida.nucleo?.atomos ?? "—", pct })}`}
        </p>
      )}
      {motivo && <p role="note" className="text-base leading-6 text-amber-300">{motivo}</p>}
      {!medida.diferenciaComparable && (
        <p role="note" className="text-base leading-6 text-amber-300">{t("pn_ana_delta_no_comparable")}</p>
      )}
      {medida.diferencias.length > 0 && (
        <dl className="grid gap-x-6 text-base sm:grid-cols-2">
          {medida.diferencias.map((d) => (
            <div key={d.field} className="flex flex-wrap items-baseline justify-between gap-x-3 py-1">
              <dt className="text-zinc-400">{t(`pn_cmp_f_${d.field}`)}</dt>
              <dd className="font-mono text-zinc-200 [overflow-wrap:anywhere]">
                {d.field === "receptor_sha256"
                  ? `${String(d.a ?? "").slice(0, 8)}… → ${String(d.b ?? "").slice(0, 8)}…`
                  : `${d.a ?? t("pn_cmp_no_declarado")} → ${d.b ?? t("pn_cmp_no_declarado")}`}
              </dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

const COLORES_DE_CONTACTO = {
  izquierda: CARBONO_DE_LIGANDO.primero,
  derecha: CARBONO_DE_LIGANDO.superpuesto,
  compartido: CONTACTO_COMPARTIDO,
} as const;

/** El nombre de un tipo de contacto; si el análisis trae uno que la interfaz no conoce, se enseña tal cual. */
function etiquetaDeTipo(t: (key: string) => string, tipo: string): string {
  const texto = t(`cm_type_${tipo}`);
  return texto === `cm_type_${tipo}` ? tipo : texto;
}

function ladoParaElResumen(lado: LadoDePose, estado: EstadoDelLado) {
  const fila = estado.kind === "ready" ? estado.datos.poses.find((p) => p.rank === lado.rank) : undefined;
  return {
    etiqueta: lado.fuente.etiqueta,
    taskId: lado.fuente.taskId,
    rank: lado.rank,
    vina: typeof fila?.affinity === "number" ? fila.affinity : null,
  };
}

/**
 * Los contactos de las dos poses elegidas, uno frente al otro. Se piden con un botón: el análisis (ProLIF) tarda unos
 * segundos y sólo vale entre poses del mismo receptor preparado. El que se pide vale para ESAS dos poses.
 */
function ContactosDeLasPoses({
  puede,
  estado,
  onComparar,
  dibujar,
  onDibujar,
}: {
  puede: boolean;
  estado: EstadoDeContactos | null;
  onComparar: () => void;
  dibujar: boolean;
  onDibujar: (dibujar: boolean) => void;
}) {
  const { t } = useLanguage();
  const datos = estado?.kind === "ready" ? estado.datos : null;
  const grupos: ReadonlyArray<{ estado: ContactoComparado["estado"]; clave: string; color: string }> = [
    { estado: "solo_izquierda", clave: "pn_cmp3d_contactos_solo_izq", color: COLORES_DE_CONTACTO.izquierda },
    { estado: "ambas", clave: "pn_cmp3d_contactos_ambas", color: COLORES_DE_CONTACTO.compartido },
    { estado: "solo_derecha", clave: "pn_cmp3d_contactos_solo_der", color: COLORES_DE_CONTACTO.derecha },
  ];
  const metros = (valor: number) => valor.toFixed(1);

  return (
    <section aria-label={t("pn_cmp3d_contactos_titulo")} className="space-y-3 border-t border-surface-800 px-5 py-4 font-sans">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <h3 className="text-sm uppercase tracking-wider text-zinc-400">{t("pn_cmp3d_contactos_titulo")}</h3>
          <p className="mt-1 text-base leading-6 text-zinc-300">
            {puede ? t("pn_cmp3d_contactos_ayuda") : t("pn_cmp3d_contactos_requiere")}
          </p>
        </div>
        {!datos?.disponible && (
          <button
            type="button"
            disabled={!puede || estado?.kind === "loading"}
            onClick={onComparar}
            className="inline-flex min-h-11 items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-purple-500 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {t("pn_cmp3d_contactos_boton")}
          </button>
        )}
      </div>

      {estado?.kind === "loading" && (
        <p role="status" className="flex items-center gap-2 text-base text-zinc-400">
          <Loader2 size={16} className="animate-spin text-purple-300" aria-hidden="true" />{t("pn_cmp3d_contactos_calculando")}
        </p>
      )}
      {estado?.kind === "error" && <p role="alert" className="text-base leading-6 text-amber-300">{t("pn_cmp3d_contactos_error")}</p>}
      {datos && !datos.disponible && (
        <p role="note" className="text-base leading-6 text-amber-300">
          {datos.motivo === "RECEPTORES_DISTINTOS" ? t("pn_cmp3d_contactos_receptores")
            : datos.motivo === "MOTORES_DISTINTOS" ? t("pn_cmp3d_contactos_motores")
            : t("pn_cmp3d_contactos_error")}
        </p>
      )}
      {datos?.disponible && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            {grupos.map((grupo) => {
              const filas = datos.contactos.filter((c) => c.estado === grupo.estado);
              return (
                <div key={grupo.estado} className="min-w-0 rounded-xl border border-surface-800 bg-black/40 p-3">
                  <h4 className="flex items-center gap-2 text-base font-semibold text-zinc-200">
                    <span aria-hidden="true" className="inline-block h-3 w-3 shrink-0 rounded-full" style={{ backgroundColor: grupo.color }} />
                    {t(grupo.clave, { n: filas.length })}
                  </h4>
                  {filas.length === 0 ? (
                    <p className="mt-2 text-base text-zinc-500">{t("pn_cmp3d_contactos_ninguno")}</p>
                  ) : (
                    <ul className="mt-2 space-y-1 text-base text-zinc-300">
                      {filas.map((c) => (
                        <li key={c.clave} className="[overflow-wrap:anywhere]">
                          <span className="font-mono font-semibold text-zinc-100">{c.residuo}</span>{" "}
                          <span className="text-zinc-400">{etiquetaDeTipo(t, c.tipo)}</span>{" "}
                          <span className="font-mono text-zinc-400">
                            {c.izquierda && c.derecha
                              ? `${metros(c.izquierda.distancia)} → ${metros(c.derecha.distancia)} Å`
                              : `${metros((c.izquierda ?? c.derecha)?.distancia ?? 0)} Å`}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              );
            })}
          </div>
          <label className="inline-flex min-h-9 cursor-pointer items-center gap-2 text-base text-zinc-200">
            <input type="checkbox" checked={dibujar} onChange={(event) => onDibujar(event.target.checked)} className="h-4 w-4 accent-purple-500" />
            {t("pn_cmp3d_contactos_dibujar")}
          </label>
          <p role="note" className="text-base leading-6 text-zinc-400">{t("pn_cmp3d_contactos_nota", { motor: datos.motor })}</p>
        </>
      )}
    </section>
  );
}

/** Un botón que deja en el portapapeles el resumen de lo que se ve, con sus límites, para un informe o un mensaje. */
function CopiarResumen({ resumen }: { resumen: () => string }) {
  const { t } = useLanguage();
  const [estado, setEstado] = useState<"reposo" | "copiado" | "error">("reposo");
  useEffect(() => {
    if (estado === "reposo") return;
    const id = window.setTimeout(() => setEstado("reposo"), 2500);
    return () => window.clearTimeout(id);
  }, [estado]);
  return (
    <div className="flex flex-wrap items-center gap-3 border-t border-surface-800 px-5 py-4 font-sans">
      <button
        type="button"
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(resumen());
            setEstado("copiado");
          } catch {
            setEstado("error");
          }
        }}
        className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-zinc-700 px-4 py-2 text-sm font-semibold text-zinc-100 transition-colors hover:bg-zinc-800 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-purple-400"
      >
        <Copy size={16} aria-hidden="true" />
        {t("pn_cmp3d_copiar")}
      </button>
      <span role="status" className={`text-base ${estado === "error" ? "text-amber-300" : "text-emerald-300"}`}>
        {estado === "copiado" ? t("pn_cmp3d_copiado") : estado === "error" ? t("pn_cmp3d_copiar_error") : ""}
      </span>
    </div>
  );
}
