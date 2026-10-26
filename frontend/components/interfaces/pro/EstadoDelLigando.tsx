"use client";


import { useLanguage } from "@/context/LanguageContext";
import React, {useId} from "react";
import {useResultReading} from "./ResultReadingPresentation";
import styles from "./ResultPanels.module.css";
import { AlertTriangle, FlaskConical } from "lucide-react";
import type { EvaluationResult } from "../../../lib/types";

// =====================================================================
// La especie que de verdad se acopló
// =====================================================================
//
// EL HUECO QUE CIERRA. El backend ya registraba con detalle qué tautómero
// eligió RDKit y qué estado de protonación produjo dimorphite-dl a pH 7.4
// (`chem/conformer.py::estado_del_ligando`), y emitía un aviso cuando la
// especie cambiaba. Pero en la pantalla el usuario seguía viendo ÚNICAMENTE el
// SMILES que él escribió, y los descriptores —MW, LogP, TPSA— se calculan
// sobre esa forma neutra.
//
// Medido, con moléculas que cualquiera reconoce:
//
//     escrito                          acoplado                     carga
//     CC(=O)Oc1ccccc1C(=O)O            …C(=O)[O-]                     −1
//     CN(C)CCOC(c1ccccc1)c1ccccc1      …[NH+](C)C…                    +1
//
// Es decir: la aspirina se acopla como anión y la difenhidramina como catión,
// y en pantalla las dos aparecían neutras. Quien mire un puente salino o
// interprete el LogP está mirando una especie distinta de la que produjo las
// poses.
//
// Esta tarjeta no cambia nada del cálculo: enseña lo que ya se había decidido.

const ESTILO_CARGA: Record<string, string> = {
  positiva: "border-sky-500/30 bg-sky-500/[0.08] text-sky-200",
  negativa: "border-orange-500/30 bg-orange-500/[0.08] text-orange-200",
  neutra: "border-white/[0.12] bg-white/[0.04] text-zinc-300",
};

function etiquetaDeCarga(carga: number | null | undefined): {
  texto: string;
  estilo: string;
} {
  if (carga == null) return { texto: "carga sin determinar", estilo: ESTILO_CARGA.neutra };
  if (carga > 0) return { texto: `catión ${carga > 1 ? `+${carga}` : "+1"}`, estilo: ESTILO_CARGA.positiva };
  if (carga < 0) return { texto: `anión ${carga < -1 ? carga : "−1"}`, estilo: ESTILO_CARGA.negativa };
  return { texto: "especie neutra", estilo: ESTILO_CARGA.neutra };
}

