import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { RendererSettings } from "../RendererSettings";

const api = vi.hoisted(() => ({
  configurarMolcy: vi.fn(), instalacionMolcy: vi.fn(), instalarBlenderMolcy: vi.fn(),
  FALTA_PARA_EL_PAQUETE: new Set(["falta_blender", "blender_antiguo", "falta_addon"]) as ReadonlySet<string>,
}));
vi.mock("@/lib/molcy", () => api);
vi.mock("@/context/LanguageContext", () => ({ useLanguage: () => ({ locale: "es", t: (key: string) => key }) }));

const estado = { estado: "inactivo", version: "5.2.2", descarga_bytes: 404453484, reserva_bytes: 1, ruta: "C:/datos/molcy/blender/blender.exe",
  instalado: false, configuracion: {} };
const incluido = { disponible: false, motivo: null, motor: "C:/Program Files/MolDesign/tools/molcy", motor_origen: "incluido" as const, motor_incluido: true };
const sinMotor = { disponible: false, motivo: null, motor_origen: "ninguno" as const, motor_incluido: false };

beforeEach(() => {
  vi.clearAllMocks();
  api.instalacionMolcy.mockResolvedValue(estado);
  api.configurarMolcy.mockResolvedValue(estado);
});
afterEach(cleanup);

/**
 * Descargar e instalar vive en el estudio, debajo del guion visual (propietario, 2026-10-12): aquí sólo se elige qué Blender
 * usa Molcy. Antes había un «Descargar Blender para MolDesign» en esta columna además del botón de Molecular Nodes.
 */
