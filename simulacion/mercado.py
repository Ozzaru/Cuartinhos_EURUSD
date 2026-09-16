# -*- coding: utf-8 -*-
"""
MERCADO — generador de precios artificiales sin memoria.

Paseo aleatorio en log con subpasos por minuto, volatilidad que depende de la
hora de Londres y de un regimen diario AR(1), semana de mercado de Nueva York,
spread bid-ask y calendario de noticias. Ningun ingrediente mira precios
pasados para decidir la direccion futura: cualquier efecto que el motor
encuentre aqui es un falso positivo.

Pendiente: punto de control D.
"""
