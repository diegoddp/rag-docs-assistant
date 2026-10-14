# RAG Docs Assistant

A FastAPI service that answers questions about a folder of Markdown documents using Retrieval-Augmented Generation (RAG). It indexes the documents into a vector database (Chroma), retrieves the most relevant passages for each question and asks an LLM to answer using only that context, citing the source.

**v2** adds document chunking, a retrieval funnel (over-fetch, score threshold, de-duplication), metadata filtering by category and a retrieval evaluation script with a golden set.

## Features

- POST /perguntar: answers a question using only the indexed documents and returns the sources used
- Documents are read from `docs/<category>/*.md`; the folder name becomes the document category (metadata)
- Long documents are split into paragraph chunks, so retrieval returns the relevant passage, not the whole file
- Retrieval funnel: fetch top-8, drop low-score passages, remove duplicates, keep the best 3
- If nothing passes the funnel, the API answers "not found" without calling the LLM (cheaper, no hallucination)
- Optional `categoria` filter restricts retrieval to one category (e.g. tenant or product isolation)
- Retrieval quality measured against a golden set (`avaliar.py`), see table below
- Mock mode for local development and tests (no API calls, no cost)
- Configurable via environment variables

## How it works

1. **Load**: every `.md` file under `docs/<category>/` is read, keeping `category/file.md` as its source and the folder as its category.
2. **Chunk**: each document is split on blank lines into paragraphs; each chunk keeps the source with a `#n` suffix (e.g. `suporte/politica_atendimento.md#2`).
3. **Embed and store**: each chunk is embedded and stored in a Chroma collection with `fonte` and `categoria` as metadata. Runs only when the collection is empty.
4. **Retrieve**: the question is embedded and Chroma returns the 8 closest chunks (cosine), optionally filtered by category. Chunks below the score threshold are dropped, duplicates removed, and the best 3 are kept.
5. **Generate**: the retrieved passages are placed in the prompt as context and the LLM is instructed to answer only from that context and to cite the source. The API returns the answer and the list of sources used.

## Tech stack

- Python 3.12 · FastAPI · Pydantic · Chroma · OpenAI API (gpt-4o-mini, text-embedding-3-small) · pytest · Docker

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `USAR_MOCK` | `true` | `false` uses the real OpenAI embeddings and LLM |
| `OPENAI_API_KEY` | — | required when `USAR_MOCK=false` |
| `PASTA_DOCS` | `docs` | folder with the Markdown documents (one subfolder per category) |
| `PASTA_DB` | `chroma_db` | where Chroma persists the vector index |
| `K_BUSCA` | `8` | how many chunks to fetch from Chroma before filtering |
| `SCORE_MINIMO` | `0.3` | minimum cosine similarity to keep a chunk |
| `TOP_FINAL` | `3` | how many chunks go into the LLM context |

## Run with Docker

```powershell
docker build -t rag-docs .

# mock mode (free)
docker run --rm -p 8000:8000 -v "${PWD}/chroma_db:/app/chroma_db" rag-docs

# real LLM + embeddings
docker run --rm -p 8000:8000 -v "${PWD}/chroma_db:/app/chroma_db" -e USAR_MOCK=false -e OPENAI_API_KEY=$env:OPENAI_API_KEY rag-docs
```

Docs: http://127.0.0.1:8000/docs

The `-v` flag mounts `chroma_db/` from the host, so the index survives container restarts and is only built once.

## Example

Request:

```json
POST /perguntar
{ "pergunta": "quero meu dinheiro de volta, como funciona?" }
```

Response (real LLM):

```json
{
  "resposta": "Os reembolsos são processados em até 7 dias úteis após o cancelamento. O valor será devolvido pelo mesmo meio de pagamento usado na compra, mas apenas para compras que foram realizadas há menos de 30 dias. (financeiro/reembolso.md#1)",
  "fontes": ["financeiro/reembolso.md#1", "financeiro/plano.md#1"]
}
```

With a category filter, retrieval is restricted to that folder only:

```json
{ "pergunta": "quero meu dinheiro de volta", "categoria": "conta" }
```

For a question outside the documents (e.g. "what is the capital of France?") the funnel returns no passages and the assistant answers that it could not find the information, without calling the LLM.

## Retrieval quality

`avaliar.py` runs a golden set of 10 questions (phrased differently from the documents) and checks in which position the expected file appears:

```powershell
docker run --rm -v "${PWD}:/app" rag-docs python avaliar.py
docker run --rm -v "${PWD}:/app" -e USAR_MOCK=false -e OPENAI_API_KEY=$env:OPENAI_API_KEY rag-docs python avaliar.py
```

| Embedding | hit@1 | hit@3 |
|-----------|-------|-------|
| mock (letter frequency) | 3/10 | 6/10 |
| OpenAI text-embedding-3-small | 9/10 | 10/10 |

The mock embedding exists only to run the pipeline for free; the table shows why embedding quality is the main driver of retrieval quality.

## Tests

```powershell
python -m pytest -v
```

Tests cover the pure logic (document loading, chunking, funnel filters, context building) and run without the vector DB or an API key.

## Next steps

- Answer evaluation (is the LLM answer correct and grounded?), not only retrieval
- Guardrails for off-topic or unsafe questions
- Sliding-window chunking with overlap for documents without paragraph structure
