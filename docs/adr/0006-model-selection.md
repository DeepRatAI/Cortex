# ADR-0006: Hugging Face Model Selection for Production-like Free Tier

Date: 2025-11-11
Status: Accepted
Context: We switch default real provider to Hugging Face Inference for a small, publicly available, instruction-tuned chat model. Requirements: fast cold start, low token cost, stable hosting, permissive license suitable for internal corporate experimentation, reasonably aligned instruction following.

## Candidates Surveyed

| Model                              | Params | Pros                                                              | Cons                                                 | Notes                                          |
| ---------------------------------- | ------ | ----------------------------------------------------------------- | ---------------------------------------------------- | ---------------------------------------------- |
| TinyLlama/TinyLlama-1.1B-Chat-v1.0 | 1.1B   | Very small, fast, widely mirrored; instruction tuned; low latency | Lower quality vs 3B+/7B; may hallucinate more        | Good balance for smoke, low infra footprint    |
| tiiuae/falcon-7b-instruct          | 7B     | Better coherence; widely known                                    | Slower cold starts; higher inference cost; may queue | Previously default in code; replaced for speed |
| mistralai/Mistral-7B-Instruct-v0.2 | 7B     | Strong performance, modern arch                                   | Slightly heavier; potential loading delays           | Suitable upgrade path                          |
| meta-llama/Llama-3.2-3B-Instruct   | 3B     | Mid-size trade-off quality vs cost                                | May not always be free / could be gated              | Consider if quality complaints arise           |
| google/gemma-2-2b-it               | 2B     | Small, decent instruction following                               | Availability varies; may load slower than TinyLlama  | Alternative small fallback                     |

## Decision

Pick: `TinyLlama/TinyLlama-1.1B-Chat-v1.0`
Rationale: Minimizes latency and cost while providing basic instruction-following for RAG scaffolding. Aligns with goal of fast developer feedback loops. Larger models can be opted into via env (`CKA_HF_MODEL`).

## Trade-offs

- Quality: Sacrifices depth and reduced hallucination control vs 7B+ models. Mitigated by retrieval grounding.
- Token limits: Smaller context window; we enforce input/output token ceilings already.
- Future: May upgrade default once reliability + retrieval evaluation indicates need for higher reasoning quality.

## Known Limits

- Higher hallucination probability (recommend grounding citations and maybe rejection sampling in future).
- Might produce shorter or generic responses for complex queries.
- Model updates upstream could slightly shift behavior; health check tolerates 503 during loading.

## Implementation Notes

- Added env variable `CKA_HF_MODEL` (fallback to TinyLlama if absent).
- Health endpoint surfaces hint when HF provider unhealthy (missing key, model load, unauthorized).
- Fake provider remains selectable (`CKA_LLM_PROVIDER=Fake`) for offline tests.

## Alternatives Considered

Keeping Falcon 7B as default rejected due to slower dev loop and higher resource usage.
Switching to Mistral 7B early rejected until quality need justifies cost.

## Consequences

- Faster local real-mode validation (`make smoke` after key injection).
- Slightly less representative of higher-quality production model; document upgrade path.

## Follow-ups

- Add automatic fallback to Fake provider when HF request errors exceed threshold.
- Consider structured response format (tool call JSON) with a larger model.
