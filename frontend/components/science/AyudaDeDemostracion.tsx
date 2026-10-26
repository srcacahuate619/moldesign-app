"use client";

import { useCallback, useEffect, useId, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import styles from "./AyudaDeDemostracion.module.css";

/** La condición del catálogo permanece visible; su explicación es consultable. */
export function AyudaDeDemostracion({ etiqueta, texto }: { etiqueta: string; texto: string }) {
  const [mounted, setMounted] = useState(false);
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const tip = useRef<HTMLSpanElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const hovered = useRef(false);
  const keyboardFocused = useRef(false);
  const pinned = useRef(false);
  const pointerType = useRef("mouse");
  const id = useId();

  const cancelHide = useCallback(() => {
    if (timer.current !== null) clearTimeout(timer.current);
    timer.current = null;
  }, []);
  const close = useCallback(() => {
    cancelHide();
    pinned.current = false;
    setOpen(false);
    setPosition(null);
  }, [cancelHide]);
  function scheduleHide() {
    cancelHide();
    if (!hovered.current && !keyboardFocused.current && !pinned.current) {
      timer.current = setTimeout(close, 120);
    }
  }

  useEffect(() => { setMounted(true); return cancelHide; }, [cancelHide]);
  useLayoutEffect(() => {
    if (!open || !mounted) return;
    function place() {
      if (!trigger.current || !tip.current) return;
      const anchor = trigger.current.getBoundingClientRect();
      const box = tip.current.getBoundingClientRect();
      const margin = 16;
      const left = Math.max(margin, Math.min(anchor.left, window.innerWidth - box.width - margin));
      const below = anchor.bottom + 8;
      const top = below + box.height <= window.innerHeight - margin ? below : Math.max(margin, anchor.top - box.height - 8);
      setPosition({ left, top });
    }
    place();
    window.addEventListener("resize", place);
    document.addEventListener("scroll", place, true);
    return () => {
      window.removeEventListener("resize", place);
      document.removeEventListener("scroll", place, true);
    };
  }, [open, mounted, texto]);
  useEffect(() => {
    if (!open) return;
    function escape(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      // La ayuda abierta consume Escape antes del drawer de casos.
      event.preventDefault(); event.stopPropagation(); close();
    }
    function outside(event: PointerEvent) {
      const node = event.target as Node;
      if (!trigger.current?.contains(node) && !tip.current?.contains(node)) close();
    }
    window.addEventListener("keydown", escape, true);
    document.addEventListener("pointerdown", outside);
    return () => {
      window.removeEventListener("keydown", escape, true);
      document.removeEventListener("pointerdown", outside);
    };
  }, [open, close]);

  return <>
    <button
      ref={trigger}
      type="button"
      className={styles.trigger}
      data-demo-help
      aria-describedby={mounted ? id : undefined}
      onPointerDown={event => { pointerType.current = event.pointerType; keyboardFocused.current = false; }}
      onPointerEnter={event => {
        if (event.pointerType === "touch") return;
        hovered.current = true; cancelHide(); setOpen(true);
      }}
      onPointerLeave={() => { hovered.current = false; scheduleHide(); }}
      onFocus={event => {
        keyboardFocused.current = event.currentTarget.matches(":focus-visible");
        if (keyboardFocused.current) { cancelHide(); setOpen(true); }
      }}
      onBlur={() => { keyboardFocused.current = false; scheduleHide(); }}
      onClick={event => {
        cancelHide();
        if (pointerType.current === "touch" || event.detail === 0) {
          if (pinned.current) close();
          else { pinned.current = true; setOpen(true); }
        } else setOpen(true);
      }}
    ><span className={styles.chip}>{etiqueta}</span></button>
    {mounted && createPortal(<span
      ref={tip}
      id={id}
      role="tooltip"
      hidden={!open}
      className={styles.tip}
      style={{ left: position?.left ?? 16, top: position?.top ?? 16, visibility: position ? "visible" : "hidden" }}
      onPointerEnter={() => { hovered.current = true; cancelHide(); }}
      onPointerLeave={() => { hovered.current = false; scheduleHide(); }}
    >{texto}</span>, document.body)}
  </>;
}
