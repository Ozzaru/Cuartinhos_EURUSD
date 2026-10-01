# -*- coding: utf-8 -*-
"""
FUENTES — los datos reales: descarga, candado, conversion y control de calidad.

Punto G. Los precios viven fuera del repositorio (rutas en config.py, seccion
12). Toda lectura de precios pasa por `cargador.py`; ningun otro modulo abre
un archivo de precios.

Modulos:
  cargador.py           el candado (pre-registro 2.4) y la unica lectura de
                        precios; convierte los crudos a parquet en UTC.
  formatos.py           interpreta el texto de cada fuente. No abre archivos:
                        recibe el flujo que le pasa el cargador.
  manifiesto.py         registro versionado de los crudos (archivo, URL, fecha,
                        tamano y sha256), sin precios.
  descarga_histdata.py  descarga de HistData, con pausas, reintentos y
                        retomable. Rechaza toda fecha desde el inicio del
                        sellado.
  calidad.py            control de calidad del pre-registro (3.3). Solo usa
                        rupturas: si hay, direccion y minuto.

Este archivo no importa los submodulos, por la misma razon que `motor`: quien
pide uno no carga los demas.
"""
