"use client";


import { useLanguage } from "@/context/LanguageContext";
import { useRouter } from "next/navigation";
import { DownloadCard } from "@/components/DownloadCard";
import { useDownload } from "@/hooks/useDownload";
import { PRODUCT } from "@/lib/softwareCatalog";

export function LauncherScreen() {
  const { t } = useLanguage();
  const router = useRouter();
  const { manifest, models, checkModules } = useDownload();

  const allReady = manifest.every((module) => models[module.id] === "ready");
  const requiredReady = manifest.filter((module) => module.required).every((module) => models[module.id] === "ready");
  const downloading = manifest.filter((module) => models[module.id] === "downloading" || models[module.id] === "extracting").length;

  return (
    <main className="min-h-dvh bg-[var(--bg)] px-4 py-10 text-[var(--text)] sm:px-6">
      <div className="mx-auto w-full max-w-2xl">
        <header className="mb-10 border-b border-[var(--border)] pb-7">
          <p className="mb-2 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--accent)]">
            {t("pg_lanzador_componentes_locales")}
          </p>
          <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{t("pg_lanzador_modelos_motores")}</h1>
          <p className="mt-3 max-w-xl text-sm font-medium leading-6 text-[var(--text-secondary)]">
            {t("auto_7194e52d2e3f")}
            {downloading > 0 && t(downloading === 1 ? "pg_lanzador_descarga_una" : "pg_lanzador_descargas_varias", { n: downloading })}
          </p>
        </header>

        <section aria-label={t("pg_lanzador_componentes_disponibles")} className="space-y-4">
          {manifest.map((entry) => <DownloadCard key={entry.id} entry={entry} />)}
        </section>

        <div className="mt-6 grid gap-3 sm:grid-cols-[1fr_auto]">
          <button
            type="button"
            disabled={!requiredReady}
            onClick={() => router.push("/")}
            className="min-h-12 whitespace-nowrap border border-[var(--accent)] bg-[var(--accent)] px-5 text-sm font-bold text-white transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)] disabled:cursor-not-allowed disabled:border-[var(--border)] disabled:bg-[var(--bg-alt)] disabled:text-[var(--text-dim)]"
          >
            {requiredReady ? (allReady ? t("pg_lanzador_abrir") : t("auto_1f88e3bba8e6")) : (downloading > 0 ? t("auto_8497fd8cc5e0") : t("pg_lanzador_instalar_requerido"))}
          </button>
          <button
            type="button"
            onClick={checkModules}
            className="min-h-12 whitespace-nowrap border border-[var(--border)] bg-transparent px-5 text-sm font-semibold text-[var(--text-secondary)] hover:bg-[var(--bg-alt)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent-strong)]"
          >
            {t("pn_verificar_instalacion")}
          </button>
        </div>

        <footer className="mt-10 border-t border-[var(--border)] pt-5 text-xs leading-5 text-[var(--text-dim)]">
          {t("pn_descargas_huggingface")}
          <span className="mt-2 block">{PRODUCT.name} v{PRODUCT.version}</span>
        </footer>
      </div>
    </main>
  );
}