# LOGOS operational use cases

> Languages: **English** · [Русский](./use-cases.ru.md) · [Español](./use-cases.es.md) · [Français](./use-cases.fr.md) · [中文](./use-cases.zh.md)

These are operator workflows, not marketing stories. Values in the worked examples were
read from the live local LOGOS API on **2026-08-10 17:24 UTC**. They are a dated
observation, not constants. Repeat each request to obtain the current result.

## 1. Morning federation handover

**Who:** the on-call platform engineer taking the next shift.

1. Open the dashboard or request `GET /api/v1/report/daily`.
2. Read the ratio, then open `GET /api/v1/snapshot` for provenance.
3. Separate catalogue visibility from active reachability.

Observed example: the report said `overall_status=warn`, `1/4` hubs healthy and `53`
capabilities. The snapshot still named the Oracle Family (42 capabilities), GAIA IoT
(11), and the Factory peer. The correct handover is therefore “the catalogue is
available, but active health is degraded” — not “three hubs disappeared.”

**Decision:** investigate health polling while preserving routing/catalogue evidence.
**Honesty check:** `healthy=false` and `latency_ms=null` are not converted to zero latency.

## 2. FinOps: can we project next month's spend?

**Who:** the operator deciding whether to fund a payment channel.

Request `GET /api/v1/consumption`. In the observed response LOGOS measured `$0.04`
settled volume, zero invocations in the published 24-hour window, 52 paid capabilities,
one free capability and a maximum routed price of `$0.0505` per call. It returned
`estimated_monthly_spend_usd=null` and `spend_basis=unavailable` because the Hub did
not publish a usable 24-hour settlement window.

**Decision:** fund nothing from a made-up forecast; restore settlement-window telemetry,
then wait for a representative interval and rerun the query.

## 3. Supplier concentration before a launch

**Who:** a product owner who needs two independent capability sources.

1. Request `GET /api/v1/snapshot` and `GET /api/v1/federation/capabilities`.
2. Group external capabilities by `source_hub`.
3. Compare the requested capability, price and trust — not just total catalogue size.

Observed supply was 42 Oracle Family capabilities and 11 GAIA IoT capabilities: 79.25%
of external catalogue entries came from one family. That is a concentration signal, not
proof of an outage or misconduct.

**Decision:** locate a second route for the exact production capability or explicitly
accept single-family dependency in the launch record.

## 4. Security-to-remediation evidence chain

**Who:** the security lead correlating MOMUS findings with SKOPOS remediation.

Configure `LOGOS_MOMUS_URL` and `LOGOS_SKOPOS_URL`, then inspect the snapshot, open
anomalies and related insights. LOGOS may correlate counts, severity, affected Hub and
remediation status; it must not expose secret finding detail to the language model.

In the observed deployment `findings.status=no_data` and `total_findings=0` because no
MOMUS URL was configured. The correct result is “source unavailable,” not “the fleet has
zero vulnerabilities.” When a real source is connected, an operator can acknowledge the
LOGOS anomaly only after the linked remediation state is understood.

## 5. Prove whether a catalogue change was transient

**Who:** an SRE responding to “the federation lost tools.”

Request `GET /api/v1/trend?metric=total_capabilities&hours=24`. The observed series had
24 stored points from 15:08 to 17:21 UTC and every value was exactly `53.0`.

**Decision:** reject the claim of a catalogue contraction for that measured window and
look instead at reachability, client filtering or a different Hub. If the series has too
few points, LOGOS reports the available history; it does not synthesize a baseline.

## 6. Ask in natural language without losing provenance

**Who:** an incident commander who does not know the endpoint names.

Ask: “Are capabilities missing, or are peers merely unhealthy?” The assistant retrieves
stored snapshots and fixed-query results, applies the input guard, and answers in the
selected language. A useful answer must cite the observation time, distinguish 53 indexed
capabilities from 1/4 healthy hubs, and mark MOMUS/Treasury as unavailable when their
sources are absent.

**Never acceptable:** invented causal explanations, a fabricated spend forecast, or
turning `null` into `0`.
