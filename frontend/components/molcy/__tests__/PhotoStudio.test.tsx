import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { PhotoStudio, dimensionesFoto, duracion, etiquetaMomento, tamanoImpreso } from "../PhotoStudio";
import type { MolcyJob } from "@/lib/molcy";

const api = vi.hoisted(() => ({
  RESOLUCIONES_FOTO: ["720p", "1080p", "1440p", "4k"],
  imagenMolcy: vi.fn(), tomarFotoMolcy: vi.fn(), vistaMolcy: vi.fn(), estimacionFotoMolcy: vi.fn(),
  descargarFotoMolcy: vi.fn(), revelarMolcy: vi.fn(),
}));
vi.mock("@/lib/molcy", () => api);
vi.mock("@/context/LanguageContext", () => ({
  useLanguage: () => ({ locale: "es", t: (key: string, values?: Record<string, unknown>) => values ? `${key} ${JSON.stringify(values)}` : key }),
}));

const MOMENTOS = [
  { id: "general-42", fotograma: 42, beat: "general", tipo: "titulo" as const, etiquetas: 0, pose: null, orden: 1 },
  { id: "llegada_por_fundido-253", fotograma: 253, beat: "llegada_por_fundido", tipo: "lectura" as const, etiquetas: 6, pose: null, orden: 2 },
];
const sesion = (cambios: Partial<MolcyJob> = {}): MolcyJob => ({
  id: "fotos-1", estado: "completo", tipo: "fotos", orientacion: "vertical", escena: "resultado",
  escena_fotos: { fotogramas_fuente: 389, beats: { general: [1, 87], llegada_por_fundido: [192, 273], exploracion: [274, 381] } },
  momentos: MOMENTOS, fotos: [], vistas: {}, ...cambios,
});
const renderer = { disponible: true, motivo: null, foto_disponible: true, foto_gpu_disponible: true,
  espacio_fotos: { "720p": { libre_bytes: 9e9, necesario_bytes: 1e9, disponible: true }, "1080p": { libre_bytes: 9e9, necesario_bytes: 1e9, disponible: true },
    "1440p": { libre_bytes: 9e9, necesario_bytes: 1e9, disponible: true }, "4k": { libre_bytes: 9e9, necesario_bytes: 1.2e9, disponible: true } } };

beforeEach(() => {
  vi.clearAllMocks();
  api.imagenMolcy.mockImplementation(async (_id: string, clase: string, clave: string) => ({ url: `blob:${clase}-${clave}`, nombre: null }));
  api.estimacionFotoMolcy.mockResolvedValue({ estimado_s: null, muestras: 0 });
  api.tomarFotoMolcy.mockResolvedValue(sesion({ estado: "renderizando", fase: "foto" }));
  api.vistaMolcy.mockResolvedValue(sesion({ estado: "renderizando", fase: "vista" }));
  URL.revokeObjectURL = vi.fn();
});
afterEach(cleanup);

describe("Resoluciones y nombres", () => {
  it("van de 720p a 4K en 9:16 y 16:9, con su tamaño de impresión a 300 ppp", () => {
    expect(dimensionesFoto("vertical", "720p")).toEqual([720, 1280]);
    expect(dimensionesFoto("horizontal", "1080p")).toEqual([1920, 1080]);
    expect(dimensionesFoto("horizontal", "4k")).toEqual([3840, 2160]);
    expect(tamanoImpreso(3840, 2160, "es")).toBe("32.5 × 18.3 cm");          // es-MX usa punto decimal
    expect(tamanoImpreso(3840, 2160, "en")).toBe("32.5 × 18.3 cm");
  });
  it("el nombre de un momento sale de lo que es, no de su número", () => {
    expect(etiquetaMomento({ tipo: "titulo", beat: "general", pose: null })).toEqual(["cy_moment_titulo"]);
    expect(etiquetaMomento({ tipo: "lectura", beat: "convergencia", pose: 3 })).toEqual(["cy_moment_pose", { pose: 3 }]);
    expect(etiquetaMomento({ tipo: "lectura", beat: "llegada_por_fundido", pose: null })).toEqual(["cy_moment_interacciones"]);
    expect(etiquetaMomento({ tipo: "recorrido", beat: "exploracion", pose: null })).toEqual(["cy_moment_vuelta"]);
    expect(etiquetaMomento({ tipo: "recorrido", beat: "inventado", pose: null })).toEqual(["cy_moment_recorrido"]);
  });
  it("las duraciones se leen sin decimales", () => {
    expect(duracion(25.4)).toBe("25 s");
    expect(duracion(95)).toBe("1 min 35 s");
    expect(duracion(804)).toBe("13 min");
  });
});

