"use client";

import { LegalModal } from "./ui/LegalModal";

interface TermsModalProps {
  open: boolean;
  onClose: () => void;
}

/** @deprecated Usa `components/ui/LegalModal`. Se conserva como adaptador. */
export function TermsModal({ open, onClose }: TermsModalProps) {
  return <LegalModal isOpen={open} onClose={onClose} />;
}
