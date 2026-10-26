/**
 * La música del tráiler, sintetizada aquí mismo: no hay ninguna pista de terceros ni licencia que declarar.
 *
 * Re menor, 96 pulsos por minuto: un pad (sierras desafinadas con filtro y reverberación), un arpegio suave, un bajo y,
 * en cada pulsación del cursor, un clic discreto. Antes de que entre el vídeo de Molcy sube un barrido y, al entrar, se abre
 * el filtro; el final resuelve en Re menor y se apaga con el cierre de MolDesign. Sale en WAV de 48 kHz, estéreo, 24 bits;
 * el volumen final (−16 LUFS) lo ajusta ffmpeg al codificar.
 */
import { writeFile } from "node:fs/promises";

const SR = 48000;
const PULSO = 60 / 96;
const midi = (n) => 440 * Math.pow(2, (n - 69) / 12);

// Acordes (voces del pad), bajos y notas del arpegio: Rem(add9) – Si♭(add9) – Fa(add9) – Do(add9).
const ACORDES = [
  { pad: [50, 57, 65, 69, 76], bajo: 38, arpegio: [62, 65, 69, 74] },
  { pad: [46, 53, 62, 65, 72], bajo: 34, arpegio: [58, 62, 65, 70] },
  { pad: [53, 60, 65, 69, 79], bajo: 41, arpegio: [60, 65, 69, 72] },
  { pad: [48, 55, 64, 67, 74], bajo: 36, arpegio: [60, 64, 67, 72] },
];
const PATRON = [0, 1, 2, 3, 2, 1, 2, 3];

/** Diente de sierra con polyBLEP (sin el aliasing de la sierra ingenua). */
function sierra(fase, dt) {
  let v = 2 * fase - 1;
  if (fase < dt) { const x = fase / dt; v -= x + x - x * x - 1; }
  else if (fase > 1 - dt) { const x = (fase - 1) / dt; v -= x * x + x + x + 1; }
  return v;
}

/** Reverberación de Schroeder/Freeverb, ligera: cuatro peines amortiguados y dos pasatodo por canal. */
function reverb(entrada, { sala = 0.84, amortiguado = 0.22, desfase = 0 }) {
  const n = entrada.length;
  const salida = new Float32Array(n);
  const escala = SR / 44100;
  for (const d of [1116, 1188, 1277, 1356]) {
    const L = Math.round((d + desfase) * escala);
    const buf = new Float32Array(L);
    let i = 0, filtro = 0;
    for (let k = 0; k < n; k++) {
      const y = buf[i];
      filtro = y * (1 - amortiguado) + filtro * amortiguado;
      buf[i] = entrada[k] + filtro * sala;
      salida[k] += y;
      i = (i + 1) % L;
    }
  }
  for (const d of [556, 441]) {
    const L = Math.round((d + desfase) * escala);
    const buf = new Float32Array(L);
    let i = 0;
    for (let k = 0; k < n; k++) {
      const b = buf[i];
      const x = salida[k];
      salida[k] = -x + b;
      buf[i] = x + b * 0.5;
      i = (i + 1) % L;
    }
  }
  for (let k = 0; k < n; k++) salida[k] *= 0.12;
  return salida;
}

/**
 * @param {string} destino  ruta del WAV
 * @param {{duracion: number, clics: number[], entradaMolcy: number}} cues  en segundos del tráiler
 */
