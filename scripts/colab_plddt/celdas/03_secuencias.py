# ── Secuencias de UniProt y la referencia de AlphaFold DB ──
import urllib.request


def descargar(url, destino=None):
    peticion = urllib.request.Request(url, headers={"User-Agent": "convencion-plddt/1.0"})
    with urllib.request.urlopen(peticion, timeout=120) as resp:
        datos = resp.read()
        cabeceras = {k: resp.headers.get(k) for k in ("X-UniProt-Release", "X-UniProt-Release-Date", "Last-Modified")}
    if destino:
        Path(destino).write_bytes(datos)
    return datos, cabeceras


secuencias = cargar_procedencia().get("secuencias", {})
for acc in sorted({c["uniprot"] for c in CASOS}):
    if acc in secuencias:
        continue
    datos, cab = descargar(f"https://rest.uniprot.org/uniprotkb/{acc}.fasta")
    cabecera, *resto = datos.decode().strip().splitlines()
    seq = "".join(resto).strip()
    if not seq or not set(seq) <= set("ACDEFGHIKLMNPQRSTVWYXUO"):
        raise ValueError(f"secuencia inesperada para {acc}: {cabecera}")
    secuencias[acc] = {"cabecera": cabecera, "longitud": len(seq), "sha256": hashlib.sha256(seq.encode()).hexdigest(),
                       "version_uniprot": cab["X-UniProt-Release"], "fecha_version": cab["X-UniProt-Release-Date"],
                       "descargada": ahora(), "secuencia": seq}
    print(acc, len(seq), cabecera[:90])

ref_dir = RES / "referencias"
ref_dir.mkdir(exist_ok=True)
af_ruta = ref_dir / Path(REFERENCIA_AFDB["url"]).name
referencia = {"url": REFERENCIA_AFDB["url"]}
try:
    if not af_ruta.exists():
        _, cab = descargar(REFERENCIA_AFDB["url"], af_ruta)
        referencia["last_modified"] = cab["Last-Modified"]
    h = hashlib.sha256(af_ruta.read_bytes()).hexdigest()
    referencia.update(sha256=h, igual_que_el_del_producto=(h == REFERENCIA_AFDB["sha256_en_el_producto"]))
except Exception as exc:  # el control de sentido es opcional: su falta se registra y no para nada
    referencia["error"] = f"{type(exc).__name__}: {exc}"
print(referencia)
guardar_procedencia(secuencias=secuencias, referencia_afdb_descargada=referencia)
respaldar()
