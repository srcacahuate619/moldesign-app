/**
 * Monta el tráiler de la Microsoft Store a partir de las tomas de `capturas.mjs`.
 *
 *   node scripts/trailer-store/montar.mjs --tomas D:\moldesign-qa\trailer-es\tomas --salida D:\moldesign-qa\trailer-es\montaje
 *
 * Tres pasos, cada uno reutiliza lo anterior si ya existe (`--rehacer` los repite):
 *   1. `plan.json`: la escaleta (los seis pasos del tutorial de Inicio, con sus títulos) sobre las tomas reales.
 *   2. `recorrido.mp4`: la primera parte, fotograma a fotograma desde `montaje.html` (casi sin pérdida).
 *   3. `MolDesign_trailer_<idioma>.mp4`: el recorrido, el vídeo que generó Molcy y la música, con la codificación que pide
 *      Partner Center (H.264 High, 1920×1080, 2 B consecutivos, GOP cerrado de medio segundo, CABAC, AAC-LC 48 kHz
 *      estéreo a 384 kb/s, moov al principio, sin listas de edición); y la miniatura PNG 1920×1080.
 *
 * `--hasta <s>` corta el recorrido (para revisar un tramo); `--solo-miniatura` rehace sólo la miniatura (`--portada-s`
 * elige el instante del vídeo de Molcy de la portada, que es también el arranque); `--ffmpeg <exe>` (o FFMPEG) si no está en el PATH.
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, readFile, readdir, writeFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { chromium } from "@playwright/test";
import { escribirMusica } from "./musica.mjs";

const AQUI = path.dirname(fileURLToPath(import.meta.url));
const FRONTEND = path.resolve(AQUI, "..", "..");
const REPO = path.resolve(FRONTEND, "..");
const FPS = 30;

const args = process.argv.slice(2);
const valor = (nombre, defecto) => (args.includes(nombre) ? args[args.indexOf(nombre) + 1] : defecto);
const TOMAS = path.resolve(valor("--tomas", "tomas-trailer"));
const SALIDA = path.resolve(valor("--salida", path.join(TOMAS, "..", "montaje")));
const FFMPEG = valor("--ffmpeg", process.env.FFMPEG || "ffmpeg");
const HASTA = valor("--hasta", null);
const REHACER = args.includes("--rehacer");

const TEXTOS = {
  es: {
    intro: { marca: "MOLDESIGN", titulo: "Del caso al vídeo, en seis pasos.", subtitulo: "Docking con Vina en tu equipo · vídeos con Molcy (Beta)" },
    pasos: ["Crea un caso", "Selecciona un receptor", "Ejecuta la evaluación", "Guárdala en Moldex", "Elígela en Molcy", "Genera el vídeo"],
    paso: (n) => `PASO ${String(n).padStart(2, "0")} / 06`,
    demo: "LOS DEL CATÁLOGO SON DE DEMOSTRACIÓN",
    vina: (x) => `VINA 1.2.7 EN TU EQUIPO · ACELERADO ×${x}`,
    render: (min, gpu) => `RENDER EN GPU · ${min} MIN REALES EN UNA ${gpu}, ACELERADO`,
    resultado: { num: "RESULTADO", titulo: "El vídeo que generó Molcy", nota: "8HFI (DEMOSTRACIÓN) · DESIPRAMINA · POSE DE VINA" },
    titulo: "MolDesign: del caso al vídeo",
    portada: "Del caso al vídeo,\nen seis pasos.",
  },
  en: {
    intro: { marca: "MOLDESIGN", titulo: "From case to video in six steps.", subtitulo: "Docking with Vina on your computer · videos with Molcy (Beta)" },
    pasos: ["Create a case", "Select a receptor", "Run the evaluation", "Save it in Moldex", "Choose it in Molcy", "Generate the video"],
    paso: (n) => `STEP ${String(n).padStart(2, "0")} / 06`,
    demo: "CATALOG RECEPTORS ARE DEMOS",
    vina: (x) => `VINA 1.2.7 ON YOUR COMPUTER · SPED UP ×${x}`,
    render: (min, gpu) => `RENDERED ON GPU · ${min} MIN REAL TIME ON A ${gpu}, SPED UP`,
    resultado: { num: "RESULT", titulo: "The video Molcy made", nota: "8HFI (DEMO) · DESIPRAMINE · VINA POSE" },
    titulo: "MolDesign: from case to video",
    portada: "From case to video\nin six steps.",
  },
};

// --- Escaleta ---------------------------------------------------------------------------------------------------------

function constructor(registro) {
  const porId = new Map(registro.tomas.map((t) => [t.id, t]));
  const src = (id) => pathToFileURL(path.resolve(TOMAS, toma(id).archivo)).href;
  const toma = (id) => {
    const t = porId.get(id);
    if (!t) throw new Error(`Falta la toma ${id}`);
    return t;
  };
  const serie = (prefijo) => registro.tomas.filter((t) => t.id.startsWith(prefijo)).map((t) => t.id);
  const planos = [];
  const rotulos = [];
  const cues = { clics: [] };
  let t = 0;
  let camara = { cx: 720, cy: 405, z: 1 };
  let cursor = null;

  const centro = ([x, y, w, h]) => ({ x: x + w / 2, y: y + h / 2 });
  /** El encuadre que contiene todas las cajas con margen, sin pasar de `zmax`. */
  function encuadre(cajas, { zmax = 1.9, margen = 70, z = null } = {}) {
    const x0 = Math.min(...cajas.map((c) => c[0])), y0 = Math.min(...cajas.map((c) => c[1]));
    const x1 = Math.max(...cajas.map((c) => c[0] + c[2])), y1 = Math.max(...cajas.map((c) => c[1] + c[3]));
    const zz = z ?? Math.min(zmax, 1440 / (x1 - x0 + 2 * margen), 810 / (y1 - y0 + 2 * margen));
    return { cx: (x0 + x1) / 2, cy: (y0 + y1) / 2, z: Math.max(1, zz) };
  }

  /**
   * Un plano: una o varias tomas en su instante local, la cámara que viaja desde donde quedó la anterior hasta `destino`,
   * y, si hay `objetivo`, el cursor que llega a él y pulsa en `clic` (con el recuadro del tutorial).
   */
  function plano({ ids, tiempos = null, dur, destino, llegada = 0.62, objetivo = null, clic = null, entra = 0.22, fundido = 0,
    anillo = true, desdeCursor = null, presionado = null, rutaCursor = null }) {
    const imagenes = ids.map((id, i) => ({ t: tiempos ? tiempos[i] : (i * dur) / ids.length, src: src(id) }));
    // El instante va siempre al final del fotograma clave: una posición heredada de otro plano trae su propio `t`
    // (la ruta del giro) y, delante, lo pisaría. Pasó: el cursor se quedaba quieto y pulsaba fuera de «Guardar en MolDex».
    const punto = ({ x, y }) => ({ x, y });
    const p = { inicio: t, dur, entra: planos.length ? entra : 0, imagenes, fundido,
      camara: [{ ...camara, t: 0 }, { ...camara, t: 0.08 }, { ...destino, t: dur * llegada }] };
    if (objetivo || rutaCursor) {
      const meta = punto(objetivo ? centro(objetivo) : rutaCursor.at(-1));
      const inicio = punto(desdeCursor ?? cursor ?? { x: meta.x + 240, y: meta.y + 160 });
      p.cursor = rutaCursor ? rutaCursor : [{ ...inicio, t: 0.05 }, { ...meta, t: (clic ?? dur) - 0.12 }];
      if (clic != null) { p.clics = [clic]; cues.clics.push(t + clic); }
      if (presionado) p.presionado = presionado;
      if (objetivo && anillo) p.anillo = { caja: objetivo, desde: Math.max(0.1, (clic ?? dur) - 0.6), hasta: null };
      cursor = meta;
    }
    // Fotogramas clave en orden: si no, `clave()` sostendría el primero todo el plano.
    for (const claves of [p.camara, p.cursor].filter(Boolean)) {
      for (let i = 1; i < claves.length; i++) {
        if (!(claves[i].t > claves[i - 1].t)) throw new Error(`Fotogramas clave fuera de orden en ${ids[0]}: ${claves.map((c) => c.t).join(", ")}`);
      }
    }
    planos.push(p);
    camara = { ...destino };
    t += dur;
    return p;
  }

  function paso(numero, titulo, nota, inicio = t) {
    if (rotulos.length) rotulos.at(-1).fin = inicio;
    rotulos.push({ inicio, fin: null, num: textos.paso(numero), titulo, nota });
  }

  function cerrar(finRecorrido) {
    for (let i = 0; i < planos.length; i++) {
      const sig = planos[i + 1];
      planos[i].fin = sig ? sig.inicio + sig.entra : finRecorrido;
    }
    rotulos.at(-1).fin = finRecorrido;
  }

  let textos;
  return { toma, serie, encuadre, centro, plano, paso, cerrar, planos, rotulos, cues,
    get t() { return t; }, set t(v) { t = v; }, set textos(v) { textos = v; }, get camara() { return camara; } };
}

