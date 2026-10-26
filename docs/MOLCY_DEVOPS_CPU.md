# Molcy: operación y selección de CPU

> **Nota de reubicación (2026-10-11).** La salida `dist/molcy-devops-20260929` se movió a F: el 2026-10-10. Los comandos de abajo citan la ruta antigua; para repetir la prueba, usa esa carpeta de F: como `--salida`. Índice: [REUBICACIONES_2026-10-11.md](REUBICACIONES_2026-10-11.md).

Fecha: 2026-09-29. Trabajo en ramas aisladas, sin build ni integración.

## Lo que recibe el usuario

Al seleccionar CPU, Molcy declara cuántos **hilos lógicos** tiene disponibles.
El selector permite de 1 al máximo permitido por la afinidad del proceso, con
un límite técnico de 1024. La recomendación es todos menos uno, mínimo uno.
Esto configura los hilos de Cycles; **no es una cuota de CPU del sistema operativo**
ni garantiza reservar un núcleo. Denoising y procesos auxiliares pueden usar
otros hilos. GPU conserva su opción y recomendación cuando EEVEE funciona.

La cantidad elegida se envía como `cpu_hilos` en `POST /molcy/trabajos`, se
persiste en el trabajo y se transmite al programa independiente mediante
`MOLCY_CPU_THREADS`. La escena y el outro aplican esa cantidad. El acta debe
acreditarla antes de aceptar el MP4. Un motor anterior permite su CPU fija;
para usar el selector se requiere actualizar el motor a `adb6a4f` o posterior.
El límite de **3 segundos de escena + outro** se conserva.

La interfaz muestra la cantidad usada por cada trabajo CPU, bloquea el selector
mientras hay un render activo y permite volver a la recomendación. Al cambiar
rápidamente el control, aborta la consulta anterior e ignora respuestas atrasadas.

## Cómo se estima

`POST /molcy/cpu/estimacion` consulta sólo el historial del usuario autenticado,
con acceso comprobado a la fuente. Se usan hasta tres de las últimas treinta
corridas que coincidan en fuente exacta, hashes del receptor/poses, formato,
modelo CPU y procesadores disponibles, código/plantilla del motor y versiones
de Blender/Molecular Nodes. Los trabajos fallidos, incompletos, reanudados o
con medidas ilegibles no sirven de calibración.

- Con medidas para los mismos hilos: mediana de los tiempos moleculares.
- Con medidas para otros hilos: mediana de `tiempo × hilos_medidos / hilos_elegidos`.
  Se anuncia como **proyección aproximada**: la aceleración no es proporcional.
- Sin medidas comparables: no se inventa un tiempo. El primer render actualiza
  su estimación con sus primeros fotogramas, como antes.

El valor se refiere **únicamente al tramo molecular**. No incluye título,
outro ni codificación. El primer outro puede sumar varios minutos. No se
pretende estimar el tiempo completo sólo contando procesadores.
La cantidad de hilos no inicia automáticamente un benchmark ni una descarga.

## Puertas de operación

[verificar_molcy.py](../scripts/verificar_molcy.py) ejecuta siete puertas locales:
backend Molcy, frontend Molcy con guardianes de idioma, TypeScript, ESLint de
Molcy, lógica pura del motor, CSP de medios locales y contrato OpenAPI. No
construye la app, instala paquetes, inicia servidores ni genera videos.
Requiere el intérprete distribuido y las dependencias frontend ya presentes.

Ejemplo PowerShell, desde el worktree MolDesign:

```powershell
& 'D:/moldesign-build/python-embed/python.exe' 'scripts/verificar_molcy.py' `
  --node 'C:/nvm4w/nodejs/node.exe' `
  --motor 'E:/proyect3d-worktrees/molcy' `
  --salida 'D:/moldesign-build/dist/molcy-devops-20260929'
```

Cada ejecución crea una carpeta UUID con datos QA aislados, logs por puerta e
`informe.json`. El proceso devuelve 0 si todas pasan, 1 si falla una puerta y
2 si faltan argumentos o dependencias. TypeScript y los guardianes compartidos
leen el proyecto para verificar los cambios; las suites ejecutadas se limitan
a Molcy y a sus guardianes. La recolección global sólo actualiza el registro.

## Medido en esta iteración

- Ryzen 5 5500: 12 hilos disponibles, recomendación 11.
- Python distribuido 3.11.9: **69 pruebas Molcy aprobadas**, una advertencia
  preexistente del adaptador Starlette/httpx.
- Frontend Molcy y guardianes: **36 pruebas aprobadas**.
- Motor independiente: **61 aprobadas, 2 omitidas**.
- TypeScript, lint Molcy, CSP y OpenAPI correctos; siete puertas aprobadas.
- Registro backend: 3026 pruebas **recolectadas**; no se ejecutaron las suites
  científicas ni las de otros módulos en esta iteración.
- Blender 5.2.2: Cycles aplicó 1 y 4 hilos en dos cuadros de 8×8 a una muestra.
  Configuración del outro confirmó los mismos valores sin renderizarlo.
  Estos sondeos no permiten comparar rendimiento ni estimar un video real.

Evidencia: `D:/moldesign-build/dist/molcy-devops-20260929` (ahora en F:\Backups\moldesign-evidencia\2026-10-10-limpieza-D\dist\molcy-devops-20260929), con logs,
`informe-devops.json`, recursos y sondeos. Los MP4 GPU/CPU de la iteración
anterior se conservan, pero **no prueban el nuevo selector**. No se generaron
videos completos adicionales ni se amplió el límite original de dos.

## Pendiente para producción

Verificación del módulo en el artefacto instalado/WebView2, formatos completos,
receptor subido, máquinas con otras CPU/GPU, estrés RAM/VRAM y distribución del
motor independiente. La precisión de la proyección entre cantidades de hilos
requiere videos comparables adicionales; no se presenta como validada.
