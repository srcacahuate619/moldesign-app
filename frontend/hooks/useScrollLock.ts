import { useEffect } from "react";

/**
 * Impide que la página de detrás se desplace mientras hay un modal abierto.
 *
 * LO QUE SE ARREGLÓ AQUÍ, y por qué importa más de lo que parece:
 *
 * 1. LA RESTAURACIÓN GUARDABA EL VALOR COMPUTADO. `getComputedStyle(body).overflow`
 *    no devuelve «lo que había escrito el autor», devuelve el valor resuelto por
 *    la cascada. Al cerrar, ese valor se escribía como ESTILO EN LÍNEA, que gana
 *    a cualquier hoja de estilos. `app/globals.css` declara
 *    `body { overflow-x: clip }` a propósito —evita que un elemento ancho
 *    ensanche la página en móvil— y abrir un modal una sola vez lo anulaba para
 *    el resto de la sesión. Ahora se guarda y se repone la propiedad EN LÍNEA,
 *    que es lo único que este hook tiene derecho a tocar.
 *
 * 2. EL DESPLAZAMIENTO AL BLOQUEAR. Quitar la barra de la ventana devuelve su
 *    anchura al contenido y toda la página salta hacia la derecha al abrir el
 *    modal, y hacia la izquierda al cerrarlo. Se compensa con `padding-right`
 *    del ancho exacto que ocupaba la barra.
 *
 * 3. `documentElement` TAMBIÉN. La propagación de `overflow` del `body` al
 *    viewport sólo ocurre mientras el `html` tenga `overflow: visible`. Si algo
 *    —una hoja de un tercero, un tema— se lo cambia, bloquear sólo el `body`
 *    deja de tener efecto y no hay forma de notarlo leyendo este archivo.
 *    Bloquear los dos cuesta lo mismo y no depende de esa condición.
 */
export function useScrollLock(isOpen: boolean) {
  useEffect(() => {
    if (!isOpen) return;

    const { body, documentElement: html } = document;
    const overflowPrevioBody = body.style.overflow;
    const overflowPrevioHtml = html.style.overflow;
    const paddingPrevio = body.style.paddingRight;

    // `window.innerWidth` incluye la barra; `clientWidth` no. La diferencia es
    // su anchura real, que depende del sistema y no se puede suponer.
    //
    // ACOTADA A PROPÓSITO. `clientWidth` vale 0 mientras el documento no está
    // maquetado —en jsdom siempre, y en un navegador durante el primer
    // fotograma—, y entonces la resta da el ancho entero de la ventana: el
    // hook metería mil píxeles de `padding-right` y descolocaría la página que
    // pretende estabilizar. Ninguna barra de escritorio pasa de ~20 px, así
    // que fuera de ese rango la medida no es una barra y se ignora.
    const ANCHO_MAXIMO_DE_BARRA = 40;
    const medida = window.innerWidth - html.clientWidth;
    const anchoBarra = medida > 0 && medida <= ANCHO_MAXIMO_DE_BARRA ? medida : 0;

    body.style.overflow = "hidden";
    html.style.overflow = "hidden";
    if (anchoBarra > 0) {
      const actual = Number.parseFloat(window.getComputedStyle(body).paddingRight) || 0;
      body.style.paddingRight = `${actual + anchoBarra}px`;
    }

    return () => {
      body.style.overflow = overflowPrevioBody;
      html.style.overflow = overflowPrevioHtml;
      body.style.paddingRight = paddingPrevio;
    };
  }, [isOpen]);
}
