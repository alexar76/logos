# Casos de uso operativos de LOGOS

> Idiomas: [English](./use-cases.md) · [Русский](./use-cases.ru.md) · **Español** · [Français](./use-cases.fr.md) · [中文](./use-cases.zh.md)

Son flujos operativos, no relatos comerciales. Los valores se leyeron de la API local
en vivo el **2026-08-10 17:24 UTC**; son una observación fechada, no constantes.

## 1. Entrega del turno de federación

El operador abre `GET /api/v1/report/daily` y confirma la procedencia en
`GET /api/v1/snapshot`. El ejemplo mostraba `overall_status=warn`, `1/4` Hubs sanos y
`53` capabilities indexadas, mientras el catálogo aún enumeraba Oracle Family (42),
GAIA IoT (11) y Factory.

**Decisión:** investigar el sondeo de salud sin afirmar que tres Hubs desaparecieron.
`latency_ms=null` no significa latencia cero.

## 2. FinOps: proyección del gasto mensual

`GET /api/v1/consumption` midió `$0.04` liquidados, 52 capabilities de pago, una gratis
y un precio máximo enrutado de `$0.0505`. LOGOS devolvió
`estimated_monthly_spend_usd=null` y `spend_basis=unavailable` porque faltaba una ventana
de liquidación de 24 horas utilizable.

**Decisión:** no financiar según una proyección inventada; restaurar la telemetría,
esperar una ventana representativa y volver a calcular.

## 3. Concentración de proveedores antes del lanzamiento

El responsable agrupa `GET /api/v1/federation/capabilities` por `source_hub` y compara
capability, precio y confianza. 42 de 53 entradas externas procedían de Oracle Family
(79,25%) y 11 de GAIA IoT.

**Decisión:** buscar una segunda ruta para la capability exacta o aceptar explícitamente
la dependencia. La concentración indica riesgo; no demuestra una caída.

## 4. Cadena seguridad-remediación

Con `LOGOS_MOMUS_URL` y `LOGOS_SKOPOS_URL`, el responsable correlaciona severidad, Hub
y remediation sin enviar detalles secretos al LLM. En el despliegue observado
`findings.status=no_data`: MOMUS no estaba configurado. Significa “fuente ausente”, no
“cero vulnerabilidades”.

## 5. Verificar una supuesta contracción

`GET /api/v1/trend?metric=total_capabilities&hours=24` devolvió 24 puntos guardados
entre 15:08 y 17:21 UTC, todos `53.0`.

**Decisión:** descartar una contracción en esa ventana y revisar reachability, filtros
del cliente u otro Hub. LOGOS nunca fabrica una línea base cuando falta historia.

## 6. Pregunta natural con procedencia

Pregunta: “¿Faltan capabilities o solo están enfermos los peers?” Una respuesta válida
indica hora, separa 53 capabilities indexadas de 1/4 Hubs sanos y marca MOMUS/Treasury
como no disponibles. Nunca inventa causa, previsión ni convierte `null` en `0`.
