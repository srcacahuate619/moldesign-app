import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { TRANSLATIONS, interpolar } from "../../context/LanguageContext";
import {
  DESCRIPTOR_FEATURES, ECIF_LIGAND_TYPES, ECIF_PROTEIN_TYPES, SHELL_LIGAND_ELEMENTS, SHELL_PROTEIN_ELEMENTS,
  explainFeature, notaDelPar,
} from "../xaiFeatures";

/**
 * Controles de explicabilidad, lado interfaz. La respuesta conocida es el propio Modelo A distribuido
 * (`rescoring/artifacts`): las 167 características que el SHAP puede nombrar y lo que cada nombre
 * significa en el extractor (`rescoring/tests/test_xai_controles_extractor.py`, X01-X02):
 *   ecif_{tipo de PROTEÍNA}_{elemento del LIGANDO}   ·   shell_{elemento PROTEÍNA}_{elemento LIGANDO}_{d}_{D}
 */
const aquí = path.dirname(fileURLToPath(import.meta.url));
const metadatos = JSON.parse(
  readFileSync(path.resolve(aquí, "../../../rescoring/artifacts/model_a_universal.metadata.json"), "utf-8"),
) as { feature_names: string[] };
const características = metadatos.feature_names;
const tFor = (locale: "es" | "en") => (key: string, values?: Readonly<Record<string, string | number>>) =>
  interpolar(TRANSLATIONS[locale][key] ?? key, values);

// Lo que la interfaz NO puede afirmar de una característica: cada frase salió de una afirmación que
// el extractor no respalda (ver `rescoring/feature_extractor.py`: conteos geométricos por distancia).
const AFIRMACIONES_SIN_RESPALDO: Array<[string, RegExp]> = [
  ["los donadores son del ligando", /donador(es)? del ligando|ligand (donor|donors)\b/i],
  ["borde del solvente", /borde del solvente|solvent edge|surface proteica|protein surface/i],
  ["interacción fuerte", /interactuando fuertemente|interacting strongly|fuerte indicador|strong indicator/i],
  ["puentes de H implícitos", /puentes? de h impl[ií]citos|implicit h-?bonds?/i],
  ["bolsillo ambiguo", /bolsillo ambiguo|ambiguous pocket/i],
  ["efectos conformacionales", /efectos conformacionales|conformational effects/i],
  ["propiedad del complejo (falso para logP)", /Propiedad físico-química extraída del complejo|physicochemical property extracted from the complex/i],
];

