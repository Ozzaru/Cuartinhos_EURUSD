# -*- coding: utf-8 -*-
"""
RECURSOS — cuanta memoria hay y cuantos procesos caben.

Un mercado de 13 anos ocupa varios cientos de megas mientras se procesa. Lanzar
un proceso por nucleo llenaria la memoria y el sistema empezaria a usar el
disco, que es entre diez y cien veces mas lento: la corrida "paralela"
terminaria tardando mas que la secuencial.

Por eso el numero de procesos sale de la memoria disponible y no de los nucleos.
Sin dependencias externas: se le pregunta directo a Windows, y en otros sistemas
se cae a una estimacion conservadora.
"""
import ctypes
import math
import os
import threading
import time


class _EstadoMemoria(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def memoria_gb():
    """(total, disponible) en gigabytes. Si no se puede saber, (nan, nan)."""
    try:
        estado = _EstadoMemoria()
        estado.dwLength = ctypes.sizeof(_EstadoMemoria)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado))
        return estado.ullTotalPhys / 1e9, estado.ullAvailPhys / 1e9
    except (AttributeError, OSError):
        return float("nan"), float("nan")


def medir_pico(funcion, intervalo=0.05):
    """
    Corre `funcion` y estima cuanta memoria llego a ocupar, en gigabytes.

    Se mide mirando cuanto BAJA la memoria disponible del sistema mientras la
    funcion trabaja. Es una estimacion, no una medicion exacta: si otro
    programa pide o suelta memoria al mismo tiempo, el numero se ensucia. Para
    decidir cuantos procesos lanzar alcanza y sobra, y tiene la ventaja de no
    depender de ninguna biblioteca externa.

    Devuelve (resultado de la funcion, pico estimado en GB, segundos).
    """
    muestras = []
    parar = threading.Event()

    def vigilar():
        while not parar.is_set():
            muestras.append(memoria_gb()[1])
            parar.wait(intervalo)

    _, antes = memoria_gb()
    vigilante = threading.Thread(target=vigilar, daemon=True)
    vigilante.start()
    comienzo = time.perf_counter()
    try:
        resultado = funcion()
    finally:
        parar.set()
        vigilante.join(timeout=1.0)
    segundos = time.perf_counter() - comienzo

    minimo = min(muestras) if muestras else antes
    return resultado, max(0.0, antes - minimo), segundos


def procesos_que_caben(memoria_por_proceso_gb, fraccion=0.70, tope=None):
    """
    Cuantos procesos lanzar sin pasarse de `fraccion` de la memoria disponible.

    Nunca devuelve menos de 1: si no cabe ni uno, igual hay que correr, aunque
    sea de a uno, y el informe dira que la memoria quedo justa.
    """
    nucleos = os.cpu_count() or 1
    tope = nucleos if tope is None else min(tope, nucleos)
    _, disponible = memoria_gb()
    if not memoria_por_proceso_gb > 0 or math.isnan(disponible):
        return max(1, min(tope, nucleos // 2))
    caben = int((disponible * fraccion) // memoria_por_proceso_gb)
    return max(1, min(tope, caben))


def describir():
    """Una linea para el encabezado de los reportes."""
    total, disponible = memoria_gb()
    return (f"{os.cpu_count()} nucleos logicos, "
            f"{total:.1f} GB de RAM ({disponible:.1f} GB disponibles)")
