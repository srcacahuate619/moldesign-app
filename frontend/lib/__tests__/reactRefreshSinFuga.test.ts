/**
 * React Refresh no vuelve a apuntar una raíz que hace un commit después de desmontarse (`lib/reactRefreshSinFuga.ts`).
 *
 * El gancho de mentira hace lo que hace el runtime de React Refresh, copiado de su `onCommitFiberRoot`: apunta la raíz
 * en CADA commit y sólo la borra en el commit que la desmonta. Lo que se mira es si la raíz muerta sigue apuntada.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";

import { cuentaDeRefresh, protegerReactRefresh } from "../reactRefreshSinFuga";

type Fibra = { memoizedState: { element: unknown } | null; alternate: Fibra | null };
type Raiz = { current: Fibra };

/** El runtime de React Refresh, en lo que toca a las raíces. */
function reactRefresh() {
  const helpersByRoot = new Map<Raiz, object>();
  const mountedRoots = new Set<Raiz>();
  const failedRoots = new Set<Raiz>();
  const deDevTools = vi.fn();
  const gancho = {
    onCommitFiberRoot(id: number, root: Raiz, _prioridad?: unknown, didError?: boolean) {
      helpersByRoot.set(root, {});
      const current = root.current;
      const alternate = current.alternate;
      if (alternate !== null) {
        const wasMounted = alternate.memoizedState != null && alternate.memoizedState.element != null && mountedRoots.has(root);
        const isMounted = current.memoizedState != null && current.memoizedState.element != null;
        if (!wasMounted && isMounted) { mountedRoots.add(root); failedRoots.delete(root); }
        else if (wasMounted && !isMounted) {
          mountedRoots.delete(root);
          if (didError) failedRoots.add(root); else helpersByRoot.delete(root);
        } else if (!wasMounted && !isMounted) { if (didError) failedRoots.add(root); }
      } else mountedRoots.add(root);
      return deDevTools(id, root);
    },
  };
  return { gancho, helpersByRoot, mountedRoots, failedRoots, deDevTools };
}

/** Una raíz de React y sus commits: cada uno intercambia la fibra actual por su alterna, como hace React. */
function raizDeReact() {
  const raiz: Raiz = { current: { memoizedState: { element: null }, alternate: null } };
  const confirmar = (elemento: unknown) => {
    raiz.current = { memoizedState: { element: elemento }, alternate: raiz.current };
    return raiz;
  };
  return { raiz, confirmar };
}

beforeEach(() => { cuentaDeRefresh.apartados = 0; });

