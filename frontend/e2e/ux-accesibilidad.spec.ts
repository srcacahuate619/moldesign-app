// =====================================================================
// Revisión de UX comprobable — escalas, teclado, foco, contraste, textos largos
// =====================================================================
//
// Las pruebas unitarias corren en jsdom, que no calcula layout ni color: no
// pueden decir si un texto se corta, si el foco se ve, o si el contraste llega
// a AA. Esta suite sí, porque corre en un navegador real con estilos aplicados.
//
// No sustituye a mirar la aplicación en Windows a 125 % y 150 % —el escalado de
// sistema afecta a fuentes y densidad de píxeles de una forma que el zoom del
// navegador sólo aproxima—, y eso queda declarado como pendiente humano. Lo que
// sí hace es convertir en repetible todo lo que no depende de un par de ojos:
// una regresión de contraste o un texto truncado irreversiblemente fallan aquí
// la próxima vez, en vez de dentro de tres meses.

import { expect, test, type Page } from "@playwright/test";

/** Escalas de Windows del §11, aproximadas con `deviceScaleFactor` + viewport. */
const ESCALAS = [
  { nombre: "100%", ancho: 1440, alto: 900 },
  { nombre: "125%", ancho: 1152, alto: 720 },
  { nombre: "150%", ancho: 960, alto: 600 },
  { nombre: "200%", ancho: 720, alto: 450 },
];

const RUTAS = [
  { nombre: "Casos", ruta: "/" },
  { nombre: "Moldex", ruta: "/moldex" },
];

function sesion() {
  return {
    token: "token-ux",
    refreshToken: "refresh-ux",
    user: { user_id: "ux", username: "ux", email: "ux@local.test" },
  };
}

async function abrir(page: Page, ruta: string) {
  await page.addInitScript((auth) => {
    localStorage.setItem("moldesign_auth", JSON.stringify(auth));
  }, sesion());
  await page.goto(ruta, { waitUntil: "domcontentloaded" });
  // El backend no está: lo que se revisa es la superficie, sus estados vacíos y
  // su legibilidad, que es justo lo que hay que mirar cuando algo falla.
  await page.waitForTimeout(1200);
}

