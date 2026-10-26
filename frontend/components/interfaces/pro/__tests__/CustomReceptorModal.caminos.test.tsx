import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { pro } from "../../../../context/traducciones/pro";
import {
  CAMINOS,
  CustomReceptorModal,
  EXTENSIONES_ORIGEN,
  extensionAdmitida,
} from "../CustomReceptorModal";

const upload = vi.hoisted(() => vi.fn());
vi.mock("@/lib/api", () => ({ uploadCustomTarget: upload }));
vi.mock("@/context/LanguageContext", () => ({
  useLanguage: () => ({ t: (key: string, vars?: Record<string, string>) => (vars ? `${key}:${JSON.stringify(vars)}` : key) }),
}));
beforeEach(() => {
  upload.mockReset();
  upload.mockResolvedValue({});
});

const archivo = (nombre: string) => new File(["ATOM\n"], nombre, { type: "text/plain" });

function montar() {
  const onSuccess = vi.fn();
  const view = render(<CustomReceptorModal onClose={() => {}} onSuccess={onSuccess} />);
  const principal = () => view.container.querySelectorAll('input[type="file"]')[0] as HTMLInputElement;
  const camino = (id: "A" | "B" | "C") => view.container.querySelector(`[data-camino="${id}"]`) as HTMLElement;
  const nombrar = (valor = "Mi receptor") =>
    fireEvent.change(screen.getByPlaceholderText("pr_custom_name_placeholder"), { target: { value: valor } });
  const elegir = (nombre: string) => fireEvent.change(principal(), { target: { files: [archivo(nombre)] } });
  const enviar = () => fireEvent.submit(view.container.querySelector("form")!);
  const caja = (x: string, y: string, z: string) => {
    fireEvent.change(screen.getByLabelText("X"), { target: { value: x } });
    fireEvent.change(screen.getByLabelText("Y"), { target: { value: y } });
    fireEvent.change(screen.getByLabelText("Z"), { target: { value: z } });
  };
  const alerta = () => screen.queryByRole("alert")?.textContent ?? null;
  return { view, onSuccess, principal, camino, nombrar, elegir, enviar, caja, alerta };
}

describe("las extensiones de cada camino", () => {
  it("coinciden con las que lee el backend: sin distinguir mayúsculas y con .gz", () => {
    expect(extensionAdmitida("8HFI_CRUDO.PDB", CAMINOS.A.extensiones)).toBe(true);
    expect(extensionAdmitida("8hfi.CIF", CAMINOS.A.extensiones)).toBe(true);
    expect(extensionAdmitida("8hfi.mmcif.gz", CAMINOS.A.extensiones)).toBe(true);
    expect(extensionAdmitida("pdb1abc.ent", CAMINOS.A.extensiones)).toBe(true);
    expect(extensionAdmitida("equipo.pqr", CAMINOS.B.extensiones)).toBe(true);
    expect(extensionAdmitida("receptor.PDBQT.GZ", CAMINOS.C.extensiones)).toBe(true);
  });

  it("no admiten lo que el backend rechaza (control)", () => {
    expect(extensionAdmitida("molecula.sdf", CAMINOS.A.extensiones)).toBe(false);
    expect(extensionAdmitida("equipo.pqr", CAMINOS.A.extensiones)).toBe(false);     // un PQR es de quien ya preparó
    expect(extensionAdmitida("receptor.pdbqt", CAMINOS.A.extensiones)).toBe(false);
    expect(extensionAdmitida("estructura.pdb", CAMINOS.C.extensiones)).toBe(false);
    expect(extensionAdmitida("pdb", CAMINOS.A.extensiones)).toBe(false);            // sin punto no es una extensión
    expect(extensionAdmitida("archivo.gz", CAMINOS.A.extensiones)).toBe(false);
  });

  it("la estructura de origen admite las mismas que el camino B", () => {
    expect([...EXTENSIONES_ORIGEN]).toEqual([...CAMINOS.B.extensiones]);
  });
});

