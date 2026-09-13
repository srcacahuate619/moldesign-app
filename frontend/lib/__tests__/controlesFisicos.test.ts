import { describe, expect, it } from "vitest";
import { nombreDeControl } from "../controlesFisicos";
import { TRANSLATIONS } from "../../context/LanguageContext";

// ─────────────────────────────────────────────────────────────────────────
// `checks_que_fallan` viaja con los nombres de columna que devuelve
// PoseBusters —`minimum_distance_to_protein`, `internal_steric_clash`,
// `non-aromatic_ring_non-flatness`— y la pestana «Evidencia estructural» los
// imprimia crudos. En una pantalla en espanol, la linea que decide si una pose
// sirve estaba escrita en ingles y en jerga de identificador.
//
// El codigo canonico NO se pierde: sigue en el resultado, en el dossier y en el
// `title` de cada control. Traducir la etiqueta y perder el identificador
// habria cambiado un problema por otro peor.
// ─────────────────────────────────────────────────────────────────────────

/** El `t` real del diccionario, para no probar contra un doble complaciente. */
const t = (clave: string): string => TRANSLATIONS.es[clave] ?? clave;
const tEn = (clave: string): string => TRANSLATIONS.en[clave] ?? clave;

/** Los nombres que PoseBusters 0.6.5 emite en configuracion `dock`. */
const CONTROLES_DOCK = [
  "mol_pred_loaded",
  "mol_cond_loaded",
  "sanitization",
  "inchi_convertible",
  "all_atoms_connected",
  "no_radicals",
  "bond_lengths",
  "bond_angles",
  "internal_steric_clash",
  "aromatic_ring_flatness",
  "non-aromatic_ring_non-flatness",
  "double_bond_flatness",
  "internal_energy",
  "protein-ligand_maximum_distance",
  "minimum_distance_to_protein",
  "minimum_distance_to_organic_cofactors",
  "minimum_distance_to_inorganic_cofactors",
  "minimum_distance_to_waters",
  "volume_overlap_with_protein",
  "volume_overlap_with_organic_cofactors",
  "volume_overlap_with_inorganic_cofactors",
  "volume_overlap_with_waters",
];

describe("nombreDeControl", () => {
  it.each(CONTROLES_DOCK)("traduce %s", (codigo) => {
    const nombre = nombreDeControl(t, codigo);
    expect(nombre).not.toBe(codigo);
    expect(nombre).not.toMatch(/_/);
  });

  it("cubre los 22 controles de la configuracion dock", () => {
    const sinTraducir = CONTROLES_DOCK.filter((c) => nombreDeControl(t, c) === c);
    expect(sinTraducir).toEqual([]);
  });

  it("un control nuevo se ensena con su codigo, no desaparece", () => {
    // Feo a proposito: asi una version nueva de PoseBusters con un control
    // nuevo se ve —y se puede traducir— en vez de caerse de la lista.
    expect(nombreDeControl(t, "control_que_no_existe")).toBe("control_que_no_existe");
  });

  it("el ingles tambien recibe una frase, no un identificador", () => {
    for (const codigo of CONTROLES_DOCK) {
      const nombre = nombreDeControl(tEn, codigo);
      expect(nombre).not.toBe(codigo);
      expect(nombre).not.toMatch(/_/);
    }
  });

  it("las dos lenguas cubren exactamente los mismos controles", () => {
    const claves = (dic: Record<string, string>) =>
      Object.keys(dic).filter((k) => k.startsWith("se_check_")).sort();
    expect(claves(TRANSLATIONS.es)).toEqual(claves(TRANSLATIONS.en));
  });
});
