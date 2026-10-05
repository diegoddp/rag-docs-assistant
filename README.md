# RAG Docs Assistant

A FastAPI service that answers questions about a folder of Markdown documents using Retrieval-Augmented Generation (RAG). It indexes the documents into a vector database (Chroma), retrieves the most relevant passages for each question and asks an LLM to answer using only that context, citing the source.

## Features

- POST /perguntar: answers a question using only the indexed documents and returns the sources used
- Documents are read from `docs/*.md` and indexed into Chroma on first start (persisted on disk)
- Mock mode for local development and tests (no API calls, no cost)
- Configurable via environment variables (mock/real, documents folder, database path)

## How it works

1. **Load**: every `.md` file in `docs/` is read into memory, keeping the file name as its source.
2. **Embed and store**: each document is turned into an embedding vector and stored in a Chroma collection, together with its source as metadata. This runs only when the collection is empty.
3. **Retrieve**: the question is embedded the same way and Chroma returns the top-3 closest documents (cosine distance).
4. **Generate**: the retrieved passages are placed in the prompt as context and the LLM is instructed to answer only from that context and to cite the source. The API returns the answer and the list of sources used.

## Tech stack

- Python 3.12 · FastAPI · Pydantic · Chroma · OpenAI API (gpt-4o-mini, text-embedding-3-small) · pytest · Docker

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `USAR_MOCK` | `true` | `false` uses the real OpenAI embeddings and LLM |
| `OPENAI_API_KEY` | — | required when `USAR_MOCK=false` |
| `PASTA_DOCS` | `docs` | folder with the Markdown documents |
| `PASTA_DB` | `chroma_db` | where Chroma persists the vector index |

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
  "resposta": "Os reembolsos são processados em até 7 dias úteis após o cancelamento. O valor será devolvido pelo mesmo meio de pagamento usado na compra, mas apenas para compras que foram realizadas há menos de 30 dias. (reembolso.md)",
  "fontes": [
    "reembolso.md",
    "pagamento.md",
    "plano.md"
  ]
}
```

For a question outside the documents (e.g. "what is the capital of France?") the assistant answers that it could not find the information instead of guessing.

## Tests

```powershell
python -m pytest -v
```

Tests cover the pure logic (document loading, context building) and run without the vector DB or an API key.

## Next steps

- Chunking for long documents (one file is one vector today)
- Metadata filters (e.g. restrict retrieval to a section or product)
- Retrieval quality evaluation (does the right document come first?)
