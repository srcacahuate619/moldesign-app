"use client";


import { useLanguage } from "@/context/LanguageContext";
/**
 * Bloque del menu de inicio: el marcador del registro experimental.
 *
 * Lee el mismo `index.json` que la vista completa, asi que las cifras de la portada no
 * pueden desviarse de las del registro. Si el JSON no esta generado, el bloque no se
 * pinta — la portada nunca queda rota por falta de datos.
 */

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  cargarIndice,
  ESTILO_CATEGORIA,
  type IndiceRegistro,
} from "@/lib/registro";

export function ContrasteInicio() {
  const { t } = useLanguage();
  const [idx, setIdx] = useState<IndiceRegistro | null>(null);

  useEffect(() => {
    cargarIndice()
      .then(setIdx)
      .catch(() => setIdx(null));
  }, []);

  if (!idx) return null;

  const h = idx.conteo.hallazgo ?? 0;
  const r = idx.conteo.refutacion ?? 0;
  const contexto =
    (idx.conteo.medicion ?? 0) +
    (idx.conteo.prerregistro ?? 0) +
    (idx.conteo.corrigendum ?? 0) +
    (idx.conteo.inconcluso ?? 0);

  const destH = idx.destacados.hallazgo ?? [];
  const destR = idx.destacados.refutacion ?? [];

  return (
    <section className="py-32 border-t border-theme px-8 lg:px-16">
      <div style={{ maxWidth: 1180, margin: "0 auto" }}>
        <div
          className="font-mono"
          style={{
            fontSize: 11,
            letterSpacing: "0.16em",
            textTransform: "uppercase",
            color: "var(--text-dim)",
            marginBottom: 18,
          }}
        >
          {t("auto_b76b2b4f5246")} {idx.total} artefactos sellados
        </div>

        <h2
          style={{
            fontSize: "clamp(30px, 4.4vw, 50px)",
            lineHeight: 1.06,
            fontWeight: 800,
            letterSpacing: "-0.03em",
            color: "var(--text)",
            marginBottom: 20,
            maxWidth: 860,
            fontFamily: "var(--font-display)",
          }}
        >
          {t("rg_no_empaquetamos")}
        </h2>

        <p
          style={{
            fontSize: 16,
            lineHeight: 1.7,
            color: "var(--text-secondary)",
            maxWidth: 700,
            marginBottom: 44,
            fontFamily: "var(--font-sans)",
          }}
        >
          {t("rg_detras_de_cada")}
        </p>

        {/* marcador */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: 1,
            background: "var(--border)",
            border: "1px solid var(--border)",
            marginBottom: 32,
          }}
        >
          <Panel
            n={h}
            color={ESTILO_CATEGORIA.hallazgo.color}
            titulo="Gates superados"
            desc={t("auto_8cd782f9aaaa")}
            ids={destH}
          />
          <Panel
            n={r}
            color={ESTILO_CATEGORIA.refutacion.color}
            titulo="Hipótesis derribadas"
            desc={t("auto_fa14698a6e5a")}
            ids={destR}
          />
          <Panel
            n={contexto}
            color="var(--text-muted)"
            titulo="Mediciones y prerregistros"
            desc={t("auto_d64c24cabf94")}
            ids={[]}
          />
        </div>

        <p
          style={{
            fontSize: 13,
            lineHeight: 1.65,
            color: "var(--text-dim)",
            maxWidth: 700,
            marginBottom: 28,
            fontFamily: "var(--font-sans)",
          }}
        >
          {t("rg_cociente_crudo")}
        </p>

        <Link
          href="/ciencia"
          className="font-mono"
          style={{
            display: "inline-block",
            padding: "14px 28px",
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.12em",
            textTransform: "uppercase",
            color: "var(--bg)",
            background: "var(--text)",
            textDecoration: "none",
          }}
        >
          {t("rg_abrir_registro")}
        </Link>
      </div>
    </section>
  );
}

function Panel({
  n,
  color,
  titulo,
  desc,
  ids,
}: {
  n: number;
  color: string;
  titulo: string;
  desc: string;
  ids: string[];
}) {
  return (
    <div style={{ background: "var(--bg)", padding: "28px 26px" }}>
      <div
        style={{
          fontSize: 46,
          fontWeight: 800,
          lineHeight: 1,
          color,
          fontFamily: "var(--font-display)",
          marginBottom: 10,
        }}
      >
        {n}
      </div>
      <div
        className="font-mono"
        style={{
          fontSize: 11,
          letterSpacing: "0.12em",
          textTransform: "uppercase",
          color: "var(--text)",
          marginBottom: 10,
          fontWeight: 700,
        }}
      >
        {titulo}
      </div>
      <p
        style={{
          fontSize: 13,
          lineHeight: 1.6,
          color: "var(--text-muted)",
          fontFamily: "var(--font-sans)",
          marginBottom: ids.length ? 14 : 0,
        }}
      >
        {desc}
      </p>
      {ids.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
          {ids.map((id) => (
            <Link
              key={id}
              href={`/ciencia?exp=${id}`}
              className="font-mono"
              style={{
                fontSize: 10.5,
                padding: "3px 7px",
                borderRadius: 2,
                color,
                border: `1px solid ${color}44`,
                textDecoration: "none",
              }}
            >
              {id}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