function submuestra(lista, n) {
  if (lista.length <= n) return lista;
  return Array.from({ length: n }, (_, i) => lista[Math.round((i * (lista.length - 1)) / (n - 1))]);
}

function escaleta(registro, idioma, primerFotograma, gpu, portada) {
  const x = TEXTOS[idioma];
  const B = constructor(registro);
  B.textos = x;
  const caja = (id) => B.toma(id).caja;
  const intro = { inicio: 0, fin: 3.2, portada };
  B.t = intro.fin - 0.55; // el primer plano espera debajo del título, que se funde

  // 1. Crea un caso.
  B.paso(1, x.pasos[0], null, intro.fin - 0.15);
  B.plano({ ids: ["01-caso"], dur: 1.9, destino: B.encuadre([caja("01-caso")], { zmax: 1.75, margen: 160 }), llegada: 0.7,
    objetivo: caja("01-caso"), clic: 1.45 });
  const tecleo = B.serie("01-tecleo-");
  const tiemposTecleo = [0, ...tecleo.map((_, i) => 0.3 + i * 0.075), 0.3 + tecleo.length * 0.075 + 0.25];
  B.plano({ ids: ["01-dialogo-vacio", ...tecleo, "01-dialogo-lleno"], tiempos: tiemposTecleo, dur: 2.5,
    destino: B.encuadre([caja("01-dialogo-vacio"), caja("01-dialogo-lleno")], { zmax: 1.6, margen: 90 }), llegada: 0.3,
    objetivo: caja("01-dialogo-lleno"), clic: 2.15 });

  // 2. Selecciona un receptor (del catálogo de demostración).
  B.paso(2, x.pasos[1], x.demo);
  B.plano({ ids: ["02-receptor"], dur: 1.5, destino: B.encuadre([caja("02-receptor")], { zmax: 1.7, margen: 150 }),
    objetivo: caja("02-receptor"), clic: 1.1 });
  B.plano({ ids: ["02-buscador", "02-encontrado"], tiempos: [0, 0.7], dur: 2.0,
    destino: B.encuadre([caja("02-buscador"), caja("02-encontrado")], { zmax: 1.6, margen: 80 }), llegada: 0.4,
    objetivo: caja("02-encontrado"), clic: 1.6 });

  // 3. Ejecuta la evaluación: la molécula, el botón y Vina trabajando (acelerado).
  const ejemplo = B.toma("03-smiles-ejemplo");
  const smiles = B.toma("03-smiles-ligando");
  B.paso(3, x.pasos[2], null);
  B.plano({ ids: ["03-smiles-ejemplo", "03-smiles-ligando"], tiempos: [0, 0.75], dur: 1.6,
    destino: B.encuadre([smiles.caja], { z: 1.35 }), llegada: 0.45, objetivo: ejemplo.caja, clic: 0.55, anillo: false });
  B.plano({ ids: ["03-evaluar"], dur: 1.3, destino: B.encuadre([caja("03-evaluar")], { zmax: 1.6, margen: 170 }),
    objetivo: caja("03-evaluar"), clic: 0.95 });
  const evaluando = B.serie("03-evaluando-0");
  const realEval = (B.toma("04-resultado-arriba").t_ms - B.toma("03-evaluar").t_ms) / 1000;
  const durEval = 2.6;
  const factorVina = Math.max(2, Math.round(realEval / durEval));
  B.rotulos.at(-1).nota = x.vina(factorVina);
  const fotosEval = ["03-evaluando-boton", ...submuestra(evaluando, 10), "04-resultado-arriba"];
  B.plano({ ids: fotosEval, tiempos: fotosEval.map((_, i) => (i === 0 ? 0 : 0.35 + ((i - 1) * (durEval - 0.75)) / (fotosEval.length - 2))),
    dur: durEval, fundido: 0.12, destino: { cx: 980, cy: 260, z: 1.35 }, llegada: 0.35 });

  // 4. Guárdala en Moldex: la pose acoplada (con «Identificar mi diseño», si se capturó), girándola, y el botón.
  B.paso(4, x.pasos[3], null);
  const giroPose = B.serie("04b-giro-");
  if (giroPose.length) {
    const visor = B.toma(giroPose.at(-1)).visor;
    const boton = B.toma("04b-pose-antes").caja;
    const enfoque = B.serie("04b-enfoque-");
    B.plano({ ids: ["04b-pose-antes", ...enfoque], tiempos: [0, ...enfoque.map((_, i) => 0.95 + i * 0.05)], dur: 2.0,
      destino: B.encuadre([visor], { z: 1.45 }), llegada: 0.35, objetivo: boton, clic: 0.85 });
    const cx = visor[0] + visor[2] / 2, cy = visor[1] + visor[3] / 2;
    B.plano({ ids: giroPose, tiempos: giroPose.map((_, i) => 0.2 + (i * 1.9) / giroPose.length), dur: 2.4, entra: 0.08,
      destino: { cx, cy, z: 1.75 }, llegada: 0.9,
      rutaCursor: [{ t: 0.0, x: cx - 120, y: cy + 30 }, { t: 0.18, x: cx - 100, y: cy }, { t: 2.1, x: cx + 102, y: cy }],
      presionado: [[0.2, 2.12]] });
  }
  const giro = giroPose.length ? [] : B.serie("04-giro-");
  const visor = giro.length ? B.toma(giro.at(-1)).visor : null;
  if (giro.length && visor) {
    const cx = visor[0] + visor[2] / 2, cy = visor[1] + visor[3] / 2;
    const durGiro = 2.0;
    B.plano({ ids: giro, tiempos: giro.map((_, i) => 0.25 + (i * 1.5) / giro.length), dur: durGiro,
      destino: { cx, cy, z: 1.7 }, llegada: 0.5,
      rutaCursor: [{ t: 0.0, x: cx - 140, y: cy + 40 }, { t: 0.22, x: cx - 90, y: cy }, { t: 1.75, x: cx + 90, y: cy }],
      presionado: [[0.24, 1.78]] });
  }
  B.plano({ ids: ["04-guardar"], dur: 1.5, destino: B.encuadre([caja("04-guardar")], { zmax: 1.7, margen: 170 }),
    objetivo: caja("04-guardar"), clic: 1.1 });
  B.plano({ ids: ["04-guardado"], dur: 0.8, destino: B.camara, objetivo: caja("04-guardado"), anillo: true });

  // 5. Elígela en Molcy.
  B.paso(5, x.pasos[4], null);
  B.plano({ ids: ["05-molcy-sin-fuente", "05-corrida"], tiempos: [0, 1.0], dur: 2.2,
    destino: B.encuadre([caja("05-corrida")], { zmax: 1.6, margen: 200 }), llegada: 0.4, objetivo: caja("05-corrida"), clic: 0.85 });

  // 6. Genera el vídeo: formato horizontal, «Generar video» y el render en la GPU (acelerado).
  B.paso(6, x.pasos[5], null);
  B.plano({ ids: ["06-formato-vertical", "06-formato-horizontal"], tiempos: [0, 0.95], dur: 1.4,
    destino: B.encuadre([caja("06-formato-horizontal"), caja("06-generar")], { zmax: 1.6, margen: 120 }), llegada: 0.45,
    objetivo: caja("06-formato-horizontal"), clic: 0.85 });
  B.plano({ ids: ["06-generar"], dur: 1.2, destino: B.camara, objetivo: caja("06-generar"), clic: 0.8 });
  const render = B.serie("07-render-");
  const completo = B.toma("07-completo");
  const v = completo.caja;
  const durRender = 2.8;
  B.rotulos.at(-1).nota = x.render(Math.round(registro.render_min), gpu);
  const fotosRender = submuestra(render, 14);
  // El fotograma en vivo, donde lo midió la captura (o, si no se midió, encima del vídeo terminado: 584×328 en los dos).
  const vivo = [...render].reverse().map((id) => B.toma(id).vivo).find(Boolean) ?? [v[0], v[1] - 201, v[2], v[3]];
  B.plano({ ids: fotosRender, tiempos: fotosRender.map((_, i) => (i * durRender) / fotosRender.length),
    dur: durRender, fundido: 0.14, destino: B.encuadre([vivo], { zmax: 1.6, margen: 90 }), llegada: 0.4 });
  // El vídeo terminado (con su origen conservado) y, sobre su reproductor, el primer fotograma del MP4 de Molcy: la cámara
  // entra en él hasta llenar la pantalla, y ahí empieza el vídeo de verdad.
  const lleno = { cx: v[0] + v[2] / 2, cy: v[1] + v[3] / 2, z: Math.min(1440 / v[2], 810 / v[3]) };
  B.plano({ ids: ["07-completo"], dur: 0.9, destino: { cx: v[0] + v[2] / 2, cy: 810 - 405 / 1.45, z: 1.45 }, llegada: 0.5, entra: 0.18 });
  const entrada = B.plano({ ids: ["07-completo"], dur: 1.0, destino: lleno, llegada: 0.92, entra: 0 });
  entrada.libre = true;
  entrada.superpuesta = { src: pathToFileURL(primerFotograma).href, caja: v, desde: 0 };

  const finRecorrido = B.t;
  B.cerrar(finRecorrido);
  return { fps: FPS, duracion: finRecorrido, intro, planos: B.planos, rotulos: B.rotulos, cues: B.cues,
    idioma, factor_vina: factorVina, real_eval_s: realEval };
}

