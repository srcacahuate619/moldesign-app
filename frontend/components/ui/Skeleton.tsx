"use client";

import React from "react";

interface SkeletonProps {
  className?: string;
  variant?: "text" | "circular" | "rectangular";
  width?: string | number;
  height?: string | number;
  count?: number;
}

export function Skeleton({ className = "", variant = "text", width, height, count = 1 }: SkeletonProps) {
  const base = "animate-pulse rounded bg-zinc-700/50";
  const variants = {
    text: "h-4 rounded-md",
    circular: "rounded-full",
    rectangular: "rounded-lg",
  };

  const style: React.CSSProperties = {};
  if (width) style.width = typeof width === "number" ? `${width}px` : width;
  if (height) style.height = typeof height === "number" ? `${height}px` : height;

  return (
    <>
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className={`${base} ${variants[variant]} ${className}`} style={style} />
      ))}
    </>
  );
}

export function EvaluationSkeleton() {
  return (
    <div className="space-y-6 p-4">
      {/* Score cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="p-4 rounded-xl border border-zinc-700/30 bg-zinc-800/20 space-y-3">
            <Skeleton variant="text" className="w-20" />
            <Skeleton variant="text" className="h-8 w-24" />
            <Skeleton variant="text" className="w-32" />
          </div>
        ))}
      </div>

      {/* Drug-likeness */}
      <div className="rounded-xl border border-zinc-700/30 bg-zinc-800/20 p-4 space-y-3">
        <Skeleton variant="text" className="w-40" />
        <div className="flex gap-2">
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} variant="rectangular" className="h-8 w-20" />
          ))}
        </div>
      </div>

      {/* 3D Viewer placeholder */}
      <Skeleton variant="rectangular" className="h-[420px] w-full" />
    </div>
  );
}
