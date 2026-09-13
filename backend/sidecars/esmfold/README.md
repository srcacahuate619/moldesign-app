# ESMFold Local Service — MolDesign Nivel 3

Servicio FastAPI ligero que corre en tu PC local y lo llama el servidor Ubuntu
de MolDesign para docking proteína-péptido (Nivel 3 del pipeline).

## Arquitectura

```
┌──────────────────────┐        HTTP POST /predict         ┌─────────────────────┐
│   PC LOCAL (GPU)     │ ← LAN <IP-DEL-PC>:8100 ←──────── │   SERVER UBUNTU     │
│                      │                                    │   (MolDesign API)    │
│  ┌────────────────┐  │         SI PC apagada:             │                     │
│  │ esmfold    │  │    ConnectionRefused →             │  Fallback: Vina     │
│  │ local service  │  │    Circuit breaker →               │  (se mantiene el    │
│  │ (FastAPI)     │  │    mensaje claro al usuario         │   pipeline E2E)     │
│  └──────┬─────────┘  │                                    └─────────────────────┘
│         │            │
│    Stub o Real       │
│    ESMFold        │
└──────────────────────┘
         │
         │ Auto-apagado tras X min sin requests
         ▼
    Se cierra el proceso. La PC no queda con nada corriendo.
```

## Quick Start

### 1. Instalar dependencias (una sola vez)

```powershell
cd D:\molecular-design\local_services\esmfold
pip install -r requirements.txt
```

O usar `start.bat` directamente — instala deps automáticamente al primer arranque.

### 2. Arrancar el servicio

```powershell
# Opción A: doble click en start.bat
start.bat

# Opción B: desde terminal
set ESMFOLD_PORT=8100
set ESMFOLD_MODE=fast    # fast (ESMFold+Vina+OpenMM), stub (dummy), pro (completo)
set ESMFOLD_IDLE_MIN=10    # se apaga 10 min después del último request
python -m uvicorn app:app --host 0.0.0.0 --port 8100 --log-level info
```

Verás algo como:

```
============================================================
 ESMFold Local Service
 Puerto: 8100
  Modo:   fast
 Auto-shutdown: 10 min sin requests
============================================================
 Logs:    D:\...\local_services\esmfold\logs\
 Apagar:  stop.bat  (o esperar inactividad)
 Health:  http://localhost:8100/health
============================================================
```

### 3. Verificar que está vivo

```bash
curl http://localhost:8100/health
# {"status":"ok","mode":"stub","uptime_seconds":4.2,...}
```

### 4. Probar una predicción

```bash
curl -X POST http://localhost:8100/predict \
  -H "Content-Type: application/json" \
  -d '{
    "protein_pdb": "ATOM    1  N   ALA A   1      10.000  10.000  10.000  1.00  0.00           N\nATOM    2  CA  ALA A   1      11.000  10.000  10.000  1.00  0.00           C\nEND\n",
    "peptide_smiles": "NCC(=O)NCC(=O)O",
    "num_poses": 3,
    "grid_center": [10.0, 10.0, 10.0],
    "grid_size": [25.0, 25.0, 25.0]
  }'
```

## Configuración del Servidor Ubuntu

En el servidor Ubuntu, agrega/actualiza la variable de entorno del backend:

```bash
# En backend/.env
ESMFOLD_API_URL=http://<IP-DEL-PC>:8100
```

Y reinicia el worker/celery:

```bash
cd ~/molecule-design
docker compose restart worker
# o si no usas docker:
celery -A api.celery_app restart
```

### Notas de red

- **IP de tu PC**: averíguala con `ipconfig` (adaptador Wi-Fi o Ethernet) y ponla
  en `ESMFOLD_API_URL`. Si cambia —con DHCP cambia—, hay que actualizarla.
