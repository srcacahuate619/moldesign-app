import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import MolcyPage from "../page";
import { AUTO_PRESENTATION } from "@/components/molcy/PresentationControls";
import { KeepAliveContext } from "@/context/KeepAliveContext";
import { verificacionDePrueba } from "@/lib/__tests__/fixtures/verificacionReceptor";
import type { Target } from "@/lib/api";

const sello = vi.hoisted(() => ({ getResult: vi.fn(), targets: [] as Target[] }));
vi.mock("@/lib/api", async load => ({ ...await load<object>(), getEvaluationResult: sello.getResult }));
vi.mock("@/hooks/useCatalogoDeReceptores", () => ({ useCatalogoDeReceptores: () => sello.targets }));

const api = vi.hoisted(() => ({
  RESOLUCIONES_FOTO: ["720p", "1080p", "1440p", "4k"],
  // Las constantes del paquete Blender + Molecular Nodes que usa la tarjeta del estudio (las reales de lib/molcy.ts).
  FALTA_PARA_EL_PAQUETE: new Set(["falta_blender", "blender_antiguo", "falta_addon"]) as ReadonlySet<string>,
  MOLECULAR_NODES_MB_MEDIDOS: 133, ID_AVISO_PAQUETE_MOLCY: "molcy:paquete",
  crearFotosMolcy: vi.fn(), tomarFotoMolcy: vi.fn(), vistaMolcy: vi.fn(), imagenMolcy: vi.fn(), estimacionFotoMolcy: vi.fn(),
  descargarFotoMolcy: vi.fn(), revelarMolcy: vi.fn(),
  fuentesMolcy: vi.fn(), renderizadorMolcy: vi.fn(), recursosMolcy: vi.fn(), crearMolcy: vi.fn(),
  estadoMolcy: vi.fn(), descargarMolcy: vi.fn(), videoMolcy: vi.fn(), fotogramaMolcy: vi.fn(), pieDelFotograma: vi.fn(),
  estadoAddonMolcy: vi.fn(), instalarAddonMolcy: vi.fn(),
  instalacionMolcy: vi.fn(), instalarBlenderMolcy: vi.fn(), configurarMolcy: vi.fn(), cancelarBlenderMolcy: vi.fn(),
  salidaMolcy: vi.fn(), fijarSalidaMolcy: vi.fn(), elegirCarpetaSalidaMolcy: vi.fn(),
  trabajosMolcy: vi.fn(), cancelarMolcy: vi.fn(), eliminarMolcy: vi.fn(), descargarProcedenciaMolcy: vi.fn(),
}));
// El pie del fotograma en vivo es una función pura: se usa la real y se espía qué recibe.
vi.mock("@/lib/molcy", async load => {
  api.pieDelFotograma.mockImplementation((await load<typeof import("@/lib/molcy")>()).pieDelFotograma);
  return api;
});
const auth = vi.hoisted(() => ({ userId: "usuario-qa" }));
vi.mock("@/lib/auth", () => ({ useAuth: () => ({ user: { user_id: auth.userId } }) }));
const language = vi.hoisted(() => ({ locale: "es" as "es" | "en" }));
vi.mock("@/context/LanguageContext", async () => {
  const { resultados } = await import("@/context/traducciones/resultados");
  const t = (key: string) => (resultados[language.locale] as Record<string,string>)[key] ?? key;
  return { useLanguage: () => ({ locale: language.locale, t }) };
});
vi.mock("@/components/interfaces/pro/CustomReceptorModal", () => ({
  CustomReceptorModal: () => <div role="dialog">Formulario existente</div>,
}));

const fuentes = {
  moldex: [{ id: "molecule-1", task_id: "run-2026", nombre: "Aspirina", receptor: "1HSG", disponible: true, motivo: null }],
  receptores: [{ id: "USR_QA", nombre: "Receptor propio", propio: true, disponible: true, motivo: null }],
};
const resources = { cpu_hilos:4, cpu_hilos_disponibles:8, cpu_hilos_maximos:6, cpu_uso_actual_pct:0,
  gpu_vram_monitorizable:true, gpu_vram_total_mib:8192, gpu_vram_libre_mib:6144,
  gpu_vram_reserva_mib:2048, gpu_vram_max_mib:4096, gpu_vram_recomendado_mib:2048 };

// /molcy/recursos?task_id=… trae el espacio de esa corrida y lo rotula con `espacio_task_id`; la interfaz
// ya no usa el espacio general del renderizador para una corrida de Moldex. El simulacro lo imita: devuelve
// el espacio que cada prueba declaró en `renderizadorMolcy`, rotulado con la corrida que se pidió.
async function recursosConEspacio(taskId?: string | null, extra: object = {}, salidaId?: string | null) {
  let espacio: object = {};
  for (const resultado of [...api.renderizadorMolcy.mock.results].reverse()) {
    try {
      const valor = await resultado.value;
      if (valor && ("espacio" in valor || "espacio_fotos" in valor)) {
        espacio = { espacio: valor.espacio, espacio_fotos: valor.espacio_fotos };
        break;
      }
    } catch { /* un sondeo fallido no declara espacio */ }
  }
  return { ...resources, ...extra, ...espacio, espacio_task_id: taskId ?? null, espacio_salida_id: salidaId ?? null };
}

// Elegir una corrida pide su espacio en disco a /molcy/recursos; hasta que llega la interfaz declara
// «espacio desconocido» y no deja generar. Las pruebas esperan a que se resuelva en vez de suponerlo.
async function esperarEspacio() {
  await waitFor(() => expect(screen.queryByText("cy_space_unknown")).not.toBeInTheDocument());
}

beforeEach(() => {
  auth.userId = "usuario-qa";
  language.locale = "es";
  localStorage.clear();
  vi.clearAllMocks();
  sello.targets = [];
  sello.getResult.mockReset();
  api.salidaMolcy.mockResolvedValue({ disponible: false, global: null, problema: null, predeterminada: "C:/MolDesign/data/molcy" });
  api.recursosMolcy.mockImplementation((taskId?: string | null, salidaId?: string | null) => recursosConEspacio(taskId, {}, salidaId));
  api.estimacionFotoMolcy.mockResolvedValue({ estimado_s: null, muestras: 0 });
  api.crearFotosMolcy.mockResolvedValue({ id: "fotos-1", estado: "en_cola", tipo: "fotos", fase: "preparando" });
  api.fuentesMolcy.mockResolvedValue(fuentes);
  api.renderizadorMolcy.mockResolvedValue({ ...resources, disponible: true, motivo: null, gpu_disponible: true,
    foto_disponible: true, foto_gpu_disponible: true, foto_gpu_nombres: ["GPU de prueba"], espacio: {
    biblioteca: { libre_bytes: 20e9, necesario_bytes: 8e9, disponible: true },
    social_vertical: { libre_bytes: 20e9, necesario_bytes: 5e9, disponible: true },
    previsualizacion: { libre_bytes: 20e9, necesario_bytes: 3e9, disponible: true },
  }, espacio_fotos: { "4k": { libre_bytes: 20e9, necesario_bytes: 1.2e9, disponible: true } } });
  api.trabajosMolcy.mockResolvedValue({ trabajos: [] });
  api.instalacionMolcy.mockResolvedValue({ estado: "inactivo", ruta: "C:/MolDesign/tools/blender/blender.exe", version: "5.2.2", descarga_bytes: 404453484, reserva_bytes: 4 * 2**30, instalado: false, configuracion: {} });
  api.estadoAddonMolcy.mockResolvedValue({ estado: "inactivo" });
  api.crearMolcy.mockResolvedValue({ id: "job-1", estado: "en_cola" });
  api.fotogramaMolcy.mockResolvedValue(null);
  URL.revokeObjectURL = vi.fn();
});
afterEach(cleanup);