describe("controles de explicabilidad · características del Modelo A", () => {
  it("K01 las 167 características del modelo tienen etiqueta y descripción propias, en los dos idiomas", () => {
    expect(características).toHaveLength(167);
    for (const locale of ["es", "en"] as const) {
      const t = tFor(locale);
      const sinDescribir = características.filter(f => {
        const e = explainFeature(f, t);
        return e.kind === "unknown" || !e.label || !e.desc || e.label === f || e.desc === t("xai_f_unknown_desc");
      });
      expect(sinDescribir, `${locale}: sin etiqueta o descripción`).toEqual([]);
    }
  });

  it("K02 la lista de descriptores cubre EXACTAMENTE lo que el modelo tiene fuera de ECIF y capas", () => {
    const resto = características.filter(f => !f.startsWith("ecif_") && !f.startsWith("shell_")).sort();
    expect([...DESCRIPTOR_FEATURES].sort()).toEqual(resto);
  });

  it("K03 todo nombre ECIF y de capa del modelo se parsea y se compone de tipos conocidos", () => {
    const ecif = características.filter(f => f.startsWith("ecif_"));
    const capas = características.filter(f => f.startsWith("shell_"));
    expect(ecif).toHaveLength(ECIF_PROTEIN_TYPES.length * ECIF_LIGAND_TYPES.length);
    expect(capas).toHaveLength(SHELL_PROTEIN_ELEMENTS.length * SHELL_LIGAND_ELEMENTS.length * 3);
    for (const f of [...ecif, ...capas]) expect(explainFeature(f, tFor("es")).kind).not.toBe("unknown");
  });

  it("K04 ECIF nombra primero lo de la PROTEÍNA, en la etiqueta y en la descripción", () => {
    for (const locale of ["es", "en"] as const) {
      const t = tFor(locale);
      for (const protein of ECIF_PROTEIN_TYPES) for (const ligand of ECIF_LIGAND_TYPES) {
        const e = explainFeature(`ecif_${protein}_${ligand}`, t);
        const p = t(`xai_p_${protein}`), l = t(`xai_l_${ligand}`);
        // «carbono» (ligando) es prefijo de «carbono alifático» (proteína): se exige que el último
        // «ligando» empiece DESPUÉS de que termine el texto de la proteína, no sólo que aparezca después.
        for (const [donde, texto] of [["etiqueta", e.label], ["descripción", e.desc]] as const) {
          const iniP = texto.indexOf(p);
          expect(iniP, `${locale} ${protein}/${ligand} ${donde}`).toBeGreaterThanOrEqual(0);
          expect(texto.lastIndexOf(l), `${locale} ${protein}/${ligand} ${donde}: ligando tras proteína`)
            .toBeGreaterThanOrEqual(iniP + p.length);
        }
      }
    }
  });

  it("K05 el tipo donador/aceptor sólo se atribuye a la proteína; el ligando sólo tiene elemento", () => {
    for (const ligand of ECIF_LIGAND_TYPES) expect(tFor("es")(`xai_l_${ligand}`)).not.toMatch(/donador|aceptor/i);
    for (const protein of ["N_don", "N_acc", "O_don", "O_acc"] as const)
      expect(tFor("es")(`xai_p_${protein}`)).toMatch(/donador|aceptor/);
    // Caso que el diccionario anterior describía al revés: N con H de la proteína · C del ligando.
    const e = explainFeature("ecif_N_don_C", tFor("es"));
    expect(e.label).toBe("Proteína: nitrógeno con hidrógeno (potencial donador) · Ligando: carbono");
  });

  it("K06 las capas dicen proteína, ligando y el intervalo [desde, hasta) y no se llaman densidad", () => {
    expect(explainFeature("shell_O_N_4_8", tFor("es")).label).toBe("Capa 4–8 Å · proteína O – ligando N");
    expect(explainFeature("shell_C_Br_8_12", tFor("en")).label).toBe("Shell 8–12 Å · protein C – ligand Br");
    const d = explainFeature("shell_N_C_8_12", tFor("es")).desc;
    expect(d).toContain("(incluida)");
    expect(d).toContain("(excluida)");
    expect(d).toMatch(/no es una densidad/);
  });

  it("K07 ninguna descripción afirma lo que el extractor no mide", () => {
    for (const locale of ["es", "en"] as const) {
      const t = tFor(locale);
      for (const [motivo, patrón] of AFIRMACIONES_SIN_RESPALDO) {
        const culpables = [...características, "no_existe_en_el_modelo"].filter(f => {
          const e = explainFeature(f, t);
          return patrón.test(e.label) || patrón.test(e.desc);
        });
        expect(culpables, `${locale}: «${motivo}»`).toEqual([]);
      }
    }
  });

  it("K08 una característica nueva sin descripción se dice sin descripción, no se le inventa una", () => {
    const e = explainFeature("nueva_caracteristica_x", tFor("es"));
    expect(e).toMatchObject({ kind: "unknown", label: "nueva caracteristica x", desc: "Característica del modelo sin descripción registrada." });
  });

  it("K09 las notas químicas siguen la regla: carbono → empaquetamiento, N/O con N/O → compatible sin verificar", () => {
    const casos: Array<[string, string, "carbono" | "polar" | "ninguna"]> = [
      ["C_ali", "O", "carbono"], ["C_aro", "N", "carbono"], ["N_don", "C", "carbono"],
      ["N_don", "O", "polar"], ["O_acc", "N", "polar"], ["O_don", "O", "polar"],
      ["S", "N", "ninguna"], ["N_acc", "Hal", "ninguna"], ["other", "O", "ninguna"], ["N_don", "F", "ninguna"],
    ];
    for (const [p, l, esperado] of casos) expect(notaDelPar(p, l), `${p}/${l}`).toBe(esperado);
    const t = tFor("es");
    expect(explainFeature("ecif_N_don_O", t).desc).toContain(t("xai_ecif_note_polar"));
    expect(explainFeature("ecif_C_ali_O", t).desc).toContain(t("xai_ecif_note_carbon"));
    expect(explainFeature("ecif_S_Hal", t).desc).not.toMatch(/puente/);
  });

  it("K10 contacts_per_ha avisa de que depende de los hidrógenos del archivo (límite medido en X08)", () => {
    for (const f of ["contacts_per_ha_4A", "contacts_per_ha_6A"]) {
      expect(explainFeature(f, tFor("es")).desc).toMatch(/hidrógenos/);
      expect(explainFeature(f, tFor("en")).desc).toMatch(/hydrogens/);
      expect(explainFeature(f, tFor("es")).desc).toMatch(/No es una eficiencia de unión/);
    }
  });

  it("K11 la puntuación de Vina se presenta como entrada del modelo, no como afinidad", () => {
    const e = explainFeature("vina_best_score", tFor("es"));
    expect(e.label).toBe("Puntuación Vina de la mejor pose");
    expect(e.desc).toMatch(/no sobre la afinidad/);
  });
});
