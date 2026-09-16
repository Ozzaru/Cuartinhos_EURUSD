# -*- coding: utf-8 -*-
"""
AUDITORIA — prueba de truncamiento contra el sesgo de anticipacion.

Idea heredada del proyecto anterior (Cuartinhos_Goty, motor.py::causality_audit):
correr la deteccion con la muestra cortada en un instante y con la muestra
completa; los eventos anteriores al corte deben ser identicos. Alli se
verifico que NO conviene dejar un margen de seguridad alrededor del corte:
justamente las decisiones pegadas al corte son las unicas que una fuga
intradia puede alterar.

Pendiente: punto de control E.
"""
