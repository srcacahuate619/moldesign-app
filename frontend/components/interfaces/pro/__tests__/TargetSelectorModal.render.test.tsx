import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LanguageProvider } from "../../../../context/LanguageContext";
import { AuthProvider } from "../../../../lib/auth";
import type { Target } from "../../../../lib/api";
import { writeClassificationMode } from "../../../../lib/targetGrouping";
import TargetSelectorModal from "../TargetSelectorModal";
import { verificacionDePrueba } from "../../../../lib/__tests__/fixtures/verificacionReceptor";
import { intentoPublicado } from "../../../../lib/__tests__/fixtures/intentoPublicado";

// jsdom declara `en-US` y `LanguageProvider` elige el idioma del navegador: los textos
// que se comprueban aquí son los de la interfaz en español.
beforeEach(() => {
  vi.spyOn(window.navigator, "language", "get").mockReturnValue("es-ES");
});
afterEach(() => {
  vi.restoreAllMocks();
  window.localStorage.clear();
});

// Receptores con la forma que sirve `GET /targets/`. Los motivos son los REALES de
// dos de los 15 receptores `disponible: false` del catálogo (medidos el 2026-10-03).
const EXCEPCION =
  "Meeko no puede construir el receptor (RuntimeError: for residue_key='A:383', 3 have passed: ['HIE', 'HID', 'HIP'] and tied for fewest missing and excess H: HIE HID ).";
const FRASE =
  "Meeko elimina 1 residuo(s) a 6 Å o menos de la caja, del sitio: GLU A55 (0.941 Å). No se acopla contra un sitio incompleto.";

function receptor(pdb: string, extra: Partial<Target> = {}): Target {
  return {
    id: `id-${pdb}`,
    pdb_id: pdb,
    name: `Receptor ${pdb}`,
    organism: "Homo sapiens",
    chain: "A",
    structural_family: "protease",
    therapeutic_family: null,
    calibration_status: "listo",
    hotspot_count: 15,
    is_prepared: true,
    resolution: 2.0,
    disponible: true,
    motivo_no_disponible: null,
    ...extra,
  } as unknown as Target;
}

function modal(targets: Target[], onSelect = () => {}, isOpen = true) {
  return (
    <AuthProvider>
      <LanguageProvider>
        <TargetSelectorModal isOpen={isOpen} onClose={() => {}} targets={targets} onSelect={onSelect} selectedTargetId={null} />
      </LanguageProvider>
    </AuthProvider>
  );
}

function montar(targets: Target[], onSelect = () => {}) {
  return render(modal(targets, onSelect));
}

/** Las secciones del catálogo son pestañas: sólo la activa pinta sus tarjetas. */
function pestana(nombre: RegExp | string): HTMLElement {
  return screen.getByRole("tab", { name: nombre });
}
function abrir(nombre: RegExp | string) {
  fireEvent.click(pestana(nombre));
}

function tarjeta(pdb: string): HTMLElement {
  const card = [...document.querySelectorAll<HTMLElement>(".target-card")].find((c) => c.textContent?.includes(pdb));
  if (!card) throw new Error(`no hay tarjeta de ${pdb}`);
  return card;
}

describe("catálogo de receptores: tarjeta de un receptor que no se puede preparar (QA1-003)", () => {
  const targets = [
    receptor("1AAA"),
    receptor("6S1Z", { disponible: false, motivo_no_disponible: EXCEPCION }),
    receptor("1M9Z", { disponible: false, motivo_no_disponible: FRASE }),
  ];

  it("el recuadro «Preparación» de un receptor no disponible NO dice «Listo»", () => {
    montar(targets);
    // Control positivo: el receptor disponible sí dice «Listo».
    expect(within(tarjeta("1AAA")).getByText("Listo")).toBeTruthy();
    // Los dos no disponibles llegan con `is_prepared` verdadero y `calibration_status: listo`.
    expect(within(tarjeta("6S1Z")).queryByText("Listo")).toBeNull();
    expect(within(tarjeta("1M9Z")).queryByText("Listo")).toBeNull();
    // Dicen lo que son, en el recuadro además de en el aviso.
    expect(within(tarjeta("6S1Z")).getAllByText(/no disponible/i).length).toBeGreaterThanOrEqual(2);
  });

  it("la excepción de Python no se enseña como motivo: va una frase y el texto técnico detrás de «Detalle técnico»", () => {
    montar(targets);
    const card = tarjeta("6S1Z");
    expect(within(card).getByText(/no puede construir este receptor/i)).toBeTruthy();
    // La tarjeta ya lleva un <details> propio («Qué significa»): se busca el del texto técnico.
    const detalle = [...card.querySelectorAll("details")].find((d) => d.textContent?.includes("RuntimeError"));
    expect(detalle).toBeTruthy();
    expect(detalle?.open).toBe(false);
    expect(within(card).getByText("Detalle técnico")).toBeTruthy();
    // Fuera del desplegable, la excepción no aparece.
    const visible = card.textContent?.replace(detalle?.textContent ?? "", "") ?? "";
    expect(visible).not.toContain("RuntimeError");
  });

  it("un motivo ya redactado se enseña tal cual, sin desplegable", () => {
    montar(targets);
    const card = tarjeta("1M9Z");
    expect(within(card).getByText(/Meeko elimina 1 residuo/)).toBeTruthy();
    expect([...card.querySelectorAll("details")].some((d) => d.textContent?.includes("Detalle técnico"))).toBe(false);
  });
});

