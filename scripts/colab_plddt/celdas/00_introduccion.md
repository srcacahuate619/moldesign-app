# Convención del pLDDT de Boltz-2 y Chai-1, con archivos reales

**Qué mide.** MolDesign sólo lee el pLDDT de una estructura predicha si la convención de su fuente está verificada
con un archivo real (`backend/services/targets/prediccion.py`). Hoy sólo lo está la de AlphaFold DB: una estructura
de Boltz o de Chai-1 sale con el pLDDT «no disponible». Este cuaderno genera esos archivos y compara cada campo
candidato del archivo (factor B por átomo, media por residuo, `_ma_qa_metric_local`) con el pLDDT que devuelve el
propio modelo: el `plddt_*.npz` de Boltz y el tensor `plddt` que devuelve `run_inference` en Chai-1.

**Criterio, fijado antes de ejecutar.** La convención queda verificada para un grupo (herramienta, formato) si se
cumplen las dos condiciones:

- el grupo tiene **al menos dos estructuras** terminadas;
- en **todas** ellas, un mismo campo del archivo reproduce el pLDDT del modelo residuo a residuo (o átomo a átomo).
  Debe hacerlo con **una sola escala** (×1, ×100 o ×0,01) y con una diferencia que no supere el redondeo con que el
  archivo escribe el número.

Si una sola estructura no cumple, el grupo queda sin verificar. Lo que no termina (por memoria o por bf16) se
registra y no cuenta ni a favor ni en contra. La correlación con AlphaFold DB es un control de sentido y no forma
parte del criterio.

**Casos.**

| Caso | Boltz | Chai-1 |
|---|---|---|
| CDK2 sin ligando (P24941) | mmCIF y PDB | mmCIF, 5 muestras |
| CDK2 con un ligando del benchmark de OpenFF | mmCIF y PDB | mmCIF, 5 muestras |
| NET humano (P23975, la misma proteína del fixture de AlphaFold DB del producto) | mmCIF | mmCIF, 5 muestras |

**Qué sale de Colab.** No sale nada del repositorio ni de MolDesign. Sólo se conecta con estos servicios públicos:

- UniProt (`rest.uniprot.org`), de donde se descargan las secuencias;
- el servidor MSA de ColabFold (`api.colabfold.com`), que recibe esas secuencias si `USAR_SERVIDOR_MSA` está activado;
- AlphaFold DB (EBI), de donde se descarga el modelo de P23975;
- PyPI y los sitios de donde cada modelo descarga sus pesos.

**Entorno.** Elige L4 en *Entorno de ejecución → Cambiar tipo de entorno de ejecución*. Chai-1 necesita bf16, así
que en una T4 probablemente no corra. Una A100 también sirve, pero gasta más unidades por hora.

**Coste.** Es una estimación, no una medida: la instalación y las descargas llevan unos 20–30 min y las predicciones
unos 20–45 min. En total, alrededor de una hora de L4.

**Cómo ejecutarlo.**

1. Elige *Entorno de ejecución → Ejecutar todo*.
2. El cuaderno pide permiso para montar tu Drive, donde copia los resultados después de cada paso. Si Colab se
   desconecta, o si quieres repetir lo que falló, vuelve a ejecutarlo todo. Retoma los resultados de Drive, instala y
   corre sólo las herramientas con corridas pendientes, y salta las que ya terminaron. Lo que falló se aparta con su
   fecha, aquí y en Drive; no se borra nada.
3. Al final descarga un zip.
4. **Desconecta el entorno** en cuanto termine, porque una GPU conectada gasta unidades aunque no esté haciendo nada.
