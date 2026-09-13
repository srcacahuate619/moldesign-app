"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  children: React.ReactNode;
  fallback?: React.ReactNode;
  rootMargin?: string;
};

export function LazyVisible({ children, fallback, rootMargin = "600px" }: Props) {
  const [visible, setVisible] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }

    const obs = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setVisible(true);
          obs.disconnect();
        }
      },
      { rootMargin }
    );

    obs.observe(el);
    return () => obs.disconnect();
  }, [rootMargin]);

  if (!visible) {
    return (
      <div ref={ref} className="min-h-[400px]">
        {fallback || null}
      </div>
    );
  }

  return <div ref={ref}>{children}</div>;
}
