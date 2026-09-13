import { Scale, Droplets, Magnet, FlaskConical, Handshake, Hand, RefreshCw, Star, Droplet, Heart, Brain, Pill, Target, ScrollText, Lock, Dna, Download, Clock, BarChart3, FileText } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const ICON_MAP: Record<string, LucideIcon> = {
  Scale, Droplets, Magnet, FlaskConical, Handshake, Hand, RefreshCw, Star,
  Droplet, Heart, Brain, Pill, Target, ScrollText, Lock, Dna, Download,
  Clock, BarChart3, FileText,
};

export function EduIcon({ name, className = "w-6 h-6" }: { name: string; className?: string }) {
  const Icon = ICON_MAP[name];
  if (!Icon) return <span className={className}>{name}</span>;
  return <Icon className={`${className} text-zinc-400`} />;
}