describe("Molcy desde fuentes verificables", () => {
  it("compara el snapshot de la fuente de Moldex y deja el receptor sin corrida", async () => {
    sello.targets = [{ pdb_id: "8HFI", name: "Receptor verificado", seccion_catalogo: "verificado", verificacion: verificacionDePrueba } as Target];
    sello.getResult.mockResolvedValue({ receptor_sha256: "otro", docking_protocol: { exhaustiveness: 32, num_poses: 9 } });
    api.fuentesMolcy.mockResolvedValue({ moldex: [{ ...fuentes.moldex[0], receptor: "8HFI" }], receptores: [{ id: "8HFI", nombre: "Receptor verificado", disponible: true, motivo: null }] });
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    expect(await screen.findByText("cat_receptor_distinto")).toBeVisible();
    expect(screen.getByText("cat_parametros_distintos")).toBeVisible();
    expect(screen.getByText("cat_parametros_sin_declarar")).toBeVisible();
    expect(sello.getResult).toHaveBeenCalledExactlyOnceWith("molecule-1", "run-2026");
    fireEvent.click(screen.getByRole("button", { name: "cy_origen_receptor" }));
    fireEvent.click(screen.getByRole("tab", { name: "cat_verificados" }));
    fireEvent.click(await screen.findByRole("button", { name: /Receptor verificado.*8HFI/ }));
    expect(screen.getAllByText("cat_verificado")).toHaveLength(2);
    for (const badge of screen.getAllByText("cat_verificado")) expect(badge).toBeVisible();
    expect(screen.queryByText("cat_receptor_distinto")).toBeNull();
    expect(screen.queryByText("cat_parametros_sin_declarar")).toBeNull();
    expect(sello.getResult).toHaveBeenCalledTimes(1);
  });
  it("habilita Búsqueda solo para una corrida que declara la traza y envía esa corrida", async () => {
    const contract = await vi.importActual<typeof import("@/lib/molcy")>("@/lib/molcy");
    const payload = {...fuentes,moldex:[{...fuentes.moldex[0],escenas_disponibles:["resultado","receptor","busqueda"]}]};
    api.fuentesMolcy.mockImplementation(async () => {
      contract.validarMolcy("/molcy/fuentes", payload);
      return payload;
    });
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    const search=screen.getByRole("button",{name:/Búsqueda.*03/});
    expect(search).toBeEnabled();
    fireEvent.click(search);
    expect(screen.queryByText("cy_busqueda_falta")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:/Generar video/}));
    await waitFor(()=>expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({task_id:"run-2026",escena:"busqueda"})));
    fireEvent.click(screen.getByRole("button", {name:"cy_origen_receptor"}));
    fireEvent.click(screen.getByRole("tab", {name:"cy_catalog_own"}));
    expect(screen.getByRole("button", {name:/Receptor propio.*USR_QA/})).toBeInTheDocument();
  });
  it("habilita Ensamble sólo para una corrida de ensamble verificable y envía esa escena", async () => {
    const contract = await vi.importActual<typeof import("@/lib/molcy")>("@/lib/molcy");
    const payload = {...fuentes,moldex:[{...fuentes.moldex[0],escenas_disponibles:["receptor","ensamble"]}]};
    api.fuentesMolcy.mockImplementation(async () => {
      contract.validarMolcy("/molcy/fuentes", payload);
      return payload;
    });
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    expect(screen.getByRole("button",{name:/Ensamble.*04/})).toBeDisabled();
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    const ensemble = screen.getByRole("button",{name:/Ensamble.*04/});
    expect(ensemble).toBeEnabled();
    fireEvent.click(ensemble);
    expect(screen.queryByText("cy_ensamble_falta")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:/Generar video/}));
    await waitFor(()=>expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({task_id:"run-2026",escena:"ensamble"})));
  });
  it("no habilita Ensamble si la corrida no es un ensamble verificable y lo explica", async () => {
    api.fuentesMolcy.mockResolvedValue({...fuentes,moldex:[{...fuentes.moldex[0],escenas_disponibles:["resultado","receptor"]}]});
    render(<MolcyPage />);
    await screen.findByRole("option",{name:/Aspirina/});
    expect(screen.queryByText("cy_ensamble_falta")).not.toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("cy_elegir"),{target:{value:"run-2026"}});
    await esperarEspacio();
    expect(screen.getByRole("button",{name:/Ensamble.*04/})).toBeDisabled();
    expect(screen.getByText("cy_ensamble_falta")).toBeInTheDocument();
  });
  it("Ensamble no existe para un receptor solo: no hay corrida que contar", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option",{name:/Aspirina/});
    fireEvent.click(screen.getByRole("button", {name:"cy_origen_receptor"}));
    expect(screen.getByRole("button",{name:/Ensamble.*04/})).toBeDisabled();
    expect(screen.queryByText("cy_ensamble_falta")).not.toBeInTheDocument();
  });
  it("selecciona Receptor si esa corrida ya no conserva las poses", async () => {
    api.fuentesMolcy.mockResolvedValue({...fuentes,moldex:[{...fuentes.moldex[0],escenas_disponibles:["receptor"]}]});
    render(<MolcyPage />);
    await screen.findByRole("option",{name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"),{target:{value:"run-2026"}});
    await esperarEspacio();
    expect(screen.getByRole("button",{name:/Receptor.*02/})).toHaveAttribute("aria-pressed","true");
    expect(screen.getByRole("button",{name:/Resultado.*01/})).toBeDisabled();
    fireEvent.click(screen.getByRole("button",{name:/Generar video/}));
    await waitFor(()=>expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({task_id:"run-2026",escena:"receptor"})));
  });
  it("envía el task_id exacto de Moldex con la escena y formato elegidos", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /Generar video/ }));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalledWith({
      origen: "moldex", id: "molecule-1", task_id: "run-2026",
      escena: "resultado", formato: "vertical", dispositivo: "gpu", presentacion: AUTO_PRESENTATION,
    }));
  });

  it("dice en la pantalla de formato que todo video lleva el cierre de MolDesign y no ofrece quitarlo", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    expect(screen.getByTestId("aviso-cierre").textContent).toBe("cy_outro_note");
    expect(screen.queryByRole("checkbox", { name: /cierre|outro/i })).toBeNull();
    expect(screen.queryByLabelText(/cierre|outro/i)).toBeNull();
  });

  it("ofrece el receptor propio y reutiliza el formulario de subida", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.click(screen.getByRole("button", { name: "cy_origen_receptor" }));
    expect(screen.getByRole("tab", { name: "cat_demostracion" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(screen.getByRole("tab", { name: "cy_catalog_own" }));
    fireEvent.click(await screen.findByRole("button", { name: /Receptor propio.*USR_QA/ }));
    fireEvent.click(screen.getByRole("button", { name: /Generar video/ }));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({
      origen: "receptor", id: "USR_QA", escena: "receptor",
    })));
    fireEvent.click(screen.getByRole("button", { name: "cat_subir" }));
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("se abstiene cuando falta el renderizador local", async () => {
    api.renderizadorMolcy.mockResolvedValue({ disponible: false, motivo: "Falta Blender" });
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    expect(screen.getByRole("button", { name: /Generar video/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByText(/Falta Blender/)).toBeTruthy();
  });

  it("bloquea el formato si no alcanza la reserva de disco", async () => {
    api.renderizadorMolcy.mockResolvedValue({ disponible: true, motivo: null, gpu_disponible: true, espacio: {
      social_vertical: { libre_bytes: 1e9, necesario_bytes: 5e9, disponible: false },
    } });
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    expect(screen.getByRole("button", { name: /Generar video/ }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("alert").textContent).toContain("cy_space_low");
  });

  it("cuando falta Molecular Nodes, el estudio lo instala debajo del guion visual y la columna no repite el botón", async () => {
    vi.useFakeTimers();
    api.renderizadorMolcy.mockResolvedValue({ disponible: false, motivo: "Falta Molecular Nodes", motivo_codigo: "falta_addon" });
    api.instalarAddonMolcy.mockResolvedValue({ estado: "instalando", fase: "comprobando" });
    // El sondeo de la tarjeta debe reflejar la instalación iniciada; el mock global
    // devolvía «inactivo» y borraba el estado antes de observarlo bajo carga.
    api.estadoAddonMolcy.mockResolvedValueOnce({ estado: "inactivo" }).mockResolvedValue({ estado: "instalando", fase: "descargando" });
    try {
      await act(async () => { render(<MolcyPage />); });
      const estudio = screen.getByTestId("molcy-paquete-estudio");
      // Dentro del panel central y después del guion visual: donde se ve.
      const guion = screen.getByText("GUION VISUAL");
      expect(guion.closest("section")).toBe(estudio.closest("section"));
      expect(guion.compareDocumentPosition(estudio) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(within(estudio).getByTestId("paquete-molcy-porque")).toHaveTextContent("cy_pack_studio_why");
      expect(screen.getAllByRole("button", { name: "cy_addon_install" })).toHaveLength(1);
      expect(screen.getByText("cy_pack_needed_short")).toBeInTheDocument();
      const comprobar = screen.getByRole("button", { name: "cy_recheck" });
      expect(comprobar).not.toBeDisabled();
      await act(async () => { fireEvent.click(within(estudio).getByRole("button", { name: "cy_addon_install" })); });
      expect(api.instalarAddonMolcy).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
      expect(within(estudio).getByText(/cy_pack_step_addon/)).toBeInTheDocument();
      // Mientras Blender instala, la configuración espera.
      expect(comprobar).toBeDisabled();
    } finally {
      cleanup();
      vi.useRealTimers();
    }
  });

  it("al quedar listo el paquete, la página usa esa comprobación sin volver a lanzar Blender y la tarjeta se va", async () => {
    vi.useFakeTimers();
    const listo = { ...resources, disponible: true, motivo: null, gpu_disponible: false, foto_disponible: true, foto_gpu_disponible: false,
      version_blender: [5, 2, 2], molecular_nodes: "520.2.0" };
    // La página pregunta una vez; la tarjeta, al montarse, otra; el sondeo forzado tras instalar Blender dice «listo».
    api.renderizadorMolcy.mockResolvedValueOnce({ disponible: false, motivo: "No se encontró Blender.", motivo_codigo: "falta_blender" })
      .mockResolvedValueOnce({ disponible: false, motivo: "No se encontró Blender.", motivo_codigo: "falta_blender" })
      .mockResolvedValue(listo);
    const instalando = { estado: "instalando", fase: "descargando", ruta: "C:/MolDesign/data/molcy/blender/blender.exe", version: "5.2.2",
      descarga_bytes: 404453484, recibidos_bytes: 1, reserva_bytes: 5e9, instalado: false, configuracion: {} };
    api.instalarBlenderMolcy.mockResolvedValue(instalando);
    api.instalacionMolcy.mockResolvedValueOnce({ ...instalando, estado: "inactivo" })
      .mockResolvedValueOnce({ ...instalando, estado: "inactivo" })
      .mockResolvedValue({ ...instalando, estado: "completo", fase: "completo", instalado: true });
    try {
      await act(async () => { render(<MolcyPage />); });
      const estudio = screen.getByTestId("molcy-paquete-estudio");
      await act(async () => { fireEvent.click(within(estudio).getByRole("button", { name: "cy_pack_install_full" })); });
      expect(api.instalarBlenderMolcy).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(1500); });
      expect(screen.queryByTestId("molcy-paquete-estudio")).toBeNull();
      // Tres sondeos: página, tarjeta y el forzado tras instalar. La página no lanza un cuarto.
      expect(api.renderizadorMolcy).toHaveBeenCalledTimes(3);
      // Sin GPU, el estudio abre en fotos (la misma regla que al cargar).
      expect(screen.getByRole("button", { name: /cy_mode_photo/ })).toHaveAttribute("aria-pressed", "true");
    } finally {
      cleanup();
      vi.useRealTimers();
    }
  });

  it("sin EEVEE abre en fotos con la CPU y el vídeo explica que necesita GPU (decisión del 2026-10-08)", async () => {
    api.renderizadorMolcy.mockResolvedValue({ disponible: true, motivo: null,
      gpu_disponible: false, motivo_gpu: "Sin contexto GPU", foto_disponible: true, foto_gpu_disponible: false,
      espacio: { social_vertical: { libre_bytes: 20e9, necesario_bytes: 5e9, disponible: true } },
      espacio_fotos: { "4k": { libre_bytes: 20e9, necesario_bytes: 1.2e9, disponible: true } } });
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    await waitFor(() => expect(screen.getByRole("button", { name: /cy_mode_photo/ })).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByRole("button", { name: /cy_photo_device_gpu/ })).toBeDisabled();
    expect(screen.getByRole("button", { name: /cy_photo_device_cpu/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /Preparar tomas/ }));
    await waitFor(() => expect(api.crearFotosMolcy).toHaveBeenCalledWith(expect.objectContaining({
      task_id: "run-2026", escena: "resultado", orientacion: "vertical", dispositivo: "cpu" })));
    fireEvent.click(screen.getByRole("button", { name: /cy_mode_video/ }));
    expect(screen.getByTestId("video-sin-gpu")).toHaveTextContent("Sin contexto GPU");
    expect(screen.getByRole("button", { name: /Generar video/ })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: "cy_switch_to_photos" }));
    expect(screen.getByRole("button", { name: /cy_mode_photo/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("el vídeo no ofrece CPU: siempre se pide con GPU", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    expect(screen.getByRole("button", { name: /cy_mode_video/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.queryByRole("button", { name: /cy_photo_device_cpu/ })).toBeNull();
    expect(screen.getByText("cy_video_gpu_only")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /Generar video/ }));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({ dispositivo: "gpu" })));
    expect(api.crearMolcy.mock.calls[0][0]).not.toHaveProperty("cpu_hilos");
  });

  it("las fotos con GPU se piden con la orientación elegida y la marca se anuncia", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.click(screen.getByRole("button", { name: /cy_mode_photo/ }));
    expect(screen.getByTestId("aviso-marca")).toHaveTextContent("cy_photo_mark_note");
    expect(screen.getByRole("button", { name: /cy_photo_device_gpu/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /Horizontal/ }));
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /Preparar tomas/ }));
    await waitFor(() => expect(api.crearFotosMolcy).toHaveBeenCalledWith({
      origen: "moldex", id: "molecule-1", task_id: "run-2026", escena: "resultado", orientacion: "horizontal", dispositivo: "gpu", presentacion: AUTO_PRESENTATION }));
    expect(api.crearMolcy).not.toHaveBeenCalled();
  });
});


