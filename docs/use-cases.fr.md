# Cas d’usage opérationnels de LOGOS

> Langues : [English](./use-cases.md) · [Русский](./use-cases.ru.md) · [Español](./use-cases.es.md) · **Français** · [中文](./use-cases.zh.md)

Ce sont des procédures d’exploitation, pas des récits marketing. Les valeurs ont été
lues dans l’API locale en direct le **2026-08-10 à 17:24 UTC** : elles sont datées et
doivent être remesurées.

## 1. Relève matinale de la fédération

L’astreinte lit `GET /api/v1/report/daily`, puis vérifie la provenance dans
`GET /api/v1/snapshot`. L’exemple indiquait `overall_status=warn`, `1/4` Hubs sains et
`53` capabilities indexées, tandis que le catalogue citait toujours Oracle Family (42),
GAIA IoT (11) et Factory.

**Décision :** enquêter sur le health polling sans prétendre que trois Hubs ont disparu.
`latency_ms=null` ne vaut pas une latence nulle.

## 2. FinOps : peut-on projeter le mois prochain ?

`GET /api/v1/consumption` mesurait `$0.04` réglés, 52 capabilities payantes, une
gratuite et un prix routé maximal de `$0.0505`. LOGOS renvoyait
`estimated_monthly_spend_usd=null` et `spend_basis=unavailable`, faute de fenêtre de
règlement 24 h exploitable.

**Décision :** ne pas financer sur une prévision inventée ; restaurer la télémétrie,
attendre une période représentative, puis recalculer.

## 3. Concentration des fournisseurs avant lancement

Le responsable groupe `GET /api/v1/federation/capabilities` par `source_hub` et compare
capability, prix et confiance. 42 entrées externes sur 53 venaient d’Oracle Family
(79,25 %), 11 de GAIA IoT.

**Décision :** trouver une deuxième route pour la capability exacte ou accepter
explicitement la dépendance. Une concentration est un signal de risque, pas une panne.

## 4. Chaîne sécurité-remédiation

Avec `LOGOS_MOMUS_URL` et `LOGOS_SKOPOS_URL`, le responsable corrèle sévérité, Hub et
remediation sans transmettre les détails secrets au LLM. Dans le déploiement observé,
`findings.status=no_data` car MOMUS n’était pas configuré : cela signifie « source
absente », jamais « zéro vulnérabilité ».

## 5. Prouver une contraction supposée

`GET /api/v1/trend?metric=total_capabilities&hours=24` renvoyait 24 points stockés entre
15:08 et 17:21 UTC, tous à `53.0`.

**Décision :** rejeter la contraction sur cette fenêtre et vérifier reachability,
filtres client ou autre Hub. LOGOS ne synthétise pas de baseline manquante.

## 6. Question naturelle avec provenance

Question : « Des capabilities manquent-elles ou les peers sont-ils seulement malsains ? »
Une réponse valide horodate l’observation, distingue 53 capabilities indexées de 1/4
Hubs sains et marque MOMUS/Treasury indisponibles. Elle n’invente ni cause, ni prévision,
et ne transforme jamais `null` en `0`.
