"""
services/alphafold/__init__.py

Servicio de integración con AlphaFold Database.

Permite obtener estructuras 3D predichas por AlphaFold2 para proteínas
que no tienen estructura experimental disponible en el PDB.

Esto expande las posibilidades de target del docking más allá de las
~200,000 estructuras experimentales del PDB, cubriendo potencialmente
cualquier proteína del proteoma humano (~20,000 proteínas).

Limitaciones (transparencia científica obligatoria):
- Las estructuras de AlphaFold son PREDICCIONES, no datos experimentales.
- El pLDDT score indica la confianza del modelo — regiones con pLDDT < 70
  NO deben usarse para docking.
- El docking contra estructuras predichas tiene mayor incertidumbre
  que contra estructuras experimentales cryo-EM o cristalográficas.
- Deben reportarse warnings explícitos cuando se usa un target de AlphaFold.
"""