describe("el modal presenta los tres caminos", () => {
  it("muestra A, B y C con sus extensiones, y A por defecto", () => {
    const { camino } = montar();

    expect(screen.getByRole("radiogroup")).toBeTruthy();
    expect(camino("A").getAttribute("aria-checked")).toBe("true");
    expect(camino("B").getAttribute("aria-checked")).toBe("false");
    expect(within(camino("A")).getByText(".pdb .ent .cif .mmcif")).toBeTruthy();
    expect(within(camino("B")).getByText(".pdb .ent .cif .mmcif .pqr")).toBeTruthy();
    expect(within(camino("C")).getByText(".pdbqt")).toBeTruthy();
    expect(within(camino("A")).getByText("pr_rp_a_titulo")).toBeTruthy();
    expect(within(camino("B")).getByText("pr_rp_b_titulo")).toBeTruthy();
    expect(within(camino("C")).getByText("pr_rp_c_titulo")).toBeTruthy();
  });

  it("el campo de estructura de origen sólo existe en el camino C", () => {
    const { camino } = montar();

    expect(screen.queryByTestId("rp-origen")).toBeNull();
    fireEvent.click(camino("B"));
    expect(screen.queryByTestId("rp-origen")).toBeNull();
    fireEvent.click(camino("C"));
    expect(screen.getByTestId("rp-origen")).toBeTruthy();
    expect(screen.getByText("pr_rp_origen")).toBeTruthy();
  });

  it("cada camino explica lo que promete", () => {
    const { camino } = montar();

    expect(screen.getByTestId("rp-puntos").textContent).toContain("pr_rp_a_punto2");      // la confianza (pLDDT) de una predicción
    fireEvent.click(camino("B"));
    expect(screen.getByTestId("rp-puntos").textContent).toContain("pr_rp_b_punto1");      // la protonación es del equipo
    fireEvent.click(camino("C"));
    expect(screen.getByTestId("rp-puntos").textContent).toContain("pr_rp_c_punto2");      // el origen, para auditar
  });

  it("la caja es opcional en A y B y obligatoria en C", () => {
    const { camino } = montar();

    expect(screen.getByText("pr_rp_caja_opcional")).toBeTruthy();
    fireEvent.click(camino("B"));
    expect(screen.getByText("pr_rp_caja_opcional")).toBeTruthy();
    fireEvent.click(camino("C"));
    expect(screen.getByText("pr_rp_caja_obligatoria")).toBeTruthy();
  });
});

