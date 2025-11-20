# ADR 0004: Observability and Tracing Strategy

## Status

Accepted

## Context

Enterprise readiness requires actionable observability: metrics for SLO tracking, structured logs for correlation, and tracing for root-cause analysis and latency breakdown. Initially the system had only logging; metrics/tracing absent. We added Prometheus metrics and optional OpenTelemetry instrumentation.

## Decision

1. Use Prometheus client library for in-process metrics: counters (requests) and histograms (latency, chunk counts).
2. Instrument all requests via FastAPI middleware for uniform latency measurement and status class counting.
3. Provide a dedicated `/metrics` endpoint exposing Prometheus exposition format.
4. Integrate OpenTelemetry tracing optionally via env flag `CKA_ENABLE_TRACING`; export spans using OTLP over HTTP to ensure compatibility with common collectors (Tempo, Jaeger, OpenTelemetry Collector).
5. Keep tracing disabled by default to avoid overhead in minimal dev setups.

## Alternatives Considered

| Option                       | Reason Rejected                                       |
| ---------------------------- | ----------------------------------------------------- |
| Custom metrics endpoint JSON | Not compatible with Prometheus/Grafana ecosystem      |
| Proprietary APM agent        | Vendor lock-in; conflicts with educational/demo goals |
| Always-on tracing            | Unnecessary overhead for resource-limited local runs  |

## Consequences

Positive:

- Enables dashboards, alerts, and latency monitoring out-of-the-box.
- Simplifies incident diagnostics (trace spans show retrieval vs generation time).
- Standard tooling reduces integration friction.

Negative:

- Slight runtime overhead when tracing enabled.
- Requires outbound connectivity/config to OTLP collector.

## Follow-up Tasks

- Add span attributes for chunk count, token budget, cache hits.
- Export structured logs with trace_id correlation (inject trace context into logger).
- Provide Grafana dashboard templates in `docs/diagrams/`.

## References

- OpenTelemetry Specification: https://opentelemetry.io/
- Prometheus Client Python: https://github.com/prometheus/client_python
