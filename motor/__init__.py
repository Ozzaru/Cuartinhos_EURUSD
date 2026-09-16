# -*- coding: utf-8 -*-
"""
MOTOR — deteccion causal de eventos de ruptura de franja y su medicion.

Regla unica de causalidad, valida en todos los modulos de este paquete:
el indice del DataFrame es la hora de APERTURA de la barra; su informacion
recien esta disponible en el CIERRE, es decir indice + 1 minuto. Para un
evento en el instante t solo se pueden usar barras cuyo cierre sea <= t.

Modulos:
  franjas.py      asigna fecha de Londres, franja y cobertura a cada minuto.
  eventos.py      detecta ruptura, ruptura sostenida y reingreso.
  resultados.py   sigma_ref y retornos normalizados posteriores al evento.
  moderadores.py  variables de H3 y H4, todas con informacion pasada.
  nula.py         hipotesis nula emparejada por franja, dia y volatilidad.
  inferencia.py   regresiones y correccion por pruebas multiples.
  auditoria.py    prueba de truncamiento: verifica que no haya fuga de futuro.
"""
