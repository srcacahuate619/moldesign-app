"use client";


import { useLanguage } from "@/context/LanguageContext";
import React from "react";
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
  const estado = result?.ligand_state;
  if (!estado) return null;

  const cambio = Boolean(estado.cambio_respecto_a_la_entrada);
  const carga = etiquetaDeCarga(estado.carga_formal_neta);
  const taut = estado.tautomeria;
  const prot = estado.protonacion;

  return (
    <section
      aria-labelledby="estado-ligando-titulo"
      className="rounded-xl border border-white/[0.08] bg-black/20 p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4
          id="estado-ligando-titulo"
          className="flex items-center gap-2 font-mono text-xs font-bold uppercase tracking-[0.14em] text-zinc-200"
        >
          <FlaskConical size={14} aria-hidden="true" className="text-purple-300" />
          Especie acoplada a pH 7.4
        </h4>
        <span
          className={`rounded-md border px-2 py-0.5 font-mono text-[11px] font-bold ${carga.estilo}`}
        >
          {carga.texto}
        </span>
      </div>

      <dl className="mt-3 grid gap-x-6 gap-y-2 sm:grid-cols-2">
        <div className="min-w-0">
          <dt className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            {t("pn_lo_que_escribiste")}
          </dt>
          <dd className="truncate font-mono text-xs text-zinc-400" title={estado.smiles_entrada ?? undefined}>
            {estado.smiles_entrada ?? "—"}
          </dd>
        </div>
        <div className="min-w-0">
          <dt className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
            {t("auto_a10f57b88037")}{estado.formula_acoplada ? ` · ${estado.formula_acoplada}` : ""}
          </dt>
          <dd
            className={`truncate font-mono text-xs ${cambio ? "text-amber-200" : "text-zinc-400"}`}
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
          <div className="min-w-0 space-y-1 text-[11px] leading-relaxed text-amber-100/85">
            <p>
              <strong className="font-semibold">{t("pn_no_es_la_que_escribiste")}</strong>{" "}
              {taut?.aplicada && (
                <>
                  {t("auto_e930067de091")}
                  {taut.alternativas ? ` entre ${taut.alternativas} enumerados` : ""}.{" "}
                </>
              )}
              {prot?.aplicada && (
                <>
                  {t("auto_69c1421c8782")} {prot.ph} {t("auto_b1f6e510eb0f")} {prot.motor}
                  {prot.alternativas ? ` (${prot.alternativas} estados devueltos; se usó el primero)` : ""}.
                </>
              )}
            </p>
            <p className="text-amber-100/70">
              {t("pn_alternativas_descartadas")}
            </p>
          </div>
        </div>
      ) : (
        <p className="mt-3 text-[11px] leading-relaxed text-zinc-500">
          {t("pn_ph_no_cambia")}
        </p>
      )}

      {prot?.motivo && (
        <p
          role="status"
          className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-2.5 text-[11px] leading-relaxed text-amber-100/85"
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
      <p className="mt-2 text-[11px] leading-relaxed text-[var(--text-dim)]">
        <strong className="font-semibold">{t("pn_taut_titulo")}</strong> {t("pn_taut_unico")}
      </p>
    );
  }
  const codigo = estado === "NO_RESUELTO" ? (declaracion?.motivo ?? "").split(":")[0].trim() : "";
  return (
    <p
      role="status"
      className="mt-2 rounded-lg border border-amber-500/25 bg-amber-500/[0.05] p-2.5 text-[11px] leading-relaxed text-amber-900 dark:text-amber-100/85"
    >
      <strong className="font-semibold">{t("pn_taut_titulo")}</strong>{" "}
      {estado === "MULTIESTADO_REQUERIDO"
        ? t("pn_taut_multiestado", { n: declaracion?.n_candidatos ?? "?" })
        : t("pn_taut_no_resuelto")}
      {codigo ? <span className="font-mono"> ({codigo})</span> : null}
    </p>
  );
}
