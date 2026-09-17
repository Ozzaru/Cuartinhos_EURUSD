# -*- coding: utf-8 -*-
"""
Utilidades para armar series de mercado pequenas y hechas a mano.

La idea es que cada test escriba minuto a minuto lo que quiere probar y que
el resultado esperado se pueda calcular con lapiz y papel.
"""
from types import SimpleNamespace

import numpy as np
import pandas as pd

import config

PIP = 0.0001


def cfg_prueba(**cambios):
    """
    Una copia de config.py con los cambios que pida el test.

    Se trabaja sobre una copia para que ningun test modifique la configuracion
    de verdad y contamine a los demas.
    """
    base = {k: v for k, v in vars(config).items() if k.isupper()}
    base.update(cambios)
    return SimpleNamespace(**base)


def indice(inicio, minutos):
    """Un indice de minutos en UTC a partir de una fecha escrita como texto."""
    return pd.date_range(inicio, periods=minutos, freq="min", tz="UTC")


def datos(velas, inicio=None, idx=None, spread_pips=0.2):
    """
    Arma el DataFrame de mercado a partir de velas del precio MEDIO.

    `velas` es una lista de tuplas (open, high, low, close). Se puede pasar
    `inicio` (y el indice sale correlativo) o un `idx` propio, que es como se
    construyen los huecos de datos y los cierres de mercado.

    El bid y el ask se arman simetricos alrededor del medio, asi el precio medio
    que recupera el motor es exactamente el que escribio el test.
    """
    velas = np.asarray(velas, dtype=float)
    if velas.ndim != 2 or velas.shape[1] != 4:
        raise ValueError("cada vela debe ser (open, high, low, close)")
    if idx is None:
        idx = indice(inicio, len(velas))
    if len(idx) != len(velas):
        raise ValueError("el indice y las velas no tienen el mismo largo")

    medio = spread_pips * PIP / 2.0
    tabla = {}
    for k, lado in enumerate(["open", "high", "low", "close"]):
        tabla[f"bid_{lado}"] = velas[:, k] - medio
        tabla[f"ask_{lado}"] = velas[:, k] + medio
    return pd.DataFrame(tabla, index=idx)


def velas_de_cierres(cierres, apertura=None, altos=None, bajos=None):
    """
    Convierte una lista de cierres en velas (open, high, low, close).

    La apertura de cada vela es el cierre de la anterior. El maximo y el minimo
    salen de la apertura y del cierre, salvo que el test los indique aparte:
    eso permite escribir una vela cuyo maximo rompe un nivel aunque su cierre
    se quede adentro.
    """
    cierres = np.asarray(cierres, dtype=float)
    ap = np.empty_like(cierres)
    ap[0] = cierres[0] if apertura is None else apertura
    ap[1:] = cierres[:-1]
    alto = np.maximum(ap, cierres) if altos is None else np.asarray(altos, dtype=float)
    bajo = np.minimum(ap, cierres) if bajos is None else np.asarray(bajos, dtype=float)
    return np.column_stack([ap, alto, bajo, cierres])


def plano(minutos, precio):
    """`minutos` velas sin movimiento, todas en el mismo precio."""
    return np.tile(np.array([precio, precio, precio, precio], dtype=float), (minutos, 1))


def camino_aleatorio(minutos, semilla, vol_minuto=1e-4, precio=1.10):
    """
    Un paseo aleatorio simple para tests que necesitan muchos eventos.

    No pretende parecerse al EUR/USD: para eso esta simulacion/mercado.py. Aqui
    solo hace falta una serie variada y reproducible.
    """
    rng = np.random.default_rng(semilla)
    cierres = precio * np.exp(np.cumsum(rng.normal(0.0, vol_minuto, minutos)))
    aperturas = np.concatenate([[precio], cierres[:-1]])
    mecha = np.abs(rng.normal(0.0, vol_minuto, minutos)) * cierres
    altos = np.maximum(aperturas, cierres) + mecha
    bajos = np.minimum(aperturas, cierres) - mecha
    return np.column_stack([aperturas, altos, bajos, cierres])


def posicion(idx, momento):
    """Posicion de la vela que ABRE en `momento` (escrito como texto UTC)."""
    return int(idx.get_loc(pd.Timestamp(momento, tz="UTC")))


def fijar(velas, idx, momento, apertura=None, alto=None, bajo=None, cierre=None):
    """
    Cambia a mano la vela que abre en `momento`. Lo que no se indica, no cambia.

    Sirve para escribir el caso justo que el test quiere probar: "en este minuto
    el maximo llega hasta aca y el cierre se queda aca".
    """
    k = posicion(idx, momento)
    for col, valor in enumerate([apertura, alto, bajo, cierre]):
        if valor is not None:
            velas[k, col] = valor
    return velas


def sigma_fija(n_franjas, valor=1e-4):
    """
    Un sigma_ref constante para todas las franjas.

    Los tests de deteccion usan series de pocos dias, donde sigma_ref de verdad
    no existe (hacen falta DIAS_VOL_REF_MIN dias previos). Pasarlo a mano deja
    el test corto y enfocado en lo que quiere probar. El calculo real de
    sigma_ref tiene sus propios tests.
    """
    return np.full(n_franjas, float(valor))