describe("lo que se envía a la API", () => {
  it("A: estructura cruda en modo automático, en cualquier grafía de la extensión", async () => {
    const { nombrar, elegir, enviar, onSuccess } = montar();
    nombrar();
    elegir("8HFI_CRUDO.PDB");
    enviar();

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    const datos = upload.mock.calls[0][0] as FormData;
    expect(datos.get("modo_preparacion")).toBe("automatico");
    expect(datos.get("is_curated")).toBe("false");
    expect((datos.get("file") as File).name).toBe("8HFI_CRUDO.PDB");
    expect(datos.get("source_file")).toBeNull();
    expect(datos.get("grid_center_x")).toBeNull();          // sin caja: se detecta del ligando del cristal
  });

  it("A: un mmCIF comprimido y una cadena de varias letras pasan tal cual", async () => {
    const { nombrar, elegir, enviar, onSuccess } = montar();
    nombrar();
    elegir("8hfi.mmcif.gz");
    fireEvent.change(screen.getByPlaceholderText("pr_rp_cadena_otra"), { target: { value: "AAA" } });
    enviar();

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    const datos = upload.mock.calls[0][0] as FormData;
    expect(datos.get("chain_id")).toBe("AAA");
    expect((datos.get("file") as File).name).toBe("8hfi.mmcif.gz");
  });

  it("A: con la caja completa envía el centro y el tamaño", async () => {
    const { nombrar, elegir, caja, enviar, onSuccess } = montar();
    nombrar();
    elegir("AF-P23975-F1-model_v6.pdb");
    caja("-13.077", "0.458", "-0.079");
    enviar();

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    const datos = upload.mock.calls[0][0] as FormData;
    expect([datos.get("grid_center_x"), datos.get("grid_center_y"), datos.get("grid_center_z")]).toEqual(["-13.077", "0.458", "-0.079"]);
    expect(datos.get("grid_size_x")).toBe("20.0");
  });

  it("B: estructura ya preparada, modo respetar, y acepta un PQR (que A rechaza)", async () => {
    const { camino, nombrar, elegir, enviar, onSuccess, alerta } = montar();
    nombrar();
    elegir("equipo.pqr");                                   // en A se rechaza
    expect(alerta()).toContain("pr_rp_extension_invalida");
    expect(upload).not.toHaveBeenCalled();

    fireEvent.click(camino("B"));
    elegir("equipo.pqr");
    enviar();

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    const datos = upload.mock.calls[0][0] as FormData;
    expect(datos.get("modo_preparacion")).toBe("respetar");
    expect(datos.get("is_curated")).toBe("false");
    expect(datos.get("cofactors_whitelist")).toBeNull();    // en B nada se retira por una lista blanca
  });

  it("C: pide la caja antes de enviar nada", async () => {
    const { camino, nombrar, elegir, enviar, alerta } = montar();
    fireEvent.click(camino("C"));
    nombrar();
    elegir("receptor.pdbqt");
    enviar();

    expect(alerta()).toContain("pr_rp_caja_obligatoria_falta");
    expect(upload).not.toHaveBeenCalled();
  });

  it("C sin origen: PDBQT tal cual con su caja y sin estructura de origen", async () => {
    const { camino, nombrar, elegir, caja, enviar, onSuccess } = montar();
    fireEvent.click(camino("C"));
    nombrar();
    elegir("receptor.PDBQT");
    caja("100.281", "100.843", "101.442");
    enviar();

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    const datos = upload.mock.calls[0][0] as FormData;
    expect(datos.get("modo_preparacion")).toBe("pdbqt");
    expect(datos.get("is_curated")).toBe("true");
    expect(datos.get("source_file")).toBeNull();
    expect(datos.get("grid_center_y")).toBe("100.843");
  });

  it("C con origen: envía la estructura de origen como source_file", async () => {
    const { camino, nombrar, elegir, caja, enviar, onSuccess } = montar();
    fireEvent.click(camino("C"));
    nombrar();
    elegir("receptor.pdbqt");
    caja("100.281", "100.843", "101.442");
    fireEvent.change(screen.getByTestId("rp-origen"), { target: { files: [archivo("8HFI.cif")] } });
    enviar();

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    const datos = upload.mock.calls[0][0] as FormData;
    expect((datos.get("source_file") as File).name).toBe("8HFI.cif");
    expect((datos.get("file") as File).name).toBe("receptor.pdbqt");
  });

  it("C: el origen se puede quitar y entonces no se envía", async () => {
    const { camino, nombrar, elegir, caja, enviar, onSuccess } = montar();
    fireEvent.click(camino("C"));
    nombrar();
    elegir("receptor.pdbqt");
    caja("1", "2", "3");
    fireEvent.change(screen.getByTestId("rp-origen"), { target: { files: [archivo("origen.pdb")] } });
    fireEvent.click(screen.getByText("pr_rp_origen_quitar"));
    enviar();

    await waitFor(() => expect(onSuccess).toHaveBeenCalledTimes(1));
    expect((upload.mock.calls[0][0] as FormData).get("source_file")).toBeNull();
  });
});

describe("lo que se rechaza antes de enviar", () => {
  it("un SDF no es un formato de receptor en ningún camino", () => {
    const { camino, elegir, alerta } = montar();

    for (const id of ["A", "B", "C"] as const) {
      fireEvent.click(camino(id));
      elegir("ligando.sdf");
      expect(alerta()).toContain("pr_rp_extension_invalida");
    }
    expect(upload).not.toHaveBeenCalled();
  });

  it("la estructura de origen de un PDBQT no puede ser otro PDBQT", () => {
    const { camino, alerta } = montar();
    fireEvent.click(camino("C"));

    fireEvent.change(screen.getByTestId("rp-origen"), { target: { files: [archivo("otro.pdbqt")] } });

    expect(alerta()).toContain("pr_rp_extension_invalida");
    expect(alerta()).toContain(".pdb .ent .cif .mmcif .pqr");
  });

  it("una caja con una o dos coordenadas se rechaza", () => {
    const { nombrar, elegir, enviar, alerta } = montar();
    nombrar();
    elegir("equipo.pdb");
    fireEvent.change(screen.getByLabelText("X"), { target: { value: "1" } });
    enviar();

    expect(alerta()).toContain("pr_rp_caja_incompleta");
    expect(upload).not.toHaveBeenCalled();
  });

  it("sin archivo no se envía y se dice qué falta", () => {
    const { nombrar, enviar, alerta } = montar();
    nombrar();
    enviar();

    expect(alerta()).toContain("pr_rp_falta_archivo");
    expect(upload).not.toHaveBeenCalled();
  });

  it("al cambiar de camino se descarta el archivo que ya no corresponde y se conserva el que sí", () => {
    const { camino, elegir } = montar();

    elegir("equipo.pdb");
    fireEvent.click(camino("B"));                           // un .pdb vale en B
    expect(screen.getByText("equipo.pdb")).toBeTruthy();
    fireEvent.click(camino("C"));                           // y no en C
    expect(screen.queryByText("equipo.pdb")).toBeNull();
    expect(screen.getAllByText("pr_rp_sin_archivo")).toHaveLength(2);      // el principal y la estructura de origen
  });
});