// --- Fotogramas -------------------------------------------------------------------------------------------------------

function ffmpeg(argumentos, { entrada = false } = {}) {
  const proc = spawn(FFMPEG, ["-hide_banner", "-loglevel", "error", "-y", ...argumentos], { stdio: [entrada ? "pipe" : "ignore", "inherit", "inherit"] });
  const fin = new Promise((ok, mal) => proc.on("close", (c) => (c === 0 ? ok() : mal(new Error(`ffmpeg salió con ${c}`)))));
  return { proc, fin };
}

async function pagina(browser) {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.goto(pathToFileURL(path.join(AQUI, "montaje.html")).href);
  return page;
}

async function renderRecorrido(browser, plan, destino) {
  const page = await pagina(browser);
  await page.evaluate((p) => window.cargar(p), plan);
  const total = Math.round((HASTA ? Math.min(Number(HASTA), plan.duracion) : plan.duracion) * FPS);
  const { proc, fin } = ffmpeg(["-f", "image2pipe", "-framerate", String(FPS), "-c:v", "png", "-i", "-",
    "-c:v", "libx264", "-preset", "slow", "-crf", "6", "-pix_fmt", "yuv420p", "-r", String(FPS), destino], { entrada: true });
  const inicio = Date.now();
  for (let i = 0; i < total; i++) {
    await page.evaluate((t) => window.pintar(t), i / FPS);
    const png = await page.screenshot({ type: "png", clip: { x: 0, y: 0, width: 1920, height: 1080 } });
    if (!proc.stdin.write(png)) await new Promise((r) => proc.stdin.once("drain", r));
    if (i % 60 === 0) process.stdout.write(`\r  recorrido: ${i}/${total} fotogramas (${((Date.now() - inicio) / 1000).toFixed(0)} s)`);
  }
  proc.stdin.end();
  await fin;
  process.stdout.write(`\r  recorrido: ${total}/${total} fotogramas en ${((Date.now() - inicio) / 1000).toFixed(0)} s\n`);
  await page.close();
}

