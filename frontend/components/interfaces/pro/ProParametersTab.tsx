"use client";

import React from "react";
import { LiquidOrb } from "./LiquidOrb";
import { numeroOGuion } from "../../../lib/formatoNumerico";
import { etiquetaPPB } from "../../../lib/admetEtiquetas";

interface Props {
  result: {
    // Básicos
    qed?: number | null;
    sa_score?: number | null;
    molecular_weight?: number | null;
    log_p?: number | null;
    sa_reasons?: string[] | null;
    // ADMET
    //
    // `| null` NO ES DECORACIÓN. El backend, cuando ADMET-AI no está disponible
    // en el equipo, pone TODOS estos campos a `null` a propósito
    // (`chem/blood_viability.py::calculate_blood_viability`, rama
    // `admet_unavailable_skipping`) para no fabricar valores. Este tipo los
    // declaraba sólo como `boolean | undefined`, así que la comprobación de
    // «no hay dato» se escribió `=== undefined` y `null` se colaba por la rama
    // negativa: una aspirina sin predicción salía en rojo como «✗ No permeable»
    // y «✗ Baja». Eso no es degradar: es afirmar lo contrario de lo que se sabe.
    blood_viability_score?: number | null;
    blood_solubility_logs?: number | null;
    blood_ppb_category?: string | null;
    blood_hia_permeable?: boolean | null;
    blood_bbb_permeable?: boolean | null;
    // Por qué salió ese veredicto de BBB. El booleano solo no distingue «lo dijo
    // el modelo con p = 0.98» de «lo dijo una regla de polaridad contra el
    // modelo», y esa diferencia es justo la que el usuario necesita para saber
    // cuánto fiarse. Ver `backend/chem/bbb_consenso.py`.
    blood_bbb_motivo?: string | null;
    blood_cns_mpo?: number | null;
    blood_systemic_reactivity?: string[] | null;
    /** "evaluado" | "fallo" | "no_evaluado"; null en evaluaciones anteriores
     *  al 2026-09-04, en las que TabPFN nunca llego a clasificar. */
    blood_tabpfn_estado?: string | null;
    // Drug-likeness
    lipinski_pass?: boolean | null;
    veber_pass?: boolean | null;
    ghose_pass?: boolean | null;
    egan_pass?: boolean | null;
    muegge_pass?: boolean | null;
    muegge_score?: number | null;
    fsp3?: number | null;
    is_pains?: boolean | null;
    pains_matches?: string[] | null;
    // Propiedades FQ
    tpsa?: number | null;
    hbd?: number | null;
    hba?: number | null;
    rotatable_bonds?: number | null;
    heavy_atom_count?: number | null;
    ring_count?: number | null;
    ligand_efficiency?: number | null;
    lipophilic_efficiency?: number; // LLE
    affinity_threshold?: number | null;
    // Contexto de scoring (F-21): modelo usado (target_family y pesos de
    // stacking YA se renderizan en el DOT de ProEvaluation — no duplicar)
    model_used?: string | null;
    engine_used?: string | null;
  } | null | undefined;
}

