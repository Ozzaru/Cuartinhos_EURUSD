# Cuartinhos EUR/USD

Tesis (Magister en Finanzas UAI). Estudia que pasa con el EUR/USD despues de que el precio rompe el maximo o el minimo de la franja horaria anterior: si sigue en la direccion de la ruptura (cascada de stops) o si se devuelve (presion de liquidez), de que depende y si el efecto sobrevive a los costos.

Las franjas son 4 bloques de 6 horas en hora de Londres. La regla que gobierna todo el codigo: **en el instante t solo se usan barras cuyo CIERRE es <= t**. El indice de cada barra es su hora de APERTURA, asi que su informacion recien existe en indice + 1 minuto.

El motor y la estadistica se validaron con mercados simulados (puntos A a F). En el punto G se obtuvieron los datos reales (Dukascopy y HistData, 2003-2020) y se reviso su calidad **a ciegas**: sin calcular ningun resultado. Toda lectura de precios pasa por un candado (`fuentes/cargador.py`): mientras no exista la etiqueta `prerregistro-v1`, solo el control de calidad recibe datos. El tramo sellado (desde 2021) no se descarga.

## Mapa de carpetas

| Carpeta | Que hay |
|---|---|
| `config.py` | Todos los parametros. Ningun otro archivo inventa numeros. |
| `motor/` | `franjas` (calendario), `eventos` (ruptura, sostenida, reingreso), `resultados` (retornos normalizados), `moderadores` (H3, H4), `nula` (nula emparejada), `inferencia` (regresiones y pruebas multiples), `auditoria` (prueba de truncamiento). |
| `simulacion/` | `mercado` (precios artificiales sin memoria) e `inyeccion` (efecto conocido). |
| `fuentes/` | Datos reales: `cargador` (candado y unica lectura de precios), `formatos`, `manifiesto`, `descarga_histdata`, `calendario` (anuncios oficiales) y `calidad` (control de calidad del pre-registro, 3.3). |
| `calendario/` | Lista cerrada de anuncios (`anuncios.csv`, sin precios), lo excluido y lo pendiente. |
| `experimentos/` | Control negativo (falsos positivos), control positivo (potencia, diseno D y control B), diagnostico del tamano, auditoria causal, potencia de H3 y H4 y anexo de sensibilidad de la deteccion. |
| `tests/` | Pruebas con series pequenas hechas a mano. |
| `registro/` | Bitacora de trabajo, tabla de decisiones del punto F, pre-registro, registro de lecturas de precios (`aperturas.md`, solo crece) y manifiesto de los crudos (`manifiesto_datos.csv`: archivo, URL, fecha, tamano y sha256). |
| `datos/`, `resultados/` | Ignoradas por git. Se regeneran corriendo el codigo. |

Los precios viven fuera del repositorio: crudos en `C:\WorkSpace\20_Data\Raw\Cuartinhos_EURUSD\` y procesados (parquet en UTC) en `C:\WorkSpace\20_Data\Processed\Cuartinhos_EURUSD\`. Las rutas estan en `config.py` y se cambian con `CUARTINHOS_CRUDOS` y `CUARTINHOS_PROCESADOS`.

## Como correr

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
```

Datos (punto G; Dukascopy se exporta a mano con JForex, porque sus terminos prohiben la descarga automatica):

```
python -m fuentes.descarga_histdata                                   HistData, 2003-2020
python -m fuentes.manifiesto --registrar-manuales dukascopy           registra los CSV exportados
python -m fuentes.cargador --convertir dukascopy --desde 2003-05-04 --hasta 2020-12-31
python -m fuentes.cargador --convertir histdata --desde 2003-05-04 --hasta 2020-12-31
python -m fuentes.calendario                                          anuncios (pide CUARTINHOS_CONTACTO para el BLS)
python -m fuentes.calidad --desde 2003-05-04 --hasta 2020-12-31       control de calidad -> resultados/calidad.md
```

Para retomar el trabajo en una sesion nueva basta leer este archivo y `registro/bitacora.md`.
