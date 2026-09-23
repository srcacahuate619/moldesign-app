"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import Image from "next/image";
import { motion } from "framer-motion";
import { BookOpen, Github } from "lucide-react";
import { PipelineFlowchart } from "@/components/PipelineFlowchart";
import { ContrasteInicio } from "@/components/registro/ContrasteInicio";
import { getGlobalStats } from "@/lib/api";
import { getLeaderboard } from "@/lib/proApi";
import { useLanguage, Translated } from "@/context/LanguageContext";
import { PRODUCT } from "@/lib/softwareCatalog";

import { ExternalLink } from "@/components/ui/ExternalLink";
const TechNetwork3D = dynamic(() => import("@/components/TechNetwork3D").then((m) => m.TechNetwork3D), {
  ssr: false,
  loading: () => <div className="w-full h-[500px] flex items-center justify-center text-muted font-mono text-xs uppercase tracking-widest animate-pulse"><Translated id="pg_inicio_iniciando_red_3d" /></div>,
});

// La ausencia del backend no es una medición de cero.
const EMPTY_STATS = {
  total_molecules: null as number | null,
  best_affinity: null as number | null,
  total_certifications: null as number | null,
};

// ─── Animation Constants ──────────────────────────────────────
const ease = [0.16, 1, 0.3, 1] as const;

function AnimatedLine({ text, delay = 0 }: { text: string; delay?: number }) {
  return (
    <span className="block overflow-hidden py-2 -my-2">
      <motion.span
        initial={{ y: "100%", opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.7, delay, ease }}
        className="block"
      >
        {text}
      </motion.span>
    </span>
  );
}

// ═══════════════════════════════════════════════════════════════
//  HERO SPLIT — Desktop-first, symmetrical, large type
// ═══════════════════════════════════════════════════════════════

