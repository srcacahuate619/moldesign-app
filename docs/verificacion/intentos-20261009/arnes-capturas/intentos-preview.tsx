import React from "react";
import { createRoot } from "react-dom/client";
import { AuthProvider } from "../lib/auth";
import { LanguageProvider } from "../context/LanguageContext";
import TargetSelectorModal from "../components/interfaces/pro/TargetSelectorModal";
import type { Target } from "../lib/api";
import datos from "./intentos-datos.json";
import "./intentos-preview.css";
document.documentElement.classList.add("dark");
createRoot(document.getElementById("root")!).render(<AuthProvider><LanguageProvider>
  <TargetSelectorModal isOpen targets={datos.targets as unknown as Target[]} selectedTargetId={null} onClose={() => {}} onSelect={() => {}} />
</LanguageProvider></AuthProvider>);
