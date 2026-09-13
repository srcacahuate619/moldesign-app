"use client";

import React, { ReactNode } from "react";
import { Info, HelpCircle } from "lucide-react";

/**
 * Hallmark Anti-Slop Primitives
 * Design system tokens & reusable UI components.
 */

// --- Button ---
interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "outline" | "ghost" | "danger" | "brand";
  size?: "sm" | "md" | "lg";
  children: ReactNode;
  icon?: ReactNode;
}

export function Button({
  variant = "primary",
  size = "md",
  children,
  icon,
  className = "",
  disabled,
  ...props
}: ButtonProps) {
  const baseClasses =
    "inline-flex items-center justify-center font-medium transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-purple-500/50 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg active:scale-[0.98]";

  const variantClasses = {
    primary: "bg-surface-800 hover:bg-surface-700 text-white border border-surface-700 shadow-sm",
    secondary: "bg-surface-900 hover:bg-surface-800 text-surface-200 border border-surface-800",
    brand: "bg-brand-600 hover:bg-brand-500 text-white shadow-md shadow-brand-600/20 border border-brand-500/30 font-semibold",
    outline: "bg-transparent hover:bg-surface-800/60 text-surface-300 hover:text-white border border-surface-700",
    ghost: "bg-transparent hover:bg-surface-800/40 text-surface-400 hover:text-surface-200",
    danger: "bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30",
  };

  const sizeClasses = {
    sm: "px-2.5 py-1 text-xs gap-1.5",
    md: "px-3.5 py-1.5 text-sm gap-2",
    lg: "px-5 py-2.5 text-base gap-2.5 font-semibold",
  };

  return (
    <button
      className={`${baseClasses} ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}
      disabled={disabled}
      {...props}
    >
      {icon && <span className="shrink-0">{icon}</span>}
      <span>{children}</span>
    </button>
  );
}

// --- Card ---
interface CardProps {
  children: ReactNode;
  className?: string;
  header?: ReactNode;
  title?: string;
  subtitle?: string;
  action?: ReactNode;
}

export function Card({ children, className = "", header, title, subtitle, action }: CardProps) {
  return (
    <div className={`bg-surface-900/90 border border-surface-800/80 rounded-xl p-5 shadow-lg backdrop-blur-sm relative overflow-hidden ${className}`}>
      {(title || header || action) && (
        <div className="flex items-center justify-between pb-3 mb-4 border-b border-surface-800/60">
          <div>
            {title && <h3 className="font-bold text-base text-surface-100 flex items-center gap-2">{title}</h3>}
            {subtitle && <p className="text-xs text-surface-400 mt-0.5">{subtitle}</p>}
            {header}
          </div>
          {action && <div className="shrink-0">{action}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

// --- Badge ---
interface BadgeProps {
  children: ReactNode;
  variant?: "neutral" | "brand" | "success" | "warning" | "error" | "info";
  size?: "sm" | "md";
  className?: string;
}

export function Badge({ children, variant = "neutral", size = "sm", className = "" }: BadgeProps) {
  const variantClasses = {
    neutral: "bg-surface-800 text-surface-300 border-surface-700",
    brand: "bg-purple-500/15 text-purple-300 border-purple-500/30 font-semibold",
    success: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
    warning: "bg-amber-500/15 text-amber-300 border-amber-500/30",
    error: "bg-red-500/15 text-red-300 border-red-500/30",
    info: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  };

  const sizeClasses = {
    sm: "px-2 py-0.5 text-[10px] uppercase font-mono tracking-wider",
    md: "px-2.5 py-1 text-xs font-mono",
  };

  return (
    <span className={`inline-flex items-center gap-1 border rounded-md font-medium ${variantClasses[variant]} ${sizeClasses[size]} ${className}`}>
      {children}
    </span>
  );
}

// --- Guided Tooltip / Info Callout (Mejora solicitada para EDU/PRO) ---
interface InfoCalloutProps {
  title: string;
  children: ReactNode;
  variant?: "info" | "tip" | "warning";
  defaultOpen?: boolean;
}

export function InfoCallout({ title, children, variant = "info", defaultOpen = false }: InfoCalloutProps) {
  const [isOpen, setIsOpen] = React.useState(defaultOpen);

  const colors = {
    info: "bg-blue-500/10 border-blue-500/20 text-blue-300",
    tip: "bg-purple-500/10 border-purple-500/20 text-purple-300",
    warning: "bg-amber-500/10 border-amber-500/20 text-amber-300",
  };

  return (
    <div className={`border rounded-lg p-3 transition-all duration-200 ${colors[variant]}`}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between text-xs font-medium text-left focus:outline-none"
      >
        <span className="flex items-center gap-2 font-semibold">
          <HelpCircle className="w-3.5 h-3.5 shrink-0 opacity-80" />
          {title}
        </span>
        <span className="text-[10px] font-mono uppercase opacity-70 underline">
          {isOpen ? "Ocultar Explicación" : "Ver Explicación Didáctica"}
        </span>
      </button>
      {isOpen && (
        <div className="mt-2.5 pt-2 border-t border-white/10 text-xs text-surface-300 leading-relaxed animate-in fade-in duration-150">
          {children}
        </div>
      )}
    </div>
  );
}

// --- DataMetric (para desplegar métricas científicas numéricas limpias) ---
interface DataMetricProps {
  label: string;
  value: string | number;
  unit?: string;
  subtitle?: string;
  badge?: ReactNode;
  status?: "good" | "neutral" | "bad";
}

export function DataMetric({ label, value, unit, subtitle, badge, status = "neutral" }: DataMetricProps) {
  const statusColors = {
    good: "text-emerald-400",
    neutral: "text-surface-100",
    bad: "text-amber-400",
  };

  return (
    <div className="bg-surface-950/60 border border-surface-800/80 rounded-lg p-3 flex flex-col justify-between">
      <div className="flex items-center justify-between text-xs text-surface-400 mb-1">
        <span className="font-mono text-[11px] tracking-wider uppercase">{label}</span>
        {badge}
      </div>
      <div className="flex items-baseline gap-1 mt-1">
        <span className={`text-xl font-mono font-bold ${statusColors[status]}`}>{value}</span>
        {unit && <span className="text-xs font-mono text-surface-400">{unit}</span>}
      </div>
      {subtitle && <p className="text-[10px] text-surface-500 mt-1">{subtitle}</p>}
    </div>
  );
}
