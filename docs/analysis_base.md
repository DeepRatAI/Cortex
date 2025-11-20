# Reverse Engineering Report (Generalized)

This document captures a thorough reverse engineering of the provided base project (generalized, with all real institution names removed). It explains what the system does, how it is structured, the data flows, and the engineering decisions observed.

## Purpose

The base repository implements a multi-service Retrieval-Augmented Generation (RAG) platform. It supports ingesting documents, embedding them into vectors, storing vectors in a database, and answering user questions by retrieving relevant chunks and generating a response with an LLM. A frontend provides an enterprise-friendly chat UI.

## High-Level Components

- API Gateway and microservices (embedding, LLM, RAG orchestration)
- Vector DB (Qdrant) and caches (Redis)
- Frontend (Next.js) with i18n and E2E tests
- Orchestration with Docker Compose, and auxiliary services (Airflow, Kafka placeholders)

## Data Flow (Query)

1. User sends a question via the frontend
2. API orchestrates: embeds query, retrieves similar chunks from vector DB
3. Builds a prompt combining question and chunks
4. Calls LLM to generate an answer
5. Returns answer with optional citations

## Data Flow (Ingestion)

1. Load raw documents (manuals, policies)
2. Split into chunks (size heuristic)
3. Embed chunks with sentence-transformers
4. Upsert vectors and payload into Qdrant

## Key Technical Decisions Observed

- Separation of concerns across layers/services
- Use of local embeddings for privacy and reproducibility
- Vector DB chosen: Qdrant for similarity search
- Optional caching and rate limiting
- Docker-based reproducibility

## Risks/Challenges Identified

- External dependency reliability (LLM/Vector services)
- Token/context budgeting for long prompts
- Observability gaps (metrics/tracing)
- Security hardening (headers, auth, dependency audits)

## Guidance Applied to New Implementation

- Clean/hexagonal architecture with ports/adapters
- Structured logging, input validation, rate limiting
- Resilient adapters with graceful fallbacks in tests
- Prometheus metrics and health endpoints
- CI with lint/type/test/coverage and dependency audit gating

This report enables recreating the base architecture and rationale without reliance on any real-world names, using only generic corporate terminology.
