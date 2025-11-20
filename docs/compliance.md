# Compliance & Supply Chain

## SBOM

- Generated using Syft (`make sbom`). Published as CI artifact.
  - CI job: `sbom` uploads `sbom.json` (CycloneDX).

## Image Scanning

- Trivy scans the built image and fails CI on HIGH/CRITICAL.
  - CI job: `image-scan` builds `cortex-ka:ci` and runs Trivy.

## Dependency Audit

- pip-audit runs in CI and fails on HIGH/CRITICAL vulnerabilities.

## Test Strategy

- Unit/integration tests run in `build-test` job.
- E2E tests marked `@pytest.mark.e2e` and may require `HF_API_KEY`; skipped if absent.
- Streaming functionality verified under `@pytest.mark.streaming`.

## Operational Controls

- Logs are structured and can be shipped to SIEM.
- Metrics and tracing provide evidence for SLO compliance.

---

Keep this page updated with audit evidence and links to SBOM artifacts.
