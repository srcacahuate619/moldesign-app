// Helper de audio seguro para Next.js (SSR) que utiliza la librería cuelume.
// Genera sonidos mediante Web Audio API sintetizándolos en tiempo real.
// Soporta mute global persistido en localStorage.
import { getUserItem, setUserItem } from "./userStorage";

let cuelume: any = null;
const CUELUME_MODULE = "cuelume";

if (typeof window !== "undefined") {
  // @ts-ignore
  import(/* webpackIgnore: true */ CUELUME_MODULE).then((mod) => {
    cuelume = mod;
  }).catch(() => {
    // cuelume no disponible; la app sigue funcionando sin audio
  });
}

export type SoundName =
  | "chime"
  | "sparkle"
  | "droplet"
  | "bloom"
  | "whisper"
  | "tick"
  | "press"
  | "release"
  | "toggle"
  | "success";

const MUTE_KEY = "moldesign_sounds_muted";

export function isSoundMuted(): boolean {
  if (typeof window === "undefined") return true;
  try {
    return getUserItem(MUTE_KEY) === "true";
  } catch {
    return false;
  }
}

export function setSoundMuted(muted: boolean): void {
  if (typeof window === "undefined") return;
  try {
    setUserItem(MUTE_KEY, muted ? "true" : "false");
  } catch {}
}

export function toggleSoundMuted(): boolean {
  const next = !isSoundMuted();
  setSoundMuted(next);
  return next;
}

/**
 * Reproduce un sonido sintetizado en tiempo real.
 * Si el usuario ha silenciado los sonidos, esta función no hace nada.
 * @param name Nombre del sonido en cuelume.
 */
export function playSound(name: SoundName) {
  if (typeof window === "undefined") return;
  if (isSoundMuted()) return;

  if (cuelume && cuelume.play) {
    try {
      cuelume.play(name);
    } catch (e) {
      // El navegador suele bloquear el audio context si no ha habido interacción previa
    }
  }
}
