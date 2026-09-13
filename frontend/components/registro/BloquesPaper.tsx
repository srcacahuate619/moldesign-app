"use client";

/**
 * Renderiza los bloques estructurados de un paper.
 *
 * El generador (`scripts/build_registro_cientifico.py`) convierte el markdown escrito
 * a mano en bloques tipados. Aqui se pintan con componentes reales: nada de
 * `dangerouslySetInnerHTML`, porque la app corre con CSP estricta.
 */

import type { Bloque, Frag } from "@/lib/registro";
import { esExterno } from "@/lib/openExternal";
import { ExternalLink } from "@/components/ui/ExternalLink";

function Fragmento({ f }: { f: Frag }) {
  if (f.m === "fuerte")
    return <strong style={{ fontWeight: 650, color: "var(--text)" }}>{f.t}</strong>;
  if (f.m === "enfasis") return <em>{f.t}</em>;
  if (f.m === "codigo")
    return (
      <code
        style={{
          fontFamily: "var(--font-mono)",
          fontSize: "0.88em",
          padding: "0.1em 0.35em",
          borderRadius: 3,
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
        }}
      >
        {f.t}
      </code>
    );
  if (f.m === "enlace") {
    const href = f.href ?? "";
    const style = { color: "var(--accent-strong)", textDecoration: "underline", textUnderlineOffset: 3 };
    if (!href) return <>{f.t}</>;
    if (esExterno(href)) {
      return (
        <ExternalLink href={href} style={style}>
          {f.t}
        </ExternalLink>
      );
    }
    // Unsafe/unknown schemes are rendered as text, never as executable links.
    if (/^[a-z][a-z\d+.-]*:/i.test(href) || href.startsWith("//")) return <>{f.t}</>;
    return (
      <a href={href} style={style}>
        {f.t}
      </a>
    );
  }
  return <>{f.t}</>;
}

function Frags({ frag }: { frag: Frag[] }) {
  return (
    <>
      {frag.map((f, i) => (
        <Fragmento key={i} f={f} />
      ))}
    </>
  );
}

const ALINEACION = { izquierda: "left", centro: "center", derecha: "right" } as const;

export function BloquesPaper({ bloques }: { bloques: Bloque[] }) {
  return (
    <div style={{ fontSize: 15, lineHeight: 1.75, color: "var(--text-secondary)" }}>
      {bloques.map((b, i) => {
        switch (b.tipo) {
          case "encabezado": {
            const tam = b.nivel === 2 ? 22 : b.nivel === 3 ? 17 : 15;
            const Tag = (b.nivel === 2 ? "h2" : b.nivel === 3 ? "h3" : "h4") as "h2";
            return (
              <Tag
                key={i}
                style={{
                  fontSize: tam,
                  fontWeight: 700,
                  color: "var(--text)",
                  letterSpacing: "-0.01em",
                  marginTop: b.nivel === 2 ? 40 : 28,
                  marginBottom: 12,
                  fontFamily: "var(--font-display)",
                }}
              >
                <Frags frag={b.frag} />
              </Tag>
            );
          }

          case "parrafo":
            return (
              <p key={i} style={{ margin: "0 0 18px" }}>
                <Frags frag={b.frag} />
              </p>
            );

          case "cita":
            return (
              <blockquote
                key={i}
                style={{
                  margin: "24px 0",
                  padding: "14px 20px",
                  borderLeft: "3px solid var(--accent)",
                  background: "var(--bg-secondary)",
                  color: "var(--text)",
                  fontSize: 15,
                }}
              >
                <Frags frag={b.frag} />
              </blockquote>
            );

          case "lista": {
            const Tag = (b.ordenada ? "ol" : "ul") as "ul";
            return (
              <Tag
                key={i}
                style={{
                  margin: "0 0 18px",
                  paddingLeft: 22,
                  listStyle: b.ordenada ? "decimal" : "disc",
                }}
              >
                {b.items.map((it, j) => (
                  <li key={j} style={{ margin: "0 0 7px" }}>
                    <Frags frag={it} />
                  </li>
                ))}
              </Tag>
            );
          }

          case "tabla":
            return (
              <div key={i} style={{ overflowX: "auto", margin: "0 0 24px" }}>
                <table
                  style={{
                    width: "100%",
                    borderCollapse: "collapse",
                    fontSize: 13.5,
                    fontVariantNumeric: "tabular-nums",
                  }}
                >
                  <thead>
                    <tr>
                      {b.cabecera.map((c, j) => (
                        <th
                          key={j}
                          style={{
                            textAlign: ALINEACION[b.alineacion[j] ?? "izquierda"],
                            padding: "9px 12px",
                            borderBottom: "1px solid var(--border-light)",
                            color: "var(--text)",
                            fontWeight: 650,
                            whiteSpace: "nowrap",
                          }}
                        >
                          <Frags frag={c} />
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {b.filas.map((fila, j) => (
                      <tr key={j}>
                        {fila.map((c, k) => (
                          <td
                            key={k}
                            style={{
                              textAlign: ALINEACION[b.alineacion[k] ?? "izquierda"],
                              padding: "9px 12px",
                              borderBottom: "1px solid var(--border)",
                            }}
                          >
                            <Frags frag={c} />
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );

          case "codigo":
            return (
              <pre
                key={i}
                style={{
                  margin: "0 0 24px",
                  padding: "14px 16px",
                  overflowX: "auto",
                  background: "var(--bg-secondary)",
                  border: "1px solid var(--border)",
                  borderRadius: 4,
                  fontFamily: "var(--font-mono)",
                  fontSize: 12.5,
                  lineHeight: 1.6,
                  color: "var(--text)",
                }}
              >
                {b.texto}
              </pre>
            );

          default:
            return null;
        }
      })}
    </div>
  );
}