export function EstadoDelLigando({ result }: { readonly result: EvaluationResult | null | undefined }) {
  const { t } = useLanguage();
  const reading=useResultReading();
  const titleId=useId();
  const estado = result?.ligand_state;
  if (!estado) return null;

  const cambio = Boolean(estado.cambio_respecto_a_la_entrada);
  const carga = etiquetaDeCarga(estado.carga_formal_neta);
  const taut = estado.tautomeria;
  const prot = estado.protonacion;
  // SCI-A-066: sólo atribuir pH cuando la protonación aplicada lo registra.
  const ph = prot?.aplicada === true && typeof prot.ph === "number" && Number.isFinite(prot.ph) ? prot.ph : null;
  const titulo = prot?.aplicada === false
    ? t("pr_ligand_species_no_protonation")
    : ph === null ? t("pr_ligand_species_protonation_unknown") : t("pr_ligand_species_ph", { ph });
  const sinCambio = prot?.aplicada === false
    ? t("pn_prot_no_aplicada_sin_cambio")
    : ph === null ? t("pn_prot_desconocida_sin_cambio") : t("pn_ph_no_cambia", { ph });
  const seleccion = prot?.seleccion;
  const criterios: Record<string, string> = {
    primer_smiles_alfabetico_sin_centros: "pn_prot_seleccion_alfabetica",
    grupo_reconocido_sin_pka: "pn_prot_seleccion_sin_pka",
    sin_microestados: "pn_prot_seleccion_sin_estados",
    sin_microestados_validos: "pn_prot_seleccion_sin_validos",
  };
  const criterio = seleccion?.criterio ?? "";
  let detalleSeleccion = t(Object.prototype.hasOwnProperty.call(criterios, criterio)
    ? criterios[criterio] : "pn_prot_seleccion_desconocida");
  if (criterio.startsWith("cargas_esperadas_ph_")) {
    const sufijo = criterio.slice("cargas_esperadas_ph_".length);
    const phCriterio = sufijo.trim() !== "" && Number.isFinite(Number(sufijo)) ? Number(sufijo) : prot?.ph;
    detalleSeleccion = typeof phCriterio === "number" && Number.isFinite(phCriterio)
      ? t("pn_prot_seleccion_cargas", { ph: phCriterio })
      : t("pn_prot_seleccion_cargas_sin_ph");
  }

  if(reading.enabled) return <section className={styles.section} aria-labelledby={titleId} data-ligand-state="true">
    <div className={styles.sectionHeader}><h4 id={titleId}>{titulo}</h4><span className={styles.badge} data-state={cambio?"review":"not_evaluated"}>{carga.texto}</span></div>
    {cambio?<p className={styles.warning}><strong>{t("pn_no_es_la_que_escribiste")}</strong> {t("ux_species_brief")}</p>:<p className={styles.note}>{sinCambio}</p>}
    <DeclaracionDelTautomero declaracion={taut?.declaracion}/>
    {seleccion?.quimica_resuelta===false&&<p className={styles.warning}>{t("pn_prot_quimica_no_resuelta")}</p>}
    {ph!==null&&typeof prot?.ph_solicitado==="number"&&Number.isFinite(prot.ph_solicitado)&&prot.ph_solicitado!==ph&&<p className={styles.note}>{t("pn_ph_solicitado_ejecutado",{solicitado:prot.ph_solicitado,ejecutado:ph})}</p>}
    {prot?.aviso_de_ph&&<p className={styles.warning}>{prot.aviso_de_ph}</p>}
    {prot?.motivo&&<p className={styles.warning}>{prot.motivo}</p>}
    <details className={styles.details}>
      <summary>{t("ux_species_details")}</summary>
      <div className={styles.detailBody}>
        <dl className={styles.rows}>
          <div className={styles.row}><dt>{t("pn_lo_que_escribiste")}</dt><dd className={styles.chemicalCode}>{estado.smiles_entrada??"—"}</dd></div>
          <div className={styles.row}><dt>{t("auto_a10f57b88037")}{estado.formula_acoplada?` · ${estado.formula_acoplada}`:""}</dt><dd className={styles.chemicalCode}>{estado.smiles_acoplado??"—"}</dd></div>
        </dl>
        {taut?.aplicada&&<p className={styles.note}>{t("auto_e930067de091")}{taut.alternativas!=null?` ${t("pn_taut_enumerados",{n:taut.alternativas})}`:""}.</p>}
        {prot?.aplicada&&<p className={styles.note}>{ph===null?t("pn_prot_ph_no_consta"):`${t("ux_protonation_assigned")} ${ph}`} {prot.motor?`${t("auto_b1f6e510eb0f")} ${prot.motor}`:""}{prot.alternativas!=null?` (${t("pn_prot_estados_devueltos",{n:prot.alternativas})})`:""}.</p>}
        {cambio&&<p className={styles.note}>{t("pn_alternativas_descartadas")}</p>}
        <p className={styles.note}>{detalleSeleccion}</p>
        {seleccion?.motivo&&<p className={styles.note}>{seleccion.motivo}</p>}
      </div>
    </details>
  </section>;

  return (
    <section
      aria-labelledby={titleId}
      className="rounded-xl border border-white/[0.08] bg-black/20 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4
          id={titleId}
          className="flex items-center gap-2 font-sans text-base font-bold uppercase tracking-[0.14em] text-zinc-200"
        >
          <FlaskConical size={14} aria-hidden="true" className="text-purple-300" />
          {titulo}
        </h4>
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-sm font-bold ${carga.estilo}`}
        >
          {carga.texto}
        </span>
      </div>

      <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="font-sans text-sm uppercase tracking-wider text-zinc-400">
            {t("pn_lo_que_escribiste")}
          </dt>
          <dd className="truncate font-sans text-base text-zinc-400 leading-6" title={estado.smiles_entrada ?? undefined}>
            {estado.smiles_entrada ?? "—"}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="font-sans text-sm uppercase tracking-wider text-zinc-400">
            {t("auto_a10f57b88037")}{estado.formula_acoplada ? ` · ${estado.formula_acoplada}` : ""}
          </dt>
          <dd
            className={`truncate font-sans text-base leading-6 ${cambio ? "text-amber-200" : "text-zinc-400"}`}
            title={estado.smiles_acoplado ?? undefined}
          >
            {estado.smiles_acoplado ?? "—"}
          </dd>
        </div>
      </dl>

      {cambio ? (
        <div
          role="status"
          className="mt-3 flex items-start gap-2.5 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-3"
        >
          <AlertTriangle size={15} aria-hidden="true" className="mt-0.5 shrink-0 text-amber-300" />
          <div className="min-w-0 space-y-1 text-base leading-6 text-amber-100 font-sans">
            <p>
              <strong className="font-semibold">{t("pn_no_es_la_que_escribiste")}</strong>{" "}
              {taut?.aplicada && (
                <>
                  {t("auto_e930067de091")}
                  {taut.alternativas != null ? ` ${t("pn_taut_enumerados", { n: taut.alternativas })}` : ""}.{" "}
                </>
              )}
              {prot?.aplicada && (
                <>
                  {ph === null ? t("pn_prot_ph_no_consta") : <>{t("ux_protonation_assigned")} {ph}</>}{" "}
                  {prot.motor ? <>{t("auto_b1f6e510eb0f")} {prot.motor}</> : null}
                  {prot.alternativas != null ? ` (${t("pn_prot_estados_devueltos", { n: prot.alternativas })})` : ""}.
                </>
              )}
            </p>
            <p className="text-amber-100">
              {t("pn_alternativas_descartadas")}
            </p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-base leading-6 text-zinc-300 font-sans">
          {sinCambio}
        </p>
      )}

      {ph !== null && typeof prot?.ph_solicitado === "number" && Number.isFinite(prot.ph_solicitado) && prot.ph_solicitado !== ph && (
        <p className="mt-2 text-base leading-6 text-zinc-300 font-sans">
          {t("pn_ph_solicitado_ejecutado", { solicitado: prot.ph_solicitado, ejecutado: ph })}
        </p>
      )}
      {prot?.aviso_de_ph && (
        <p className="mt-2 text-base leading-6 text-amber-100 font-sans">{prot.aviso_de_ph}</p>
      )}

      <div className="mt-2 space-y-1 text-base leading-6 text-zinc-300 font-sans">
        <p>{detalleSeleccion}</p>
        {seleccion?.quimica_resuelta === false && <p>{t("pn_prot_quimica_no_resuelta")}</p>}
        {seleccion?.motivo && <p>{seleccion.motivo}</p>}
      </div>

      {prot?.motivo && (
        <p
          role="status"
          className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-2.5 text-base leading-6 text-amber-100 font-sans"
        >
          {prot.motivo}
        </p>
      )}

      <DeclaracionDelTautomero declaracion={taut?.declaracion} />
    </section>
  );
}

/**
 * Qué tautómero se acopló, y si quedaron otros sin descartar (FEP-ready, paso 1).
 *
 * Se traduce desde el CÓDIGO que emite el backend (`estado`, `n_candidatos`), no
 * desde su frase en castellano: es el contrato de F→B-004 del canal entre
 * sesiones. De `motivo` sólo se enseña el código del principio. El resto puede
 * ser el texto de una excepción. Sin declaración (corridas anteriores a
 * 56e8733) no se enseña nada, igual que en el expediente.
 */
function DeclaracionDelTautomero({
  declaracion,
}: {
  declaracion?: { estado?: string; n_candidatos?: number | null; motivo?: string | null } | null;
}) {
  const { t } = useLanguage();
  const estado = declaracion?.estado;
  if (!estado) return null;

  if (estado === "RESUELTO_UNICO") {
    return (
      <p className="mt-2 text-base leading-6 text-[var(--text-dim)] font-sans">
        <strong className="font-semibold">{t("pn_taut_titulo")}</strong> {t("pn_taut_unico")}
      </p>
    );
  }
  const codigo = estado === "NO_RESUELTO" ? (declaracion?.motivo ?? "").split(":")[0].trim() : "";
  return (
    <p
      role="status"
      className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-2.5 text-base leading-6 text-amber-900 dark:text-amber-100 font-sans"
    >
      <strong className="font-semibold">{t("pn_taut_titulo")}</strong>{" "}
      {estado === "MULTIESTADO_REQUERIDO"
        ? t("pn_taut_multiestado", { n: declaracion?.n_candidatos ?? "?" })
        : t("pn_taut_no_resuelto")}
      {codigo ? <span className="font-mono"> ({codigo})</span> : null}
    </p>
  );
}
