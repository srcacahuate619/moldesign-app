"use client";


import { useLanguage } from "@/context/LanguageContext";
/**
 * Registro cientifico — vista de contraste.
 *
 * Dos columnas protagonistas: lo que se sostuvo y lo que se cayo. Las otras cuatro
 * poblaciones (mediciones, prerregistros, corrigenda, inconclusos) son capas de
 * contexto que se activan aparte, porque mezclarlas en el numerador convertiria la
 * cifra en marketing. Es la misma advertencia que el propio programa se hace en la
 * seccion 19.3 del doc. 49.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import { BloquesPaper } from "./BloquesPaper";
import {
  cargarIndice,
  cargarPaper,
  duracionLegible,
  fechaLegible,
  ESTILO_CATEGORIA,
  ORDEN_CATEGORIAS,
  type Categoria,
  type Experimento,
  type IndiceRegistro,
  type Paper,
} from "@/lib/registro";

// ─────────────────────────────────────────────────────────────── piezas chicas

function Insignia({ cat }: { cat: Categoria }) {
  const e = ESTILO_CATEGORIA[cat];
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        fontSize: 12,
        fontWeight: 700,
        letterSpacing: "0.08em",
        textTransform: "uppercase",
        color: e.color,
        background: e.fondo,
        border: `1px solid ${e.color}44`,
        borderRadius: 3,
        whiteSpace: "nowrap",
      }}
    >
      {e.nombre}
    </span>
  );
}

function Tarjeta({ e, onClick }: { e: Experimento; onClick: () => void }) {
  const est = ESTILO_CATEGORIA[e.categoria];
  return (
    <button
      onClick={onClick}
      className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]"
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        padding: "14px 16px",
        marginBottom: 8,
        background: "var(--bg-card)",
        border: "1px solid var(--border)",
        borderLeft: `3px solid ${est.color}`,
        borderRadius: 4,
        cursor: "pointer",
        color: "inherit",
        transition: "border-color 0.15s, transform 0.15s",
      }}
      onMouseEnter={(ev) => {
        ev.currentTarget.style.borderColor = est.color;
        ev.currentTarget.style.borderLeftColor = est.color;
        ev.currentTarget.style.transform = "translateX(2px)";
      }}
      onMouseLeave={(ev) => {
        ev.currentTarget.style.borderColor = "var(--border)";
        ev.currentTarget.style.borderLeftColor = est.color;
        ev.currentTarget.style.transform = "translateX(0)";
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 5 }}>
        <span
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            fontWeight: 700,
            color: est.color,
          }}
        >
          {e.id}
        </span>
        {e.tiene_paper && (
          <span
            style={{
              fontSize: 12,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "var(--text-dim)",
              border: "1px solid var(--border-light)",
              padding: "1px 5px",
              borderRadius: 2,
            }}
          >
            paper
          </span>
        )}
        {e.etiquetas.includes("corrigendum") && (
          <span style={{ fontSize: 12, letterSpacing: "0.1em", color: "#fbbf24" }}>
            CORRIGENDUM
          </span>
        )}
        {e.reemplazado_por && (
          <span
            style={{
              fontSize: 12,
              letterSpacing: "0.1em",
              textTransform: "uppercase",
              color: "#fbbf24",
              border: "1px solid #fbbf2455",
              padding: "1px 5px",
              borderRadius: 2,
            }}
          >
            cifras reemplazadas
          </span>
        )}
      </div>
      <div
        style={{
          fontSize: 13.5,
          lineHeight: 1.5,
          color: "var(--text)",
          display: "-webkit-box",
          WebkitLineClamp: 3,
          WebkitBoxOrient: "vertical",
          overflow: "hidden",
        }}
      >
        {e.entradilla || e.hipotesis || e.gate}
      </div>
      <div
        style={{
          marginTop: 8,
          fontSize: 12,
          fontFamily: "var(--font-mono)",
          color: "var(--text-dim)",
          display: "flex",
          gap: 12,
          flexWrap: "wrap",
        }}
      >
        {e.n_complejos > 0 && <span>n={e.n_complejos}</span>}
        {duracionLegible(e.duracion_s) && <span>{duracionLegible(e.duracion_s)}</span>}
        {e.n_hashes > 0 && <span>{e.n_hashes} hashes</span>}
        {fechaLegible(e.sellado_en) && <span>{fechaLegible(e.sellado_en)}</span>}
      </div>
    </button>
  );
}

function Dato({ k, v }: { k: string; v: React.ReactNode }) {
  if (v == null || v === "") return null;
  return (
    <div style={{ display: "flex", gap: 10, padding: "5px 0", fontSize: 12.5 }}>
      <span
        style={{
          minWidth: 130,
          color: "var(--text-dim)",
          fontFamily: "var(--font-mono)",
          fontSize: 12,
          textTransform: "uppercase",
          letterSpacing: "0.05em",
        }}
      >
        {k}
      </span>
      <span style={{ color: "var(--text-secondary)", wordBreak: "break-word" }}>{v}</span>
    </div>
  );
}

function Seccion({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 32 }}>
      <h3
        style={{
          fontSize: 12,
          fontWeight: 700,
          letterSpacing: "0.14em",
          textTransform: "uppercase",
          color: "var(--text-dim)",
          marginBottom: 12,
          paddingBottom: 8,
          borderBottom: "1px solid var(--border)",
        }}
      >
        {titulo}
      </h3>
      {children}
    </section>
  );
}

// ──────────────────────────────────────────────────────────────────── detalle

function VistaExperimento({
  e,
  volver,
  abrir,
}: {
  e: Experimento;
  volver: () => void;
  abrir: (id: string) => void;
}) {
  const { t } = useLanguage();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [cargando, setCargando] = useState(e.tiene_paper);

  useEffect(() => {
    let vivo = true;
    if (!e.tiene_paper) {
      setPaper(null);
      setCargando(false);
      return;
    }
    setCargando(true);
    cargarPaper(e.id)
      .then((p) => vivo && setPaper(p))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, [e.id, e.tiene_paper]);

  const est = ESTILO_CATEGORIA[e.categoria];

  return (
    <div style={{ maxWidth: 780, margin: "0 auto", padding: "0 24px 96px" }}>
      <button
        onClick={volver}
        className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]"
        style={{
          background: "none",
          border: "none",
          color: "var(--text-dim)",
          fontSize: 12,
          fontFamily: "var(--font-mono)",
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          cursor: "pointer",
          padding: "24px 0",
        }}
      >
        {t("auto_14fb488bd307")}
      </button>

      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 14 }}>
        <Insignia cat={e.categoria} />
        {e.decision && (
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              fontWeight: 700,
              letterSpacing: "0.1em",
              color: e.decision === "NO_GO" ? "#f87171" : "var(--text-muted)",
            }}
          >
            {e.decision}
          </span>
        )}
        {e.etiquetas.map((t) => (
          <span
            key={t}
            style={{
              fontSize: 12,
              letterSpacing: "0.08em",
              textTransform: "uppercase",
              color: "var(--text-dim)",
              border: "1px solid var(--border)",
              padding: "1px 6px",
              borderRadius: 2,
            }}
          >
            {t}
          </span>
        ))}
      </div>

      <div
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: 13,
          color: est.color,
          marginBottom: 6,
          fontWeight: 700,
        }}
      >
        {e.id}
      </div>
      <h1
        style={{
          fontSize: 32,
          lineHeight: 1.2,
          fontWeight: 800,
          letterSpacing: "-0.02em",
          color: "var(--text)",
          marginBottom: 28,
          fontFamily: "var(--font-display)",
        }}
      >
        {e.titulo}
      </h1>

      {e.reemplazado_por && (
        <div
          role="note"
          style={{
            padding: "14px 18px",
            marginBottom: 28,
            background: "rgba(251, 191, 36, 0.08)",
            border: "1px solid rgba(251, 191, 36, 0.35)",
            borderRadius: 4,
            fontSize: 13.5,
            lineHeight: 1.6,
            color: "var(--text-secondary)",
          }}
        >
          <strong style={{ color: "#fbbf24" }}>Cifras reemplazadas.</strong> {t("pr_reg_defecto_detectado")} <em>{t("pr_reg_despues")}</em> {t("auto_c1b398a5da7e")}{" "}
          <button
            type="button"
            onClick={() => abrir(e.reemplazado_por as string)}
            className="font-mono"
            style={{
              background: "none",
              border: "none",
              padding: 0,
              color: "#fbbf24",
              fontSize: 13,
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            {e.reemplazado_por}
          </button>{" "}
          {t("auto_db0393069f56")}
        </div>
      )}

      {cargando && (
        <p style={{ color: "var(--text-dim)", fontSize: 13 }}>{t("pr_reg_cargando_paper")}</p>
      )}

      {paper && (
        <div style={{ marginBottom: 44 }}>
          <BloquesPaper bloques={paper.bloques} />
        </div>
      )}

      {!cargando && !paper && (
        <div
          style={{
            padding: "14px 18px",
            marginBottom: 40,
            background: "var(--bg-secondary)",
            border: "1px dashed var(--border-light)",
            borderRadius: 4,
            fontSize: 13,
            color: "var(--text-muted)",
          }}
        >
          {t("pr_reg_sin_paper")}
        </div>
      )}

      <Seccion titulo={t("auto_a2b452f155f4")}>
        <div style={{ fontSize: 14, lineHeight: 1.7, color: "var(--text-secondary)" }}>
          {e.hipotesis && (
            <p style={{ marginBottom: 16 }}>
              <strong style={{ color: "var(--text)" }}>{t("pr_reg_hipotesis")} </strong>
              {e.hipotesis}
            </p>
          )}
          {e.gate && (
            <p style={{ marginBottom: 16 }}>
              <strong style={{ color: "var(--text)" }}>Gate preregistrado. </strong>
              {e.gate}
            </p>
          )}
          {e.protocolo && (
            <p style={{ marginBottom: 16 }}>
              <strong style={{ color: "var(--text)" }}>Protocolo. </strong>
              {e.protocolo}
            </p>
          )}
          {e.razonamiento && (
            <div
              style={{
                marginTop: 20,
                padding: "16px 20px",
                background: est.fondo,
                borderLeft: `3px solid ${est.color}`,
                borderRadius: 3,
              }}
            >
              <div
                style={{
                  fontSize: 12,
                  letterSpacing: "0.12em",
                  textTransform: "uppercase",
                  color: est.color,
                  fontWeight: 700,
                  marginBottom: 8,
                }}
              >
                {t("pr_reg_razon_decision")}
              </div>
              <div style={{ fontSize: 14, lineHeight: 1.7 }}>{e.razonamiento}</div>
            </div>
          )}
        </div>
      </Seccion>

      {e.metricas && Object.keys(e.metricas).length > 0 && (
        <Seccion titulo="Métricas registradas">
          {Object.entries(e.metricas).map(([k, v]) => (
            <Dato key={k} k={k} v={String(v)} />
          ))}
        </Seccion>
      )}

      <Seccion titulo="Reproducibilidad">
        <Dato k="commit" v={e.git.commit ? `${e.git.commit}${e.git.sucio ? " (dirty)" : ""}` : null} />
        <Dato k="rama" v={e.git.rama} />
        <Dato k="semilla" v={e.semillas != null ? String(e.semillas) : null} />
        <Dato k="sellado" v={fechaLegible(e.sellado_en)} />
        <Dato k="duración" v={duracionLegible(e.duracion_s)} />
        <Dato k="complejos" v={e.n_complejos > 0 ? String(e.n_complejos) : null} />
        <Dato k="fallos" v={e.n_fallos > 0 ? String(e.n_fallos) : null} />
        <Dato k="hashes sha-256" v={e.n_hashes > 0 ? String(e.n_hashes) : null} />
        <Dato
          k="entorno"
          v={[
            e.entorno.os,
            e.entorno.cpu ? `${e.entorno.cpu} núcleos` : null,
            e.entorno.ram_mb ? `${Math.round(e.entorno.ram_mb / 1024)} GB` : null,
            e.entorno.gpu && e.entorno.gpu !== "unknown" ? e.entorno.gpu : null,
          ]
            .filter(Boolean)
            .join(" · ")}
        />
        {e.mantenimiento_sello > 0 && (
          <Dato
            k="mantenimiento"
            v={`${e.mantenimiento_sello} entrada(s) de deriva de assets documentada(s)`}
          />
        )}
      </Seccion>
    </div>
  );
}

// ────────────────────────────────────────────────────────────────── contraste

export function RegistroCientifico() {
  const { t } = useLanguage();
  const [idx, setIdx] = useState<IndiceRegistro | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [abierto, setAbierto] = useState<string | null>(null);
  const [capas, setCapas] = useState<Categoria[]>([]);

  useEffect(() => {
    cargarIndice()
      .then(setIdx)
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  // el id abierto vive en la URL para que el enlace se pueda compartir
  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("exp");
    if (p) setAbierto(p);
  }, []);

  const abrir = useCallback((id: string | null) => {
    setAbierto(id);
    const u = new URL(window.location.href);
    if (id) u.searchParams.set("exp", id);
    else u.searchParams.delete("exp");
    window.history.replaceState(null, "", u.toString());
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, []);

  const porCat = useMemo(() => {
    const m: Partial<Record<Categoria, Experimento[]>> = {};
    for (const e of idx?.experimentos ?? []) {
      (m[e.categoria] ||= []).push(e);
    }
    return m;
  }, [idx]);

  if (error)
    return (
      <div style={{ padding: 80, textAlign: "center", color: "var(--text-muted)" }}>
        <p>{t("pr_reg_no_cargado")}</p>
        <p style={{ fontSize: 12, fontFamily: "var(--font-mono)", marginTop: 8 }}>{error}</p>
        <p style={{ fontSize: 12, marginTop: 16 }}>
          {t("auto_e1592998873b")}{" "}
          <code>python scripts/build_registro_cientifico.py</code>
        </p>
      </div>
    );

  if (!idx)
    return (
      <div style={{ padding: 80, textAlign: "center", color: "var(--text-dim)", fontSize: 13 }}>
        {t("pr_reg_cargando")}
      </div>
    );

  const activo = abierto ? idx.experimentos.find((e) => e.id === abierto) : null;
  if (activo)
    return <VistaExperimento e={activo} volver={() => abrir(null)} abrir={abrir} />;

  const hallazgos = porCat.hallazgo ?? [];
  const refutaciones = porCat.refutacion ?? [];
  const contexto = ORDEN_CATEGORIAS.filter(
    (c) => c !== "hallazgo" && c !== "refutacion"
  );

  return (
    <div style={{ maxWidth: 1180, margin: "0 auto", padding: "0 24px 96px" }}>
      {/* encabezado */}
      <header style={{ padding: "72px 0 44px" }}>
        <div
          style={{
            fontFamily: "var(--font-mono)",
            fontSize: 12,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "var(--text-dim)",
            marginBottom: 16,
          }}
        >
          {t("auto_b76b2b4f5246")} {idx.total} artefactos sellados
        </div>
        <h1
          style={{
            fontSize: "clamp(34px, 5vw, 56px)",
            lineHeight: 1.05,
            fontWeight: 800,
            letterSpacing: "-0.03em",
            color: "var(--text)",
            marginBottom: 22,
            fontFamily: "var(--font-display)",
            maxWidth: 900,
          }}
        >
          {t("pr_reg_lo_que_se_sostuvo")}
        </h1>
        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "var(--text-secondary)",
            maxWidth: 720,
            marginBottom: 20,
          }}
        >
          {t("pr_reg_preregistro")}
        </p>
        <div
          style={{
            padding: "12px 16px",
            border: "1px solid var(--border)",
            borderLeft: "3px solid var(--accent)",
            background: "var(--bg-secondary)",
            fontSize: 13,
            lineHeight: 1.65,
            color: "var(--text-muted)",
            maxWidth: 720,
            borderRadius: 3,
          }}
        >
          {idx.advertencia}
        </div>
      </header>

      {/* marcador */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr auto 1fr",
          alignItems: "center",
          gap: 20,
          padding: "26px 0",
          borderTop: "1px solid var(--border)",
          borderBottom: "1px solid var(--border)",
          marginBottom: 40,
        }}
      >
        <div style={{ textAlign: "right" }}>
          <div
            style={{
              fontSize: 52,
              fontWeight: 800,
              lineHeight: 1,
              color: ESTILO_CATEGORIA.hallazgo.color,
              fontFamily: "var(--font-display)",
            }}
          >
            {hallazgos.length}
          </div>
          <div
            style={{
              fontSize: 12,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--text-dim)",
              marginTop: 6,
            }}
          >
            gates superados
          </div>
        </div>
        <div style={{ color: "var(--text-dim)", fontSize: 13, fontFamily: "var(--font-mono)" }}>
          vs
        </div>
        <div>
          <div
            style={{
              fontSize: 52,
              fontWeight: 800,
              lineHeight: 1,
              color: ESTILO_CATEGORIA.refutacion.color,
              fontFamily: "var(--font-display)",
            }}
          >
            {refutaciones.length}
          </div>
          <div
            style={{
              fontSize: 12,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: "var(--text-dim)",
              marginTop: 6,
            }}
          >
            {t("pr_reg_hipotesis_derribadas")}
          </div>
        </div>
      </div>

      {/* dos columnas */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
          gap: 32,
          marginBottom: 56,
        }}
      >
        <Columna
          titulo="Hallazgos"
          bajada={t("auto_df93272641f2")}
          cat="hallazgo"
          items={hallazgos}
          abrir={abrir}
        />
        <Columna
          titulo="Refutaciones"
          bajada={t("auto_cb3645865abe")}
          cat="refutacion"
          items={refutaciones}
          abrir={abrir}
        />
      </div>

      {/* capas de contexto */}
      <section>
        <h2
          style={{
            fontSize: 13,
            fontWeight: 700,
            letterSpacing: "0.14em",
            textTransform: "uppercase",
            color: "var(--text-dim)",
            marginBottom: 14,
          }}
        >
          {t("pr_reg_otras_poblaciones")}
        </h2>
        <p
          style={{
            fontSize: 14,
            lineHeight: 1.7,
            color: "var(--text-secondary)",
            maxWidth: 720,
            marginBottom: 20,
          }}
        >
          {t("pr_reg_ni_exitos_ni_fracasos")}
        </p>
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 24 }}>
          {contexto.map((c) => {
            const est = ESTILO_CATEGORIA[c];
            const on = capas.includes(c);
            const n = (porCat[c] ?? []).length;
            return (
              <button
                key={c}
                onClick={() =>
                  setCapas((p) => (p.includes(c) ? p.filter((x) => x !== c) : [...p, c]))
                }
                className="focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]"
                style={{
                  padding: "8px 14px",
                  fontSize: 12,
                  fontWeight: 600,
                  cursor: "pointer",
                  borderRadius: 3,
                  color: on ? est.color : "var(--text-muted)",
                  background: on ? est.fondo : "transparent",
                  border: `1px solid ${on ? est.color + "66" : "var(--border)"}`,
                }}
              >
                {est.nombre} <span style={{ opacity: 0.7 }}>{n}</span>
                <span
                  style={{
                    display: "block",
                    fontSize: 12,
                    fontWeight: 400,
                    color: "var(--text-dim)",
                    marginTop: 2,
                  }}
                >
                  {est.corto}
                </span>
              </button>
            );
          })}
        </div>

        {capas.length === 0 && (
          <p style={{ fontSize: 13, color: "var(--text-dim)", fontStyle: "italic" }}>
            {t("pr_reg_activa_capa")}
          </p>
        )}

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))",
            gap: 32,
          }}
        >
          {capas.map((c) => (
            <Columna
              key={c}
              titulo={ESTILO_CATEGORIA[c].nombre}
              bajada={idx.categorias[c] ?? ""}
              cat={c}
              items={porCat[c] ?? []}
              abrir={abrir}
            />
          ))}
        </div>
      </section>

      <footer
        style={{
          marginTop: 72,
          paddingTop: 24,
          borderTop: "1px solid var(--border)",
          fontSize: 12,
          fontFamily: "var(--font-mono)",
          color: "var(--text-dim)",
          lineHeight: 1.8,
        }}
      >
        <div>
          {idx.con_paper} {t("auto_600ccd1b7156")} {idx.total} registros tienen paper redactado.
        </div>
        <div>
          {t("pr_reg_generado_desde")} <code>{idx.generador}</code>
          {fechaLegible(idx.generado_en) ? ` el ${fechaLegible(idx.generado_en)}` : ""}{t("auto_a0c51a5fc4c9")}
        </div>
      </footer>
    </div>
  );
}

function Columna({
  titulo,
  bajada,
  cat,
  items,
  abrir,
}: {
  titulo: string;
  bajada: string;
  cat: Categoria;
  items: Experimento[];
  abrir: (id: string) => void;
}) {
  const est = ESTILO_CATEGORIA[cat];
  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <h2
            style={{
              fontSize: 19,
              fontWeight: 750,
              color: est.color,
              letterSpacing: "-0.01em",
              fontFamily: "var(--font-display)",
            }}
          >
            {titulo}
          </h2>
          <span
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: 12,
              color: "var(--text-dim)",
            }}
          >
            {items.length}
          </span>
        </div>
        {bajada && (
          <p
            style={{
              fontSize: 12.5,
              lineHeight: 1.6,
              color: "var(--text-muted)",
              marginTop: 6,
            }}
          >
            {bajada}
          </p>
        )}
      </div>
      {items.map((e) => (
        <Tarjeta key={e.id} e={e} onClick={() => abrir(e.id)} />
      ))}
    </div>
  );
}
