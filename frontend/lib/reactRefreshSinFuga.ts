// React Refresh retiene las raíces de React que hacen un commit después de desmontarse. Sólo existe en desarrollo.
//
// EL FALLO (medido el 2026-11-11 en `next dev`, con una instantánea del montón). El runtime de React Refresh —el de la
// recarga en caliente; Next trae su copia en `next/dist/compiled/react-refresh`— decora `onCommitFiberRoot` del gancho
// global de DevTools, y en CADA commit apunta la raíz en un mapa fuerte (`helpersByRoot`). Sólo la borra en el commit
// que la desmonta. Una raíz que hace otro commit después de desmontarse vuelve al mapa y ya no sale nunca.
//
// Ketcher monta su interfaz en una raíz propia (`createRoot`), y esa raíz hace justo eso: al desmontarse, algo de su
// árbol pide una actualización síncrona, y React hace un segundo commit dentro de la misma llamada a `unmount()`. La
// raíz muerta queda en el mapa, y en desarrollo las fibras conservan la pila de dónde se creó cada elemento
// (`_debugStack`), cuyos cierres alcanzan el editor de macromoléculas y su interfaz entera: 985 nodos y 470 oyentes por
// cambio de caso con el modo estricto apagado, que es cuando ésta es la única causa. Con este arreglo: 0 y 0.
//
// En el export no ocurre: allí no hay React Refresh y la raíz, sin nadie que la apunte, se recoge.
//
// EL ARREGLO. Un commit sobre una raíz que ya vimos desmontada no llega a React Refresh, que así no vuelve a apuntarla.
// No se le quita nada que necesite: de una raíz sin nada montado sólo le interesa saber si falló, para reintentarla al
// editar, y un commit con error sí se le deja pasar. Tampoco le llega a DevTools, a quien React Refresh se lo reenvía;
// de ese commit no saca nada (no monta ni desmonta).
//
// El fallo es de React y sigue en su rama principal (el `set` incondicional de `ReactFreshRuntime.js`). Si una versión
// lo corrige, esto sobra y no estorba: lo ve la prueba de resistencia contra `next dev`, que cuenta nodos y oyentes.

const NOMBRE_DEL_GANCHO = "__REACT_DEVTOOLS_GLOBAL_HOOK__";
const MARCA = "__moldesignSinFugaDeRefresh";

/** Lo que se mira de una raíz de React (`FiberRootNode`). */
type Raiz = { current?: { memoizedState?: { element?: unknown } | null } | null };
type AlConfirmar = (this: unknown, ...args: unknown[]) => unknown;
type Gancho = { onCommitFiberRoot?: AlConfirmar & { [MARCA]?: true } };

/** Para la prueba de resistencia y las pruebas: cuántos commits de raíces ya desmontadas se han apartado. */
export const cuentaDeRefresh = { apartados: 0 };

/** La misma cuenta que hace React Refresh: hay algo montado si la raíz tiene elemento. */
function tieneAlgoMontado(raiz: Raiz): boolean {
  const estado = raiz.current?.memoizedState;
  return estado != null && estado.element != null;
}

/**
 * Evita que React Refresh retenga las raíces que hacen un commit después de desmontarse.
 *
 * Hay que llamarlo en desarrollo, en cualquier momento antes de que se desmonte la primera raíz que interese. Si no hay
 * gancho (el export, las pruebas) no hace nada. Devuelve si quedó puesto.
 */
export function protegerReactRefresh(destino: unknown = globalThis): boolean {
  const gancho = (destino as Record<string, unknown> | null | undefined)?.[NOMBRE_DEL_GANCHO] as Gancho | undefined;
  const original = gancho?.onCommitFiberRoot;
  if (!gancho || typeof original !== "function") return false;
  // La recarga en caliente vuelve a evaluar este módulo: el envoltorio se pone una sola vez.
  if (original[MARCA]) return true;

  /** Las raíces que ya hicieron un commit sin nada montado. */
  const desmontadas = new WeakSet<object>();
  const envoltorio: AlConfirmar & { [MARCA]?: true } = function (this: unknown, ...args: unknown[]) {
    const raiz = args[1] as Raiz | null | undefined;
    const huboError = Boolean(args[3]);
    let apartar = false;
    try {
      if (raiz && typeof raiz === "object") {
        if (tieneAlgoMontado(raiz)) desmontadas.delete(raiz);
        // La primera vez pasa: es el commit que la desmonta, y React Refresh tiene que verlo para darla de baja.
        else if (!desmontadas.has(raiz)) desmontadas.add(raiz);
        else apartar = !huboError;
      }
    } catch { /* ante la duda, el commit pasa */ }
    if (apartar) { cuentaDeRefresh.apartados++; return undefined; }
    return original.apply(this, args);
  };
  envoltorio[MARCA] = true;
  gancho.onCommitFiberRoot = envoltorio;
  return true;
}
