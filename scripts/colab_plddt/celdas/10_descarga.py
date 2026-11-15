# ── Descarga: un zip con todo (entradas, salidas, procedencia, análisis) ──
# Con la hora en el nombre: una segunda ejecución del mismo día no pisa el zip de la primera en Drive.
zip_ruta = Path(shutil.make_archive(f"/content/plddt_boltz_chai_{sello()}", "zip", RES))
zip_sha = hashlib.sha256(zip_ruta.read_bytes()).hexdigest()
print(zip_ruta.name, round(zip_ruta.stat().st_size / 1e6, 1), "MB  SHA-256", zip_sha)
if GUARDAR_EN_DRIVE and Path("/content/drive/MyDrive").exists():
    shutil.copy(zip_ruta, DRIVE.parent / zip_ruta.name)
    print("Copia en Drive:", DRIVE.parent / zip_ruta.name)
from google.colab import files

files.download(str(zip_ruta))
print("Hecho. Desconecta el entorno: Entorno de ejecución → Desconectar y eliminar entorno de ejecución.")