describe("catálogo de demostración", () => {
  it("ofrece las tres secciones como pestañas, con la Demostración abierta de entrada", () => {
    montar([receptor("1AAA"), receptor("LOCAL", { is_private: true })]);
    expect(screen.getByRole("tablist", { name: "Secciones del catálogo" })).toBeTruthy();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Demostración1", "Tus receptores1", "Verificados0"]);
    expect(pestana(/Demostración/).getAttribute("aria-selected")).toBe("true");
    expect(pestana(/Tus receptores/).getAttribute("aria-selected")).toBe("false");
    expect(pestana(/Verificados/).getAttribute("aria-selected")).toBe("false");
    // Sólo la sección activa se pinta, y el panel lleva el nombre de su pestaña.
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Demostración"]);
    expect(screen.getByRole("tabpanel", { name: /Demostración/ })).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Demostración" })).getByText("Receptor 1AAA")).toBeTruthy();
    expect(screen.queryByText("Receptor LOCAL")).toBeNull();
  });
  it("cada pestaña enseña su sección: la invitación a subir y el estado vacío de Verificados", () => {
    montar([receptor("1AAA"), receptor("LOCAL", { is_private: true })]);
    abrir(/Tus receptores/);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Tus receptores"]);
    expect(within(screen.getByRole("region", { name: "Tus receptores" })).getByRole("button", { name: "Subir receptor" })).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Tus receptores" })).getByText("Receptor LOCAL")).toBeTruthy();
    expect(screen.queryByText("Receptor 1AAA")).toBeNull();
    abrir(/Verificados/);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Verificados"]);
    expect(screen.getByText(/Todavía no hay receptores verificados en esta versión/)).toBeTruthy();
    expect(pestana(/Verificados/).getAttribute("aria-selected")).toBe("true");
  });
  it("con las flechas, Inicio y Fin se pasa de pestaña y el foco acompaña a la selección", () => {
    montar([receptor("1AAA"), receptor("LOCAL", { is_private: true })]);
    const demostracion = pestana(/Demostración/);
    demostracion.focus();
    // Sólo la pestaña activa entra en el orden del tabulador.
    expect(demostracion.tabIndex).toBe(0);
    expect(pestana(/Tus receptores/).tabIndex).toBe(-1);
    fireEvent.keyDown(demostracion, { key: "ArrowRight" });
    expect(pestana(/Tus receptores/).getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(pestana(/Tus receptores/));
    fireEvent.keyDown(pestana(/Tus receptores/), { key: "End" });
    expect(pestana(/Verificados/).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(pestana(/Verificados/), { key: "ArrowRight" });
    expect(pestana(/Demostración/).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(pestana(/Demostración/), { key: "ArrowLeft" });
    expect(pestana(/Verificados/).getAttribute("aria-selected")).toBe("true");
    fireEvent.keyDown(pestana(/Verificados/), { key: "Home" });
    expect(pestana(/Demostración/).getAttribute("aria-selected")).toBe("true");
    expect(document.activeElement).toBe(pestana(/Demostración/));
  });
  it("al volver a abrir el menú empieza otra vez en la Demostración", () => {
    const targets = [receptor("1AAA"), receptor("LOCAL", { is_private: true })];
    const { rerender } = render(modal(targets));
    abrir(/Tus receptores/);
    expect(pestana(/Tus receptores/).getAttribute("aria-selected")).toBe("true");
    rerender(modal(targets, () => {}, false));
    expect(screen.queryByRole("tablist")).toBeNull();
    rerender(modal(targets, () => {}, true));
    expect(pestana(/Demostración/).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByText("Receptor 1AAA")).toBeTruthy();
  });
  it("la evidencia verificada muestra rho, intervalo, n, panel y pose", () => {
    montar([receptor("8HFI", { seccion_catalogo: "verificado", verificacion: verificacionDePrueba })]);
    abrir(/Verificados/);
    const section = screen.getByRole("region", { name: "Verificados" });
    expect(within(section).getByText("ρ = 0.41 (IC 95 %: 0.17–0.61; n = 57; Ki, CHEMBL853189)")).toBeTruthy();
    expect(within(section).getByText("Pose del cristal reproducida en 4 de 5 semillas (RMSD ≤ 2 Å)")).toBeTruthy();
    expect(within(section).getByText("Verificado")).toBeVisible();
    expect(within(section).getByText(/Medido con exhaustividad 8, 9 poses y semilla 42/)).toBeVisible();
    expect(within(section).getByText(/El receptor se acopló sin los iones del depósito/)).toBeVisible();
    expect(within(section).getByText(/El panel es casi entero una serie de análogos/)).toBeVisible();
    expect(within(section).getByText(/desplazamiento de \[3H\]nisoxetina; el pH, la temperatura/)).toBeVisible();
  });
  it("un aviso medido no impide elegir un receptor de demostración", () => {
    const select = vi.fn();
    montar([receptor("1UZJ", { avisos_catalogo: ["SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA"] })], select);
    expect(within(tarjeta("1UZJ")).getByText(/el sitio podría ser un contacto del cristal/)).toBeTruthy();
    fireEvent.click(tarjeta("1UZJ"));
    expect(select).toHaveBeenCalledWith("1UZJ");
  });
  it("busca propios y comunidad junto al catálogo, y cada pestaña cuenta lo suyo", () => {
    montar([receptor("1AAA"), receptor("PRIVADO", { is_private: true }), receptor("COMUNIDAD", { is_community: true })]);
    fireEvent.change(screen.getByPlaceholderText(/Buscar por PDB ID/i), { target: { value: "Receptor" } });
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Demostración1", "Tus receptores2", "Verificados0"]);
    expect(document.querySelectorAll(".target-card")).toHaveLength(1);
    abrir(/Tus receptores/);
    expect(document.querySelectorAll(".target-card")).toHaveLength(2);
  });
  it("la búsqueda conserva las pestañas con su recuento y las tarjetas de demostración sólo conservan avisos y respaldo", () => {
    montar([receptor("1UZJ", { avisos_catalogo: ["SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA"] }), receptor("LOCAL", { is_private: true })]);
    fireEvent.change(screen.getByPlaceholderText(/Buscar por PDB ID/i), { target: { value: "Receptor" } });
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Demostración1", "Tus receptores1", "Verificados0"]);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Demostración"]);
    expect(document.querySelectorAll(".target-card")).toHaveLength(1);
    expect(within(tarjeta("1UZJ")).queryByText("Demostración")).toBeNull();
    expect(within(tarjeta("1UZJ")).getByText(/el sitio podría ser un contacto del cristal/)).toBeVisible();
    expect(within(tarjeta("1UZJ")).getByText(/Respaldo sin comprobar/)).toBeVisible();
  });
  it("si la sección abierta no tiene coincidencias, lo dice y señala dónde las hay", () => {
    montar([receptor("1AAA"), receptor("LOCAL", { is_private: true, name: "Mi receptor propio" })]);
    fireEvent.change(screen.getByPlaceholderText(/Buscar por PDB ID/i), { target: { value: "propio" } });
    expect(document.querySelectorAll(".target-card")).toHaveLength(0);
    expect(pestana(/Demostración/).textContent).toBe("Demostración0");
    expect(screen.getByRole("status").textContent).toBe("Ningún receptor de esta sección coincide con la búsqueda. Hay coincidencias en: Tus receptores (1).");
    // La búsqueda no cambia de pestaña por su cuenta: eso lo decide quien mira.
    expect(pestana(/Demostración/).getAttribute("aria-selected")).toBe("true");
    abrir(/Tus receptores/);
    expect(document.querySelectorAll(".target-card")).toHaveLength(1);
    expect(screen.queryByRole("status")).toBeNull();
  });
  it("el texto y los avisos también están en inglés", () => {
    vi.spyOn(window.navigator, "language", "get").mockReturnValue("en-US");
    montar([receptor("1UZJ", { structural_family: "protein_interaction", avisos_catalogo: ["SITIO_FUERA_DE_LA_UNIDAD_BIOLOGICA"] }), receptor("5COP")]);
    expect(screen.getByRole("tablist", { name: "Catalog sections" })).toBeTruthy();
    expect(screen.getAllByRole("tab").map((tab) => tab.textContent)).toEqual(["Demo2", "Your receptors0", "Verified0"]);
    expect(screen.getAllByRole("heading", { level: 3 }).map((h) => h.textContent)).toEqual(["Demo"]);
    expect(screen.getByRole("heading", { name: "Protease" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Protein–Protein Interaction" })).toBeTruthy();
    expect(screen.getByText(/the site could be a crystal contact/)).toBeTruthy();
    abrir(/Verified/);
    expect(screen.getByText(/There are no verified receptors in this version yet/)).toBeTruthy();
  });
});

describe("catálogo de receptores: eje «Familia terapéutica» (QA1-006)", () => {
  it("sin datos terapéuticos no se ofrece el conmutador y todo se agrupa por familia química", () => {
    montar([receptor("1AAA"), receptor("1BBB", { structural_family: "kinase" })]);
    expect(screen.queryByText(/Familia terap/i)).toBeNull();
    expect(screen.queryByText(/No clasificada/i)).toBeNull();
    // Un único eje: no hay conmutador (tampoco el de «Familia química») y los grupos son los químicos.
    expect(screen.queryByText(/Familia qu/i)).toBeNull();
    expect(screen.getByText(/Proteasa/i)).toBeTruthy();
  });

  it("con un solo receptor con familia terapéutica, el conmutador sí aparece", () => {
    montar([receptor("1AAA", { therapeutic_family: "Neurología" }), receptor("1BBB")]);
    expect(screen.getByText(/Familia terap/i)).toBeTruthy();
  });

  it("una preferencia «terapéutica» guardada no deja el catálogo sin clasificar cuando no hay datos", () => {
    writeClassificationMode("terapeutica");
    montar([receptor("1AAA"), receptor("1BBB")]);
    expect(screen.queryByText(/No clasificada/i)).toBeNull();
    expect(screen.getByText(/Proteasa/i)).toBeTruthy();
  });
});

describe("catálogo de receptores: «Crear variante» sobre un receptor no disponible (QA1-003, decisión del 2026-10-04)", () => {
  const targets = [
    receptor("1AAA"),
    receptor("6S1Z", { disponible: false, motivo_no_disponible: EXCEPCION }),
  ];

  it("el botón está desactivado en un receptor no disponible y dice por qué", () => {
    montar(targets);
    const boton = within(tarjeta("6S1Z")).getByRole("button", { name: /crear variante/i }) as HTMLButtonElement;
    expect(boton.disabled).toBe(true);
    expect(boton.title).toMatch(/no se puede preparar/i);
  });

  it("control positivo: en un receptor disponible sigue activo y abre el diálogo", () => {
    montar(targets);
    const boton = within(tarjeta("1AAA")).getByRole("button", { name: /crear variante/i }) as HTMLButtonElement;
    expect(boton.disabled).toBe(false);
    expect(boton.title).toBe("");
    fireEvent.click(boton);
    expect(screen.getByText("Nueva variante de preparación")).toBeTruthy();
  });

  it("pulsar el botón desactivado no abre el diálogo", () => {
    montar(targets);
    fireEvent.click(within(tarjeta("6S1Z")).getByRole("button", { name: /crear variante/i }));
    expect(screen.queryByText("Nueva variante de preparación")).toBeNull();
  });
});

describe("catálogo de receptores: búsqueda por palabras (QA1-004)", () => {
  const targets = [
    receptor("1O86", { name: "ANGIOTENSIN CONVERTING ENZYME (ACE)", structural_family: "kinase" }),
    receptor("1AAA", { name: "ACETYLCHOLINESTERASE" }),
    receptor("1BBB", { name: "DEACETYLASE" }),
    receptor("1CCC", { name: "ALCALIGENACEAE PROTEIN" }),
    receptor("1DDD", { name: "Otra proteasa" }),
    receptor("1EEE", { name: "Otra proteasa más" }),
  ];

  function buscar(texto: string) {
    fireEvent.change(screen.getByPlaceholderText(/Buscar por PDB ID/i), { target: { value: texto } });
  }
  const pdbsVisibles = () =>
    [...document.querySelectorAll<HTMLElement>(".target-card")].map((c) => /1[A-Z0-9]{3}/.exec(c.textContent ?? "")?.[0]);

  it("buscar «ACE» no devuelve lo que sólo lo contiene por la mitad de una palabra", () => {
    montar(targets);
    buscar("ACE");
    const visibles = pdbsVisibles();
    expect(visibles).toContain("1O86");
    expect(visibles).toContain("1AAA");
    for (const falso of ["1BBB", "1CCC", "1DDD", "1EEE"]) expect(visibles).not.toContain(falso);
  });

  it("la palabra exacta va antes que el comienzo de palabra, y su grupo antes que uno más grande", () => {
    montar(targets);
    // Sin búsqueda manda el tamaño del grupo: el de proteasas (5) abre la lista, no el de 1O86 (1).
    expect(pdbsVisibles()[0]).not.toBe("1O86");
    buscar("ACE");
    const visibles = pdbsVisibles();
    expect(visibles.indexOf("1O86")).toBeLessThan(visibles.indexOf("1AAA"));
    // Con búsqueda manda la mejor coincidencia: 1O86 (quinasa, palabra exacta) abre la lista aunque su
    // grupo sólo tenga un receptor y el de 1AAA (proteasa) tuviera más antes de filtrar.
    expect(visibles[0]).toBe("1O86");
  });

  it("borrar la búsqueda devuelve el orden por tamaño de grupo", () => {
    montar(targets);
    buscar("ACE");
    buscar("");
    expect(pdbsVisibles()).toHaveLength(6);
    expect(pdbsVisibles()[0]).not.toBe("1O86");
  });
});

describe("selector compartido: intento publicado real", () => {
  it.each(["es", "en"] as const)("publica el NO_GO debajo del estado vacío y conserva la búsqueda en %s", async (locale) => {
    vi.spyOn(window.navigator, "language", "get").mockReturnValue(locale === "es" ? "es-MX" : "en-US");
    const onSelect = vi.fn();
    montar([receptor("8HFI", { name: "Transportador de noradrenalina", intentos_verificacion: [intentoPublicado] }), receptor("1AAA")], onSelect);
    abrir(locale === "es" ? /Verificados/ : /Verified/);
    const region = await screen.findByRole("region", { name: locale === "es" ? "Intentos publicados" : "Published attempts" });
    const empty = screen.getByText(locale === "es" ? /Todavía no hay receptores verificados/ : /There are no verified receptors/);
    expect(empty.compareDocumentPosition(region) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(within(region).getByText(/ρ = 0.13.*n = 57/)).toBeVisible();
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "8HFI" } });
    // El receptor del intento sigue en la Demostración: se vuelve a su pestaña para elegirlo.
    abrir(locale === "es" ? /Demostración/ : /Demo/);
    const card = tarjeta("8HFI");
    expect(card.closest("section")).toHaveAccessibleName(locale === "es" ? "Demostración" : "Demo");
    const note = within(card).getByRole("note");
    expect(note.textContent).toBe(locale === "es" ? "Verificación intentada: no superó la calibración" : "Verification attempted: did not pass calibration");
    expect(note.title).toContain("CAL-8HFI-01");
    expect(within(card).queryByText(locale === "es" ? "Verificado" : "Verified", { exact: true })).toBeNull();
    fireEvent.click(card);
    expect(onSelect).toHaveBeenCalledWith("8HFI");
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "1AAA" } });
    abrir(locale === "es" ? /Verificados/ : /Verified/);
    expect(screen.queryByRole("region", { name: locale === "es" ? "Intentos publicados" : "Published attempts" })).toBeNull();
    abrir(locale === "es" ? /Demostración/ : /Demo/);
    expect(tarjeta("1AAA")).toBeVisible();
  });
});
