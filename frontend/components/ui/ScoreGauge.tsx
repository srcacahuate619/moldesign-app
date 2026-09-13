"use client";

import React from "react";

interface ScoreGaugeProps {
  value: number;
  size?: "sm" | "md" | "lg";
  label?: string;
  showValue?: boolean;
}

export function ScoreGauge({ value, size = "md", label, showValue = true }: ScoreGaugeProps) {
  const sizes = {
    sm: { dims: 64, stroke: 5, font: 14, sub: 9 },
    md: { dims: 96, stroke: 6, font: 22, sub: 10 },
    lg: { dims: 128, stroke: 8, font: 30, sub: 11 },
  };
  const { dims, stroke, font, sub } = sizes[size];
  const radius = (dims - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(Math.max(value, 0), 100);
  const offset = circumference - (progress / 100) * circumference;

  const color =
    progress >= 70 ? "#22c55e" :
    progress >= 40 ? "#eab308" :
    "#ef4444";

  const bgColor =
    progress >= 70 ? "rgba(34,197,94,0.08)" :
    progress >= 40 ? "rgba(234,179,8,0.08)" :
    "rgba(239,68,68,0.08)";

  return (
    <div className="flex flex-col items-center gap-1">
      <div className="relative" style={{ width: dims, height: dims }}>
        <svg width={dims} height={dims} className="-rotate-90">
          {/* Background circle */}
          <circle
            cx={dims / 2}
            cy={dims / 2}
            r={radius}
            fill="none"
            stroke="var(--border)"
            strokeWidth={stroke}
          />
          {/* Progress circle */}
          <circle
            cx={dims / 2}
            cy={dims / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            style={{ transition: "stroke-dashoffset 0.8s ease-out" }}
          />
        </svg>
        {showValue && (
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="font-mono font-bold text-zinc-100" style={{ fontSize: font }}>
              {Math.round(progress)}
            </span>
            <span className="text-zinc-500 font-mono" style={{ fontSize: sub }}>
              /100
            </span>
          </div>
        )}
      </div>
      {label && (
        <span className="text-xs text-zinc-500 font-medium">{label}</span>
      )}
    </div>
  );
}