describe("Molcy recursos y trabajos", () => {
  it("las fotos usan su propia reserva de disco aunque el vídeo no quepa", async () => {
    api.renderizadorMolcy.mockResolvedValue({...resources,disponible:true,motivo:null,gpu_disponible:true,foto_disponible:true,foto_gpu_disponible:true,
      espacio:{social_vertical:{libre_bytes:4e9,necesario_bytes:8e9,disponible:false}},
      espacio_fotos:{"4k":{libre_bytes:4e9,necesario_bytes:1.2e9,disponible:true}}});
    render(<MolcyPage />);
    await screen.findByRole("option",{name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"),{target:{value:"run-2026"}});
    await esperarEspacio();
    expect(screen.getByRole("button",{name:/Generar video/})).toBeDisabled();
    fireEvent.click(screen.getByRole("button",{name:/cy_mode_photo/}));
    expect(screen.getByRole("button",{name:/Preparar tomas/})).not.toBeDisabled();
  });
  it("sin Blender, el único botón de descarga está en el estudio y nombra el paquete entero", async () => {
    api.renderizadorMolcy.mockResolvedValue({disponible:false,motivo:"No se encontró Blender.",motivo_codigo:"falta_blender"});
    api.instalarBlenderMolcy.mockResolvedValue({estado:"instalando",fase:"descargando",ruta:"C:/MolDesign/tools/blender/blender.exe",version:"5.2.2",descarga_bytes:404453484,reserva_bytes:5e9,instalado:false,configuracion:{}});
    render(<MolcyPage />);
    const estudio=await screen.findByTestId("molcy-paquete-estudio");
    const button=await within(estudio).findByRole("button",{name:"cy_pack_install_full"});
    expect(screen.getAllByRole("button",{name:/cy_pack_install|cy_install_blender/})).toHaveLength(1);
    // La configuración no se abre sola: lo que falta se arregla descargando, y eso está en el estudio.
    expect(screen.getByText("cy_setup").closest("details")?.open).toBe(false);
    fireEvent.click(button);
    await waitFor(()=>expect(api.instalarBlenderMolcy).toHaveBeenCalledTimes(1));
  });
  it("con Blender listo no hay tarjeta del paquete", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option",{name:/Aspirina/});
    expect(screen.queryByTestId("molcy-paquete-estudio")).toBeNull();
  });
  it("recupera y cancela un render guardado", async () => {
    localStorage.setItem("molcy-job:usuario-qa","job-old");
    api.estadoMolcy.mockResolvedValue({id:"job-old",estado:"renderizando"});
    api.cancelarMolcy.mockResolvedValue({id:"job-old",estado:"cancelado"});
    render(<MolcyPage />);
    fireEvent.click(await screen.findByRole("button",{name:"cy_cancel_render"}));
    await waitFor(()=>expect(api.cancelarMolcy).toHaveBeenCalledWith("job-old"));
    await screen.findByText("cy_cancelado");
  });
});


describe("Carpeta de salida opcional", () => {
  const ID = "11111111-1111-4111-8111-111111111111";
  const sinGlobal = { disponible: true, global: null, problema: null, predeterminada: "C:/MolDesign/data/molcy" };
  it("no aparece fuera de la app de escritorio y el flujo por defecto no manda carpeta", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    expect(screen.queryByText("cy_out_title")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Generar video/ }));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalled());
    expect(api.crearMolcy.mock.calls[0][0]).not.toHaveProperty("salida_id");
  });
  it("«sólo para este vídeo» manda la carpeta una vez y mide el espacio de ese disco", async () => {
    api.salidaMolcy.mockResolvedValue(sinGlobal);
    api.elegirCarpetaSalidaMolcy.mockResolvedValue({ id: ID, display_path: "D:\Videos" });
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    expect(screen.getByTestId("molcy-out-estado")).toHaveTextContent("cy_out_default");
    fireEvent.click(await screen.findByRole("button", { name: "cy_out_choose" }));
    fireEvent.click(await screen.findByRole("button", { name: "cy_out_for_this" }));
    await waitFor(() => expect(api.recursosMolcy).toHaveBeenCalledWith("run-2026", ID));
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /Generar video/ }));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({ salida_id: ID, task_id: "run-2026" })));
    // No se arrastra al siguiente vídeo.
    await waitFor(() => expect(screen.getByTestId("molcy-out-estado")).toHaveTextContent("cy_out_default"));
  });
  it("«para todos los vídeos» se guarda en la cuenta y no se manda en cada vídeo", async () => {
    api.salidaMolcy.mockResolvedValue(sinGlobal);
    api.elegirCarpetaSalidaMolcy.mockResolvedValue({ id: ID, display_path: "E:\Videos" });
    api.fijarSalidaMolcy.mockResolvedValue({ ...sinGlobal, global: { id: ID, ruta: "E:\Videos" } });
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.click(await screen.findByRole("button", { name: "cy_out_choose" }));
    fireEvent.click(await screen.findByRole("button", { name: "cy_out_for_all" }));
    await waitFor(() => expect(api.fijarSalidaMolcy).toHaveBeenCalledWith(ID));
    await waitFor(() => expect(screen.getByTestId("molcy-out-estado")).toHaveTextContent("cy_out_global"));
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /Generar video/ }));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalled());
    expect(api.crearMolcy.mock.calls[0][0]).not.toHaveProperty("salida_id");
  });
  it("con una preferencia global se puede volver a la ubicación por defecto sólo en un vídeo", async () => {
    api.salidaMolcy.mockResolvedValue({ ...sinGlobal, global: { id: ID, ruta: "E:\Videos" } });
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    fireEvent.click(await screen.findByRole("button", { name: "cy_out_default_once" }));
    await waitFor(() => expect(api.recursosMolcy).toHaveBeenCalledWith("run-2026", "predeterminada"));
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /Generar video/ }));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({ salida_id: "predeterminada" })));
  });
});