export function ProParametersTab({ result }: Props) {
  if (!result) {
    return (
      <div className="space-y-3 animate-in fade-in duration-200">
        <div className="text-center text-slate-400 text-xs py-12 font-mono">
          Sin datos. Ejecuta una simulación para extraer los coeficientes fisicoquímicos detallados.
        </div>
      </div>
    );
  }

  // ── ¿Corrió ADMET-AI en este equipo? ─────────────────────────────────────
  //
  // El backend no manda una bandera; manda ausencia. Cuando el modelo no está
  // disponible pone a `null` los cinco campos del bloque a la vez, así que la
  // señal más fiel a lo que ocurrió es que NINGUNO tenga valor. Con eso se
  // decide una sola cosa —¿hubo predicción, sí o no?— y todo el bloque se pinta
  // en consecuencia, en vez de que cada campo invente su propio veredicto.
  const admetAusente =
    result.blood_viability_score == null &&
    result.blood_solubility_logs == null &&
    result.blood_ppb_category == null &&
    result.blood_hia_permeable == null &&
    result.blood_bbb_permeable == null;

  // Si el clasificador de toxicidad llegó a correr. Es una señal PROPIA y no
  // se deduce de ADMET: son dos modelos distintos y fallan por separado.
  // `blood_tabpfn_estado` es null en las evaluaciones anteriores al
  // 2026-09-04, en las que TabPFN de hecho nunca clasificó: null se trata
  // como «no evaluado», que es lo que fue.
  const tabpfnNoEvaluo =
    admetAusente || result.blood_tabpfn_estado !== "evaluado";

  /** Sí / no / no se midió. Nunca convierte la tercera en la segunda. */
  const booleanoAdmet = (valor: boolean | null | undefined, si: string, no: string) =>
    valor == null
      ? { value: "sin dato", ok: undefined as boolean | undefined, neutral: true }
      : { value: valor ? si : no, ok: valor, neutral: false };

  const drugRules = [
    { label: "Lipinski", passed: result.lipinski_pass },
    { label: "Veber", passed: result.veber_pass },
    { label: "Ghose", passed: result.ghose_pass },
    { label: "Egan", passed: result.egan_pass },
    { label: "Muegge", passed: result.muegge_pass, extra: result.muegge_score != null ? `${result.muegge_score}/9` : undefined },
    { label: "Fsp³", extra: result.fsp3?.toFixed(2), isNeutral: true },
  ];

  const physicochemical = [
    { label: "MW", value: numeroOGuion(result.molecular_weight, 1, " g/mol") },
    { label: "LogP", value: result.log_p?.toFixed(2) || "—" },
    { label: "TPSA", value: numeroOGuion(result.tpsa, 1, " Å²") },
    { label: "HBD / HBA", value: `${result.hbd ?? "—"} / ${result.hba ?? "—"}` },
    { label: "Rot. Bonds", value: result.rotatable_bonds?.toString() || "—" },
    { label: "Heavy Atoms", value: result.heavy_atom_count?.toString() || "—" },
    { label: "Rings", value: result.ring_count?.toString() || "—" },
    { label: "LE", value: result.ligand_efficiency?.toFixed(3) || "—" },
    { label: "LLE", value: result.lipophilic_efficiency?.toFixed(2) || "—" },
    { label: "Umbral de afinidad", value: result.affinity_threshold != null ? `${result.affinity_threshold} kcal/mol` : "—" },
  ];

  return (
    <div className="space-y-5 animate-in fade-in duration-200 font-sans">
      {/* ─── Header section: QED + SA Score ─── */}
      <div className="grid grid-cols-2 gap-3 text-xs font-mono">
        <div className="bg-black/40 p-3.5 rounded-xl border border-white/10 space-y-1">
          <span className="text-slate-400 block uppercase font-mono font-bold text-xs tracking-wider">QED Score:</span>
          <span className="text-white text-base font-bold font-mono">{result.qed?.toFixed(3) || "N/A"}</span>
        </div>
        <div className="bg-black/40 p-3.5 rounded-xl border border-white/10 space-y-1">
          <span className="text-slate-400 block uppercase font-mono font-bold text-xs tracking-wider">SA Score:</span>
          <span className="text-white text-base font-bold font-mono">{result.sa_score?.toFixed(2) || "N/A"}</span>
        </div>
      </div>

      {/* ─── Drug-likeness Rules ─── */}
      <div className="border-t border-white/10 pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-mono font-black uppercase tracking-widest text-slate-300">
            Drug-likeness
          </h4>
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
            Filtros farmacológicos
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {drugRules.map((rule) => (
            <div key={rule.label} className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/5 font-sans text-xs">
              {rule.isNeutral ? (
                <span className="text-white/30 font-mono">{rule.extra ?? "—"}</span>
              ) : rule.passed ? (
                <span className="text-emerald-400 text-sm font-bold">✓</span>
              ) : (
                <span className="text-red-400 text-sm font-bold">✗</span>
              )}
              <span className="text-white/70">{rule.label}</span>
              {rule.extra && !rule.isNeutral && (
                <span className="text-[11px] font-mono text-white/25 ml-auto">{rule.extra}</span>
              )}
            </div>
          ))}
          {/* PAINS */}
          <div className="flex items-center gap-2.5 px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/5 font-sans text-xs">
            {result.is_pains ? (
              <span className="text-red-400 text-sm font-bold">✗</span>
            ) : (
              <span className="text-emerald-400 text-sm font-bold">✓</span>
            )}
            <span className="text-white/70">PAINS</span>
            {result.is_pains && (
              <span className="text-[11px] font-mono text-rose-300/70 ml-auto">
                {result.pains_matches?.length ?? 0} hits
              </span>
            )}
          </div>
        </div>

        {result.is_pains && result.pains_matches && result.pains_matches.length > 0 && (
          <div className="px-3 py-2 rounded-lg bg-red-500/5 border border-red-500/10 space-y-1 font-mono text-xs">
            <span className="text-rose-400 uppercase font-bold block mb-0.5 tracking-wider">Motivos PAINS detectados:</span>
            {result.pains_matches.map((p, idx) => (
              <p key={idx} className="text-rose-300/90 text-xs leading-relaxed">• {p}</p>
            ))}
          </div>
        )}
      </div>

      {/* ─── SA Reasons ─── */}
      {result.sa_reasons && result.sa_reasons.length > 0 && (
        <div className="bg-black/40 p-4 rounded-xl border border-white/10 text-xs space-y-1.5 font-mono">
          <span className="text-rose-400 uppercase font-bold block mb-1 tracking-wider text-xs">
            Restricciones SA:
          </span>
          {result.sa_reasons.map((r, idx) => (
            <div key={idx} className="text-rose-300 font-medium text-xs leading-relaxed">• {r}</div>
          ))}
        </div>
      )}

      {/* ─── Propiedades Físico-Químicas ─── */}
      <div className="border-t border-white/10 pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-mono font-black uppercase tracking-widest text-slate-300">
            Propiedades Físico-Químicas
          </h4>
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-purple-500/15 text-purple-300 border border-purple-500/25">
            RDKit
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {physicochemical.map((p) => (
            <div key={p.label} className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/5">
              <span className="text-[10px] font-medium text-white/40 uppercase tracking-wider font-sans">{p.label}</span>
              <span className="text-xs font-bold font-mono text-white/80">{p.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ─── Contexto de Scoring (F-21) ───
          Solo campos NUEVOS (model_used/engine_used). target_family y los
          pesos de stacking YA se renderizan en el DOT Pipeline Timeline de
          ProEvaluation (familia + w= por etapa) — no duplicar (regla 4). */}
      <div className="border-t border-white/10 pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-mono font-black uppercase tracking-widest text-slate-300">
            Contexto de Scoring
          </h4>
          <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-300 border border-emerald-500/25">
            ML Stacking
          </span>
        </div>

        <div className="grid grid-cols-2 gap-2">
          {[
            {
              label: "Modelo usado",
              value:
                result.model_used === "family"
                  ? "Específico de familia"
                  : result.model_used === "universal"
                    ? "Universal"
                    : "—",
            },
            { label: "Motor", value: result.engine_used || "—" },
          ].map((m) => (
            <div key={m.label} className="flex justify-between items-center px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/5">
              <span className="text-[10px] font-medium text-white/40 uppercase tracking-wider font-sans">{m.label}</span>
              <span className="text-xs font-bold font-mono text-white/80">{m.value}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ─── ADMET Pharmacokinetics & MPO Profile ─── */}
      <div className="border-t border-white/10 pt-4 space-y-3">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-mono font-black uppercase tracking-widest text-slate-300">
            Perfil ADMET & Viabilidad
          </h4>
          <span
            className={`text-xs font-mono font-bold px-2 py-0.5 rounded border ${
              admetAusente
                ? "bg-white/[0.04] text-white/45 border-white/10"
                : "bg-indigo-500/20 text-indigo-300 border-indigo-500/30"
            }`}
          >
            {admetAusente ? "ADMET-AI no disponible" : "ADMET-AI & TabPFN"}
          </span>
        </div>

        {/* El hueco se explica UNA vez, arriba, y se dice qué hacer con él.
            Sin esta línea el usuario ve cinco guiones y no sabe si su molécula
            salió mal o si el modelo no llegó a correr.

            No se nombra UNA causa: el resultado sólo trae ausencia, y desde
            aquí no se distingue «el usuario apagó el interruptor de ADMET-AI
            en Opciones» de «el modelo no se pudo cargar». Afirmar la que no
            fue sería el mismo error, más pequeño, que el que se está
            corrigiendo. */}
        {admetAusente && (
          <p
            role="status"
            className="rounded-lg border border-amber-500/20 bg-amber-500/[0.05] px-3 py-2.5 text-[11px] leading-relaxed text-amber-100/80"
          >
            Esta corrida no tiene predicción farmacocinética: ADMET-AI no llegó a
            ejecutarse, sea porque estaba desactivado en las opciones de la corrida
            o porque el modelo no se pudo cargar en este equipo. Los campos de abajo
            están vacíos porque no se midió nada,{" "}
            <strong className="font-semibold">no</strong> porque la molécula haya dado
            un resultado desfavorable. El resto de la evaluación —acoplamiento, poses y
            controles físicos— no depende de este bloque.{" "}
            {/* Ahora SÍ hay algo que hacer. El párrafo sigue sin nombrar una causa
                —desde aquí no se distinguen— pero sí la salida: ADMET depende sólo
                del SMILES, así que se puede calcular sin repetir el acoplamiento. */}
            <strong className="font-semibold">
              Puedes calcularlo ahora desde Análisis avanzado → ADMET
            </strong>
            : no hace falta repetir el acoplamiento, porque sólo depende del SMILES.
          </p>
        )}

        {/* ── Liquid Orbs: Viabilidad (izq) + Solubilidad (der) ── */}
        <div className="grid grid-cols-2 gap-4 py-2">
          <div className="flex justify-center">
            <LiquidOrb
              value={result.blood_viability_score ?? 0}
              unavailable={result.blood_viability_score == null}
              unavailableNote="ADMET-AI no se ejecutó en esta corrida"
              absolute={numeroOGuion(result.blood_viability_score, 0, " / 100")}
              label="Perfil Sanguíneo (índice)"
              source="ADMET-AI · heurístico"
            />
          </div>
          <div className="flex justify-center">
            <LiquidOrb
              value={
                result.blood_solubility_logs != null
                  ? Math.max(0, Math.min(100, 50 + result.blood_solubility_logs * 10))
                  : 0
              }
              unavailable={result.blood_solubility_logs == null}
              unavailableNote="ADMET-AI no se ejecutó en esta corrida"
              absolute={
                result.blood_solubility_logs != null
                  ? `${result.blood_solubility_logs.toFixed(2)} logS`
                  : "—"
              }
              label="Solubilidad"
              source="ADMET-AI"
            />
          </div>
        </div>

        {/* Métricas ADMET adicionales (PPB, HIA, BBB, SA) */}
        <div className="grid grid-cols-2 gap-2 mt-2">
          {([
            {
              label: "PPB",
              value: etiquetaPPB(result.blood_ppb_category) ?? "sin dato",
              ok: undefined,
              neutral: true,
            },
            { label: "HIA", ...booleanoAdmet(result.blood_hia_permeable, "✓ Alta", "✗ Baja") },
            {
              label: "BBB",
              ...booleanoAdmet(result.blood_bbb_permeable, "✓ Permeable", "✗ No permeable"),
            },
            {
              label: "CNS MPO",
              value: numeroOGuion(result.blood_cns_mpo, 2, " / 6"),
              ok: (result.blood_cns_mpo ?? 0) >= 4,
              neutral: true,
            },
            {
              label: "SA Score",
              value: numeroOGuion(result.sa_score, 1, " / 10"),
              ok: (result.sa_score ?? 10) <= 3.5,
              neutral: true,
            },
          ] as Array<{ label: string; value: string; ok?: boolean; neutral: boolean }>).map((m) => (
            <div key={m.label} className="flex items-center justify-between px-3 py-2.5 rounded-lg bg-white/[0.02] border border-white/5">
              <span className="text-xs font-medium text-white/50 font-sans">{m.label}</span>
              <span className={`text-xs font-bold font-mono ${m.neutral ? "text-white/60" : m.ok ? "text-emerald-400" : "text-rose-400"}`}>{m.value}</span>
            </div>
          ))}
        </div>

        {/* Por qué ese veredicto de BBB: la regla que decidió, con sus números */}
        {result.blood_bbb_motivo ? (
          <p className="mt-2 px-3 py-2 rounded-lg bg-white/[0.02] border border-white/5 text-[11px] leading-relaxed text-white/45 font-sans">
            <span className="font-semibold text-white/60">BBB — </span>
            {result.blood_bbb_motivo}
          </p>
        ) : null}

        {/* Systemic Reactivity */}
        <div className="bg-black/40 p-4 rounded-xl border border-white/10 text-xs space-y-1 font-mono">
          <span className="text-slate-400 uppercase font-mono font-bold block mb-1 text-xs tracking-wider">
            Señales de reactividad sistémica:
          </span>
          {result.blood_systemic_reactivity && result.blood_systemic_reactivity.length > 0 ? (
            <div className="space-y-1">
              {result.blood_systemic_reactivity.map((err, idx) => (
                <div key={idx} className="text-rose-400 font-semibold font-mono text-xs flex items-start gap-1.5">
                  <span>⚠</span> <span>{err}</span>
                </div>
              ))}
              <p className="text-xs text-rose-300/80 font-sans mt-1">
                Señales de reactividad sistémica producidas por TabPFN; requieren validación experimental.
              </p>
            </div>
          ) : tabpfnNoEvaluo ? (
            /* Una lista vacía tiene DOS causas y decían lo mismo en verde:
               «TabPFN miró y no encontró nada» y «TabPFN no llegó a mirar».
               La segunda no es un visto bueno, y presentarla como tal es la
               única de las dos que puede hacer daño.

               La distinción se hacía con `admetAusente`, que es la señal
               EQUIVOCADA: dice si ADMET-AI estuvo disponible, no si el
               clasificador de toxicidad corrió. Y no corría nunca —leía un
               campo que no existe, ver `chem/blood_viability.py`—, así que
               con ADMET vivo esta rama no se tomaba y todo el mundo veía el
               visto bueno verde. Ahora el backend manda su propio estado. */
            <p className="text-white/45 font-semibold text-xs font-mono">
              — Sin evaluar: el clasificador de toxicidad no corrió en este equipo.
            </p>
          ) : (
            <p className="text-emerald-400 font-semibold text-xs font-mono">
              ✓ Sin alertas de reactividad sistémica identificadas por TabPFN.
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