async function renderRotulo(browser, rotulo, destino) {
  const page = await pagina(browser);
  await page.evaluate((r) => window.soloRotulo(r), rotulo);
  await page.waitForTimeout(200);
  await page.screenshot({ path: destino, omitBackground: true, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
  await page.close();
}

// --- Final ------------------------------------------------------------------------------------------------------------

async function duracionDe(archivo) {
  // ffmpeg -i escribe la duración en stderr; sin ffprobe a mano.
  return new Promise((ok, mal) => {
    const p = spawn(FFMPEG, ["-hide_banner", "-i", archivo], { stdio: ["ignore", "ignore", "pipe"] });
    let err = "";
    p.stderr.on("data", (d) => (err += d));
    p.on("close", () => {
      const m = /Duration: (\d+):(\d+):(\d+\.\d+)/.exec(err);
      m ? ok(Number(m[1]) * 3600 + Number(m[2]) * 60 + Number(m[3])) : mal(new Error(`sin duración: ${archivo}`));
    });
  });
}

/** Sonoridad integrada (LUFS, EBU R128) de un archivo de audio. */
async function sonoridadDe(archivo) {
  return new Promise((ok, mal) => {
    const p = spawn(FFMPEG, ["-hide_banner", "-nostats", "-i", archivo, "-af", "ebur128", "-f", "null", "-"], { stdio: ["ignore", "ignore", "pipe"] });
    let err = "";
    p.stderr.on("data", (d) => (err += d));
    p.on("close", () => {
      const todas = [...err.matchAll(/I:\s+(-?\d+(?:\.\d+)?) LUFS/g)];
      todas.length ? ok(Number(todas.at(-1)[1])) : mal(new Error(`sin sonoridad: ${archivo}`));
    });
  });
}

async function final({ plan, recorrido, molcy, rotulo, musica, destino }) {
  const durA = await duracionDe(recorrido);
  const durB = await duracionDe(molcy);
  const sonoridad = await sonoridadDe(musica);
  const cruce = 0.5;
  const offset = durA - cruce;
  const total = offset + durB;
  // El rótulo del resultado entra con el vídeo de Molcy y se va antes de sus propias etiquetas.
  const r0 = offset + 0.7, r1 = offset + 5.2;
  const filtro = [
    `[0:v]settb=1/${FPS},fps=${FPS},format=yuv420p[a]`,
    `[1:v]settb=1/${FPS},fps=${FPS},scale=1920:1080:flags=lanczos,format=yuv420p[b]`,
    `[a][b]xfade=transition=fade:duration=${cruce}:offset=${offset.toFixed(3)}[ab]`,
    `[2:v]format=rgba,fade=t=in:st=${r0.toFixed(3)}:d=0.4:alpha=1,fade=t=out:st=${(r1 - 0.4).toFixed(3)}:d=0.4:alpha=1[r]`,
    `[ab][r]overlay=0:0:enable='between(t,${r0.toFixed(3)},${r1.toFixed(3)})',format=yuv420p,setsar=1[v]`,
    // −16 LUFS, el nivel que recomienda Partner Center: ganancia medida en una primera pasada y limitador a −1,5 dBTP.
    `[3:a]atrim=0:${total.toFixed(3)},asetpts=N/SR/TB,volume=${(-16 - sonoridad).toFixed(2)}dB,alimiter=limit=0.84:level=false,aresample=48000[m]`,
  ].join(";");
  await ffmpeg([
    "-i", recorrido, "-i", molcy, "-loop", "1", "-framerate", String(FPS), "-t", total.toFixed(3), "-i", rotulo, "-i", musica,
    "-filter_complex", filtro, "-map", "[v]", "-map", "[m]",
    "-c:v", "libx264", "-profile:v", "high", "-preset", "slow", "-pix_fmt", "yuv420p",
    "-b:v", "50M", "-maxrate", "50M", "-bufsize", "100M",
    "-x264-params", `bframes=2:b-adapt=0:keyint=${FPS / 2}:min-keyint=${FPS / 2}:scenecut=0:open-gop=0:cabac=1`,
    "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
    "-c:a", "aac", "-profile:a", "aac_low", "-ar", "48000", "-ac", "2", "-b:a", "384k",
    "-movflags", "+faststart", "-use_editlist", "0", "-r", String(FPS), destino,
  ]).fin;
  return { total, offset, durA, durB };
}

/** Miniatura: la portada (la misma composición con la que arranca el tráiler), compuesta en el navegador. */
async function renderMiniatura(browser, portada, destino) {
  const page = await pagina(browser);
  await page.evaluate((p) => window.portada(p), portada);
  await page.waitForTimeout(200);
  await page.screenshot({ path: destino, clip: { x: 0, y: 0, width: 1920, height: 1080 } });
  await page.close();
}

// --- Principal --------------------------------------------------------------------------------------------------------

const registro = JSON.parse(await readFile(path.join(TOMAS, "tomas.json"), "utf8"));
const idioma = registro.idioma;
const x = TEXTOS[idioma];
await mkdir(SALIDA, { recursive: true });
// El primer fotograma del vídeo de Molcy: el montaje lo pone sobre el reproductor de la última captura.
const MOLCY = path.join(TOMAS, "molcy", "molcy.mp4");
const primerFotograma = path.join(SALIDA, "molcy_primer_fotograma.png");
await ffmpeg(["-i", MOLCY, "-frames:v", "1", primerFotograma]).fin;
// La GPU que rindió el vídeo, del estado del trabajo de Molcy: el tiempo del render sólo vale con ella.
const trabajo = JSON.parse(await readFile(path.join(TOMAS, "molcy", "trabajo.json"), "utf8"));
const gpu = String(trabajo.renderizador?.gpu_nombre ?? "GPU").replace(/^NVIDIA GeForce |^AMD Radeon |\/.*$/g, "").toUpperCase();
// La portada: el fotograma de 15,7 s del vídeo de Molcy (la pose con sus interacciones y sin etiquetas, en la escena
// «Resultado» del formato horizontal), ampliado ×1,35 para cubrir todo el cuadro con el ligando a la derecha del título.
// Es la miniatura y el arranque del tráiler.
const fondoPortada = path.join(SALIDA, "portada_fondo.png");
await ffmpeg(["-ss", valor("--portada-s", "15.7"), "-i", MOLCY, "-frames:v", "1", fondoPortada]).fin;
const PORTADA = {
  fondo: pathToFileURL(fondoPortada).href, logo: pathToFileURL(path.join(REPO, "backend", "assets", "logo.png")).href,
  marca: x.intro.marca, titulo: x.portada, subtitulo: x.intro.subtitulo,
  escala: 1.35, centro: [925, 545], destinoX: 1250,
};
const plan = escaleta(registro, idioma, primerFotograma, gpu, PORTADA);
await writeFile(path.join(SALIDA, "plan.json"), JSON.stringify(plan, null, 2) + "\n", "utf8");
console.log(`Plan: ${plan.planos.length} planos, ${plan.duracion.toFixed(2)} s de recorrido (Vina real ${plan.real_eval_s.toFixed(0)} s, ×${plan.factor_vina})`);

const browser = await chromium.launch({ channel: "msedge" });
try {
  if (args.includes("--solo-miniatura")) {
    await renderMiniatura(browser, PORTADA, path.join(SALIDA, `MolDesign_trailer_${idioma}_miniatura.png`));
    process.exit(0);
  }
  const recorrido = path.join(SALIDA, HASTA ? `recorrido_hasta_${HASTA}.mp4` : "recorrido.mp4");
  if (REHACER || !existsSync(recorrido)) await renderRecorrido(browser, plan, recorrido);
  if (HASTA) process.exit(0);
  const rotulo = path.join(SALIDA, "rotulo_resultado.png");
  await renderRotulo(browser, { ...x.resultado, estilo: { left: "96px", top: "112px", bottom: "auto" } }, rotulo);
  const molcy = MOLCY;
  const durB = await duracionDe(molcy);
  const durA = await duracionDe(recorrido);
  const musica = path.join(SALIDA, "musica.wav");
  await escribirMusica(musica, { duracion: durA - 0.5 + durB, clics: plan.cues.clics, entradaMolcy: durA - 0.5 });
  const destino = path.join(SALIDA, `MolDesign_trailer_${idioma}.mp4`);
  const miniatura = path.join(SALIDA, `MolDesign_trailer_${idioma}_miniatura.png`);
  const r = await final({ plan, recorrido, molcy, rotulo, musica, destino });
  await renderMiniatura(browser, PORTADA, miniatura);
  await writeFile(path.join(SALIDA, "trailer.json"), JSON.stringify({
    archivo: path.basename(destino), titulo: x.titulo, duracion_s: Math.round(r.total * 100) / 100,
    recorrido_s: r.durA, molcy_s: r.durB, entrada_molcy_s: r.offset, idioma, tomas: TOMAS,
    molcy_trabajo: registro.molcy_trabajo, render_min: registro.render_min,
  }, null, 2) + "\n", "utf8");
  console.log(`Tráiler: ${destino} (${r.total.toFixed(2)} s)`);
} finally {
  await browser.close();
}
