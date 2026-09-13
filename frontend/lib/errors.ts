/**
 * lib/errors.ts — Mapeo de errores tecnicos a mensajes humano-legibles.
 *
 * Prioridad para Steam: el usuario final no es cientifico. Los mensajes
 * deben ser claros, en español, y sugerir una acción concreta.
 */

const ERROR_MAP: Record<string, string> = {
  // ── Errores de conexión ─────────────────────────────────────────
  "fetch failed": "No se pudo conectar con el motor de simulación. Verifica que la aplicación esté funcionando correctamente e intenta de nuevo.",
  "NetworkError": "Pérdida de conexión con el servidor local. Esto puede ocurrir si tu antivirus bloqueó la aplicación. Intenta de nuevo o reinicia MolDesign.",
  "ECONNREFUSED": "El motor de cálculo no está respondiendo. La aplicación podría estar iniciándose. Espera unos segundos e intenta de nuevo.",
  "timeout": "La operación tardó demasiado. Puede deberse a una molécula muy compleja o a un receptor muy grande. Intenta con una estructura más simple.",
  "TIMEOUT": "La simulación excedió el tiempo máximo. Intenta reducir el tamaño de la molécula o usar menos hilos de ejecución en el panel de configuración.",
  "ConnectionRefusedError": "No se pudo contactar al servidor de docking. Reinicia la aplicación e intenta de nuevo.",

  // ── Errores HTTP ────────────────────────────────────────────────
  "HTTP 500": "Error interno del motor de simulación. Nuestro sistema detectó el problema. Intenta con otra molécula o receptor.",
  "HTTP 503": "El servicio de docking no está disponible temporalmente. Espera unos segundos e intenta de nuevo.",
  "HTTP 502": "El servidor de cálculo se está reiniciando. Espera 30 segundos e intenta de nuevo.",
  "HTTP 422": "La molécula no pasó las reglas de validación química. Revisa la estructura e intenta con un SMILES válido.",
  "HTTP 429": "Has alcanzado el límite de evaluaciones. Espera unos minutos antes de intentar de nuevo.",
  "HTTP 404": "El recurso solicitado no existe. Verifica que el receptor o la molécula estén disponibles.",
  "HTTP 400": "Los datos enviados no son válidos. Revisa el formato de la molécula o el archivo subido.",

  // ── Errores de docking ──────────────────────────────────────────
  "Vina": "El acoplamiento molecular encontró un problema. Esto suele pasar con moléculas muy grandes o receptores con poca resolución.",
  "docking": "La simulación de unión proteína-ligando falló. La molécula podría ser demasiado grande o tener elementos no soportados.",
  "conformer": "No se pudo generar la estructura 3D de la molécula. Esto puede ocurrir con estructuras muy tensionadas.",
  "exhaustiveness": "El parámetro de búsqueda es muy alto para tu hardware. Reduce la exhaustividad en la configuración.",
  "PDBQT": "Error en la preparación de la proteína. El receptor seleccionado podría necesitar curación adicional.",
  "Atom type": "La molécula contiene átomos que el motor de docking no reconoce. Usa solo C, N, O, S, P, F, Cl, Br, I.",
  "atom type": "La estructura contiene elementos no soportados por el motor de docking.",

  // ── Errores de validación ───────────────────────────────────────
  "SMILES": "El formato de la molécula no es válido. Un SMILES correcto se ve como 'CC(=O)Oc1ccccc1C(=O)O' (aspirina).",
  "invalido": "La molécula no es químicamente válida. Revisa que los átomos tengan las valencias correctas.",
  "valence": "Algún átomo en tu molécula tiene demasiados enlaces. Revisa la estructura.",
  "sanitize": "La molécula contiene errores estructurales que RDKit no pudo corregir.",

  // ── Errores de sistema ──────────────────────────────────────────
  "database is locked": "La base de datos está ocupada procesando otra operación. Espera unos segundos.",
  "out of memory": "Tu equipo se quedó sin memoria RAM. Cierra otras aplicaciones e intenta de nuevo.",
  "disk full": "Te quedaste sin espacio en disco. Libera espacio e intenta de nuevo.",
  "permission denied": "La aplicación no tiene permisos para escribir archivos. Ejecútala como administrador o cambia la ubicación de datos.",
  "not found": "No se encontró el archivo o recurso solicitado. Es posible que necesites reinstalar la aplicación.",
  "SQLite": "Error en la base de datos local. Esto es poco frecuente. Si persiste, reinstala la aplicación.",
  "celery": "Error interno en la cola de tareas. Reinicia la aplicación.",
  "redis": "Error en el servicio de mensajería interna. Reinicia la aplicación.",

  // ── Errores Batch ───────────────────────────────────────────────
  "Upload failed": "No se pudo procesar el archivo. Verifica el formato (CSV, Excel, SDF o TXT con SMILES).",
  "Maximo 500": "El archivo excede el límite de 500 moléculas. Divídelo en archivos más pequeños.",
  "No se encontraron SMILES": "El archivo no contiene moléculas válidas. Verifica que tenga una columna 'smiles'.",
};

export function friendlyError(technicalMessage: string): string {
  if (!technicalMessage) return "Error desconocido. Reintenta la operacion.";

  const msg = technicalMessage.toLowerCase();

  // Buscar coincidencia parcial
  for (const [key, friendly] of Object.entries(ERROR_MAP)) {
    if (msg.includes(key.toLowerCase())) {
      return friendly;
    }
  }

  // Buscar codigo HTTP
  const httpMatch = technicalMessage.match(/HTTP (\d{3})/);
  if (httpMatch) {
    const httpKey = `HTTP ${httpMatch[1]}`;
    if (ERROR_MAP[httpKey]) return ERROR_MAP[httpKey];
  }

  // Fallback generico — mostrar el error tecnico pero con prefijo amigable
  const short = technicalMessage.length > 200
    ? technicalMessage.substring(0, 200) + "..."
    : technicalMessage;
  return `La operacion no pudo completarse. Detalle tecnico: ${short}`;
}


export function friendlyStageError(stage: string, technicalMessage: string): string {
  const stageNames: Record<string, string> = {
    "validation": "Validación química",
    "conformer": "Generación 3D",
    "docking": "Acoplamiento molecular",
    "properties": "Cálculo de propiedades",
    "scoring": "Evaluación de calidad",
    "admet": "Señales ADMET",
    "report": "Generación de informe",
    "rescoring": "Re-evaluación ML",
    "gnn": "Señal de red neuronal",
    "quantum": "Cálculo cuántico",
    "mmgbsa": "Estimación MM-GBSA post-hoc",
    "peptide": "Plegamiento de péptido",
    "selectivity": "Panel de anti-targets",
  };

  const stageName = stageNames[stage] || stage;
  const friendly = friendlyError(technicalMessage);

  return `Error en "${stageName}": ${friendly}`;
}