- **Puerto**: `8100` (default). Puedes cambiarlo en `config.py` o con la variable `ESMFOLD_PORT`.
- **Firewall Windows**: asegúrate de que el puerto 8100 esté permitido en el Firewall de Windows:
  ```powershell
  # Abrir puerto en Windows Firewall (ejecutar como Admin)
  New-NetFirewallRule -DisplayName "ESMFold Local" -Direction Inbound `
    -Protocol TCP -LocalPort 8100 -Action Allow
  ```

## Variables de Entorno

| Variable | Default | Descripción |
|:---|:---|:---|
| `ESMFOLD_HOST` | `0.0.0.0` | Bind address |
| `ESMFOLD_PORT` | `8100` | Puerto TCP |
| `ESMFOLD_MODE` | `stub` | `stub` (dummy) o `real` (modelo ESMFold) |
| `ESMFOLD_IDLE_MIN` | `10` | Minutos de inactividad antes de auto-apagado. Poner `0` para desactivar |
| `ESMFOLD_MODEL_DIR` | `./models/` | Directorio del checkpoint del modelo |
| `ESMFOLD_DEVICE` | `auto` | `auto` / `cuda` / `cpu` (solo modo real) |
| `ESMFOLD_PREDICT_TIMEOUT` | `300` | Timeout por predicción en segundos |
| `ESMFOLD_MAX_POSES` | `10` | Máximo de poses que devolverá |
| `ESMFOLD_LOG_LEVEL` | `INFO` | DEBUG / INFO / WARNING |

## Endpoints

| Método | Path | Descripción |
|:---|:---|:---|
| `GET` | `/health` | Health check. 200 si el predictor está listo. |
| `GET` | `/status` | Estado detallado: uptime, modo, last activity, contadores. |
| `POST` | `/predict` | Predice poses de docking. Body JSON (ver abajo). |
| `POST` | `/shutdown?token=...` | Apagado explícito (requiere token del arranque). |

### POST /predict — Body

```json
{
  "protein_pdb": "...",          // string: contenido PDB del receptor
  "peptide_smiles": "...",       // string: SMILES del péptido
  "num_poses": 5,                // int 1-20 (cabeado a max_poses del config)
  "grid_center": [x, y, z],      // opcional
  "grid_size": [sx, sy, sz]      // opcional
}
```

### POST /predict — Response

```json
{
  "success": true,
  "method": "ESMFold-Stub",
  "poses": [
    {
      "rank": 1,
      "confidence": 0.95,
      "peptide_pdb": "ATOM ...",
      "rmsd": 1.23
    }
  ],
  "best_confidence": 0.95,
  "execution_time_s": 1.42,
  "warnings": [],
  "error": null
}
```

## Modo Stub vs Real

### Stub (default — producción lista)

Devuelve poses dummy rotadas deterministicamente. **No es científicamente válido**;
solo valida que el flujo end-to-end (server Ubuntu → tu PC → respuesta → pipeline) funciona.

Útil para: pruebas de integración, desarrollo del frontend, demos.

### Real (requiere modelo)

1. Instala las dependencias de ML:
   ```powershell
   pip install torch --index-url https://download.pytorch.org/whl/cu124
   pip install transformers rdkit biotite
   ```

2. Descarga el checkpoint del modelo:
   ```powershell
   # Clonar el repo de ESMFold y bajar el modelo
   git clone https://github.com/patrickbryant1/ESMFold.git
   # Seguir instrucciones del repo para descargar el checkpoint
   # Guardarlo en: local_services/esmfold/models/checkpoint.pt
   ```

3. Configurar:
   ```powershell
   set ESMFOLD_MODE=real
   set ESMFOLD_MODEL_DIR=D:\molecular-design\local_services\esmfold\models
   start.bat
   ```

4. Implementar `RealPredictor.predict()` en `predictor.py` (el esqueleto ya existe).

## Cómo funciona el auto-apagado

```
Llega request → _touch_activity() registra timestamp
                              ↓
                   Watchdog revisa cada 10s:
                   idle = now - last_activity
                              ↓
                   idle > ESMFOLD_IDLE_MIN?
                              ↓ sí
                   log.warning("Sin actividad por X min")
                   os._exit(0)  ← proceso termina
```

Ventajas:
- No queda nada corriendo cuando no lo usas.
- Si apagas la PC, el servicio simplemente deja de responder → el server Ubuntu detecta `ConnectionRefused` y usa Vina como fallback automáticamente.
- El circuit breaker en el cliente evita que el servidor Ubuntu spamee timeouts.

## Manejo de errores desde el servidor Ubuntu

El cliente mejorado (`backend/services/esmfold/service.py`) clasifica los fallos:

| Causa | Qué ve el usuario |
|:---|:---|
| PC apagada | `Conexión rechazada: ¿PC encendida?` → Vina |
| Timeout (>180s) | `ESMFold no respondió a tiempo` → Vina |
| Circuit breaker abierto | `ESMFold falló demasiadas veces` → Vina |
| Error HTTP del servicio | `Error interno` → Vina |
| Todo OK | ESMFold usa las poses reales |

El pipeline NUNCA se rompe. Siempre usa Vina como fallback.

## Tests

```powershell
# Unitarios (no requieren servidor corriendo)
python local_services\esmfold\tests\test_stub_predictor.py

# E2E (levanta servidor en puerto 18100, prueba /health, /predict, /status)
python local_services\esmfold\tests\test_e2e.py
```

## Estructura de archivos

```
local_services/
└── esmfold/
    ├── app.py           # Servidor FastAPI + auto-shutdown
    ├── predictor.py     # StubPredictor + RealPredictor (esqueleto)
    ├── config.py        # Configuración centralizada
    ├── logger.py        # Logging estructurado rotado
    ├── requirements.txt # Deps mínimas
    ├── start.bat        # Script de arranque
    ├── stop.bat         # Script de apagado
    ├── README.md        # Este archivo
    ├── models/          # Checkpoint del modelo real (gitignored)
    ├── logs/            # Archivos de log (gitignored)
    │   └── esmfold-YYYYMMDD.log
    └── tests/
        ├── test_stub_predictor.py  # Unitarios
        └── test_e2e.py              # Smoke test completo
```

## Troubleshooting

### `curl: (7) Failed to connect to <IP-DEL-PC>:8100`

1. ¿El servicio está corriendo? → Verificar con `curl http://localhost:8100/health`
2. ¿El Firewall de Windows bloquea el puerto? → Abrir con el comando PowerShell arriba
3. ¿Cambió la IP de la PC? → Actualizar `ESMFOLD_API_URL` en el servidor

### El servidor Ubuntu no llama nunca a ESMFold

1. Verificar que `ESMFOLD_API_URL` está configurado correctamente
2. `docker compose restart worker` para recargar env vars
3. Ver logs del worker: `docker compose logs worker | grep -i esmfold`

### El servicio se apaga antes de que llegue el request

1. Aumentar `ESMFOLD_IDLE_MIN` (ej. `30` para pipelines lentos)
2. Desactivar con `ESMFOLD_IDLE_MIN=0` si necesitas control manual

### Más de 1 predicción falla seguidas → circuit breaker

El circuit breaker abre tras 3 fallos en 60s y se cierra solo tras 30s de cooldown.
Si el modelo real tarda mucho (>300s), aumentar `ESMFOLD_PREDICT_TIMEOUT`.
