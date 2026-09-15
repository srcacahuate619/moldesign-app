
import { TRADUCCIONES_POR_SUPERFICIE } from "../context/traducciones";
import "./globals.css";
import type { ReactNode } from "react";
import { headers } from "next/headers";
import { AuthProvider } from "../lib/auth";
import { Navigation } from "../components/Navigation";
import { PersistentKeepAliveLayout } from "../components/PersistentKeepAliveLayout";
import { ThemeProvider } from "../context/ThemeContext";
import { WalletProvider } from "../components/WalletProvider";
import { LanguageProvider } from "../context/LanguageContext";
import { ErrorBoundary } from "../components/ui/ErrorBoundary";
import { AIProvider } from "../context/AIContext";
import { DownloadProvider } from "../context/DownloadProvider";
import { ChatPanel } from "../components/ai/ChatPanel";

// Hoja de estilos de Ketcher, estatica y global a proposito.
//
// Importarla desde `KetcherEditorInner` -que se carga con `next/dynamic`- la
// dejaba en un chunk que el HTML del export estatico nunca enlaza. Aqui entra
// en el conjunto inicial de <link>, que es la unica forma de garantizar que
// este cuando el editor aparezca. El codigo de Ketcher sigue difiriendose.
import "ketcher-react/dist/index.css";
import { TraspasoInvitado } from "../components/TraspasoInvitado";

const isDesktopBuild = process.env.BUILD_TARGET === "desktop";

export const metadata = {
  title: "MolDesign — Evidencia estructural reproducible",
  description: "Prepara hipótesis moleculares, explora poses y documenta la evidencia computacional de cada corrida.",
};

function translateLayout(key: string): string {
  return TRADUCCIONES_POR_SUPERFICIE.es[key] ?? key;
}

export default async function RootLayout({ children }: { children: ReactNode }) {
  const t = translateLayout;
  // La web lee el nonce inyectado por proxy vía x-nonce. En Tauri no
  // existe un servidor Next ni proxy por request: la CSP viene de
  // tauri.conf.prod.json y el layout debe poder exportarse como HTML estático.
  // CSP nonce-based: cada request tiene un nonce único que solo los scripts
  // legítimos (los de este layout) pueden usar. Scripts injectados por XSS
  // no tendrán el nonce y serán bloqueados por el browser.
  const nonce = isDesktopBuild ? "" : ((await headers()).get("x-nonce") ?? "");

  return (
    <html lang={t("auto_09cd68a2a77b")} className="dark" data-zoom="100" suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" sizes="32x32" />
        <link rel="icon" href="/favicon.png" type="image/png" />
        <script
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: t("auto_7a133b421d46"),
          }}
        />
        <script
          nonce={nonce}
          dangerouslySetInnerHTML={{
            __html: t("auto_4d382c8b0332"),
          }}
        />
        <script
          nonce={nonce}
          type="application/ld+json"
          dangerouslySetInnerHTML={{
            __html: JSON.stringify({
              "@context": "https://schema.org",
              "@type": "SoftwareApplication",
              "name": "MolDesign AI",
              "applicationCategory": "ScienceApplication",
              "operatingSystem": "Windows, Web",
              "description": t("auto_b8c87de15d58"),
              "offers": { "@type": "Offer", "price": "0", "priceCurrency": "USD" }
            })
          }}
        />
      </head>
      <body className="antialiased font-sans min-h-[100dvh] flex flex-col selection:bg-[var(--accent)] selection:text-white" style={{ backgroundColor: "var(--bg)", color: "var(--text)" }}>
        {/* Los PROVIDERS también dentro de una frontera.
            Antes sólo estaban protegidos `main` y el chat: una excepción en
            wallet, auth, tema, idioma, descargas, IA o `Navigation` escapaba
            hacia la raíz y dejaba la ventana en blanco. `global-error.tsx`
            cubre el caso extremo; esta frontera lo atrapa antes, conservando
            la ventana y ofreciendo reintentar. */}
        <ErrorBoundary>
        <WalletProvider>
          <AuthProvider>
            <ThemeProvider>
              <LanguageProvider>
                <DownloadProvider>
                  <AIProvider>
                    <Navigation />
                    {/* El ofrecimiento de traspaso vive aquí y no en una pestaña:
                        aparece justo después de registrarse, que es cuando el
                        trabajo del invitado parece haberse perdido. */}
                    <ErrorBoundary>
                      <TraspasoInvitado />
                    </ErrorBoundary>
                    <main className="flex-1 w-full">
                      <ErrorBoundary>
                        <PersistentKeepAliveLayout>
                          {children}
                        </PersistentKeepAliveLayout>
                      </ErrorBoundary>
                    </main>
                    <ErrorBoundary>
                      <ChatPanel />
                    </ErrorBoundary>
                  </AIProvider>
                </DownloadProvider>
              </LanguageProvider>
            </ThemeProvider>
          </AuthProvider>
        </WalletProvider>
        </ErrorBoundary>
      </body>
    </html>
  );
}
