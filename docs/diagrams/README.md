Mermaid diagrams placeholder. Add `.mmd` sources here.

```mermaid
 flowchart LR
	 A[User] -->|HTTP /query| B(FastAPI API)
	 B --> C[Retriever (Qdrant)]
	 B --> D[Embedder (Sentence-Transformers)]
	 C --> B
	 D --> B
	 B --> E[LLM (HF provider)]
	 E --> B
	 B -->|Answer + Citations| A
```

```mermaid
sequenceDiagram
	 participant User
	 participant API
	 participant Qdrant
	 participant Embed
	 participant LLM
	 User->>API: POST /query { query }
	 API->>Embed: embed(query)
	 Embed-->>API: vector
	 API->>Qdrant: query_points(vector, k)
	 Qdrant-->>API: top-k chunks
	 API->>LLM: generate(prompt with chunks)
	 LLM-->>API: answer
	 API-->>User: { answer, citations }
```

Mermaid diagrams placeholder. Add `.mmd` sources here.
