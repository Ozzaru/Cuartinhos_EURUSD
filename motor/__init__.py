# -*- coding: utf-8 -*-
"""
MOTOR — deteccion causal de eventos de ruptura de franja y su medicion.

Regla unica de causalidad, valida en todos los modulos de este paquete:
el indice del DataFrame es la hora de APERTURA de la barra; su informacion
recien esta disponible en el CIERRE, es decir indice + 1 minuto. Para un
evento en el instante t solo se pueden usar barras cuyo cierre sea <= t.

Modulos:
  franjas.py      asigna fecha de Londres, franja y cobertura a cada minuto.
  rupturas.py     que franjas pueden romper y donde rompen (sin sigma_ref).
  eventos.py      detecta ruptura, ruptura sostenida y reingreso.
  resultados.py   sigma_ref y retornos normalizados posteriores al evento.
  moderadores.py  variables de H3 y H4, todas con informacion pasada.
  nula.py         hipotesis nula emparejada por franja, dia y volatilidad.
  inferencia.py   regresiones y correccion por pruebas multiples.
  auditoria.py    prueba de truncamiento: verifica que no haya fuga de futuro.

Este archivo NO importa los submodulos al cargarse (punto G). Asi, quien pide
solo `motor.franjas` o `motor.rupturas` (el control de calidad de los datos
reales) no carga `resultados`, `nula` ni `inferencia`. Cada uno se importa
por su nombre: `from motor import eventos`.
"""


def preparar(datos, cfg, noticias=None):
    """
    El camino completo de la deteccion, de los datos crudos a la tabla final:
    barras -> calendario -> sigma de referencia -> eventos -> retornos ->
    moderadores.

    Devuelve (barras, calendario, eventos). Los retornos se calculan al final y
    no participan de la deteccion: esa separacion es la que mantiene el orden
    causal.
    """
    from . import eventos, franjas, moderadores, resultados

    barras = franjas.Barras.desde(datos, cfg)
    cal = franjas.calendario(barras, cfg)
    sigma = resultados.sigma_por_franja(barras, cal, cfg)
    tabla = eventos.detectar(barras, cal, cfg, sigma=sigma)
    tabla = resultados.agregar_retornos(barras, cal, tabla, cfg)
    tabla = moderadores.agregar(barras, cal, tabla, cfg, noticias=noticias)
    return barras, cal, tabla
