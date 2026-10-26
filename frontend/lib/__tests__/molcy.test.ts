import { describe, expect, it } from "vitest";
import { validarMolcy } from "../molcy";

describe("Contrato local Molcy", () => {
  it("admite una corrida con Búsqueda junto a los receptores del catálogo", () => {
    expect(() => validarMolcy("/molcy/fuentes", {
      moldex:[{id:"m",task_id:"run",nombre:"Corrida con traza",disponible:true,motivo:null,
        escenas_disponibles:["resultado","receptor","busqueda"]}],
      receptores:[{id:"4CA8",nombre:"Receptor disponible",disponible:true,motivo:null}],
    })).not.toThrow();
    expect(() => validarMolcy("/molcy/fuentes", {
      moldex:[{id:"m",nombre:"x",disponible:true,escenas_disponibles:["inventada"]}],receptores:[],
    })).toThrow();
  });
  it("admite la escena Ensamble y sigue rechazando una escena que no conoce", () => {
    const con = (escenas: string[]) => ({ moldex: [{ id: "m", nombre: "x", disponible: true, escenas_disponibles: escenas }], receptores: [] });
    expect(() => validarMolcy("/molcy/fuentes", con(["receptor", "ensamble"]))).not.toThrow();
    expect(() => validarMolcy("/molcy/fuentes", con(["receptor", "trayectoria"]))).toThrow();
  });
  it("rechaza recursos o estimaciones de foto ilegibles antes de mostrar un tiempo", () => {
    expect(() => validarMolcy("/molcy/renderizador",{disponible:true,motivo:null,cpu_hilos:9,cpu_hilos_disponibles:8})).toThrow();
    expect(() => validarMolcy("/molcy/fotos/estimacion",{estimado_s:NaN,muestras:1})).toThrow();
    expect(() => validarMolcy("/molcy/fotos/estimacion",{estimado_s:90,muestras:0})).toThrow();      // un tiempo sin medidas es inventado
    expect(() => validarMolcy("/molcy/fotos/estimacion",{estimado_s:null,muestras:0})).not.toThrow();
    expect(() => validarMolcy("/molcy/fotos/estimacion",{estimado_s:95,muestras:1})).not.toThrow();
    expect(() => validarMolcy("/molcy/renderizador",{disponible:true,motivo:null,espacio_fotos:{"4k":{libre_bytes:NaN,necesario_bytes:1,disponible:true}}})).toThrow();
  });
  it("una sesión de fotos sólo se dibuja si sus tomas y fotos son legibles", () => {
    const sesion = {id:"f",estado:"completo",tipo:"fotos",momentos:[{fotograma:42,tipo:"titulo"}],fotos:[{id:"01",ancho:1080,alto:1920}]};
    expect(() => validarMolcy("/molcy/trabajos/f",sesion)).not.toThrow();
    expect(() => validarMolcy("/molcy/fotos",{id:"f",estado:"en_cola",tipo:"fotos"})).not.toThrow();
    expect(() => validarMolcy("/molcy/trabajos/f",{...sesion,momentos:[{fotograma:0,tipo:"titulo"}]})).toThrow();
    expect(() => validarMolcy("/molcy/trabajos/f",{...sesion,fotos:[{id:"../x",ancho:1,alto:1}]})).toThrow();
    expect(() => validarMolcy("/molcy/trabajos/f",{...sesion,tipo:"otra"})).toThrow();
    expect(() => validarMolcy("/molcy/trabajos/f/revelar",{ruta:"C:/x.png",tipo:"foto"})).not.toThrow();
  });
  it("rechaza fuentes sin disponibilidad y no habilita un render por coerción", () => {
    expect(() => validarMolcy("/molcy/fuentes", {moldex:[{id:"m",nombre:"x",disponible:"true"}],receptores:[]})).toThrow();
    expect(() => validarMolcy("/molcy/renderizador", {disponible:"true",motivo:null})).toThrow();
  });
  it("rechaza límites incompatibles y memoria GPU sin margen verificable", () => {
    const cpu = {cpu_hilos:4,cpu_hilos_disponibles:8,cpu_hilos_maximos:6,gpu_vram_monitorizable:false};
    expect(() => validarMolcy("/molcy/recursos",cpu)).not.toThrow();
    expect(() => validarMolcy("/molcy/recursos",{...cpu,cpu_hilos_maximos:8})).toThrow();
    expect(() => validarMolcy("/molcy/recursos",{...cpu,cpu_uso_actual_pct:NaN})).toThrow();
    const gpu = {...cpu,gpu_vram_monitorizable:true,gpu_vram_total_mib:8192,
      gpu_vram_libre_mib:4096,gpu_vram_reserva_mib:2048,gpu_vram_max_mib:2048,gpu_vram_recomendado_mib:1024};
    expect(() => validarMolcy("/molcy/recursos",gpu)).not.toThrow();
    expect(() => validarMolcy("/molcy/recursos",{...gpu,gpu_vram_max_mib:4096})).toThrow();
    expect(() => validarMolcy("/molcy/recursos",{...gpu,gpu_vram_libre_mib:Infinity})).toThrow();
    expect(() => validarMolcy("/molcy/fuentes",{moldex:[{id:"m",nombre:"x",disponible:true,escenas_disponibles:"receptor"}],receptores:[]})).toThrow();
  });
  it("rechaza estados desconocidos y medidas de disco ilegibles", () => {
    expect(() => validarMolcy("/molcy/trabajos/j", {id:"j",estado:"success"})).toThrow();
    expect(() => validarMolcy("/molcy/renderizador", {disponible:true,motivo:null,espacio:{x:{libre_bytes:NaN,necesario_bytes:1,disponible:true}}})).toThrow();
  });
  it("el video sólo puede usar una ruta de acceso emitida por el backend local", () => {
    expect(() => validarMolcy("/molcy/trabajos/j/acceso",{ruta:"https://other.example/video.mp4"})).toThrow();
    expect(() => validarMolcy("/molcy/trabajos/j/acceso",{ruta:"/molcy/medios/"+"a".repeat(43)})).not.toThrow();
  });
  it("admite trabajos cancelados y rechaza procedencia sin acta", () => {
    expect(() => validarMolcy("/molcy/trabajos/j",{id:"j",estado:"cancelado"})).not.toThrow();
    expect(() => validarMolcy("/molcy/trabajos/j/procedencia",{schema:"molcy.procedencia/1"})).toThrow();
  });
});