describe("los errores que devuelve la subida", () => {
  it("se muestran tal cual los dio el backend (ya en el idioma de la interfaz)", async () => {
    upload.mockRejectedValue(new Error("«equipo.pdb» no contiene ningún residuo de aminoácido. Sube una estructura con proteína."));
    const { nombrar, elegir, enviar, alerta, onSuccess } = montar();
    nombrar();
    elegir("equipo.pdb");
    enviar();

    await waitFor(() => expect(alerta()).toContain("no contiene ningún residuo de aminoácido"));
    expect(onSuccess).not.toHaveBeenCalled();
  });

  it("sin texto del backend se muestra el mensaje genérico traducido, nunca un objeto", async () => {
    upload.mockRejectedValue(new Error(""));
    const { nombrar, elegir, enviar, alerta } = montar();
    nombrar();
    elegir("equipo.pdb");
    enviar();

    await waitFor(() => expect(alerta()).toBe("auto_67bfa12d71a2"));
  });
});

describe("los textos de los tres caminos", () => {
  const claves = Object.keys(pro.es).filter((k) => k.startsWith("pr_rp_"));

  it("existen en español y en inglés, con los mismos marcadores", () => {
    expect(claves.length).toBeGreaterThan(25);
    for (const clave of claves) {
      expect(pro.en[clave], clave).toBeTruthy();
      const marcadores = (s: string) => (s.match(/\{[a-z]+\}/g) ?? []).sort();
      expect(marcadores(pro.en[clave]), clave).toEqual(marcadores(pro.es[clave]));
    }
    expect(Object.keys(pro.en).filter((k) => k.startsWith("pr_rp_")).sort()).toEqual([...claves].sort());
  });

  it("no usan las palabras que el producto no puede decir ni nombran colores como elementos", () => {
    const prohibidas = /validad|producci[oó]n|certificad|fep-ready|\bvalidated\b|\bproduction\b|\bcertified\b/i;
    const colores = /\b(oro|cian|rojo|verde|azul|amarillo|gold|cyan|red|green|blue|yellow)\b/i;
    for (const clave of claves) {
      for (const idioma of ["es", "en"] as const) {
        expect(pro[idioma][clave], `${idioma}.${clave}`).not.toMatch(prohibidas);
        expect(pro[idioma][clave], `${idioma}.${clave}`).not.toMatch(colores);
      }
    }
  });

  it("el control del detector: sí encuentra lo prohibido cuando está", () => {
    const prohibidas = /validad|producci[oó]n|certificad|fep-ready|\bvalidated\b|\bproduction\b|\bcertified\b/i;
    expect("protonación validada").toMatch(prohibidas);
    expect("listo para producción").toMatch(prohibidas);
    expect("FEP-ready").toMatch(prohibidas);
    expect("protonación declarada por ti").not.toMatch(prohibidas);
  });

  it("no hay nombres de formato que no existan (SDF no es un receptor)", () => {
    for (const clave of claves) {
      for (const idioma of ["es", "en"] as const) {
        expect(pro[idioma][clave], `${idioma}.${clave}`).not.toMatch(/\bsdf\b/i);
      }
    }
  });
});
