"""Programas de terceros que MolDesign ejecuta como procesos independientes.

Un módulo entra aquí cuando el programa que envuelve **no** se enlaza ni se
importa: se invoca por línea de órdenes, con archivos o flujos de entrada y
salida, y su resultado se valida antes de aceptarse.

La distinción no es de estilo. Determina qué obligaciones de licencia arrastra
el programa envuelto hacia el código de MolDesign, y determina también qué se
puede afirmar en un informe: un adaptador que verifica el binario antes de
ejecutarlo puede decir *qué* produjo el resultado; uno que resuelve por `PATH`
sólo puede decir que algo lo produjo.
"""
