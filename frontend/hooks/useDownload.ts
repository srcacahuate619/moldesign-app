"use client";

import { useContext } from "react";
import {
  DownloadContext,
  ENGINE_IDLE,
  type DownloadContextValue,
} from "../context/DownloadProvider";

const DEFAULT_DOWNLOAD_CONTEXT: DownloadContextValue = {
  models: {},
  progress: {},
  manifest: [],
  isLauncherMode: false,
  initialized: true,
  // Sin proveedor no hay motor que gestionar: `idle` es lo cierto. Decir
  // «listo» aquí haría que la interfaz afirmara algo que nadie ha comprobado.
  engine: ENGINE_IDLE,
  retryEngine: async () => {},
  startDownload: async () => {},
  cancelDownload: async () => {},
  checkModules: async () => {},
};

export function useDownload(): DownloadContextValue {
  const ctx = useContext(DownloadContext);
  return ctx || DEFAULT_DOWNLOAD_CONTEXT;
}
