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
from rag_lib import carregar_documentos, criar_colecao, indexar_chroma, responder, USAR_MOCK

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="RAG Docs Assistant", version="1.0")

# ─────────────────────────────────────────────
# Ao subir a API: abre o banco e indexa SE estiver vazio (padrão do Dia 29).
# Roda uma vez, quando o uvicorn carrega este arquivo.
# ─────────────────────────────────────────────
colecao = criar_colecao()
if colecao.count() == 0:
    documentos = carregar_documentos()
    indexar_chroma(documentos, colecao)
    logging.info(f"indexados {len(documentos)} documentos")
else:
    logging.info(f"banco ja tem {colecao.count()} documentos")


# moldes — o que ENTRA e o que SAI
class Pergunta(BaseModel):
    pergunta: str


class Resposta(BaseModel):
    resposta: str
    fontes: list[str]


@app.get("/")
def raiz():
    modo = "mock" if USAR_MOCK else "IA real"
    return {"api": "RAG Docs Assistant", "modo": modo, "documentos": colecao.count(), "docs": "/docs"}


# ─────────────────────────────────────────────
# >>> ESCREVA AQUI a rota  POST /perguntar
#     - decorador:  @app.post("/perguntar", response_model=Resposta)
#     - função:     def perguntar(body: Pergunta)
#     - corpo:      return responder(body.pergunta, colecao)
#     Repare: responder devolve um DICT com "resposta" e "fontes" — o
#     response_model valida que o dict bate com o molde Resposta (Dia 24).
# ─────────────────────────────────────────────
@app.post("/perguntar", response_model=Resposta)
def perguntar(body: Pergunta):
    return responder(body.pergunta, colecao)