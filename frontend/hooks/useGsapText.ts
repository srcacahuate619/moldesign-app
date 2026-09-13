"use client";

import { useEffect, useRef } from "react";
import { animateElements, cancelAnimations } from "@/lib/webAnimation";
type TextAnimationType = "fade-up" | "typing" | "shimmer" | "stagger";

interface UseGsapTextOptions {
  type?: TextAnimationType;
  stagger?: number;
  duration?: number;
  delay?: number;
  enabled?: boolean;
}

export function useGsapText<T extends HTMLElement>(
  deps: unknown[],
  options: UseGsapTextOptions = {},
) {
  const ref = useRef<T | null>(null);
  const {
    type = "fade-up",
    stagger = 0.04,
    duration = 0.4,
    delay = 0,
    enabled = true,
  } = options;

  useEffect(() => {
    if (!ref.current || !enabled) return;
    const el = ref.current;

    Array.from(el.children).forEach((child, index) => {
      cancelAnimations(child);
      animateElements(
        child,
        [
          { opacity: 0, transform: type === "fade-up" ? "translateY(12px)" : "translateY(0)", filter: type === "shimmer" ? "blur(4px)" : "none" },
          { opacity: 1, transform: "translateY(0)", filter: "blur(0px)" },
        ],
        { duration: duration * 1000, delay: delay * 1000 + index * stagger * 1000, fill: "forwards", easing: "ease-out" },
      );
    });
  }, deps);

  return ref;
}

export function useGsapTyping<T extends HTMLElement>(
  text: string,
  options: { duration?: number; delay?: number; enabled?: boolean } = {},
) {
  const ref = useRef<T | null>(null);
  const { duration = 0.5, delay = 0, enabled = true } = options;

  useEffect(() => {
    if (!ref.current || !enabled) return;
    const el = ref.current;
    el.textContent = "";

    const chars = Array.from(text);
    const intervalMs = chars.length === 0 ? 0 : (duration * 1000) / chars.length;
    let currentIndex = 0;
    let interval: ReturnType<typeof setInterval> | undefined;
    const start = () => {
      interval = setInterval(() => {
        if (currentIndex >= chars.length) {
          if (interval) clearInterval(interval);
          return;
        }
        el.textContent += chars[currentIndex++];
      }, intervalMs);
    };
    const timeout = setTimeout(start, delay * 1000);
    return () => {
      clearTimeout(timeout);
      if (interval) clearInterval(interval);
    };
  }, [text, duration, delay, enabled]);

  return ref;
}
