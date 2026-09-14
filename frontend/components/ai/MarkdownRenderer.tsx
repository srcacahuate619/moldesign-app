"use client";

import React from "react";

/**
 * MOLCHAT-AUD-01, higiene del §8 — sanear el Markdown que escribe el modelo.
 *
 * Aquí había un `escapeHtml` que convertía `<` en `&lt;` antes de construir los
 * nodos. Este renderizador NO usa `dangerouslySetInnerHTML`: devuelve elementos
 * de React, que escapan el texto por diseño. El resultado era un escape doble, y
 * lo que el investigador leía era `MW &lt; 500` donde el modelo había escrito
 * `MW < 500` — un dato científico deformado por una defensa que sobraba.
 *
 * Lo que sí hay que sanear es lo que el modelo puede fabricar —o lo que le
 * llega de una recuperación externa, que es texto de terceros— y que sería
 * activo si algún día esto se renderizara como HTML o como enlace: esquemas
 * ejecutables y caracteres de control que rompen el trazado.
 */
const ESQUEMA_ACTIVO = /\b(javascript|vbscript|data)\s*:/gi;
const CONTROL = /[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g;

export function sanearMarkdown(text: string): string {
  return text.replace(CONTROL, "").replace(ESQUEMA_ACTIVO, "$1_bloqueado:");
}

function parseTableRow(line: string): string[] {
  return line
    .split("|")
    .slice(1, -1)
    .map((c) => c.trim().replace(/\*\*(.*?)\*\*/g, "$1").replace(/`([^`]+)`/g, "$1"));
}

function renderTable(lines: string[], startIdx: number): React.ReactNode {
  const tableLines: string[] = [];
  let i = startIdx;
  while (i < lines.length && lines[i].startsWith("|")) {
    tableLines.push(lines[i]);
    i++;
  }
  if (tableLines.length < 2) return null;

  const header = parseTableRow(tableLines[0]);
  const rows = tableLines.slice(2).map(parseTableRow);

  return (
    <div key={`table-${startIdx}`} style={{ overflowX: "auto", margin: "12px 0" }}>
      <table style={{
        width: "100%", borderCollapse: "collapse",
        fontSize: "0.8125rem", border: "1px solid var(--border)",
      }}>
        <thead>
          <tr style={{ borderBottom: "2px solid var(--border)", background: "var(--bg-secondary)" }}>
            {header.map((h, j) => (
              <th key={j} style={{ padding: "6px 12px", textAlign: "left", fontWeight: 600, color: "var(--text)" }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} style={{ borderBottom: "1px solid var(--border)" }}>
              {row.map((cell, ci) => (
                <td key={ci} style={{ padding: "6px 12px", color: "var(--text-secondary)" }}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function renderInline(text: string): React.ReactNode[] {
  const parts: React.ReactNode[] = [];
  const remaining = sanearMarkdown(text);

  const boldRegex = /\*\*(.*?)\*\*/g;
  const codeRegex = /`([^`]+)`/g;
  const italicRegex = /\*(.*?)\*/g;

  const tokens: { type: string; content: string; index: number }[] = [];

  let match;
  while ((match = boldRegex.exec(remaining)) !== null) {
    tokens.push({ type: "bold", content: match[1], index: match.index });
  }
  while ((match = codeRegex.exec(remaining)) !== null) {
    tokens.push({ type: "code", content: match[1], index: match.index });
  }
  while ((match = italicRegex.exec(remaining)) !== null) {
    tokens.push({ type: "italic", content: match[1], index: match.index });
  }

  tokens.sort((a, b) => a.index - b.index);

  let pos = 0;
  for (const token of tokens) {
    if (token.index > pos) {
      parts.push(remaining.slice(pos, token.index));
    }
    switch (token.type) {
      case "bold":
        parts.push(<strong key={pos}>{token.content}</strong>);
        break;
      case "code":
        parts.push(
          <code
            key={pos}
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              padding: "1px 6px",
              borderRadius: 4,
              fontSize: "0.9em",
            }}
          >
            {token.content}
          </code>
        );
        break;
      case "italic":
        parts.push(<em key={pos}>{token.content}</em>);
        break;
    }
    pos = token.index + token.content.length + (token.type === "bold" ? 4 : token.type === "code" ? 2 : 2);
  }
  if (pos < remaining.length) {
    parts.push(remaining.slice(pos));
  }

  return parts;
}

export function MarkdownRenderer({ content }: { content: string }) {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let codeLang = "";
  let inList = false;
  let listItems: React.ReactNode[] = [];

  function flushList(key: string) {
    if (listItems.length > 0) {
      elements.push(
        <ul key={key} style={{ margin: "4px 0", paddingLeft: 24 }}>
          {listItems}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith("```")) {
      if (inCodeBlock) {
        elements.push(
          <pre
            key={`code-${i}`}
            style={{
               background: "var(--bg-secondary)",
               border: "1px solid var(--border)",
              padding: 12,
              borderRadius: 8,
              overflow: "auto",
              fontSize: "0.85em",
              margin: "8px 0",
            }}
          >
            <code>{codeLines.join("\n")}</code>
          </pre>
        );
        codeLines = [];
        inCodeBlock = false;
      } else {
        flushList(`list-${i}`);
        inCodeBlock = true;
        codeLang = line.slice(3).trim();
        codeLines = [];
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(line);
      continue;
    }

    if (line.startsWith("## ")) {
      flushList(`list-${i}`);
      elements.push(
        <h3 key={`h-${i}`} style={{ margin: "16px 0 8px", fontSize: "1.1em" }}>
          {renderInline(line.slice(3))}
        </h3>
      );
      continue;
    }

    if (line.startsWith("- ") || line.startsWith("* ")) {
      inList = true;
      const content = line.slice(2);
      listItems.push(
        <li key={`li-${i}`} style={{ margin: "2px 0" }}>
          {renderInline(content)}
        </li>
      );
      continue;
    }

    if (line.match(/^\d+\.\s/)) {
      flushList(`list-${i}`);
      const content = line.replace(/^\d+\.\s/, "");
      elements.push(
        <div key={`ol-${i}`} style={{ margin: "2px 0", paddingLeft: 24 }}>
          {renderInline(content)}
        </div>
      );
      continue;
    }

    if (line.startsWith("> ")) {
      flushList(`list-${i}`);
      elements.push(
        <blockquote
          key={`quote-${i}`}
          style={{
            margin: "8px 0",
            padding: "4px 12px",
            borderLeft: "3px solid var(--border)",
            color: "var(--text-secondary)",
            background: "var(--bg-secondary)",
          }}
        >
          {renderInline(line.slice(2))}
        </blockquote>
      );
      continue;
    }

    flushList(`list-${i}`);

    if (line.trim() === "") {
      elements.push(<div key={`spacer-${i}`} style={{ height: 8 }} />);
      continue;
    }

    if (line.startsWith("|")) {
      elements.push(renderTable(lines, i));
      while (i < lines.length && lines[i].startsWith("|")) {
        i++;
      }
      i--;
      continue;
    }

    elements.push(
      <div key={`p-${i}`} style={{ margin: "4px 0", lineHeight: 1.6 }}>
        {renderInline(line)}
      </div>
    );
  }

  flushList("list-final");
  if (inCodeBlock) {
    elements.push(
      <pre
        key="code-unclosed"
        style={{
          background: "var(--bg-secondary)",
          border: "1px solid var(--border)",
          padding: 12,
          borderRadius: 8,
          overflow: "auto",
          fontSize: "0.85em",
          margin: "8px 0",
        }}
      >
        <code>{codeLines.join("\n")}</code>
      </pre>
    );
  }

  return <>{elements}</>;
}