export async function escribirMusica(destino, { duracion, clics, entradaMolcy }) {
  const n = Math.ceil(duracion * SR);
  const L = new Float32Array(n), R = new Float32Array(n);
  const envioL = new Float32Array(n), envioR = new Float32Array(n);

  // Secciones: los acordes cambian cada dos compases (~5 s); el de la entrada de Molcy y el del final son Re menor.
  const antes = Math.max(1, Math.round(entradaMolcy / 5));
  const periodoAntes = entradaMolcy / antes;
  const finalDesde = duracion - 5.2;
  const acordeEn = (t) => {
    if (t >= finalDesde) return 0;
    if (t < entradaMolcy) return Math.floor(t / periodoAntes) % 4;
    return Math.floor((t - entradaMolcy) / 5) % 4;
  };
  const inicioDelAcorde = (t) => {
    if (t >= finalDesde) return finalDesde;
    if (t < entradaMolcy) return Math.floor(t / periodoAntes) * periodoAntes;
    return entradaMolcy + Math.floor((t - entradaMolcy) / 5) * 5;
  };
  const apertura = (t) => (t < entradaMolcy - 2 ? 650 + 250 * Math.min(1, t / 12) : t < entradaMolcy ? 900 + 900 * ((t - (entradaMolcy - 2)) / 2) : 2000);
  const salidaFinal = (t) => Math.max(0, Math.min(1, (duracion - t) / 3.6));
  const entradaInicial = (t) => Math.min(1, t / 1.6);

  // Pad: cada voz, cinco sierras desafinadas (hasta ±7 centésimas) repartidas entre los canales, con un filtro de dos polos
  // que se abre en la entrada de Molcy.
  const OSC = [[0, -7], [0, 3], [1, 7], [1, -3], [2, 0]]; // [canal (0 izq., 1 der., 2 centro), centésimas]
  const osc = ACORDES.map((acorde) => acorde.pad.flatMap((nota, v) => OSC.map(([canal, cents]) => ({
    canal, dt: (midi(nota) * Math.pow(2, cents / 1200)) / SR, nivel: v === 0 ? 0.7 : 0.55, fase: Math.random() }))));
  let lpL1 = 0, lpL2 = 0, lpR1 = 0, lpR2 = 0;
  let actual = acordeEn(0), anterior = actual;
  for (let k = 0; k < n; k++) {
    const t = k / SR;
    const a = acordeEn(t);
    if (a !== actual) { anterior = actual; actual = a; }
    // Fundido entre acordes: el anterior se apaga mientras el nuevo crece (0,9 s).
    const mezcla = Math.min(1, (t - inicioDelAcorde(t)) / 0.9);
    let sl = 0, sr = 0;
    const voces = anterior === actual ? [[actual, 1]] : [[actual, mezcla], [anterior, 1 - mezcla]];
    for (const [indice, peso] of voces) {
      for (const o of osc[indice]) {
        const s = sierra(o.fase, o.dt) * peso * o.nivel;
        o.fase += o.dt; if (o.fase >= 1) o.fase -= 1;
        if (o.canal === 0) sl += s; else if (o.canal === 1) sr += s; else { sl += s * 0.6; sr += s * 0.6; }
      }
    }
    // Los osciladores del acorde que no suena siguen girando: al volver no hay salto de fase audible.
    for (let i = 0; i < 4; i++) if (i !== actual && i !== anterior) for (const o of osc[i]) { o.fase += o.dt; if (o.fase >= 1) o.fase -= 1; }
    const fc = apertura(t);
    const alfa = 1 - Math.exp((-2 * Math.PI * fc) / SR);
    lpL1 += alfa * (sl - lpL1); lpL2 += alfa * (lpL1 - lpL2);
    lpR1 += alfa * (sr - lpR1); lpR2 += alfa * (lpR1 - lpR2);
    const g = 0.034 * entradaInicial(t) * salidaFinal(t) * (t >= entradaMolcy ? 1.15 : 1);
    L[k] += lpL2 * g; R[k] += lpR2 * g;
    envioL[k] += lpL2 * g * 0.9; envioR[k] += lpR2 * g * 0.9;
  }

  // Bajo: un seno con un poco de segundo armónico, uno por compás, desde el primer paso.
  const compas = 4 * PULSO;
  for (let tc = 3.2; tc < duracion - 0.5; tc += compas) {
    const nota = ACORDES[acordeEn(tc + 0.01)].bajo;
    const f = midi(nota);
    const durNota = compas * 0.95;
    const k0 = Math.round(tc * SR), k1 = Math.min(n, Math.round((tc + durNota) * SR));
    for (let k = k0; k < k1; k++) {
      const x = (k - k0) / SR;
      // Ataque y caída suaves: un final en seco se oiría como un chasquido.
      const env = Math.min(1, x / 0.08, (durNota - x) / 0.35) * Math.exp(-x * 0.9) * salidaFinal(k / SR);
      const s = (Math.sin(2 * Math.PI * f * x) + 0.18 * Math.sin(4 * Math.PI * f * x)) * env * 0.065;
      L[k] += s; R[k] += s;
    }
  }

  // Arpegio: corcheas suaves con eco de corchea con puntillo; sube una octava cuando entra Molcy.
  const corchea = PULSO / 2;
  let paso = 0;
  for (let tc = 3.2; tc < duracion - 1.2; tc += corchea, paso++) {
    const acorde = ACORDES[acordeEn(tc + 0.01)];
    const nota = acorde.arpegio[PATRON[paso % PATRON.length]] + (tc >= entradaMolcy ? 12 : 0);
    const f = midi(nota);
    const gan = (tc < entradaMolcy ? 0.022 + 0.012 * Math.min(1, (tc - 3.2) / 14) : 0.03) * salidaFinal(tc) * (paso % 2 ? 0.75 : 1);
    const pan = 0.5 + 0.28 * Math.sin(paso * 0.9);
    for (const [eco, retardo, nivel] of [[0, 0, 1], [1, corchea * 1.5, 0.38], [2, corchea * 3, 0.15]]) {
      const k0 = Math.round((tc + retardo) * SR);
      const k1 = Math.min(n, k0 + Math.round(0.9 * SR));
      const panEco = eco % 2 ? 1 - pan : pan;
      for (let k = k0; k < k1; k++) {
        const x = (k - k0) / SR;
        const env = Math.min(1, x / 0.004) * Math.exp(-x * 7.5);
        const s = (Math.sin(2 * Math.PI * f * x) + 0.25 * Math.sin(4 * Math.PI * f * x) * Math.exp(-x * 14)) * env * gan * nivel;
        L[k] += s * (1 - panEco) * 1.4; R[k] += s * panEco * 1.4;
        envioL[k] += s * 0.6; envioR[k] += s * 0.6;
      }
    }
  }

  // Clics del cursor: ruido filtrado muy corto y un pequeño tono.
  let semilla = 7;
  const ruido = () => ((semilla = (semilla * 16807) % 2147483647) / 2147483647) * 2 - 1;
  for (const tc of clics) {
    const k0 = Math.round(tc * SR);
    let bp1 = 0, bp2 = 0;
    for (let k = k0; k < Math.min(n, k0 + Math.round(0.06 * SR)); k++) {
      const x = (k - k0) / SR;
      const r = ruido();
      bp1 += 0.35 * (r - bp1); bp2 += 0.35 * (bp1 - bp2);
      const s = ((r - bp2) * Math.exp(-x * 160) * 0.05 + Math.sin(2 * Math.PI * 2100 * x) * Math.exp(-x * 90) * 0.022);
      L[k] += s; R[k] += s;
    }
  }

  // La entrada de Molcy: un barrido de ruido que sube dos segundos y un golpe grave al entrar.
  {
    const k0 = Math.round((entradaMolcy - 2.2) * SR), kE = Math.round(entradaMolcy * SR);
    let lp = 0;
    for (let k = Math.max(0, k0); k < Math.min(n, kE + Math.round(0.3 * SR)); k++) {
      const t = k / SR;
      const f = Math.min(1, (t - (entradaMolcy - 2.2)) / 2.2);
      const alfa = 1 - Math.exp((-2 * Math.PI * (250 + 2600 * f * f)) / SR);
      lp += alfa * (ruido() - lp);
      const env = k < kE ? f * f * 0.03 : 0.03 * Math.exp(-(t - entradaMolcy) * 14);
      L[k] += lp * env; R[k] += lp * env;
      envioL[k] += lp * env * 0.8; envioR[k] += lp * env * 0.8;
    }
    for (let k = kE; k < Math.min(n, kE + Math.round(2.2 * SR)); k++) {
      const x = (k - kE) / SR;
      const f = 44 + 30 * Math.exp(-x * 9);
      const s = Math.sin(2 * Math.PI * f * x) * Math.exp(-x * 2.2) * 0.16 * Math.min(1, x / 0.006);
      L[k] += s; R[k] += s;
      envioL[k] += s * 0.25; envioR[k] += s * 0.25;
    }
  }

  // Reverberación por canal (desfasada para abrir el estéreo) y una saturación suave como limitador.
  const wetL = reverb(envioL, { desfase: 0 });
  const wetR = reverb(envioR, { desfase: 23 });
  let pico = 0;
  for (let k = 0; k < n; k++) {
    L[k] = Math.tanh((L[k] + wetL[k] * 0.9) * 1.6) / 1.6;
    R[k] = Math.tanh((R[k] + wetR[k] * 0.9) * 1.6) / 1.6;
    pico = Math.max(pico, Math.abs(L[k]), Math.abs(R[k]));
  }
  const norma = pico > 0 ? 0.7 / pico : 1; // −3 dBFS de pico; el nivel final lo fija ffmpeg (loudnorm)

  // WAV PCM de 24 bits.
  const datos = Buffer.alloc(n * 2 * 3);
  for (let k = 0; k < n; k++) {
    for (const [c, canal] of [[0, L], [1, R]]) {
      const v = Math.max(-1, Math.min(1, canal[k] * norma));
      const entero = Math.round(v * 8388607);
      datos.writeIntLE(entero, (k * 2 + c) * 3, 3);
    }
  }
  const cab = Buffer.alloc(44);
  cab.write("RIFF", 0); cab.writeUInt32LE(36 + datos.length, 4); cab.write("WAVE", 8);
  cab.write("fmt ", 12); cab.writeUInt32LE(16, 16); cab.writeUInt16LE(1, 20); cab.writeUInt16LE(2, 22);
  cab.writeUInt32LE(SR, 24); cab.writeUInt32LE(SR * 2 * 3, 28); cab.writeUInt16LE(6, 32); cab.writeUInt16LE(24, 34);
  cab.write("data", 36); cab.writeUInt32LE(datos.length, 40);
  await writeFile(destino, Buffer.concat([cab, datos]));
  return { pico_previo: pico };
}
