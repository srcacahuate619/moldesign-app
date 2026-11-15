## Después, en la estación

1. Guarda el zip **fuera del repositorio**, por ejemplo en `D:\moldesign-dev-data\colab-plddt\`, y descomprímelo.
2. Comprueba qué diría hoy el producto de cada archivo. Es la línea base del cambio:

   ```
   python-embed\python.exe -I scripts\colab_plddt\leer_con_el_producto.py D:\moldesign-dev-data\colab-plddt\<carpeta>
   ```

3. Con `CONVENCION.md` y `analisis.json` se decide qué grupos quedan verificados. El cambio en
   `backend/services/targets/prediccion.py` llevará como fixtures recortes de estos archivos, con su procedencia y
   sus hashes, igual que se hizo con AlphaFold DB. Lo que no cumpla el criterio seguirá saliendo «no disponible».
