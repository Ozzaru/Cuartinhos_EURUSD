# Cuartinhos EUR/USD

Tesis (Magister en Finanzas UAI). Estudia que pasa con el EUR/USD despues de que el precio rompe el maximo o el minimo de la franja horaria anterior: si sigue en la direccion de la ruptura (cascada de stops) o si se devuelve (presion de liquidez), de que depende y si el efecto sobrevive a los costos.

Las franjas son 4 bloques de 6 horas en hora de Londres. La regla que gobierna todo el codigo: **en el instante t solo se usan barras cuyo CIERRE es <= t**. El indice de cada barra es su hora de APERTURA, asi que su informacion recien existe en indice + 1 minuto.

Esta fase NO usa datos reales: todo se valida con mercados simulados.

## Mapa de carpetas

| Carpeta | Que hay |
|---|---|
| `config.py` | Todos los parametros. Ningun otro archivo inventa numeros. |
| `motor/` | `franjas` (calendario), `eventos` (ruptura, sostenida, reingreso), `resultados` (retornos normalizados), `moderadores` (H3, H4), `nula` (nula emparejada), `inferencia` (regresiones y pruebas multiples), `auditoria` (prueba de truncamiento). |
| `simulacion/` | `mercado` (precios artificiales sin memoria) e `inyeccion` (efecto conocido). |
| `experimentos/` | Control negativo (falsos positivos), control positivo (potencia, diseno D y control B), diagnostico del tamano y auditoria causal. |
| `tests/` | Pruebas con series pequenas hechas a mano. |
| `registro/` | Bitacora de trabajo y borrador de pre-registro. |
| `datos/`, `resultados/` | Ignoradas por git. Se regeneran corriendo el codigo. |

## Como correr

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
pytest
```

Para retomar el trabajo en una sesion nueva basta leer este archivo y `registro/bitacora.md`.