describe("Configuración de Molcy: elegir Blender, no descargarlo", () => {
  it("si falta Blender, no ofrece descargar, señala el estudio y no se abre sola", async () => {
    const { container } = render(<RendererSettings renderer={{ ...incluido, motivo_codigo: "falta_blender" }} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    expect(screen.queryByRole("button", { name: "cy_install_blender" })).toBeNull();
    expect(screen.getByText("cy_setup_hint")).toBeTruthy();
    expect(container.querySelector("details")?.open).toBe(false);
    expect(api.instalarBlenderMolcy).not.toHaveBeenCalled();
  });

  it("si lo que falla es de configuración, se abre", async () => {
    const { container } = render(<RendererSettings renderer={{ ...incluido, motivo_codigo: "addon_no_carga" }} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    expect(container.querySelector("details")?.open).toBe(true);
  });
});

/**
 * El motor Molcy viaja dentro del instalador y es el que pone el cierre de MolDesign al final de todo video (decisión del
 * propietario, 2026-10-04): la pantalla no ofrece elegir otro motor. Un campo así sería la puerta para quitar el cierre.
 */
describe("Configuración de Molcy: el motor que viaja con MolDesign y nadie cambia", () => {
  it("con motor incluido lo dice y no hay ningún campo de carpeta del motor", async () => {
    render(<RendererSettings renderer={incluido} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    expect(screen.getByTestId("motor-incluido").textContent).toBe("cy_engine_included");
    expect(screen.queryByTestId("motor-propio")).toBeNull();
    expect(screen.queryByLabelText("cy_engine_path")).toBeNull();
    expect(screen.queryByText("cy_engine_missing")).toBeNull();
  });

  it("sin motor incluido avisa que hay que reinstalar y tampoco ofrece elegir uno", async () => {
    render(<RendererSettings renderer={sinMotor} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    expect(screen.getByRole("alert").textContent).toBe("cy_engine_missing");
    expect(screen.queryByTestId("motor-incluido")).toBeNull();
    expect(screen.queryByLabelText("cy_engine_path")).toBeNull();
  });

  it("guardar manda siempre motor null, aunque la configuración guardada traiga un motor ajeno", async () => {
    api.instalacionMolcy.mockResolvedValue({ ...estado, configuracion: { modo: "administrado", motor: "E:/otro" } });
    render(<RendererSettings renderer={incluido} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    // «Guardar» espera a que la opción esté decidida (instalación y renderizador a la vista).
    await waitFor(() => expect(screen.getByRole("button", { name: "cy_save_setup" })).not.toBeDisabled());
    fireEvent.click(screen.getByRole("button", { name: "cy_save_setup" }));
    await waitFor(() => expect(api.configurarMolcy).toHaveBeenCalledWith({ modo: "administrado", blender: null, motor: null }));
  });

  it("con Blender existente manda su ruta y el motor sigue en null", async () => {
    api.instalacionMolcy.mockResolvedValue({ ...estado, configuracion: { modo: "existente", blender: "D:/Blender/blender.exe" } });
    render(<RendererSettings renderer={incluido} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect((screen.getByLabelText("cy_blender_path") as HTMLInputElement).value).toBe("D:/Blender/blender.exe"));
    fireEvent.click(screen.getByRole("button", { name: "cy_save_setup" }));
    await waitFor(() => expect(api.configurarMolcy).toHaveBeenCalledWith({ modo: "existente", blender: "D:/Blender/blender.exe", motor: null }));
  });
});

/**
 * Autodetección (2026-10-04): el backend informa de los Blender que halló (instalador oficial en cualquier carpeta, Steam, Tienda, gestores,
 * ZIP). La pantalla los ofrece en una lista en vez de pedir una ruta que el investigador no sabe cuál es.
 */
const hallado = (ruta: string, origen: string, version: string | null, apto: boolean | null) => ({ ruta, origen, version, apto });
const RAIZ_E = hallado("E:/blender.exe", "programa", "5.2.2", true);
const STEAM = hallado("D:/SteamLibrary/steamapps/common/Blender/blender.exe", "steam", "5.2", true);
const VIEJO = hallado("C:/Program Files/Blender Foundation/Blender 4.5/blender.exe", "programa", "4.5", false);
const SIN_VERSION = hallado("C:/Users/yo/Downloads/blender-x/blender.exe", "portatil", null, null);
const con = (...lista: ReturnType<typeof hallado>[]) => ({ ...incluido, blenders_encontrados: lista } as never);

describe("Configuración de Molcy: los Blender encontrados en este equipo", () => {
  it("ofrece el hallado apto de entrada, con su origen y versión, y lo guarda sin pedir ninguna ruta", async () => {
    render(<RendererSettings renderer={con(RAIZ_E, VIEJO)} onChanged={vi.fn()} busy={false} />);
    const lista = await screen.findByTestId("blender-encontrado") as HTMLSelectElement;
    await waitFor(() => expect(lista.value).toBe("E:/blender.exe"));
    expect(screen.getByRole("button", { name: "cy_existing" }).getAttribute("aria-pressed")).toBe("true");
    const opciones = Array.from(lista.options).map(o => o.textContent);
    expect(opciones).toContain("cy_origin_programa · 5.2.2 — E:/blender.exe");
    fireEvent.click(screen.getByRole("button", { name: "cy_save_setup" }));
    await waitFor(() => expect(api.configurarMolcy).toHaveBeenCalledWith({ modo: "existente", blender: "E:/blender.exe", motor: null }));
  });

  it("un Blender demasiado viejo se muestra pero no se puede elegir", async () => {
    render(<RendererSettings renderer={con(RAIZ_E, VIEJO)} onChanged={vi.fn()} busy={false} />);
    const lista = await screen.findByTestId("blender-encontrado") as HTMLSelectElement;
    const viejo = Array.from(lista.options).find(o => o.value === VIEJO.ruta)!;
    expect(viejo.disabled).toBe(true);
    expect(viejo.textContent).toContain("cy_too_old");
    const bueno = Array.from(lista.options).find(o => o.value === RAIZ_E.ruta)!;
    expect(bueno.disabled).toBe(false);
  });

  it("si sólo hay uno viejo, el Blender de MolDesign (recomendado) queda elegido de entrada", async () => {
    render(<RendererSettings renderer={con(VIEJO)} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole("button", { name: "cy_managed" }).getAttribute("aria-pressed")).toBe("true"));
    expect(screen.queryByTestId("blender-encontrado")).toBeNull();  // la lista sólo aparece al elegir «mi Blender»
  });

  it("elegir otra entrada de la lista cambia la ruta que se guarda", async () => {
    render(<RendererSettings renderer={con(RAIZ_E, STEAM)} onChanged={vi.fn()} busy={false} />);
    const lista = await screen.findByTestId("blender-encontrado") as HTMLSelectElement;
    await waitFor(() => expect(lista.value).toBe(RAIZ_E.ruta));
    fireEvent.change(lista, { target: { value: STEAM.ruta } });
    expect((screen.getByLabelText("cy_blender_path") as HTMLInputElement).value).toBe(STEAM.ruta);
    fireEvent.click(screen.getByRole("button", { name: "cy_save_setup" }));
    await waitFor(() => expect(api.configurarMolcy).toHaveBeenCalledWith({ modo: "existente", blender: STEAM.ruta, motor: null }));
  });

  it("una ruta escrita a mano que no está en la lista se conserva y la lista muestra «otra ruta»", async () => {
    api.instalacionMolcy.mockResolvedValue({ ...estado, configuracion: { modo: "existente", blender: "Z:/mio/blender.exe" } });
    render(<RendererSettings renderer={con(RAIZ_E)} onChanged={vi.fn()} busy={false} />);
    const lista = await screen.findByTestId("blender-encontrado") as HTMLSelectElement;
    await waitFor(() => expect((screen.getByLabelText("cy_blender_path") as HTMLInputElement).value).toBe("Z:/mio/blender.exe"));
    expect(lista.value).toBe("");
    expect(lista.options[0].textContent).toBe("cy_detected_other");
  });

  it("una versión desconocida se dice como tal y se puede elegir (el sondeo decide)", async () => {
    render(<RendererSettings renderer={con(SIN_VERSION)} onChanged={vi.fn()} busy={false} />);
    const lista = await screen.findByTestId("blender-encontrado") as HTMLSelectElement;
    const opcion = Array.from(lista.options).find(o => o.value === SIN_VERSION.ruta)!;
    expect(opcion.disabled).toBe(false);
    expect(opcion.textContent).toContain("cy_version_unknown");
    await waitFor(() => expect(lista.value).toBe(SIN_VERSION.ruta));
  });

  it("sin ningún Blender hallado lo dice, deja la ruta a mano y el recomendado queda elegido", async () => {
    render(<RendererSettings renderer={con()} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByRole("button", { name: "cy_managed" }).getAttribute("aria-pressed")).toBe("true"));
    fireEvent.click(screen.getByRole("button", { name: "cy_existing" }));
    expect(screen.getByTestId("sin-blender-encontrado").textContent).toBe("cy_detected_none");
    expect(screen.getByLabelText("cy_blender_path")).toBeTruthy();
    expect(screen.queryByTestId("blender-encontrado")).toBeNull();
  });

  it("una consulta nueva con la misma lista no pisa lo que el investigador ya eligió", async () => {
    const { rerender } = render(<RendererSettings renderer={con(RAIZ_E)} onChanged={vi.fn()} busy={false} />);
    await screen.findByTestId("blender-encontrado");
    fireEvent.click(screen.getByRole("button", { name: "cy_managed" }));
    rerender(<RendererSettings renderer={con(hallado(RAIZ_E.ruta, "programa", "5.2.2", true))} onChanged={vi.fn()} busy={false} />);
    expect(screen.getByRole("button", { name: "cy_managed" }).getAttribute("aria-pressed")).toBe("true");
    expect(api.instalacionMolcy).toHaveBeenCalledTimes(1);
  });
});

/**
 * Sin saltos (2026-10-10, medido en el export): la opción salía marcada en «Blender de MolDesign» por defecto y, al llegar
 * la lista de los Blender del equipo, saltaba sola a «Usar mi Blender». Ahora no se marca nada hasta tener la instalación
 * y el renderizador, y se decide una vez.
 */
describe("Configuración de Molcy: la opción de Blender no salta sola", () => {
  it("sin renderizador no marca ninguna opción; al llegar la lista marca directamente la que toca", async () => {
    const marcadas: string[] = [];
    const { rerender } = render(<RendererSettings renderer={null} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(api.instalacionMolcy).toHaveBeenCalled());
    await Promise.resolve();
    for (const nombre of ["cy_managed", "cy_existing"]) {
      expect(screen.getByRole("button", { name: nombre }).getAttribute("aria-pressed"), nombre).toBe("false");
    }
    expect(screen.getByRole("button", { name: "cy_save_setup" })).toBeDisabled();
    const observador = new MutationObserver(() => {
      const marcada = screen.queryAllByRole("button").find(b => b.getAttribute("aria-pressed") === "true");
      if (marcada && marcadas.at(-1) !== marcada.textContent) marcadas.push(marcada.textContent ?? "");
    });
    observador.observe(document.body, { subtree: true, attributes: true, attributeFilter: ["aria-pressed"] });
    rerender(<RendererSettings renderer={con(RAIZ_E)} onChanged={vi.fn()} busy={false} />);
    await waitFor(() => expect(screen.getByRole("button", { name: "cy_existing" }).getAttribute("aria-pressed")).toBe("true"));
    observador.disconnect();
    expect(marcadas).toEqual(["cy_existing"]);
  });

  it("si el renderizador llega antes que la instalación, tampoco pasa por la opción equivocada", async () => {
    let resolver!: (valor: typeof estado) => void;
    api.instalacionMolcy.mockReturnValueOnce(new Promise(r => { resolver = r; }));
    render(<RendererSettings renderer={con(RAIZ_E)} onChanged={vi.fn()} busy={false} />);
    expect(screen.getByRole("button", { name: "cy_managed" }).getAttribute("aria-pressed")).toBe("false");
    expect(screen.getByRole("button", { name: "cy_existing" }).getAttribute("aria-pressed")).toBe("false");
    resolver(estado);
    await waitFor(() => expect(screen.getByRole("button", { name: "cy_existing" }).getAttribute("aria-pressed")).toBe("true"));
    expect(screen.getByRole("button", { name: "cy_managed" }).getAttribute("aria-pressed")).toBe("false");
  });
});