describe("Recuperación de trabajos y sesiones Molcy", () => {
  it("bloquea un nuevo render al seleccionar un video antiguo mientras otro está activo", async () => {
    api.trabajosMolcy.mockResolvedValue({trabajos:[
      {id:"activo", estado:"renderizando"}, {id:"anterior", estado:"completo"},
    ]});
    api.videoMolcy.mockResolvedValue("http://127.0.0.1:8037/molcy/medios/qa");
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    fireEvent.click(await screen.findByRole("button", {name:/cy_history_job.*cy_completo/}));
    expect(screen.getByRole("button", {name:/Generar video/})).toBeDisabled();
  });

  it("renueva el acceso cuando falla la reproducción", async () => {
    localStorage.setItem("molcy-job:usuario-qa","listo");
    api.estadoMolcy.mockResolvedValue({id:"listo",estado:"completo"});
    api.videoMolcy.mockResolvedValue("http://127.0.0.1:8037/molcy/medios/qa");
    render(<MolcyPage />);
    const video = await screen.findByLabelText("cy_completo", { selector: "video" });
    fireEvent.error(video);
    fireEvent.click(screen.getByRole("button", {name:"cy_retry_video"}));
    await waitFor(() => expect(api.videoMolcy).toHaveBeenCalledTimes(2));
  });

  it("quita el video de la cuenta anterior al cambiar de usuario", async () => {
    localStorage.setItem("molcy-job:usuario-qa","listo");
    api.estadoMolcy.mockResolvedValue({id:"listo",estado:"completo"});
    api.videoMolcy.mockResolvedValue("http://127.0.0.1:8037/molcy/medios/qa");
    const view = render(<MolcyPage />);
    await screen.findByLabelText("cy_completo", { selector: "video" });
    auth.userId = "otra-cuenta";
    view.rerender(<MolcyPage />);
    expect(screen.queryByLabelText("cy_completo", { selector: "video" })).toBeNull();
    expect(localStorage.getItem("molcy-job:otra-cuenta")).toBeNull();
    await screen.findByRole("option", {name:/Aspirina/});
  });
});


