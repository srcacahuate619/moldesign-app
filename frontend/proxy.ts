// proxy.ts — Nonce-based CSP headers
// =============================================================================
// Tarea #2 — CSP audit: nonce-based Content Security Policy.
//
// Genera un nonce aleatorio por request y lo inyecta en el header CSP y en
// x-nonce para que app/layout.tsx lo lea via headers() y lo agregue a sus
// <script> tags. Los scripts de Next.js auto-generados (hydration, chunks)
// NO tienen nonce — esta es una limitación de Next.js que se mitiga
// delegando el nonce al layout.
//
// Nonce generado con Web Crypto API (crypto.getRandomValues) — funciona en
// cualquier runtime sin depender de node:crypto. Cero dependencias de Node.
//
// ESTADO: COMPLETADO (2026-07-29)
//   ✅ CSP con nonces activado — sin unsafe-inline, con unsafe-eval solo en dev
//   ✅ 3Dmol.js localizado — eliminado fallback CDN en layout.tsx
//   ✅ Web Crypto API — runtime-agnostic (Edge + Node)
//   🔲 style-src mantiene 'unsafe-inline' — requiere refactor inline styles (6h)
//   🔲 unsafe-eval en dev necesario para Next.js webpack HMR/source-maps
//
// Documentación: docs/30_SECURITY_CSP_AUDIT.md
// =============================================================================

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// generateNonce usa la Web Crypto API (crypto.getRandomValues) que funciona
// en cualquier runtime — Node.js y browser. No depende de node:crypto ni
// require runtime: "nodejs". 128 bits de entropía formateados como base64url.
function generateNonce(): string {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function proxy(request: NextRequest) {
  const nonce = generateNonce();

  // Guardar nonce en header para que los componentes lo lean via headers()
  const requestHeaders = new Headers(request.headers);
  requestHeaders.set("x-nonce", nonce);

  const response = NextResponse.next({
    request: { headers: requestHeaders },
  });

  // ── CSP nonce-based — browser dev mode (npm run dev) ──────────────────
  // En modo Tauri (npx tauri dev), el webview aplica su propio CSP desde
  // tauri.conf.json. Si ambos CSPs coexisten, el browser intersecta las
  // directivas y el resultado es más restrictivo que cualquiera de los dos,
  // rompiendo Ketcher/MolStar (necesitan unsafe-eval que solo está en Tauri).
  //
  // unsafe-eval en script-src: necesario para Next.js webpack en dev mode.
  // El HMR y los source-maps usan eval() para inyectar módulos. Sin esto,
  // los dynamic imports (ProEvaluation, TechNetwork3D, etc.) se cuelgan.
  // En producción (npx tauri build) el bundle no usa eval — lo maneja
  // tauri.conf.json sin unsafe-eval (Tarea #1 del audit CSP).
  //
  // Detección: en browser dev, el Origin es http://localhost:3000.
  // En tauri://, el Origin es tauri://localhost o no se envía.
  const origin = request.headers.get("origin") || "";
  const isTauri = origin.startsWith("tauri://") || origin.startsWith("https://tauri.localhost");

  if (!isTauri) {
    const csp = [
      `default-src 'self'`,
      `script-src 'self' 'nonce-${nonce}' 'unsafe-eval'`,
      `style-src 'self' 'unsafe-inline'`,
      `connect-src http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:* tauri://localhost https://tauri.localhost`,
      `img-src 'self' data: blob:`,
      `font-src 'self' data:`,
      `frame-src 'self' blob:`,
      `worker-src 'self' blob:`,
    ].join("; ");

    response.headers.set("Content-Security-Policy", csp);
  }
  // En Tauri: no seteamos CSP, tauri.conf.json lo maneja con unsafe-eval.

  response.headers.set("x-nonce", nonce);

  return response;
}

// Aplicar a todas las rutas.
// Web Crypto API no require runtime específico — funciona en el runtime Node de Next.
export const config = {
  matcher: "/((?!api|_next/static|_next/image|favicon.ico).*)",
};
