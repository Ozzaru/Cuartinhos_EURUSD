# -*- coding: utf-8 -*-
"""
INYECCION — agrega un efecto conocido a un mercado simulado.

Despues de cada evento del tipo elegido suma una deriva lineal en los
siguientes H minutos, calibrada para que el retorno normalizado esperado a H
sea el delta pedido.

Pendiente: punto de control E.
"""
