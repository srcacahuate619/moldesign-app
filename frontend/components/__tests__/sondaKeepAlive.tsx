import { useEffect, useState } from "react";
import { useKeepAliveActive } from "../../context/KeepAliveContext";

/** Montajes por página, para ver si una pestaña keep-alive se volvió a montar. Lo usa `PersistentKeepAliveLayout.test`. */
export const montajes: Record<string, number> = {};

/** Una página simulada: cuenta sus montajes, guarda un contador propio y enseña si está a la vista. */
export function sonda(nombre: string) {
  return function Sonda() {
    const activa = useKeepAliveActive();
    const [cuenta, setCuenta] = useState(0);
    useEffect(() => { montajes[nombre] = (montajes[nombre] ?? 0) + 1; }, []);
    return (
      <div>
        <button type="button" onClick={() => setCuenta((n) => n + 1)}>{`${nombre}: ${cuenta}`}</button>
        <span data-testid={`activa-${nombre}`}>{String(activa)}</span>
      </div>
    );
  };
}