function HeroSplit({ stats }: { stats: typeof EMPTY_STATS }) {
  const { t, locale } = useLanguage();

  const EDU_STEPS = [
    {
      step: "01",
      title: t("step_01_title"),
      desc: t("step_01_desc"),
    },
    {
      step: "02",
      title: t("step_02_title"),
      desc: t("step_02_desc"),
    },
    {
      step: "03",
      title: t("step_03_title"),
      desc: t("step_03_desc"),
    },
    // Ejecución local y límites científicos NO son letra pequeña: son parte de
    // lo que el producto es. Si viven en una nota al pie, nadie los lee.
    {
      step: "04",
      title: t("step_04_title"),
      desc: t("step_04_desc"),
    },
    {
      step: "05",
      title: t("step_05_title"),
      desc: t("step_05_desc"),
    },
  ];

  const rightDesc = () => {
    // El registro en cadena NO encabeza esta descripción. Sella la integridad de
    // un dossier —dice CUÁNDO se emitió algo—, y ponerlo primero sugeriría que
    // la propiedad intelectual es la función del producto en vez de la evidencia.
    const dict: Record<string, string> = {
      es: "Comprobación previa antes de ejecutar, docking local con AutoDock Vina, cohortes comparables bajo una configuración común, y dossier con paquete verificable. El registro de integridad en cadena es opcional y sella cuándo se emitió un dossier; no valida su ciencia.",
      en: "Preflight before running, local AutoDock Vina docking, comparable cohorts under a common configuration, and a dossier with a verifiable package. On-chain integrity registration is optional and seals when a dossier was issued; it does not validate its science.",
      pt: "Verificação prévia, docking local com AutoDock Vina, coortes comparáveis e dossiê com pacote verificável. O registro opcional em cadeia prova integridade e data, não valida a ciência.",
      fr: "Vérification préalable, docking local avec AutoDock Vina, cohortes comparables et dossier avec paquet vérifiable. L'enregistrement optionnel prouve l'intégrité et la date, pas la science.",
      de: "Vorabprüfung, lokales Docking mit AutoDock Vina, vergleichbare Kohorten und ein überprüfbares Dossier. Die optionale Blockchain-Aufzeichnung belegt Integrität und Zeitpunkt, nicht die Wissenschaft.",
      it: "Controllo preliminare, docking locale con AutoDock Vina, coorti comparabili e dossier con pacchetto verificabile. La registrazione opzionale prova integrità e data, non la validità scientifica.",
      zh: "运行前检查、本地 AutoDock Vina 对接、可比较的队列，以及包含可验证数据包的档案。可选的链上记录用于证明完整性和时间，不证明科学结论。",
      ja: "実行前チェック、ローカル AutoDock Vina ドッキング、比較可能なコホート、検証可能なパッケージを含むドシエ。任意のオンチェーン記録は完全性と発行時刻を示しますが、科学的妥当性は証明しません。",
      ko: "실행 전 점검, 로컬 AutoDock Vina 도킹, 비교 가능한 코호트와 검증 가능한 패키지를 포함한 도시에. 선택적 온체인 기록은 무결성과 발행 시점을 증명하지만 과학적 타당성을 증명하지 않습니다.",
      ru: "Предварительная проверка, локальный докинг AutoDock Vina, сопоставимые когорты и проверяемое досье. Необязательная запись в блокчейне подтверждает целостность и дату, но не научную обоснованность.",
      hi: "पूर्व-जांच, स्थानीय AutoDock Vina डॉकिंग, तुलनीय समूह और सत्यापन योग्य पैकेज वाला डॉसियर। वैकल्पिक ऑन-चेन रिकॉर्ड अखंडता और समय दिखाता है, वैज्ञानिक निष्कर्ष की पुष्टि नहीं करता।",
      ar: "فحص مسبق، وإرساء محلي باستخدام AutoDock Vina، ومجموعات قابلة للمقارنة، وملف أدلة قابل للتحقق. يسجل السجل الاختياري على السلسلة السلامة والتاريخ، ولا يثبت صحة العلم.",
      tr: "Çalıştırma öncesi kontrol, yerel AutoDock Vina docking'i, karşılaştırılabilir kohortlar ve doğrulanabilir paket içeren dosya. İsteğe bağlı zincir kaydı bütünlük ve tarihi gösterir; bilimi doğrulamaz.",
    };
    return dict[locale] || dict.es;
  };

  const getStartBtn = () => {
    const dict: Record<string, string> = {
      es: "Iniciar Evaluación",
      en: "Start Evaluation",
      pt: "Iniciar Avaliação",
      fr: "Démarrer l'Évaluation",
      de: "Bewertung starten",
      it: "Inizia Valutazione",
      zh: "开始分子评估",
      ja: "評価を開始する",
      ko: "평가 시작하기",
      ru: "Начать анализ",
      hi: "मूल्यांकन शुरू करें",
      ar: "بدء التقييم",
      tr: "Değerlendirmeyi Başlat",
    };
    return dict[locale] || dict.es;
  };

  return (
    <section className="min-h-screen grid grid-cols-1 lg:grid-cols-12 pt-48 pb-16 px-8 lg:px-16 gap-0">
      <div className="lg:col-span-5 flex flex-col pr-0 lg:pr-12 border-r-0 lg:border-r border-theme">
        <div className="max-w-2xl ml-auto">
          <motion.div
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5, ease }}
          >
            <span className="font-mono text-sm uppercase tracking-[0.3em] text-muted">
              {t("hero_tagline")}
            </span>
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tighter leading-[0.9] text-theme mt-6 uppercase">
              <AnimatedLine text={t("hero_title_1")} delay={0} />
              <AnimatedLine text={t("hero_title_2")} delay={0.06} />
              <AnimatedLine text={t("hero_title_3")} delay={0.12} />
            </h1>
          </motion.div>

          <motion.p
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2, ease }}
            className="text-base text-muted leading-relaxed mt-8 uppercase tracking-wide"
          >
            {t("hero_desc")}
          </motion.p>

          <motion.div
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.28, ease }}
            className="mt-10 space-y-5"
          >
            {EDU_STEPS.map((s) => (
              <div key={s.step} className="flex items-start gap-4">
                <div className="flex-1">
                  <span className="text-lg font-bold text-theme uppercase tracking-wide">{s.title}</span>
                  <p className="text-sm text-muted uppercase tracking-wide mt-1 leading-relaxed">{s.desc}</p>
                </div>
                <span className="text-sm text-dim font-mono uppercase tracking-wider mt-1 shrink-0">{s.step}.</span>
              </div>
            ))}
          </motion.div>

          <motion.div
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.35, ease }}
            className="mt-12 flex flex-wrap items-center gap-3"
          >
            <Link
              href="/evaluation"
              className="inline-flex items-center gap-3 px-10 py-5 font-bold uppercase tracking-widest text-sm transition-colors"
              style={{ backgroundColor: "var(--text)", color: "var(--bg)" }}
            >
              {getStartBtn()}
              <BookOpen size={18} strokeWidth={1.5} />
            </Link>
            <ExternalLink
              href={PRODUCT.sourceUrl}
              className="inline-flex items-center gap-3 border border-theme px-6 py-5 font-mono text-xs font-bold uppercase tracking-widest text-muted transition-colors hover:text-main"
            >
              GitHub
              <Github size={18} strokeWidth={1.5} />
            </ExternalLink>
          </motion.div>
        </div>
      </div>

      <div className="lg:col-span-2 flex flex-col items-center justify-center">
        <div className="w-px h-24 border-theme" style={{ borderLeftWidth: 1, borderLeftStyle: "solid", borderColor: "var(--border-light)" }} />
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ duration: 0.5, delay: 0.15, ease }}
        >
          <Link
            href="/"
            aria-label={t("auto_69b7a67b0314")}
            className="block w-20 h-20 rounded-full border-2 flex items-center justify-center transition-colors group"
            style={{ borderColor: "var(--border-light)" }}
          >
            <Image
              src="/logo.png"
              alt="MolDesign"
              width={32}
              height={32}
              className="object-contain opacity-60 group-hover:opacity-100 transition-opacity"
              unoptimized
            />
          </Link>
        </motion.div>
        <div className="w-px h-24" style={{ borderLeftWidth: 1, borderLeftStyle: "solid", borderColor: "var(--border-light)" }} />
      </div>

      <div className="lg:col-span-5 flex flex-col pl-0 lg:pl-12 border-l-0 lg:border-l border-theme">
        <div className="max-w-2xl">
          <motion.div
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5, ease }}
          >
            <span className="font-mono text-sm uppercase tracking-[0.3em] text-muted">
              {t("evidence_tagline")}
            </span>
            <h1 className="text-5xl sm:text-6xl lg:text-7xl font-black tracking-tighter leading-[0.9] text-theme mt-6 uppercase">
              <AnimatedLine text={t("evidence_title_1")} delay={0} />
              <AnimatedLine text={t("evidence_title_2")} delay={0.06} />
              <AnimatedLine text={t("evidence_title_3")} delay={0.12} />
            </h1>
          </motion.div>

          <motion.p
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.2, ease }}
            className="text-base text-muted leading-relaxed mt-8 uppercase tracking-wide"
          >
            {rightDesc()}
          </motion.p>

          <motion.div
            initial={{ y: 32, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ duration: 0.5, delay: 0.28, ease }}
            className="mt-10 grid grid-cols-2 gap-8"
          >
            <div>
              <span className="font-mono text-xs uppercase tracking-wider text-muted">{t("stats_molecules")}</span>
              <p className="text-4xl lg:text-5xl font-black text-accent font-mono mt-2">{stats.total_molecules?.toLocaleString() ?? "—"}</p>
            </div>
            <div>
              <span className="font-mono text-xs uppercase tracking-wider text-muted">{t("stats_best_score")}</span>
              <p className="text-4xl lg:text-5xl font-black text-theme font-mono mt-2">
                {stats.best_affinity?.toFixed(2) ?? "—"}{" "}
                {stats.best_affinity != null && <span className="text-base text-muted">kcal/mol</span>}
              </p>
            </div>
            <div>
              <span className="font-mono text-xs uppercase tracking-wider text-muted">{t("stats_certified")}</span>
              <p className="text-4xl lg:text-5xl font-black text-accent font-mono mt-2">{stats.total_certifications?.toLocaleString() ?? "—"}</p>
            </div>
            <div>
              <span className="font-mono text-xs uppercase tracking-wider text-muted">{t("pg_inicio_pipeline")}</span>
              <p className="text-4xl lg:text-5xl font-black text-theme font-mono mt-2">
                07 <span className="text-base text-muted">{locale === "es" ? "etapas" : "stages"}</span>
              </p>
            </div>
          </motion.div>
        </div>
      </div>
    </section>
  );
}

