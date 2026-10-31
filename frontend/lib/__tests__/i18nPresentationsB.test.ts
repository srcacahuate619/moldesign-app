import { describe, expect, it, vi } from "vitest";
import { TRANSLATIONS, interpolar } from "../../context/LanguageContext";
import { aaInfoFromName, formatResidueLabel } from "../aminoAcidPresentation";
import { antiTargetFieldText } from "../antiTargetPresentation";
import { etiquetaPPB } from "../admetEtiquetas";
import { etiquetaDeCarga } from "../../components/interfaces/pro/EstadoDelLigando";
import { getFeatureExplanation } from "../../components/interfaces/pro/ProXaiTab";
import { engineExplanation, engineStateLabel, engineStatusDetail } from "../enginePresentation";
import { ENGINE_LABELS, toEngineStatus } from "../../context/DownloadProvider";
import { comprobarWebGL, reiniciarComprobacionWebGL, webglReason } from "../webgl";
import { appLocale } from "../formatoNumerico";
import { formatoDeNumero } from "../elevacion";
import { formatRunMoment, whyRunCannotOpen } from "../../components/cases/CaseRunHistoryModal";
import type { CaseRun } from "../cases/types";
import { verificarLimitesDelContexto } from "../dossier";
import { FrontendError, frontendList, presentError, type FrontendText } from "../frontendError";
import { translateValidationMsg } from "../auth";
import { motivoDeRespuesta } from "../../context/motivoDeTurno";
import { recortar, construirMailtoDeReporte } from "../reporteDeIA";
const tFor = (locale: "es" | "en") => (key: string, values?: Readonly<Record<string, string | number>>) => interpolar(TRANSLATIONS[locale][key] ?? key, values);
const spanishNames = ["Alanina", "Valina", "Leucina", "Isoleucina", "Metionina", "Fenilalanina", "Triptófano", "Tirosina", "Histidina", "Serina", "Treonina", "Asparagina", "Glutamina", "Aspartato", "Glutamato", "Lisina", "Arginina", "Cisteína", "Prolina", "Glicina"];
const englishNames = ["Alanine", "Valine", "Leucine", "Isoleucine", "Methionine", "Phenylalanine", "Tryptophan", "Tyrosine", "Histidine", "Serine", "Threonine", "Asparagine", "Glutamine", "Aspartate", "Glutamate", "Lysine", "Arginine", "Cysteine", "Proline", "Glycine"];
describe.each(["es", "en"] as const)("presentaciones de B en %s", locale => {
  const t = tFor(locale);
  it("localiza las 20 identidades, categorías y cadenas sin alterar sus códigos ni colores", () => {
    const codes = "ALA VAL LEU ILE MET PHE TRP TYR HIS SER THR ASN GLN ASP GLU LYS ARG CYS PRO GLY".split(" ");
    codes.forEach((code,index) => {
      const info = aaInfoFromName("A:"+code+"123", t);
      expect(info.name).toBe((locale === "es" ? spanishNames : englishNames)[index]);
      expect(info.code).toBe(code);
      expect(info.typeColor).toBe(aaInfoFromName(code).typeColor);
      expect(info.typeCode).toBe(aaInfoFromName(code).typeCode);
      if (locale === "en") expect(info.type).not.toMatch(/Hidrofóbico|Aromático|Ácido|Básico|Estructural|reactivo/);
    });
    expect(formatResidueLabel("B:LEU123",t)).toBe(locale === "es" ? "LEU123 · cadena B" : "LEU123 · chain B");
    expect(aaInfoFromName("XYZ1", t).type).toBe(locale === "es" ? "Residuo" : "Residue");
  });
  it("traduce cargas y umbrales PPB manteniendo los números y el faltante", () => {
    const charge = [null,0,1,2,-1,-2].map(n=>etiquetaDeCarga(n,t).texto);
    expect(charge).toEqual(locale === "es" ? ["carga sin determinar","especie neutra","catión +1","catión +2","anión −1","anión -2"] : ["charge undetermined","neutral species","cation +1","cation +2","anion −1","anion -2"]);
    expect(["extreme","high","medium","low"].map(code=>etiquetaPPB(code,t))).toEqual(locale === "es" ? ["Extrema (>99 %)","Alta (>90 %)","Media","Baja (≤90 %)"] : ["Extreme (>99 %)","High (>90 %)","Medium","Low (≤90 %)"]);
    expect(etiquetaPPB(null,t)).toBeNull(); expect(etiquetaPPB("external-code",t)).toBe("external-code");
  });
  it("interpola ECIF y capas de distancia después de elegir la plantilla", () => {
    expect(getFeatureExplanation("ecif_C_aro_N",t).label).toBe(locale === "es" ? "Interacción C-aro-N" : "Interaction C-aro-N");
    expect(getFeatureExplanation("shell_O_N_4_8",t).label).toBe(locale === "es" ? "Capa Distancia O-N (4-8 Å)" : "Distance Shell O-N (4-8 Å)");
    if (locale === "en") for (const feature of ["ecif_C_aro_N","shell_O_N_4_8","molecular_weight"]) expect(getFeatureExplanation(feature,t).desc).not.toMatch(/[ñáéíóú]|Interacci|Propiedad/);
  });
  it("explica el motor por estado y conserva el detalle de Rust", () => {
    for (const state of Object.keys(ENGINE_LABELS) as Array<keyof typeof ENGINE_LABELS>) {
      if (locale === "es") expect(engineStateLabel(state,t)).toBe(ENGINE_LABELS[state]);
      else expect(engineStateLabel(state,t)).not.toMatch(/Motor|motor|Iniciando|arranc/);
      if (["not_installed","spawn_failed","health_failed","disconnected"].includes(state)) expect(engineExplanation(state,t)).toBeTruthy();
    }
    expect(engineStatusDetail(toEngineStatus({ state: "unknown" }),t)).toBe(locale === "es" ? "El motor devolvió un estado que esta versión no reconoce." : "The engine returned a state that this version does not recognize.");
    expect(engineStatusDetail(toEngineStatus({ state: "spawn_failed", detail: "Rust: permiso denegado" }),t)).toBe("Rust: permiso denegado");
  });
  it("traduce un diagnóstico WebGL cacheado sin repetir la medición", () => {
    reiniciarComprobacionWebGL();
    const context = vi.spyOn(HTMLCanvasElement.prototype,"getContext").mockReturnValue(null);
    const state = comprobarWebGL();
    const before = context.mock.calls.length;
    expect(webglReason(state,t)).toContain(locale === "es" ? "este equipo no expone" : "this computer does not expose");
    expect(comprobarWebGL()).toBe(state); expect(context).toHaveBeenCalledTimes(before);
    context.mockRestore(); reiniciarComprobacionWebGL();
  });
  it("usa la región de la app para el historial y la elevación", () => {
    expect(appLocale(locale)).toBe(locale === "en" ? "en-US" : "es-MX");
    expect(formatRunMoment("2026-10-25T12:30:00Z",locale,t)).toMatch(locale === "en" ? /Oct/ : /oct/);
    expect(formatRunMoment("invalid",locale,t)).toBe(locale === "es" ? "Fecha no legible" : "Unreadable date");
    expect(formatoDeNumero(1234.5,locale)).toBe(new Intl.NumberFormat(appLocale(locale),{minimumFractionDigits:1,maximumFractionDigits:1}).format(1234.5));
    const failed = { taskId: "run", executionState: "failed", startedAt: "2026-10-25" } as CaseRun;
    expect(whyRunCannotOpen(failed,t)).toBe(locale === "es" ? "Esta corrida falló, así que no produjo ningún informe." : "This run failed, so it did not produce a report.");
  });
  it("traduce preguntas y excesos del dossier sin cambiar el texto del investigador", () => {
    const context = { question: "a".repeat(4500) }; const bytes=JSON.stringify(context);
    let error: unknown; try { verificarLimitesDelContexto(context); } catch (cause) { error=cause; }
    expect(error).toBeInstanceOf(FrontendError);
    const shown=presentError(error,t);
    expect(shown).toContain(locale === "es" ? "¿Qué intenta responder este caso?" : "What question does this case address?");
    expect(shown).toContain(locale === "es" ? "500 de más" : "500 too many");
    expect(JSON.stringify(context)).toBe(bytes);
  });
  it("traduce validación por código y conserva mensajes sin código", () => {
    const messages: FrontendText[] = [translateValidationMsg({type:"string_too_short",ctx:{min_length:8},loc:["body","password"],msg:"arbitrary backend wording"}),translateValidationMsg({type:"string_too_short",ctx:{min_length:3},loc:["body","username"],msg:"other wording"})];
    expect(presentError(new FrontendError(frontendList(messages,"; ")),t)).toBe(locale === "es" ? "La contraseña debe tener al menos 8 caracteres.; El nombre de usuario debe tener al menos 3 caracteres." : "The password must have at least 8 characters.; The username must have at least 3 characters.");
    expect(translateValidationMsg({msg:"texto externo sin código",loc:["body","password"]})).toBe("texto externo sin código");
  });
  it("traduce fallbacks HTTP y el recorte del correo, preservando detalle y contenido externos", async () => {
    const response={status:401,json:async()=>({})};
    expect(await motivoDeRespuesta(response,t)).toBe(locale === "es" ? "La sesion caduco. Volve a entrar y repeti la pregunta." : "The session expired. Sign in again and repeat the question.");
    expect(await motivoDeRespuesta({...response,json:async()=>({detail:"mensaje del backend"})},t)).toBe("mensaje del backend");
    expect(recortar("abcdefgh",4,t)).toBe(locale === "es" ? "abcd\n\n[…recortado: la respuesta tenía 8 caracteres]" : "abcd\n\n[…truncated: the response contained 8 characters]");
    const mail=construirMailtoDeReporte({respuesta:"x".repeat(1300),proveedor:"local"},{asunto:"Report",cabecera:"Header",etiquetaProveedor:"Provider",etiquetaRespuesta:"Answer"},t);
    expect(decodeURIComponent(mail)).toContain(locale === "es" ? "recortado" : "truncated");
  });
  it("traduce explicaciones locales conocidas, con fallback para IDs externos", () => {
    for (const id of ["5VA1","7SRQ","4NY4"]) for (const field of ["risk","targetFunction","bioDetails","mitigationSar"] as const) {
      const shown=antiTargetFieldText(id,field,"fallback",t);
      expect(shown).not.toBe("fallback");
      if(locale === "en") expect(shown).not.toMatch(/[ñáéíóú]|Estrategias|Agonismo|El bloqueo/);
    }
    expect(antiTargetFieldText("EXTERNAL","risk","riesgo externo",t)).toBe("riesgo externo");
  });
});
