"""Lector minimo de la tabla de importacion de un PE, sin dependencias externas.

POR QUE EXISTE. Para saber si el instalador funcionara en un Windows limpio hay
que responder una pregunta concreta: que DLL va a buscar el cargador de Windows
al abrir cada binario del paquete. Un `grep` de cadenas NO la responde -da falsos
positivos a mansalva, porque `delvewheel` renombra las DLLs de las ruedas con un
hash y deja los nombres originales como texto suelto: 96 binarios de RDKit
parecian depender de `rdkitrdgeneral.dll`, que no existe ni hace falta.

Esto lee la estructura del archivo: cabecera DOS -> cabecera PE -> directorio de
importacion -> nombres. No ejecuta nada, asi que el resultado NO depende de lo
que la maquina que lo ejecuta tenga instalado. Esa independencia es el punto
entero: una comprobacion que depende del entorno no puede detectar una
dependencia del entorno.

LIMITE CONOCIDO. Solo lee el directorio de importacion estandar. Las
dependencias de CARGA DIFERIDA (delay-load) no aparecen aqui, y esta bien que
sea asi: Windows solo las resuelve si se llama a una funcion que las use, de
modo que su ausencia no impide arrancar. Ejemplo medido en este repositorio:
`llama-common.dll` carga sin problema en una maquina donde `libcrypto-3-x64.dll`
no existe ni en System32 ni en el PATH.
"""
import struct


def _rva_a_offset(secciones, rva):
    for va, tam_virtual, ptr_datos, tam_datos in secciones:
        if va <= rva < va + max(tam_virtual, tam_datos):
            delta = rva - va
            if delta < tam_datos:
                return ptr_datos + delta
    return None


def imports_de(ruta):
    """Nombres de DLL importados, en minusculas. Lista vacia si no es un PE."""
    try:
        with open(ruta, "rb") as fh:
            datos = fh.read()
    except OSError:
        return []

    if len(datos) < 0x40 or datos[:2] != b"MZ":
        return []
    pe_off = struct.unpack_from("<I", datos, 0x3C)[0]
    if pe_off + 24 > len(datos) or datos[pe_off:pe_off + 4] != b"PE\0\0":
        return []

    n_secciones = struct.unpack_from("<H", datos, pe_off + 6)[0]
    tam_opcional = struct.unpack_from("<H", datos, pe_off + 20)[0]
    opt_off = pe_off + 24
    if opt_off + 2 > len(datos):
        return []
    magic = struct.unpack_from("<H", datos, opt_off)[0]
    if magic == 0x20B:      # PE32+
        dir_off = opt_off + 112
    elif magic == 0x10B:    # PE32
        dir_off = opt_off + 96
    else:
        return []

    # El directorio 1 es el de importaciones.
    if dir_off + 16 > len(datos):
        return []
    import_rva, import_size = struct.unpack_from("<II", datos, dir_off + 8)
    if import_rva == 0 or import_size == 0:
        return []

    sec_off = opt_off + tam_opcional
    secciones = []
    for i in range(n_secciones):
        base = sec_off + i * 40
        if base + 40 > len(datos):
            break
        tam_virtual, va, tam_datos, ptr_datos = struct.unpack_from("<IIII", datos, base + 8)
        secciones.append((va, tam_virtual, ptr_datos, tam_datos))

    inicio = _rva_a_offset(secciones, import_rva)
    if inicio is None:
        return []

    nombres = []
    i = 0
    while True:
        entrada = inicio + i * 20
        if entrada + 20 > len(datos):
            break
        campos = struct.unpack_from("<IIIII", datos, entrada)
        if not any(campos):
            break
        nombre_rva = campos[3]
        off = _rva_a_offset(secciones, nombre_rva)
        if off is not None and off < len(datos):
            fin = datos.find(b"\0", off)
            if fin != -1:
                try:
                    nombres.append(datos[off:fin].decode("ascii").lower())
                except UnicodeDecodeError:
                    pass
        i += 1
        if i > 4096:
            break
    return nombres