function FutureVisionSection() {
  const { t } = useLanguage();

  return (
    <section className="border-t border-theme px-8 py-20 lg:px-16">
      <div className="mx-auto grid max-w-6xl gap-6 border-l-2 pl-5 lg:grid-cols-[minmax(0,0.7fr)_minmax(0,1.3fr)]" style={{ borderLeftColor: "var(--accent)" }}>
        <div>
          <span className="font-mono text-sm uppercase tracking-[0.25em] text-muted">
            {t("vision_label")}
          </span>
          <h2 className="mt-3 text-3xl font-black uppercase tracking-tight text-theme lg:text-4xl">
            {t("vision_title")}
          </h2>
        </div>
        <p className="max-w-3xl text-base uppercase leading-relaxed tracking-wide text-muted lg:pt-8">
          {t("vision_desc")}
        </p>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════
//  TECH STACK SECTION
// ═══════════════════════════════════════════════════════════════

function TechStackSection() {
  const { t, locale } = useLanguage();

  const getStackLabel = () => {
    return locale === "es" ? "Stack Tecnológico" : "Technology Stack";
  };
  const getStackTitle = () => {
    return locale === "es" ? "Motores de Cómputo e IA" : "Compute Engines & AI";
  };
  const getStackDesc = () => {
    return locale === "es"
      ? "Las partículas fluyendo entre los nodos representan el flujo del pipeline. Haz clic en un nodo para ver su detalle."
      : "Particles flowing between nodes represent the pipeline flow. Click on a node to view details.";
  };

  return (
    <section className="py-32 border-t border-theme overflow-hidden">
      <div className="max-w-6xl mx-auto px-8 lg:px-16 mb-16">
        <div className="border-l-2 pl-5" style={{ borderLeftColor: "var(--accent)" }}>
          <span className="font-mono text-sm uppercase tracking-[0.25em] text-muted block mb-1">
            {getStackLabel()}
          </span>
          <h2 className="text-3xl lg:text-4xl font-black tracking-tight text-theme uppercase">
            {getStackTitle()}
          </h2>
          <p className="text-base text-muted mt-3 leading-relaxed uppercase max-w-3xl">
            {getStackDesc()}
          </p>
        </div>
      </div>

      <div className="w-full max-w-none">
        <TechNetwork3D />
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════
//  LEADERBOARD SECTION
// ═══════════════════════════════════════════════════════════════

function LeaderboardSection() {
  const { t, locale } = useLanguage();
  const [leaders, setLeaders] = useState<any[]>([]);
  const [ldError, setLdError] = useState(false);

  useEffect(() => {
    getLeaderboard()
      .then((data) => setLeaders(Array.isArray(data) ? data.slice(0, 10) : []))
      .catch(() => setLdError(true));
  }, []);

  const getCommLabel = () => locale === "es" ? "Comunidad" : "Community";
  const getLeaderTitle = () => locale === "es" ? "Evaluaciones compartidas" : "Shared evaluations";
  const getEmptyDesc = () => locale === "es"
    ? "La comunidad científica está creciendo. Sé el primero en compartir una evaluación."
    : "The scientific community is growing. Be the first to share an evaluation.";
  const getLeaderDesc = () => locale === "es"
    ? "Evaluaciones compartidas por la comunidad. El orden es por afinidad observada; no es un ranking de candidatos."
    : "Evaluations shared by the community, ordered by observed docking affinity. This is not a candidate ranking.";
  const getMolCol = () => locale === "es" ? t("mx_molecula") : t("mx_molecula");

  if (ldError) return null;

  if (leaders.length === 0) {
    return (
      <section className="py-32 border-t border-theme overflow-hidden">
        <div className="max-w-6xl mx-auto px-8 lg:px-16">
          <div className="border-l-2 pl-5" style={{ borderLeftColor: "var(--accent)" }}>
            <span className="font-mono text-sm uppercase tracking-[0.25em] text-muted block mb-1">{getCommLabel()}</span>
            <h2 className="text-3xl lg:text-4xl font-black tracking-tight text-theme uppercase">{getLeaderTitle()}</h2>
          </div>
          <p className="font-mono text-sm text-muted uppercase tracking-wide mt-10 text-center">
            {getEmptyDesc()}
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="py-32 border-t border-theme overflow-hidden">
      <div className="max-w-6xl mx-auto px-8 lg:px-16 mb-16">
        <div className="border-l-2 pl-5" style={{ borderLeftColor: "var(--accent)" }}>
          <span className="font-mono text-sm uppercase tracking-[0.25em] text-muted block mb-1">
            {getCommLabel()}
          </span>
          <h2 className="text-3xl lg:text-4xl font-black tracking-tight text-theme uppercase">
            {getLeaderTitle()}
          </h2>
          <p className="text-base text-muted mt-3 leading-relaxed uppercase max-w-3xl">
            {getLeaderDesc()}
          </p>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-8 lg:px-16">
        <div className="overflow-hidden border border-theme/20">
          <div className="grid grid-cols-3 gap-4 border-b border-theme bg-[var(--bg-secondary)] px-6 py-3 text-caption font-bold text-muted">
            <span>#</span>
            <span>{getMolCol()}</span>
            <span className="text-right">{t("pg_inicio_afinidad_kcal")}</span>
          </div>
          {leaders.map((l, i) => (
            <div key={l.molecule_id || i} className="grid grid-cols-3 items-center gap-4 border-b border-theme px-6 py-3 font-mono text-xs transition-colors hover:bg-[var(--bg-secondary)]">
              <span className="text-muted">{(i + 1).toString().padStart(2, "0")}</span>
              <span className="truncate text-theme" title={l.smiles || l.target_name}>
                {(l.smiles || l.target_name || "—").slice(0, 36)}
              </span>
              <span className="text-right text-accent font-bold">
                {l.affinity_kcal != null ? l.affinity_kcal.toFixed(1) : "—"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

// ═══════════════════════════════════════════════════════════════
//  PAGE
// ═══════════════════════════════════════════════════════════════

export default function HomePage() {
  const [stats, setStats] = useState(EMPTY_STATS);
  const { t } = useLanguage();

  useEffect(() => {
    getGlobalStats()
      .then((realStats) => {
        setStats({
          total_molecules: realStats.total_molecules ?? null,
          best_affinity: realStats.best_affinity ?? realStats.best_score ?? null,
          total_certifications: realStats.total_certifications ?? null,
        });
      })
      .catch(() => {
        // La UI conserva la ausencia; no la convierte en una medición de cero.
      });
  }, []);

  return (
    <div className="min-h-screen font-mono" style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}>
      <HeroSplit stats={stats} />
      <FutureVisionSection />
      <PipelineFlowchart />
      <TechStackSection />
      <ContrasteInicio />
      <LeaderboardSection />

      <footer className="px-8 lg:px-16 py-12 border-t border-theme flex flex-col md:flex-row justify-between items-center gap-6 font-mono text-xs uppercase tracking-widest" style={{ color: "var(--text-dim)" }}>
        <div className="flex flex-col gap-1">
          <span className="text-sm font-bold" style={{ color: "var(--text-muted)" }}>MolDesign</span>
          <span>v{PRODUCT.version} · PolyForm Noncommercial</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse inline-block" />
          {t("legal_local_first")}
        </div>
        <div>{new Date().getFullYear()} {t("auto_2b5f94bbc9a7")}</div>
      </footer>
    </div>
  );
}