describe("Selección de recursos CPU", () => {
  it("permite receptor de una corrida Moldex manteniendo su identidad", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button",{name:/^Receptor/}));
    expect(screen.getByText("cy_receptor_corrida")).toBeVisible();
    expect(screen.getByRole("button",{name:/^Búsqueda/})).toBeDisabled();
    fireEvent.click(screen.getByRole("button",{name:/Generar video/}));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({origen:"moldex",task_id:"run-2026",escena:"receptor"})));
  });
  it("deja la VRAM a Blender y permite GPU sin telemetría de memoria", async () => {
    api.renderizadorMolcy.mockResolvedValue({...resources,disponible:true,motivo:null,gpu_disponible:true,
      gpu_vram_monitorizable:false,espacio:{social_vertical:{libre_bytes:20e9,necesario_bytes:5e9,disponible:true}}});
    api.recursosMolcy.mockImplementation((taskId?: string | null, salidaId?: string | null) => recursosConEspacio(taskId, {gpu_vram_monitorizable:false}, salidaId));
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    expect(screen.getByText("cy_gpu_memory_auto")).toBeVisible();
    expect(screen.queryByRole("slider")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:/Generar video/}));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalled());
    expect(api.crearMolcy.mock.calls[0][0]).toEqual(expect.objectContaining({dispositivo:"gpu"}));
    expect(api.crearMolcy.mock.calls[0][0]).not.toHaveProperty("gpu_vram_mib");
  });
  it("sin poder consultar el espacio de la corrida (fallo de recursos) no deja generar", async () => {
    // Decisión del propietario (2026-10-06): sin conocer el espacio en disco de la corrida, se bloquea.
    api.recursosMolcy.mockRejectedValue(new Error("Resources unavailable"));
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    await waitFor(() => expect(api.recursosMolcy).toHaveBeenCalled());
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    expect(await screen.findByText("cy_space_unknown")).toBeVisible();
    expect(screen.getByRole("button", {name:/Generar video/})).toBeDisabled();
    fireEvent.click(screen.getByRole("button", {name:/cy_mode_photo/}));
    fireEvent.click(screen.getByRole("button", {name:/cy_photo_device_cpu/}));
    await screen.findByText("cy_resources_error");
    expect(screen.getByRole("button", {name:/Preparar tomas/})).toBeDisabled();
  });
  it("envía los hilos elegidos para las fotos con CPU", async () => {
    api.renderizadorMolcy.mockResolvedValue({...resources,disponible:true,motivo:null,gpu_disponible:true,foto_disponible:true,
      foto_gpu_disponible:true,cpu_hilos_configurables:true,
      espacio_fotos:{"4k":{libre_bytes:20e9,necesario_bytes:1.2e9,disponible:true}}});
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.click(screen.getByRole("button", {name:/cy_mode_photo/}));
    fireEvent.click(screen.getByRole("button", {name:/cy_photo_device_cpu/}));
    const selector = screen.getByRole("slider", {name:"cy_cpu_threads"});
    expect(selector).toHaveValue("4");
    fireEvent.change(selector, {target:{value:"3"}});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", {name:/Preparar tomas/}));
    await waitFor(() => expect(api.crearFotosMolcy).toHaveBeenCalledWith(expect.objectContaining({dispositivo:"cpu",cpu_hilos:3})));
  });
});


