/* Hallmark · pre-emit critique: P5 H5 E4 S5 R5 V4
 * component: evaluation configuration · genre: modern-minimal · theme: existing MolDesign
 * Presentation only; scientific states and execution remain with their owners. */
"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { useLanguage } from "../../context/LanguageContext";
import { localizeReceptorLabel, type PreflightReport } from "../../lib/preflight";
import type { CaseStructuralSystem, PreflightSummary } from "../../lib/cases/types";
import styles from "./ConfigurationPresentation.module.css";

const Presentation = createContext<{
  target: HTMLDivElement | null;
  register: (node: HTMLDivElement | null) => void;
} | null>(null);
export const useConfigurationPresentation = () => useContext(Presentation) !== null;

export function ConfigurationPresentation({ children }: { children: ReactNode }) {
  const [target, register] = useState<HTMLDivElement | null>(null);
  const value = useMemo(() => ({ target, register }), [target]);
  return <Presentation.Provider value={value}><div className={styles.board} data-configuration-board>{children}</div></Presentation.Provider>;
}

/** Sólo cambia la ubicación; la comprobación conserva la propiedad de sus datos. */
export function ConfigurationMetadata({ fingerprint, note }: { fingerprint: string; note?: string }) {
  const presentation = useContext(Presentation);
  const { t } = useLanguage();
  const content = <section className={styles.metadata} data-configuration-metadata>
    <p className={styles.fingerprint}>{t("cf_fingerprint")}<code>{fingerprint}</code></p>
    {note && <p className={styles.metadataNote}>{note}</p>}
  </section>;
  return presentation?.target ? createPortal(content, presentation.target) : content;
}

export function ConfigurationMetadataSlot() {
  const presentation = useContext(Presentation);
  return <div className={styles.metadataSlot} ref={presentation?.register} data-configuration-metadata-slot />;
}

export function ConfigurationSystem({ system, provisional, chains, compact = false, id }: {
  system: CaseStructuralSystem; provisional: boolean; chains: string | null; compact?: boolean; id?: string;
}) {
  const { t } = useLanguage();
  const receptor = chains ? t("ca_receptor_label_multiple", { pdbId: system.receptor.pdbId, chains })
    : system.receptor.chain ? t("ca_receptor_label_single", { pdbId: system.receptor.pdbId, chain: system.receptor.chain }) : system.receptor.pdbId;
  if (compact) return <span id={id} className={styles.systemCompact} data-configuration-system data-system-compact>
    <span className={styles.systemCompactTop}>
      <span className={styles.systemCompactTitle}>{t(provisional ? "ev_sistema_provisional" : "ev_sistema_fijado")}</span>
      <span className={styles.systemCompactRun}><span className={styles.systemCompactLabel}>{t("cf_source_run")}</span><code>{system.sourceRunTaskId}</code></span>
    </span>
    <span className={styles.systemCompactFacts}>
      <span><span className={styles.systemCompactLabel}>{t("pr_preflight_receptor")}</span><span>{receptor}</span></span>
      <span><span className={styles.systemCompactLabel}>{t("cf_box_dimensions")}</span><span>{system.grid.size.map(String).join(" × ")} Å</span></span>
    </span>
  </span>;
  return <section className={styles.system} data-configuration-system>
    <div className={styles.systemHeader}>
      <h3>{t(provisional ? "ev_sistema_provisional" : "ev_sistema_fijado")}</h3>
      <p className={styles.sourceRun}><span>{t("cf_source_run")}</span><code>{system.sourceRunTaskId}</code></p>
    </div>
    <dl className={styles.systemFacts}>
      <div><dt>{t("pr_preflight_receptor")}</dt><dd>{receptor}</dd></div>
      <div><dt>{t("cf_box_dimensions")}</dt><dd>{system.grid.size.map(String).join(" × ")} Å</dd></div>
    </dl>
  </section>;
}