describe("Estudio de fotos", () => {
  it("mientras se prepara no ofrece tomas ni fotos", () => {
    render(<PhotoStudio job={sesion({ estado: "renderizando", fase: "preparando", momentos: [] })} renderer={renderer} device="gpu" onJob={vi.fn()} />);
    expect(screen.getByText("cy_photo_preparing")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cy_photo_take/ })).toBeNull();
    expect(api.imagenMolcy).not.toHaveBeenCalled();
  });

  it("enseña las tomas sugeridas, elige la de los rótulos y pide la foto con fotograma y resolución", async () => {
    const onJob = vi.fn();
    render(<PhotoStudio job={sesion()} renderer={renderer} device="gpu" onJob={onJob} />);
    await waitFor(() => expect(api.imagenMolcy).toHaveBeenCalledWith("fotos-1", "tomas", "253", expect.any(AbortSignal)));
    const interacciones = screen.getByRole("button", { name: /cy_moment_interacciones/ });
    expect(interacciones).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /cy_photo_res_1080p/ })).toHaveAttribute("aria-pressed", "true");
    fireEvent.click(screen.getByRole("button", { name: /cy_photo_res_4k/ }));
    expect(screen.getByText(/2160 × 3840/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /cy_photo_take/ }));
    await waitFor(() => expect(api.tomarFotoMolcy).toHaveBeenCalledWith("fotos-1", { dispositivo: "gpu", fotograma: 253, resolucion: "4k" }));
    expect(onJob).toHaveBeenCalledWith(expect.objectContaining({ fase: "foto" }));
  });

  it("con CPU manda los hilos elegidos", async () => {
    render(<PhotoStudio job={sesion()} renderer={{ ...renderer, cpu_hilos_configurables: true }} device="cpu" cpuThreads={3} onJob={vi.fn()} />);
    fireEvent.click(await screen.findByRole("button", { name: /cy_moment_titulo/ }));
    fireEvent.click(screen.getByRole("button", { name: /cy_photo_take/ }));
    await waitFor(() => expect(api.tomarFotoMolcy).toHaveBeenCalledWith("fotos-1", { dispositivo: "cpu", cpu_hilos: 3, fotograma: 42, resolucion: "1080p" }));
  });

  it("el momento libre se previsualiza antes de pedir la foto", async () => {
    const view = render(<PhotoStudio job={sesion()} renderer={renderer} device="gpu" onJob={vi.fn()} />);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "300" } });
    expect(screen.getByText(/cy_photo_frame .*"frame":300/)).toHaveTextContent("cy_beat_exploracion");
    fireEvent.click(screen.getByRole("button", { name: "cy_photo_free_preview" }));
    await waitFor(() => expect(api.vistaMolcy).toHaveBeenCalledWith("fotos-1", { dispositivo: "gpu", fotograma: 300 }));
    view.rerender(<PhotoStudio job={sesion({ vistas: { "300": { archivo: "v.png", sha256: "a" } } })} renderer={renderer} device="gpu" onJob={vi.fn()} />);
    await waitFor(() => expect(api.imagenMolcy).toHaveBeenCalledWith("fotos-1", "vistas", 300, expect.any(AbortSignal)));
    expect(await screen.findByAltText("cy_photo_preview_alt")).toHaveAttribute("src", "blob:vistas-300");
    fireEvent.click(screen.getByRole("button", { name: /cy_photo_take/ }));
    await waitFor(() => expect(api.tomarFotoMolcy).toHaveBeenCalledWith("fotos-1", expect.objectContaining({ fotograma: 300 })));
  });

  it("el tiempo estimado sólo aparece si está medido en este equipo", async () => {
    const view = render(<PhotoStudio job={sesion()} renderer={renderer} device="gpu" onJob={vi.fn()} />);
    expect(await screen.findByText("cy_photo_estimate_first")).toBeInTheDocument();
    api.estimacionFotoMolcy.mockResolvedValue({ estimado_s: 95, muestras: 1 });
    view.rerender(<PhotoStudio job={sesion({ fotos: [] })} renderer={renderer} device="cpu" onJob={vi.fn()} />);
    expect(await screen.findByText(/cy_photo_estimate .*1 min 35 s/)).toBeInTheDocument();
  });

  it("sin GPU de Cycles no deja tomar la foto con GPU y dice por qué", async () => {
    render(<PhotoStudio job={sesion()} renderer={{ ...renderer, foto_gpu_disponible: false, motivo_foto_gpu: "Sin GPU de Cycles" }} device="gpu" onJob={vi.fn()} />);
    expect(screen.getByText("Sin GPU de Cycles")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cy_photo_take/ })).toBeDisabled();
  });

  it("un fallo de la última foto se explica y la escena sigue lista", () => {
    render(<PhotoStudio job={sesion({ ultima_operacion: { tipo: "foto", estado: "fallido", fotograma: 253, dispositivo: "gpu", ancho: 1080, alto: 1920, resolucion: "1080p", motivo: "Cycles no encontró la GPU" } })}
      renderer={renderer} device="gpu" onJob={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Cycles no encontró la GPU");
    expect(screen.getByRole("button", { name: /cy_photo_take/ })).toBeEnabled();
  });

  it("las fotos entregadas se ven, se descargan y se muestran en su carpeta", async () => {
    const foto = { id: "01", archivo: "4FK3_resultado_0253_1080x1920_01.png", sha256: "a", bytes: 1, fotograma: 253, momento: null,
      tipo: "lectura", beat: null, resolucion: "1080p" as const, ancho: 1080, alto: 1920, dispositivo: "gpu" as const, segundos: { total: 25 } };
    api.revelarMolcy.mockResolvedValue({ ruta: "C:/x.png", tipo: "foto" });
    api.descargarFotoMolcy.mockResolvedValue(undefined);
    render(<PhotoStudio job={sesion({ fotos: [foto] })} renderer={renderer} device="gpu" onJob={vi.fn()} />);
    expect(screen.getByText(/cy_photo_item .*"id":"01"/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "cy_photo_view" }));
    expect(await screen.findByAltText(/cy_photo_delivered_alt/)).toHaveAttribute("src", "blob:fotos-01");
    fireEvent.click(screen.getByRole("button", { name: "cy_photo_download" }));
    expect(api.descargarFotoMolcy).toHaveBeenCalledWith("fotos-1", "01");
    fireEvent.click(screen.getByRole("button", { name: "cy_photo_reveal" }));
    expect(api.revelarMolcy).toHaveBeenCalledWith("fotos-1");
  });
});