describe("QA2-006: idioma de los motivos del renderizador", () => {
  it("actualiza el motivo al cambiar de idioma sin recargar la página", async () => {
    api.renderizadorMolcy.mockResolvedValueOnce({ disponible: false, motivo: "Falta Blender" })
      .mockResolvedValue({ disponible: false, motivo: "Blender is missing" });
    const view = render(<MolcyPage />);
    await screen.findByText(/Falta Blender/);
    language.locale = "en";
    view.rerender(<MolcyPage />);
    await screen.findByText(/Blender is missing/);
    expect(screen.queryByText(/Falta Blender/)).toBeNull();
  });

  it("conserva fuente, modo fotos y elección CPU después de actualizar el idioma", async () => {
    const view = render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
    await esperarEspacio();
    fireEvent.click(screen.getByRole("button", { name: /cy_mode_photo/ }));
    fireEvent.click(screen.getByRole("button", { name: /cy_photo_device_cpu/ }));
    language.locale = "en";
    view.rerender(<MolcyPage />);
    await waitFor(() => expect(api.renderizadorMolcy).toHaveBeenCalledTimes(2));
    expect(screen.getByRole("button", { name: /cy_mode_photo/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /cy_photo_device_cpu/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByLabelText("cy_elegir")).toHaveValue("run-2026");
  });
});

describe.each(["es", "en"] as const)("QA2-012: origen del vídeo conservado (%s)", (locale) => {
  it("mantiene vídeo y corrida original al elegir otra fuente para el borrador", async () => {
    language.locale=locale;
    localStorage.setItem("molcy-job:usuario-qa", "job-origin");
    api.estadoMolcy.mockResolvedValue({id:"job-origin",estado:"completo",fuente:{origen:"moldex",id:"mol-original",task_id:"run-original"}});
    api.videoMolcy.mockResolvedValue("blob:video-original");
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    const origin=await screen.findByRole("region", {name:"cy_video_origin"});
    expect(origin).toHaveTextContent("run-original");
    expect(origin).toHaveTextContent("mol-original");
    expect(origin).not.toHaveTextContent("run-2026");
    expect(document.querySelector("video")?.getAttribute("src")).toBe("blob:video-original");
  });
  it("declara la identidad ausente en un vídeo heredado sin tomar la del borrador", async () => {
    language.locale=locale;
    localStorage.setItem("molcy-job:usuario-qa", "job-legacy");
    api.estadoMolcy.mockResolvedValue({id:"job-legacy",estado:"completo"});
    api.videoMolcy.mockResolvedValue("blob:video-legacy");
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    const origin=await screen.findByRole("region", {name:"cy_video_origin"});
    expect(origin).toHaveTextContent("cy_video_origin_missing");
    expect(origin).not.toHaveTextContent("run-2026");
  });
  it("identifica un recorrido de receptor sin atribuirle una corrida de docking", async () => {
    language.locale=locale;
    localStorage.setItem("molcy-job:usuario-qa", "job-receptor");
    api.estadoMolcy.mockResolvedValue({id:"job-receptor",estado:"completo",fuente:{origen:"receptor",id:"USR_QA"}});
    api.videoMolcy.mockResolvedValue("blob:video-receptor");
    render(<MolcyPage />);
    const origin=await screen.findByRole("region", {name:"cy_video_origin"});
    expect(origin).toHaveTextContent("USR_QA");
    expect(origin).not.toHaveTextContent("cy_video_run");
  });
});

it("QA2-013: volver a seleccionar el mismo vídeo conserva el reproductor", async () => {
  const saved={id:"job-same",estado:"completo",fuente:{origen:"moldex",id:"mol-original",task_id:"run-original"}};
  localStorage.setItem("molcy-job:usuario-qa", "job-same");
  api.estadoMolcy.mockResolvedValue(saved);
  api.trabajosMolcy.mockResolvedValue({trabajos:[saved]});
  api.videoMolcy.mockResolvedValue("blob:video-same");
  render(<MolcyPage />);
  await waitFor(()=>expect(document.querySelector("video")?.getAttribute("src")).toBe("blob:video-same"));
  fireEvent.click(screen.getByRole("button",{name:/cy_history_job/}));
  expect(document.querySelector("video")?.getAttribute("src")).toBe("blob:video-same");
});

describe("Molcy es Beta (decisión del propietario, 2026-10-04)", () => {
  it("la cabecera de la página lleva la marca Beta, una sola vez", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    const marca = screen.getByTestId("pildora-beta");
    expect(marca).toHaveTextContent("c_beta");
    expect(marca.closest("header")).not.toBeNull();
    expect(screen.getAllByTestId("pildora-beta")).toHaveLength(1);
  });
});

describe("Sondeo del renderizador: sólo se fuerza cuando el usuario lo pide", () => {
  it("la carga no fuerza; «Comprobar» sí", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    expect(api.renderizadorMolcy).toHaveBeenCalledTimes(1);
    expect(api.renderizadorMolcy.mock.calls[0]).toEqual([]);
    fireEvent.click(screen.getByRole("button", { name: "cy_recheck", hidden: true }));
    await waitFor(() => expect(api.renderizadorMolcy).toHaveBeenLastCalledWith(true));
  });

  it("cambiar de idioma vuelve a pedir el estado (para traducir su motivo) pero sin forzar un sondeo nuevo", async () => {
    const view = render(<MolcyPage />);
    await screen.findByRole("option", { name: /Aspirina/ });
    language.locale = "en";
    view.rerender(<MolcyPage />);
    await waitFor(() => expect(api.renderizadorMolcy).toHaveBeenCalledTimes(2));
    expect(api.renderizadorMolcy.mock.calls[1]).toEqual([]);
  });
});

describe("Vista previa del render en curso", () => {
  const guardado = (estado: string) => {
    localStorage.setItem("molcy-job:usuario-qa", "job-vivo");
    api.estadoMolcy.mockResolvedValue({ id: "job-vivo", estado, progreso: { fotogramas: 12, total: 360 } });
  };

  it("enseña en el panel central el último fotograma renderizado, con su número y qué le falta", async () => {
    guardado("renderizando");
    api.fotogramaMolcy.mockResolvedValue({ url: "blob:fotograma-12", indice: 12, orden: 12, total: 360 });
    render(<MolcyPage />);
    const imagen = await screen.findByAltText("cy_live_alt");
    expect(imagen).toHaveAttribute("src", "blob:fotograma-12");
    expect(api.fotogramaMolcy).toHaveBeenCalledWith("job-vivo", undefined, expect.any(AbortSignal));
    expect(screen.getByText("cy_live_frame")).toBeInTheDocument();
    expect(screen.getByText("cy_live_note")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "cy_live_title" })).toBeInTheDocument();
  });

  it("pide el siguiente fotograma desde el que ya tiene y libera el anterior", async () => {
    guardado("renderizando");
    api.fotogramaMolcy
      .mockResolvedValueOnce({ url: "blob:uno", indice: 5, orden: 5, total: 360 })
      .mockResolvedValueOnce({ url: "blob:dos", indice: 6, orden: 6, total: 360 })
      .mockResolvedValue(null);
    render(<MolcyPage />);
    await screen.findByAltText("cy_live_alt");
    await waitFor(() => expect(screen.getByAltText("cy_live_alt")).toHaveAttribute("src", "blob:dos"), { timeout: 4000 });
    expect(api.fotogramaMolcy).toHaveBeenNthCalledWith(2, "job-vivo", 5, expect.any(AbortSignal));
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:uno");
  });

  it("con pausas, el pie pone sobre el total su orden entre los rendidos, no su número del guion", async () => {
    // Lo que vio el propietario: «Fotograma 681 de 667».
    guardado("renderizando");
    api.fotogramaMolcy.mockResolvedValue({ url: "blob:pausas", indice: 681, orden: 545, total: 667 });
    render(<MolcyPage />);
    await screen.findByAltText("cy_live_alt");
    expect(api.pieDelFotograma).toHaveBeenLastCalledWith(expect.objectContaining({ indice: 681, orden: 545, total: 667 }));
    expect(api.pieDelFotograma.mock.results.at(-1)?.value).toEqual({ clave: "cy_live_frame", valores: { done: 545, total: 667 } });
    expect(screen.getByText("cy_live_frame")).toBeInTheDocument();
  });

  it("sin total conocido enseña sólo el número", async () => {
    guardado("renderizando");
    api.fotogramaMolcy.mockResolvedValue({ url: "blob:x", indice: 3, total: 0 });
    render(<MolcyPage />);
    await screen.findByAltText("cy_live_alt");
    expect(screen.getByText("cy_live_frame_sin_total")).toBeInTheDocument();
  });

  it("un fallo de la vista previa no se muestra como error ni interrumpe el render", async () => {
    guardado("renderizando");
    api.fotogramaMolcy.mockRejectedValue(new Error("sin red"));
    render(<MolcyPage />);
    await screen.findByRole("button", { name: "cy_cancel_render" });
    await waitFor(() => expect(api.fotogramaMolcy).toHaveBeenCalled());
    expect(screen.queryByAltText("cy_live_alt")).not.toBeInTheDocument();
    expect(screen.queryByText("sin red")).not.toBeInTheDocument();
  });

  it("no pide fotogramas de un trabajo que no está renderizando y no enseña uno de otro", async () => {
    guardado("en_cola");
    render(<MolcyPage />);
    await screen.findByRole("button", { name: "cy_cancel_render" });
    expect(api.fotogramaMolcy).not.toHaveBeenCalled();
    expect(screen.queryByAltText("cy_live_alt")).not.toBeInTheDocument();
  });

  it("al terminar, el vídeo sustituye al fotograma y se libera su URL", async () => {
    guardado("renderizando");
    api.fotogramaMolcy.mockResolvedValue({ url: "blob:ultimo", indice: 360, orden: 360, total: 360 });
    api.videoMolcy.mockResolvedValue("http://127.0.0.1:8037/molcy/medios/qa");
    const view = render(<MolcyPage />);
    await screen.findByAltText("cy_live_alt");
    api.estadoMolcy.mockResolvedValue({ id: "job-vivo", estado: "completo" });
    // el sondeo del estado es de 3 s: se espera a que el trabajo figure completo
    const video = await screen.findByLabelText("cy_completo", { selector: "video" }, { timeout: 6000 });
    expect(video).toBeInTheDocument();
    expect(screen.queryByAltText("cy_live_alt")).not.toBeInTheDocument();
    // El estado completo monta el vídeo antes de resolver su URL y ejecutar
    // el efecto que retira el fotograma. Se comprueban ambas salidas.
    await waitFor(() => {
      expect(video).toHaveAttribute("src", "http://127.0.0.1:8037/molcy/medios/qa");
      expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:ultimo");
    });
    view.unmount();
  }, 12000);
});

