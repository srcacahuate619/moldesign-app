"use client";

import { AboutModal as ActiveAboutModal } from "./ui/AboutModal";

interface AboutModalProps {
  open: boolean;
  onClose: () => void;
}

/** @deprecated Usa `components/ui/AboutModal`. Se conserva como adaptador. */
export function AboutModal({ open, onClose }: AboutModalProps) {
  return <ActiveAboutModal isOpen={open} onClose={onClose} />;
}
