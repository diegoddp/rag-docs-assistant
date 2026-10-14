# =====================================================================
# main.py — RAG Docs Assistant API (FastAPI)
# =====================================================================
# Roda SÓ no Docker (chromadb/numpy bloqueados no host). Veja o README.
#   docker build -t rag-docs .
#   docker run --rm -p 8000:8000 -v "${PWD}/chroma_db:/app/chroma_db" rag-docs
#   -> http://127.0.0.1:8000/docs

import logging
from fastapi import FastAPI
from pydantic import BaseModel
from rag_lib import carregar_documentos, chunkar_documentos, criar_colecao, indexar_chroma, responder, USAR_MOCK

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="RAG Docs Assistant", version="2.0")

# ─────────────────────────────────────────────
# Ao subir a API: abre o banco e indexa SE estiver vazio.
# v2: os documentos passam pelo CHUNKING antes de indexar (Dia 31).
# ─────────────────────────────────────────────
colecao = criar_colecao()
if colecao.count() == 0:
    documentos = carregar_documentos()
    pedacos = chunkar_documentos(documentos)
    indexar_chroma(pedacos, colecao)
    logging.info(f"indexados {len(documentos)} documentos em {len(pedacos)} pedacos")
else:
    logging.info(f"banco ja tem {colecao.count()} pedacos")


# moldes — o que ENTRA e o que SAI
# >>> LACUNA G: acrescente ao molde Pergunta um campo OPCIONAL
#         categoria: str | None = None
#     (str | None = "texto ou nada"; = None é o padrão quando o cliente não manda — Dia 18)
class Pergunta(BaseModel):
    pergunta: str
    categoria: str | None = None



class Resposta(BaseModel):
    resposta: str
    fontes: list[str]


@app.get("/")
def raiz():
    modo = "mock" if USAR_MOCK else "IA real"
    return {"api": "RAG Docs Assistant", "modo": modo, "pedacos": colecao.count(), "docs": "/docs"}


# >>> LACUNA H: repasse a categoria pro responder:
#         return responder(body.pergunta, colecao, categoria=body.categoria)
@app.post("/perguntar", response_model=Resposta)
def perguntar(body: Pergunta):
    return responder(body.pergunta, colecao, categoria=body.categoria)