describe("Sesión de fotos (decisión del propietario, 2026-10-08)", () => {
  it("una sesión preparada se abre en el estudio y no pide vídeo ni fotogramas en vivo", async () => {
    localStorage.setItem("molcy-job:usuario-qa", "fotos-1");
    api.estadoMolcy.mockResolvedValue({ id: "fotos-1", estado: "completo", tipo: "fotos", orientacion: "vertical", escena: "resultado",
      escena_fotos: { fotogramas_fuente: 389, beats: { general: [1, 87] } },
      momentos: [{ id: "general-42", fotograma: 42, beat: "general", tipo: "titulo", etiquetas: 0, pose: null, orden: 1 }], fotos: [] });
    api.imagenMolcy.mockResolvedValue({ url: "blob:toma-42", nombre: null });
    render(<MolcyPage />);
    expect(await screen.findByRole("heading", { name: "cy_photo_studio" })).toBeInTheDocument();
    expect(await screen.findByText("cy_photo_suggested")).toBeInTheDocument();
    await waitFor(() => expect(api.imagenMolcy).toHaveBeenCalledWith("fotos-1", "tomas", "42", expect.any(AbortSignal)));
    expect(api.videoMolcy).not.toHaveBeenCalled();
    expect(api.fotogramaMolcy).not.toHaveBeenCalled();
    expect(screen.getByText("cy_photo_state_ready")).toBeInTheDocument();
  });
});

/**
 * Molcy en segundo plano (decisión del propietario, 2026-10-10): al salir de la pestaña no se desmonta. Oculta, sigue el
 * trabajo en curso y deja de pedir lo que sólo sirve a la vista (recursos, historial, fotogramas en vivo); al volver,
 * refresca las corridas guardadas sin perder lo elegido.
 */
describe("Molcy en segundo plano", () => {
  const montar = (activa: boolean) => <KeepAliveContext.Provider value={activa}><MolcyPage /></KeepAliveContext.Provider>;

  it("oculta no pide recursos ni historial; al volver refresca las corridas y conserva la elegida", async () => {
    vi.useFakeTimers();
    try {
      const view = render(montar(true));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      fireEvent.change(screen.getByLabelText("cy_elegir"), { target: { value: "run-2026" } });
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      // Control: visible, los dos sondeos de 5 s corren.
      const recursos0 = api.recursosMolcy.mock.calls.length;
      const trabajos0 = api.trabajosMolcy.mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(10_500); });
      expect(api.recursosMolcy.mock.calls.length).toBeGreaterThan(recursos0);
      expect(api.trabajosMolcy.mock.calls.length).toBeGreaterThan(trabajos0);

      view.rerender(montar(false));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      const recursos1 = api.recursosMolcy.mock.calls.length;
      const trabajos1 = api.trabajosMolcy.mock.calls.length;
      const fuentes1 = api.fuentesMolcy.mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(30_000); });
      expect(api.recursosMolcy.mock.calls.length).toBe(recursos1);
      expect(api.trabajosMolcy.mock.calls.length).toBe(trabajos1);

      // Una corrida guardada en Moldex mientras tanto aparece al volver, y la elegida sigue elegida.
      api.fuentesMolcy.mockResolvedValue({ ...fuentes, moldex: [...fuentes.moldex,
        { id: "molecule-2", task_id: "run-nueva", nombre: "Ibuprofeno", receptor: "1HSG", disponible: true, motivo: null }] });
      view.rerender(montar(true));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(api.fuentesMolcy.mock.calls.length).toBe(fuentes1 + 1);
      expect(screen.getByRole("option", { name: /Ibuprofeno/ })).toBeInTheDocument();
      expect(screen.getByLabelText("cy_elegir")).toHaveValue("run-2026");
      expect(api.recursosMolcy.mock.calls.length).toBeGreaterThan(recursos1);
      expect(api.trabajosMolcy.mock.calls.length).toBeGreaterThan(trabajos1);
    } finally {
      cleanup();
      vi.useRealTimers();
    }
  });

  it("un vídeo en curso se sigue consultando oculto, sin pedir fotogramas en vivo", async () => {
    vi.useFakeTimers();
    localStorage.setItem("molcy-job:usuario-qa", "job-en-curso");
    api.estadoMolcy.mockResolvedValue({ id: "job-en-curso", estado: "renderizando", tipo: "video", progreso: { fotogramas: 10, total: 100 } });
    try {
      const view = render(montar(true));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      await act(async () => { await vi.advanceTimersByTimeAsync(3_100); });
      expect(api.fotogramaMolcy).toHaveBeenCalled();

      view.rerender(montar(false));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      const estado1 = api.estadoMolcy.mock.calls.length;
      const fotogramas1 = api.fotogramaMolcy.mock.calls.length;
      await act(async () => { await vi.advanceTimersByTimeAsync(9_100); });
      expect(api.estadoMolcy.mock.calls.length).toBeGreaterThanOrEqual(estado1 + 3);
      expect(api.fotogramaMolcy.mock.calls.length).toBe(fotogramas1);

      // Termina con la pestaña oculta: al volver ya está completo, sin recargar la página.
      api.estadoMolcy.mockResolvedValue({ id: "job-en-curso", estado: "completo", tipo: "video" });
      api.videoMolcy.mockResolvedValue("http://127.0.0.1:8037/molcy/medios/qa");
      await act(async () => { await vi.advanceTimersByTimeAsync(3_100); });
      view.rerender(montar(true));
      await act(async () => { await vi.advanceTimersByTimeAsync(0); });
      expect(screen.getByLabelText("cy_completo", { selector: "video" })).toHaveAttribute("src", "http://127.0.0.1:8037/molcy/medios/qa");
    } finally {
      cleanup();
      vi.useRealTimers();
    }
  });

  it("al ocultarse pausa el vídeo que se esté reproduciendo", async () => {
    const pausa = vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
    localStorage.setItem("molcy-job:usuario-qa", "job-listo");
    api.estadoMolcy.mockResolvedValue({ id: "job-listo", estado: "completo", tipo: "video" });
    api.videoMolcy.mockResolvedValue("http://127.0.0.1:8037/molcy/medios/listo");
    try {
      const view = render(montar(true));
      const video = await screen.findByLabelText("cy_completo", { selector: "video" });
      await waitFor(() => expect(video).toHaveAttribute("src", "http://127.0.0.1:8037/molcy/medios/listo"));
      expect(pausa).not.toHaveBeenCalled();
      view.rerender(montar(false));
      await waitFor(() => expect(pausa).toHaveBeenCalled());
      expect(pausa.mock.contexts).toContain(video);
    } finally {
      pausa.mockRestore();
    }
  });
});

