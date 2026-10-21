# =====================================================================
# main.py — RAG Docs Assistant API (FastAPI)  — v3
# =====================================================================
# Roda SÓ no Docker (chromadb/numpy bloqueados no host). Veja o README.
#   docker build -t rag-docs .
#   docker run --rm -p 8000:8000 -v "${PWD}/chroma_db:/app/chroma_db" rag-docs
#   -> http://127.0.0.1:8000/docs

import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rag_lib import carregar_documentos, chunkar_documentos, criar_colecao, indexar_chroma, atender, USAR_MOCK
from fila import ler_fila, aprovar

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

app = FastAPI(title="RAG Docs Assistant", version="3.0")

# Ao subir: abre o banco e indexa (com chunking) SE estiver vazio.
colecao = criar_colecao()
if colecao.count() == 0:
    documentos = carregar_documentos()
    pedacos = chunkar_documentos(documentos)
    indexar_chroma(pedacos, colecao)
    logging.info(f"indexados {len(documentos)} documentos em {len(pedacos)} pedacos")
else:
    logging.info(f"banco ja tem {colecao.count()} pedacos")


# moldes — o que ENTRA e o que SAI
class Pergunta(BaseModel):
    pergunta: str
    categoria: str | None = None


# >>> LACUNA N1: o atender devolve 3 chaves agora. Acrescente ao molde Resposta:
#         rota: str
#     (sem isso, o response_model DESCARTA a chave rota da resposta — ele só deixa
#      sair o que está no molde. É a validação de SAÍDA do Dia 24.)
class Resposta(BaseModel):
    resposta: str
    fontes: list[str]
    rota: str


class Aprovacao(BaseModel):
    resposta_final: str


@app.get("/")
def raiz():
    modo = "mock" if USAR_MOCK else "IA real"
    pendentes = sum(1 for item in ler_fila() if item["status"] == "pendente")
    return {"api": "RAG Docs Assistant", "modo": modo, "pedacos": colecao.count(),
            "fila_pendentes": pendentes, "docs": "/docs"}


# >>> LACUNA N2: troque  responder  por  atender  na chamada abaixo (e no import lá em
#     cima ele já está trocado). Mesmos argumentos.
@app.post("/perguntar", response_model=Resposta)
def perguntar(body: Pergunta):
    return atender(body.pergunta, colecao, categoria=body.categoria)


# PRONTO — o atendente consulta a fila
@app.get("/fila")
def listar_fila(status: str | None = None):            # query param opcional (Dia 17): /fila?status=pendente
    itens = ler_fila()
    if status:
        itens = [i for i in itens if i["status"] == status]
    return itens


# >>> LACUNA N3: a rota do HUMANO aprovar um item da fila. CRUD do Dia 19 + path param do Dia 17.
#     - decorador:  @app.post("/fila/{id_item}/aprovar")
#     - função:     def aprovar_item(id_item: int, body: Aprovacao)
#     - corpo (3 linhas):
#           if not aprovar(id_item, body.resposta_final):
#               raise HTTPException(status_code=404, detail="item nao encontrado")
#           return {"id": id_item, "status": "aprovado"}
#     (raise HTTPException = o jeito do FastAPI de responder com erro HTTP de verdade —
#      o 404 do Dia 9 visto do lado do SERVIDOR. Nome da função ≠ aprovar, senão
#      a rota sobrescreve a função importada da fila — Dia 24.)
# --- seu código aqui ---
@app.post("/fila/{id_item}/aprovar")
def aprovar_item(id_item: int, body: Aprovacao):
    if not aprovar(id_item, body.resposta_final):
        raise HTTPException(status_code=404, detail="item nao encontrado")
    return {"id": id_item, "status": "aprovado"}