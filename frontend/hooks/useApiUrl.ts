"use client";

// Enlace React sobre la única abstracción de la dirección del backend
// (`lib/config.ts`). Existe SÓLO para los enlaces que se construyen en render
// —un `href` a un PDF, a un certificado, a un archivo de complejo— donde no se
// puede esperar a una promesa.
//
// Sin la suscripción, esos enlaces se pintarían con el puerto por defecto y se
// quedarían apuntando ahí para siempre aunque Rust hubiera arrancado el backend
// en otro puerto: un enlace que descarga un 404 en vez de un dossier.
//
// Para hacer peticiones NO se usa esto: se usa `await getApiUrl()`.

import { useEffect, useState } from "react";

import { apiUrlSnapshot, subscribeApiUrl } from "../lib/config";

export function useApiUrl(): string | null {
  const [url, setUrl] = useState(apiUrlSnapshot);
  useEffect(() => {
    // Puede haberse resuelto entre el primer render y este efecto.
    setUrl(apiUrlSnapshot());
    return subscribeApiUrl(setUrl);
  }, []);
  return url;
}