/**
 * Propietario, 2026-10-12: con un vídeo renderizándose abrió desde el historial las fotos del día anterior; el estudio pasó a
 * las fotos y ya no había manera visible de volver al progreso del vídeo (el render seguía en el backend). Ahora el estudio
 * avisa de que hay un trabajo en curso y deja volver, y el historial ofrece «Ver en el estudio» en ese trabajo.
 */
describe("Molcy: volver al trabajo en curso", () => {
  const video = { id: "job-video", tipo: "video", estado: "renderizando", progreso: { fotogramas: 120, total: 667 },
    fuente: { origen: "moldex", id: "molecule-1", task_id: "run-2026" } };
  const fotos = { id: "job-fotos", tipo: "fotos", estado: "completo", fotos: [], momentos: [], escena_fotos: { fotogramas_fuente: 0 },
    fuente: { origen: "moldex", id: "molecule-1", task_id: "run-2026" } };

  it("abrir las fotos de ayer no deja el vídeo en curso sin camino de vuelta", async () => {
    localStorage.setItem("molcy-job:usuario-qa", "job-video");
    api.estadoMolcy.mockImplementation(async (id: string) => (id === "job-video" ? video : fotos));
    api.trabajosMolcy.mockResolvedValue({ trabajos: [video, fotos] });
    render(<MolcyPage />);
    // El estudio enseña el vídeo en curso; no hace falta volver a nada.
    await screen.findByRole("button", { name: "cy_cancel_render" });
    expect(screen.queryByTestId("molcy-en-curso")).toBeNull();
    expect(screen.queryByRole("button", { name: "cy_history_view_in_studio" })).toBeNull();

    fireEvent.click(await screen.findByRole("button", { name: "cy_history_open_studio" }));
    await screen.findByText("cy_photo_studio");
    const aviso = await screen.findByTestId("molcy-en-curso");
    expect(aviso).toHaveTextContent("cy_en_curso_video");
    expect(aviso).toHaveTextContent("cy_progress");
    // El historial también lo ofrece, en el trabajo en curso.
    expect(screen.getByRole("button", { name: "cy_history_view_in_studio" })).toBeInTheDocument();

    fireEvent.click(within(aviso).getByRole("button", { name: "cy_en_curso_volver_video" }));
    await screen.findByRole("button", { name: "cy_cancel_render" });
    expect(screen.queryByText("cy_photo_studio")).toBeNull();
    expect(screen.queryByTestId("molcy-en-curso")).toBeNull();
    expect(localStorage.getItem("molcy-job:usuario-qa")).toBe("job-video");
  });

  it("desde el historial, «Ver en el estudio» vuelve también al vídeo en curso", async () => {
    localStorage.setItem("molcy-job:usuario-qa", "job-fotos");
    api.estadoMolcy.mockImplementation(async (id: string) => (id === "job-video" ? video : fotos));
    api.trabajosMolcy.mockResolvedValue({ trabajos: [video, fotos] });
    render(<MolcyPage />);
    await screen.findByText("cy_photo_studio");
    fireEvent.click(await screen.findByRole("button", { name: "cy_history_view_in_studio" }));
    await screen.findByRole("button", { name: "cy_cancel_render" });
    expect(screen.queryByTestId("molcy-en-curso")).toBeNull();
  });
});

describe("Molcy: experimental presentation and asynchronous identity", () => {
  it("a late poll from A cannot replace the photo session B selected from history", async () => {
    const video = { id: "race-video", estado: "renderizando", fuente: {task_id:"run-2026"} };
    const photo = { id: "race-photo", estado: "completo", tipo: "fotos", fotos: [], momentos: [], escena_fotos: {fotogramas_fuente:0} };
    let resolve!: (value: unknown) => void;
    const pending = new Promise(done => { resolve = done; });
    localStorage.setItem("molcy-job:usuario-qa", video.id);
    api.estadoMolcy.mockResolvedValueOnce(video).mockReturnValue(pending);
    api.trabajosMolcy.mockResolvedValue({trabajos:[video,photo]});
    render(<MolcyPage />);
    await screen.findByRole("button", { name: "cy_cancel_render" });
    await waitFor(() => expect(api.estadoMolcy).toHaveBeenCalledTimes(2), {timeout:5000});
    fireEvent.click(await screen.findByRole("button", {name:"cy_history_open_studio"}));
    await screen.findByText("cy_photo_studio");
    await act(async () => { resolve({...video, progreso:{fotogramas:99,total:100}}); });
    expect(screen.getByText("cy_photo_studio")).toBeVisible();
    expect(localStorage.getItem("molcy-job:usuario-qa")).toBe(photo.id);
  });
  it("sends independent residue/line visibility choices and restores the automatic recipe", async () => {
    render(<MolcyPage />);
    await screen.findByRole("option", {name:/Aspirina/});
    fireEvent.change(screen.getByLabelText("cy_elegir"), {target:{value:"run-2026"}});
    await esperarEspacio();
    fireEvent.click(screen.getByText("Personalizar presentación"));
    fireEvent.change(screen.getByLabelText("Título visual"), {target:{value:"Mi figura"}});
    fireEvent.click(screen.getByLabelText("Mostrar etiquetas"));
    fireEvent.click(screen.getByLabelText("Mostrar contactos"));
    fireEvent.click(screen.getByRole("button", {name:/Generar video/}));
    await waitFor(() => expect(api.crearMolcy).toHaveBeenCalledWith(expect.objectContaining({
      task_id:"run-2026", presentacion: {...AUTO_PRESENTATION,titulo:"Mi figura",etiquetas:false,contactos:false}
    })));
    api.estadoMolcy.mockResolvedValue({id:"job-1",estado:"completo"});
    await waitFor(() => expect(screen.getByRole("button", {name:"Restaurar automático"})).toBeEnabled(), {timeout:5000});
    fireEvent.click(screen.getByRole("button", {name:"Restaurar automático"}));
    expect(screen.getByLabelText("Título visual")).toHaveValue("");
    expect(screen.getByLabelText("Mostrar etiquetas")).toBeChecked();
    expect(screen.getByLabelText("Mostrar contactos")).toBeChecked();
  });
});