describe("React Refresh y las raíces desmontadas", () => {
  it("sin proteger, una raíz que hace un commit tras desmontarse se queda apuntada para siempre (el fallo)", () => {
    const { gancho, helpersByRoot } = reactRefresh();
    const { raiz, confirmar } = raizDeReact();
    gancho.onCommitFiberRoot(1, confirmar("<App/>"));
    gancho.onCommitFiberRoot(1, confirmar(null));
    expect(helpersByRoot.has(raiz)).toBe(false);
    // El segundo commit, dentro del mismo `unmount()`: es lo que hace la raíz de Ketcher.
    gancho.onCommitFiberRoot(1, confirmar(null));
    expect(helpersByRoot.has(raiz)).toBe(true);
  });

  it("protegido, ese commit no llega a React Refresh y la raíz no queda apuntada", () => {
    const { gancho, helpersByRoot, mountedRoots, deDevTools } = reactRefresh();
    expect(protegerReactRefresh({ __REACT_DEVTOOLS_GLOBAL_HOOK__: gancho })).toBe(true);
    const { raiz, confirmar } = raizDeReact();
    gancho.onCommitFiberRoot(1, confirmar("<App/>"));
    expect(mountedRoots.has(raiz)).toBe(true);
    gancho.onCommitFiberRoot(1, confirmar(null));
    // El commit que desmonta sí pasa: React Refresh tiene que darla de baja.
    expect(mountedRoots.has(raiz)).toBe(false);
    expect(deDevTools).toHaveBeenCalledTimes(2);
    gancho.onCommitFiberRoot(1, confirmar(null));
    gancho.onCommitFiberRoot(1, confirmar(null));
    expect(helpersByRoot.has(raiz)).toBe(false);
    expect(deDevTools).toHaveBeenCalledTimes(2);
    expect(cuentaDeRefresh.apartados).toBe(2);
  });

  it("una raíz viva no pierde ningún commit, y si vuelve a montarse se la vuelve a seguir", () => {
    const { gancho, helpersByRoot, mountedRoots, deDevTools } = reactRefresh();
    protegerReactRefresh({ __REACT_DEVTOOLS_GLOBAL_HOOK__: gancho });
    const { raiz, confirmar } = raizDeReact();
    for (let i = 0; i < 4; i++) gancho.onCommitFiberRoot(1, confirmar(`<App v${i}/>`));
    expect(deDevTools).toHaveBeenCalledTimes(4);
    gancho.onCommitFiberRoot(1, confirmar(null));
    gancho.onCommitFiberRoot(1, confirmar(null));
    // `root.render()` otra vez sobre la misma raíz.
    gancho.onCommitFiberRoot(1, confirmar("<App/>"));
    expect(mountedRoots.has(raiz)).toBe(true);
    expect(helpersByRoot.has(raiz)).toBe(true);
    gancho.onCommitFiberRoot(1, confirmar(null));
    gancho.onCommitFiberRoot(1, confirmar(null));
    expect(mountedRoots.has(raiz)).toBe(false);
    expect(helpersByRoot.has(raiz)).toBe(false);
    expect(cuentaDeRefresh.apartados).toBe(2);
  });

  it("un commit con error pasa siempre: React Refresh lo necesita para reintentar la raíz al editar", () => {
    const { gancho, failedRoots } = reactRefresh();
    protegerReactRefresh({ __REACT_DEVTOOLS_GLOBAL_HOOK__: gancho });
    const { raiz, confirmar } = raizDeReact();
    gancho.onCommitFiberRoot(1, confirmar("<App/>"));
    gancho.onCommitFiberRoot(1, confirmar(null));
    gancho.onCommitFiberRoot(1, confirmar(null), undefined, true);
    expect(failedRoots.has(raiz)).toBe(true);
    expect(cuentaDeRefresh.apartados).toBe(0);
  });

  it("el desmontaje de una raíz montada antes de proteger también pasa", () => {
    const { gancho, mountedRoots } = reactRefresh();
    const { raiz, confirmar } = raizDeReact();
    gancho.onCommitFiberRoot(1, confirmar("<App/>"));
    protegerReactRefresh({ __REACT_DEVTOOLS_GLOBAL_HOOK__: gancho });
    gancho.onCommitFiberRoot(1, confirmar(null));
    expect(mountedRoots.has(raiz)).toBe(false);
    expect(cuentaDeRefresh.apartados).toBe(0);
  });

  it("se pone una sola vez, conserva `this` y los argumentos, y sin gancho no hace nada", () => {
    expect(protegerReactRefresh({})).toBe(false);
    expect(protegerReactRefresh(null)).toBe(false);
    expect(protegerReactRefresh({ __REACT_DEVTOOLS_GLOBAL_HOOK__: {} })).toBe(false);
    const recibido: unknown[][] = [];
    const gancho = { onCommitFiberRoot(this: unknown, ...args: unknown[]) { recibido.push([this, ...args]); return "devuelto"; } };
    const destino = { __REACT_DEVTOOLS_GLOBAL_HOOK__: gancho };
    expect(protegerReactRefresh(destino)).toBe(true);
    const puesto = gancho.onCommitFiberRoot;
    expect(protegerReactRefresh(destino)).toBe(true);
    expect(gancho.onCommitFiberRoot).toBe(puesto);
    const { confirmar } = raizDeReact();
    const raiz = confirmar("<App/>");
    expect(gancho.onCommitFiberRoot(7, raiz, 3, false)).toBe("devuelto");
    expect(recibido).toEqual([[gancho, 7, raiz, 3, false]]);
  });
});
