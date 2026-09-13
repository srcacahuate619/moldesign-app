const isDesktopBuild = process.env.BUILD_TARGET === "desktop";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,

  // Directorio de trabajo de Next, separable por proceso.
  //
  // POR QUÉ EXISTE ESTA LÍNEA. `next dev` y `next build` escriben el mismo
  // directorio, y en Windows el servidor de desarrollo mantiene `trace` con
  // bloqueo EXCLUSIVO. Con los dos a la vez, el build no falla de forma
  // legible: se queda en «Creating an optimized production build…» y no
  // devuelve nunca. Medido en este repo: con un `next dev` vivo, la memoria de
  // node llegó a 19 GB y el build no terminó; en solitario, pico de 4,4 GB.
  //
  // El build de producción conserva `.next` —es lo que esperan `next start`,
  // el despliegue y las cachés de CI— y sólo el servidor de desarrollo se
  // aparta a `.next-dev` (ver el script `dev` en package.json). Así los dos
  // pueden convivir, que es justo lo que hace falta cuando `tauri dev` tiene
  // el frontend levantado mientras alguien compila.
  distDir: process.env.NEXT_DIST_DIR || ".next",

  // En escritorio, el puerto del backend lo elige RUST, no una variable de
  // entorno.
  //
  // EL FALLO QUE ARREGLA. `.env.local` declara
  // `NEXT_PUBLIC_API_URL=http://127.0.0.1:8000` para el desarrollo web, y
  // `next build` lo HORNEA en el bundle estático. En el instalador del
  // 2026-09-01 esa constante viajaba dentro de cuatro chunks. Rust elige el
  // primer puerto libre del rango 8000-8019, así que en cualquier equipo con
  // el 8000 ocupado el frontend quedaba hablando con un producto ajeno: en
  // esta máquina, `legaldesk-server.exe`, que contesta 200 con HTML. El
  // síntoma era «los receptores cargan para siempre», sin ningún error.
  //
  // `lib/config.ts` ya trata la variable como el ÚLTIMO recurso y sólo la usa
  // cuando no hay puente Tauri. Vaciarla aquí cierra también ese camino: en
  // escritorio, no conocer el puerto tiene que ser un error visible y nunca
  // «prueba con el vecino».
  //
  // `noHardcodedApiPort.test.ts` vigila el árbol de código, pero un archivo de
  // entorno entra por debajo del guardián: escanea fuentes, no variables.
  ...(isDesktopBuild ? { env: { NEXT_PUBLIC_API_URL: "" } } : {}),

  // Tauri carga archivos estáticos desde `frontend/out`; el servidor Next no
  // existe dentro del instalador. La build web conserva SSR y sus rutas API.
  ...(isDesktopBuild
    ? {
        output: "export",
        images: { unoptimized: true },
        // Las rutas API son endpoints del deployment web (NextAuth/métricas),
        // no existen dentro del WebView. Excluir archivos .ts de la detección
        // de rutas evita intentar exportarlas como HTML estático.
        pageExtensions: ["tsx", "jsx"],
      }
    : {}),

  // Tree-shaking agresivo para libs con muchos exports nombrados.
  // Next.js reescribe los imports named-only para que no se bundlen exports
  // que no se usan — reduce el initial bundle size en algunos casos 50%+.
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "framer-motion",
      "@react-three/drei",
      "@react-three/fiber",
      "rdkit",
    ],
  },

  webpack: (config) => {
    // paper.js (ketcher-core dep) has conditional require() for Node-only
    // modules (jsdom, canvas). In the browser `self` is already `window`,
    // so those branches are never taken at runtime.
    // Tell webpack to NOT parse paper.js, avoiding unresolvable requires.
    //
    // molstar/build/viewer also uses dynamic require() calls and pre-compiled
    // CSS that is incompatible with webpack static analysis — add to noParse.
    config.module.noParse = [
      ...(config.module.noParse || []),
      /paper[\\/]dist[\\/]/,
      /molstar[\\/]build[\\/]/,
    ];

    // Exclude molstar's pre-compiled CSS from Next.js css-loader pipeline
    // It's loaded manually via a <style> tag in AdvancedMolstarViewer
    config.module.rules = config.module.rules.map((rule) => {
      if (rule.oneOf) {
        rule.oneOf = rule.oneOf.map((one) => {
          if (one.test && one.test.toString().includes("css")) {
            return {
              ...one,
              exclude: [
                ...(one.exclude ? (Array.isArray(one.exclude) ? one.exclude : [one.exclude]) : []),
                /molstar[\\/]build[\\/]/,
              ],
            };
          }
          return one;
        });
      }
      return rule;
    });

    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      path: false,
      canvas: false,
    };

    config.resolve.alias = {
      ...config.resolve.alias,
      "pdfjs-dist/build/pdf.worker.mjs": false,
      "pdfjs-dist/build/pdf.worker.min.mjs": false,
    };

    return config;
  },
};

module.exports = nextConfig;
