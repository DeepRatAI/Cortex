# Installation & Operations Guide

## Prerequisites

- Python 3.11+
- Docker & Docker Compose

## Local (no Docker)

```bash
make install
make run
```

Open http://localhost:8088/docs

## Docker Compose

```bash
cp .env.example .env
make compose-up
```

Services:

- API: http://localhost:8088
- Qdrant: http://localhost:6333
- Ollama: http://localhost:11434
- Redis: internal only

### Initialize Qdrant collection

Run (after services are up):

```bash
make qdrant-init
```

### Ingest synthetic demo documents

```bash
make ingest
```

Verify points via Qdrant API:

```bash
curl -s http://localhost:6333/collections/corporate_docs/points/scroll | jq . | head
```

## Testing & Quality

```bash
make format
make lint
make typecheck
make coverage
make audit
```

## Environments

- Development: defaults from `.env.example`
- Production: set `CKA_*` vars via secret manager / orchestrator; adjust Docker resources and security.