export function ConfigurationInputs({ report, summary }: { report?: PreflightReport; summary?: PreflightSummary }) {
  const { t } = useLanguage();
  const live = report?.effective_config;
  const saved = summary?.executionConfig;
  const center = live?.grid_center ?? saved?.gridCenter;
  const size = live?.grid_size ?? saved?.gridSize;
  const chains = [...new Set(report?.receptor.site_chains ?? [])].filter(Boolean).sort();
  const receptor = report
    ? chains.length > 1 ? t("ca_receptor_label_multiple", { pdbId: report.receptor.pdb_id, chains: chains.join("+") })
      : report.receptor.chain ? t("ca_receptor_label_single", { pdbId: report.receptor.pdb_id, chain: report.receptor.chain }) : report.receptor.pdb_id
    : localizeReceptorLabel(summary?.receptorLabel ?? t("c_no_definido"), t);
  const ligand = report ? report.ligand.canonical_smiles ?? report.ligand.input_smiles : summary?.ligandLabel;
  const config = live ? {
    engine: live.docking_engine, exhaustiveness: live.exhaustiveness, poses: live.num_poses, seed: live.seed,
    conformers: live.conformers, references: live.hotspots,
  } : saved ? {
    engine: saved.dockingEngine, exhaustiveness: saved.exhaustiveness, poses: saved.numPoses, seed: saved.seed,
    conformers: saved.conformers, references: saved.customHotspots,
  } : null;
  const value = (number: unknown) => typeof number === "number" && Number.isFinite(number) ? String(number) : t("c_no_definido");
  return <dl className={styles.inputFacts} data-configuration-inputs>
    <div><dt>{t("pr_preflight_receptor")}</dt><dd>{receptor}</dd></div>
    <div><dt>{t("pr_preflight_ligand")}</dt><dd><code className={styles.smiles}>{ligand || t("c_no_definido")}</code>
      {report && report.ligand.canonical_smiles == null && <p className={styles.fieldNote}>{t("cf_input_smiles")}</p>}
    </dd></div>
    <div><dt>{t("pr_preflight_effective_box")}</dt><dd>
      {center && size ? <><table className={styles.axisTable} aria-label={t("pr_preflight_effective_box")}>
        <thead><tr><th scope="col">{t("cf_box_measure")}</th>{["X", "Y", "Z"].map(axis => <th scope="col" key={axis}>{axis}</th>)}</tr></thead>
        <tbody>
          <tr><th scope="row">{t("cf_center_angstrom")}</th>{center.map((number, i) => <td key={i}>{value(number)}</td>)}</tr>
          <tr><th scope="row">{t("cf_size_angstrom")}</th>{size.map((number, i) => <td key={i}>{value(number)}</td>)}</tr>
        </tbody>
      </table>{summary?.gridLabel && <p className={styles.fieldNote}>{t("cf_saved_box_description", { label: summary.gridLabel })}</p>}</> : <><p>{summary?.gridLabel ?? t("c_no_definido")}</p><p className={styles.fieldNote}>{t("cf_legacy_box")}</p></>}
    </dd></div>
    <div><dt>{t("se_gen_protocol")}</dt><dd>
      {config ? <dl className={styles.protocolFacts} data-has-conformers={config.conformers !== undefined}>
        <div><dt>{t("cf_engine")}</dt><dd>{config.engine}</dd></div>
        <div><dt>{t("cf_requested_poses")}</dt><dd>{value(config.poses)}</dd></div>
        <div><dt>{t("c_exhaustividad")}</dt><dd>{value(config.exhaustiveness)}</dd></div>
        <div><dt>{t("cf_seed")}</dt><dd>{value(config.seed)}</dd></div>
        {config.conformers !== undefined && <div><dt>{t("cf_initial_conformers")}</dt><dd>{value(config.conformers)}</dd></div>}
      </dl> : <p className={styles.fieldNote}>{t("cf_missing_protocol")}</p>}
    </dd></div>
    {config && <div><dt>{t("cf_reference_residues")}</dt><dd>{config.references.length
      ? <code className={styles.references}>{config.references.join(", ")}</code> : t("cf_no_references")}</dd></div>}
  </dl>;
}