/** Luminancia relativa WCAG. */
function luminancia(rgb: number[]): number {
  const [r, g, b] = rgb.map((v) => {
    const c = v / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contraste(a: number[], b: number[]): number {
  const la = luminancia(a);
  const lb = luminancia(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

function parseRgb(valor: string): number[] | null {
  const m = valor.match(/rgba?\(([^)]+)\)/);
  if (!m) return null;
  const partes = m[1].split(",").map((x) => parseFloat(x.trim()));
  if (partes.length >= 4 && partes[3] === 0) return null; // transparente
  return partes.slice(0, 3);
}

test.describe("la aplicación se lee a cualquier escala", () => {
  for (const escala of ESCALAS) {
    for (const { nombre, ruta } of RUTAS) {
      test(`${nombre} a ${escala.nombre} no desborda en horizontal`, async ({ page }) => {
        await page.setViewportSize({ width: escala.ancho, height: escala.alto });
        await abrir(page, ruta);

        const desborde = await page.evaluate(() => {
          const doc = document.documentElement;
          return {
            scroll: doc.scrollWidth,
            cliente: doc.clientWidth,
            culpables: Array.from(document.querySelectorAll("*"))
              .filter((el) => {
                const r = el.getBoundingClientRect();
                return r.width > 0 && r.right > document.documentElement.clientWidth + 2;
              })
              .slice(0, 5)
              .map((el) => `${el.tagName.toLowerCase()}.${(el.className || "").toString().slice(0, 60)}`),
          };
        });

        expect(
          desborde.scroll,
          `desborde horizontal en ${nombre} a ${escala.nombre}: ${desborde.culpables.join(" | ")}`,
        ).toBeLessThanOrEqual(desborde.cliente + 2);
      });
    }
  }
});

test.describe("el teclado alcanza y el foco se ve", () => {
  test("hay orden de tabulación y el foco es visible", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await abrir(page, "/");

    const recorridos: string[] = [];
    let sinFocoVisible = 0;

    for (let i = 0; i < 15; i++) {
      await page.keyboard.press("Tab");
      const info = await page.evaluate(() => {
        const el = document.activeElement as HTMLElement | null;
        if (!el || el === document.body) return null;
        const estilo = getComputedStyle(el);
        const tieneAnillo =
          estilo.outlineStyle !== "none" && parseFloat(estilo.outlineWidth || "0") > 0;
        const tieneSombra = estilo.boxShadow !== "none" && estilo.boxShadow !== "";
        const tieneBorde = parseFloat(estilo.borderWidth || "0") > 0;
        return {
          etiqueta: `${el.tagName.toLowerCase()}${el.getAttribute("aria-label") ? `[${el.getAttribute("aria-label")}]` : ""}`,
          visible: tieneAnillo || tieneSombra || tieneBorde,
        };
      });
      if (!info) continue;
      recorridos.push(info.etiqueta);
      if (!info.visible) sinFocoVisible++;
    }

    expect(recorridos.length, "ningún elemento recibió el foco con Tab").toBeGreaterThan(0);
    expect(
      sinFocoVisible,
      `elementos enfocados sin indicación visible: ${sinFocoVisible} de ${recorridos.length}`,
    ).toBeLessThanOrEqual(Math.floor(recorridos.length / 2));
  });

  test("los controles alcanzables tienen nombre accesible", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await abrir(page, "/");

    const anonimos = await page.evaluate(() => {
      const seleccion = "button, a[href], input, select, textarea, [role=button]";
      return Array.from(document.querySelectorAll(seleccion))
        .filter((el) => {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) return false;
          const texto = (el.textContent || "").trim();
          const etiqueta =
            el.getAttribute("aria-label") ||
            el.getAttribute("title") ||
            el.getAttribute("alt") ||
            (el as HTMLInputElement).placeholder;
          return !texto && !etiqueta;
        })
        .slice(0, 8)
        .map((el) => `${el.tagName.toLowerCase()}.${(el.className || "").toString().slice(0, 50)}`);
    });

    expect(anonimos, `controles sin nombre accesible: ${anonimos.join(" | ")}`).toEqual([]);
  });
});

test.describe("el texto cumple contraste AA", () => {
  test("ningún texto normal baja de 4.5:1 sobre su fondo", async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await abrir(page, "/");

    const muestras = await page.evaluate(() => {
      function fondoEfectivo(el: Element): string {
        let actual: Element | null = el;
        while (actual) {
          const c = getComputedStyle(actual).backgroundColor;
          if (c && !c.includes("rgba(0, 0, 0, 0)")) return c;
          actual = actual.parentElement;
        }
        return getComputedStyle(document.body).backgroundColor || "rgb(0,0,0)";
      }
      return Array.from(document.querySelectorAll("p, span, div, li, h1, h2, h3, h4, label, button, a"))
        .filter((el) => {
          const texto = Array.from(el.childNodes)
            .filter((n) => n.nodeType === Node.TEXT_NODE)
            .map((n) => (n.textContent || "").trim())
            .join("");
          if (texto.length < 3) return false;
          const r = el.getBoundingClientRect();
          return r.width > 0 && r.height > 0 && r.top < window.innerHeight;
        })
        .slice(0, 120)
        .map((el) => {
          const estilo = getComputedStyle(el);
          return {
            texto: (el.textContent || "").trim().slice(0, 40),
            color: estilo.color,
            fondo: fondoEfectivo(el),
            tamano: parseFloat(estilo.fontSize),
            peso: parseInt(estilo.fontWeight || "400", 10),
          };
        });
    });

    const fallos: string[] = [];
    for (const m of muestras) {
      const color = parseRgb(m.color);
      const fondo = parseRgb(m.fondo);
      if (!color || !fondo) continue;
      // AA: 4.5:1 normal; 3:1 para texto grande (>=18.66px, o >=24px).
      const grande = m.tamano >= 24 || (m.tamano >= 18.66 && m.peso >= 700);
      const minimo = grande ? 3 : 4.5;
      const razon = contraste(color, fondo);
      if (razon < minimo) {
        fallos.push(
          `"${m.texto}" ${razon.toFixed(2)}:1 (mín ${minimo}:1, ${m.tamano}px) ` +
            `color=${m.color} fondo=${m.fondo}`,
        );
      }
    }

    expect(fallos, `textos por debajo de AA:\n${fallos.join("\n")}`).toEqual([]);
  });
});

test.describe("los datos largos no se pierden", () => {
  test("un hash o un SMILES truncado sigue siendo recuperable", async ({ page }) => {
    await page.setViewportSize({ width: 960, height: 600 });
    await abrir(page, "/");

    // Truncar visualmente está bien; truncar de forma irreversible no. Lo que
    // se exige es que el texto completo siga en el DOM —copiable, o en un
    // `title`— y no recortado con `slice()` antes de pintarlo.
    const irrecuperables = await page.evaluate(() => {
      return Array.from(document.querySelectorAll("*"))
        .filter((el) => {
          const estilo = getComputedStyle(el);
          const recorta =
            estilo.textOverflow === "ellipsis" || estilo.overflow === "hidden";
          if (!recorta) return false;
          const texto = (el.textContent || "").trim();
          if (texto.length < 20) return false;
          // Si termina en «…» y no hay título ni texto completo, se perdió.
          return texto.endsWith("…") && !el.getAttribute("title");
        })
        .slice(0, 5)
        .map((el) => (el.textContent || "").trim().slice(0, 60));
    });

    expect(
      irrecuperables,
      `texto recortado sin forma de recuperarlo: ${irrecuperables.join(" | ")}`,
    ).toEqual([]);
  });
});
