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
  // Tauri dev también navega a localhost:3000: su Origin no permite distinguir
  // esa navegación de un navegador. Cuando coexisten dos políticas se aplica
  // su intersección; este header debe permitir el IPC de Tauri por sí mismo.
  // Incidente 2026-10-07: permitir tauri.localhost no permite ipc.localhost.
  // Al bloquear este último, ensure_backend y event.listen emitían «IPC custom
  // protocol failed ... Failed to fetch» y pasaban al canal postMessage.
  // Ver docs/auditorias/arranque_idioma_ipc_2026-10-07.md y smoke-ipc-csp.mjs.
  //
  // unsafe-eval en script-src: necesario para Next.js webpack en dev mode.
  // El HMR y los source-maps usan eval() para inyectar módulos. Sin esto,
  // los dynamic imports (ProEvaluation, TechNetwork3D, etc.) se cuelgan.
  // En producción no hay servidor Next: se usan tauri.conf.prod.json o el
  // overlay MSIX. Conservan unsafe-eval porque MolStar y 3Dmol lo necesitan.
  //
  // Sólo se omite el header cuando Origin identifica el origen Tauri.
  // Una navegación a localhost puede no enviar Origin, también desde Tauri dev.
  const origin = request.headers.get("origin") || "";
  const isTauri = origin.startsWith("tauri://") || origin.startsWith("https://tauri.localhost");

  if (!isTauri) {
    const csp = [
      `default-src 'self'`,
      `script-src 'self' 'nonce-${nonce}' 'unsafe-eval'`,
      `style-src 'self' 'unsafe-inline'`,
      `connect-src 'self' ipc: http://ipc.localhost https://api.devnet.solana.com wss://api.devnet.solana.com http://127.0.0.1:* http://localhost:* ws://127.0.0.1:* ws://localhost:* tauri://localhost http://tauri.localhost https://tauri.localhost data:`,
      `img-src 'self' data: blob:`,
      `font-src 'self' data:`,
      `media-src 'self' http://127.0.0.1:* http://localhost:*`,
      `frame-src 'self' blob: http://127.0.0.1:*`,
      `worker-src 'self' blob:`,
    ].join("; ");

    response.headers.set("Content-Security-Policy", csp);
  }
  // Tauri dev normalmente recibe el header anterior; no depender de que se omita.

  response.headers.set("x-nonce", nonce);

  return response;
}

// Aplicar a todas las rutas.
// Web Crypto API no require runtime específico — funciona en el runtime Node de Next.
export const config = {
  matcher: "/((?!api|_next/static|_next/image|favicon.ico).*)",
};
