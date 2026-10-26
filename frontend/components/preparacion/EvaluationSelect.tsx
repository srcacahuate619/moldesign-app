"use client";

import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { ChevronDown } from "lucide-react";

export type EvaluationOption = {
  value: string;
  summary: string;
  mode: string;
  disabledReason: string | null;
};

/** El UUID ocupa su propio renglón, también en el valor seleccionado. */
export function EvaluationSelect({ id, label, hintId, value, options, placeholder, disabled, onChange }: {
  id: string;
  label: string;
  hintId: string;
  value: string;
  options: EvaluationOption[];
  placeholder: string;
  disabled: boolean;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [activeValue, setActiveValue] = useState("");
  const container = useRef<HTMLDivElement>(null);
  const list = useRef<HTMLDivElement>(null);
  const selected = options.find((option) => option.value === value);
  const available = options.filter((option) => !option.disabledReason);
  const expanded = open && !disabled;
  const activeIndex = options.findIndex((option) => option.value === activeValue);

  useEffect(() => {
    if (!expanded) return;
    const dismiss = (event: PointerEvent) => {
      if (event.target instanceof Node && !container.current?.contains(event.target)) setOpen(false);
    };
    document.addEventListener("pointerdown", dismiss);
    return () => document.removeEventListener("pointerdown", dismiss);
  }, [expanded]);

  useEffect(() => {
    if (!expanded) return;
    const option = list.current?.children.item(activeIndex);
    if (option instanceof HTMLElement) option.scrollIntoView({ block: "nearest" });
  }, [activeIndex, expanded]);

  const show = (last = false) => {
    setActiveValue((!selected?.disabledReason && selected?.value) || (last ? available.at(-1)?.value : available[0]?.value) || "");
    setOpen(true);
  };

  const choose = (option: EvaluationOption | undefined) => {
    if (!option || option.disabledReason) return;
    setOpen(false);
    onChange(option.value);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
    if (event.key === "Tab") {
      setOpen(false);
      return;
    }
    if (event.key === "Escape") {
      if (expanded) event.preventDefault();
      setOpen(false);
      return;
    }
    if (["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) {
      event.preventDefault();
      if (!expanded) {
        show(event.key === "End" || event.key === "ArrowUp");
        if (event.key === "Home") setActiveValue(available[0]?.value || "");
        if (event.key === "End") setActiveValue(available.at(-1)?.value || "");
        return;
      }
      const index = available.findIndex((option) => option.value === activeValue);
      const next = event.key === "Home" ? 0 : event.key === "End" ? available.length - 1
        : event.key === "ArrowDown" ? Math.min(index + 1, available.length - 1) : Math.max(index - 1, 0);
      setActiveValue(available[next]?.value || "");
      return;
    }
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (expanded) choose(options[activeIndex]);
      else show();
    }
  };

  const rows = (option: EvaluationOption) => (
    <>
      <span className="flex min-w-0 items-baseline gap-1 pr-4 text-xs leading-5">
        <span className="min-w-0 truncate">{option.summary}</span>
        <span className="shrink-0">· {option.mode}</span>
      </span>
      <span className="mt-1 block font-mono text-xs leading-5 text-[var(--text-muted)] [overflow-wrap:anywhere]">{option.value}</span>
      {option.disabledReason && <span className="mt-1 block text-[11px] leading-4 text-[var(--text-dim)]">{option.disabledReason}</span>}
    </>
  );

  return (
    <div ref={container} className="relative min-w-0" onBlur={(event) => {
      if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);
    }}>
      <label id={`${id}-label`} htmlFor={id} className="block font-mono text-[10px] uppercase tracking-[0.14em] text-[var(--text-dim)]">{label}</label>
      <button
        id={id}
        type="button"
        role="combobox"
        aria-labelledby={`${id}-label`}
        aria-describedby={hintId}
        aria-haspopup="listbox"
        aria-expanded={expanded}
        aria-controls={`${id}-list`}
        aria-activedescendant={expanded && activeIndex >= 0 ? `${id}-option-${activeIndex}` : undefined}
        disabled={disabled}
        onKeyDown={onKeyDown}
        onClick={() => expanded ? setOpen(false) : show()}
        className="relative mt-2 block min-h-11 w-full min-w-0 cursor-pointer border border-[var(--border-light)] bg-[var(--bg-secondary)] px-3 py-2.5 text-left text-[var(--text)] hover:border-[var(--accent-strong)] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--accent-strong)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {selected ? rows(selected) : <span className="block pr-4 text-xs [overflow-wrap:anywhere]">{placeholder}</span>}
        <ChevronDown aria-hidden="true" size={14} className={`absolute right-2 top-3.5 text-[var(--text-dim)] ${expanded ? "rotate-180" : ""}`} />
      </button>
      {expanded && (
        <div
          ref={list}
          id={`${id}-list`}
          role="listbox"
          aria-labelledby={`${id}-label`}
          onPointerDown={(event) => event.preventDefault()}
          className="absolute inset-x-0 top-full z-30 mt-1 max-h-[min(18rem,45vh)] overflow-y-auto overscroll-contain border border-[var(--border-light)] bg-[var(--bg-secondary)] shadow-xl"
        >
          {options.map((option, index) => (
            <div
              key={option.value}
              id={`${id}-option-${index}`}
              role="option"
              aria-selected={value === option.value}
              aria-disabled={Boolean(option.disabledReason)}
              onPointerMove={() => { if (!option.disabledReason) setActiveValue(option.value); }}
              onClick={() => choose(option)}
              title={`${option.summary} · ${option.mode}\n${option.value}${option.disabledReason ? `\n${option.disabledReason}` : ""}`}
              className={`min-w-0 border-l-2 px-3 py-2.5 text-[var(--text)] ${option.disabledReason ? "cursor-not-allowed border-transparent opacity-50" : "cursor-pointer"} ${!option.disabledReason && activeValue === option.value ? "bg-[var(--bg-card)] outline-1 -outline-offset-1 outline-[var(--accent-strong)]" : ""} ${value === option.value ? "border-[var(--accent-strong)]" : "border-transparent"}`}
            >
              {rows(option)}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
