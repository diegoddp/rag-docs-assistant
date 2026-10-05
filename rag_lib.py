# =====================================================================
# rag_lib.py — a LÓGICA do assistente RAG (sem FastAPI aqui)
# =====================================================================
# Fluxo:  docs/*.md  →  carregar_documentos  →  indexar_chroma  →  [Chroma]
#         pergunta   →  buscar_chroma  →  montar_contexto  →  chamar_llm  →  resposta + fontes
#
# Regra de ouro deste arquivo: NADA de chromadb no topo. O import fica
# DENTRO de criar_colecao. Motivo: o chromadb puxa numpy, que o ThreatLocker
# bloqueia no seu PC. Com o import lá dentro, os testes e o resto da lib
# rodam no venv local; só a parte do banco exige o Docker.

import os
import math
import logging

USAR_MOCK = os.getenv("USAR_MOCK", "true").lower() == "true"
PASTA_DOCS = os.getenv("PASTA_DOCS", "docs")
PASTA_DB = os.getenv("PASTA_DB", "chroma_db")


# ─────────────────────────────────────────────
# PRONTO — embedding (Dia 26)
# ─────────────────────────────────────────────
def _embedding_mock(texto):
    texto = texto.lower()
    vetor = [0.0] * 26
    for ch in texto:
        if "a" <= ch <= "z":
            vetor[ord(ch) - ord("a")] += 1
    total = sum(vetor) or 1
    return [v / total for v in vetor]


def _embedding_real(texto):
    from openai import OpenAI
    return OpenAI().embeddings.create(model="text-embedding-3-small", input=texto).data[0].embedding


def embedding(texto):
    return _embedding_mock(texto) if USAR_MOCK else _embedding_real(texto)


# =====================================================================
# LACUNA 1 — def carregar_documentos(pasta=PASTA_DOCS)   [NOVO — você escreve]
# =====================================================================
# Papel: ler TODOS os arquivos .md da pasta e devolver a lista de dicts
# {"fonte": nome_do_arquivo, "texto": conteudo} — o mesmo formato do
# DOCUMENTOS fixo dos Dias 28/29, só que agora vindo do disco (Dia 6).
# Passos:
#   1. documentos = []
#   2. for nome in sorted(os.listdir(pasta)):         # os.listdir = lista os nomes dos arquivos da pasta
#   3.     if not nome.endswith(".md"):                # ignora o que não for .md
#   4.         continue                                # continue = pula pro próximo item do for
#   5.     caminho = os.path.join(pasta, nome)         # junta "docs" + "senha.md" → "docs/senha.md"
#   6.     with open(caminho, encoding="utf-8") as f:
#   7.         texto = f.read()
#   8.     documentos.append({"fonte": nome, "texto": texto})
#   9. return documentos
# --- seu código aqui ---
def carregar_documentos(pasta=PASTA_DOCS):
    documentos = []
    for nome in sorted(os.listdir(pasta)):
        if not nome.endswith(".md"):
            continue
        caminho = os.path.join(pasta, nome)
        with open(caminho, encoding="utf-8") as f:
            texto = f.read()
        documentos.append({"fonte": nome, "texto": texto})
    return documentos         

# =====================================================================
# LACUNA 2 — criar_colecao, indexar_chroma, buscar_chroma   [COLE do dia29_chroma.py]
# =====================================================================
# Cole as 3 funções exatamente como você escreveu no Dia 29. Depois faça
# DUAS trocas pequenas em criar_colecao:
#   - o import chromadb fica DENTRO da função (leia a regra de ouro lá no topo)
#   - path="chroma_db"  →  path=PASTA_DB   (a constante lá de cima)
# --- seu código aqui ---
def criar_colecao():
    import chromadb
    client = chromadb.PersistentClient(path=PASTA_DB)
    nome = "ajuda_mock" if USAR_MOCK else "ajuda_real"
    colecao = client.get_or_create_collection(name=nome, metadata={"hnsw:space": "cosine"})
    return colecao

def indexar_chroma(documentos, colecao):
    ids, textos, vetores, fontes = [], [], [], []
    for i, doc in enumerate(documentos):
        ids.append(f"doc{i}")
        textos.append(doc["texto"])
        vetores.append(embedding(doc["texto"]))
        fontes.append({"fonte": doc["fonte"]})   
    colecao.add(ids=ids, documents=textos, embeddings=vetores, metadatas=fontes)


def buscar_chroma(pergunta, colecao, k=3):
    res = colecao.query(query_embeddings=[embedding(pergunta)], n_results=k)
    textos     = res["documents"][0]
    metadatas  = res["metadatas"][0]
    distancias = res["distances"][0]
    resultados = []
    for texto, meta, dist in zip(textos, metadatas, distancias):
        resultados.append({"fonte": meta["fonte"], "texto": texto, "score": 1 - dist})
    return resultados

# ─────────────────────────────────────────────
# PRONTO — LLM e montagem do contexto (Dias 22, 28)
# ─────────────────────────────────────────────
SISTEMA = (
    "Você é um assistente de suporte. Responda à pergunta usando APENAS o "
    "contexto fornecido. Se a resposta não estiver no contexto, diga "
    "'Não encontrei essa informação.' Ao final, cite a fonte entre parênteses."
)


def _chat_mock(messages):
    user = messages[-1]["content"]
    primeira_linha = user.split("\n")[1] if "\n" in user else user
    return f"[MOCK] Com base no contexto: {primeira_linha[:70]}..."


def _chat_real(messages):
    from openai import OpenAI
    r = OpenAI().chat.completions.create(model="gpt-4o-mini", messages=messages)
    return r.choices[0].message.content


def chamar_llm(messages):
    return _chat_mock(messages) if USAR_MOCK else _chat_real(messages)


def montar_contexto(resultados):
    linhas = []
    for r in resultados:
        linhas.append(f"({r['fonte']}) {r['texto']}")
    return "\n".join(linhas)


# =====================================================================
# LACUNA 3 — def responder(pergunta, colecao)   [ADAPTE o do Dia 29]
# =====================================================================
# Diferença pro Dia 29: a API precisa devolver a resposta E a lista de fontes
# consultadas (sem repetir). Então em vez de  return chamar_llm(messages),
# a função devolve um DICT com duas chaves.
# Passos:
#   1. resultados = buscar_chroma(pergunta, colecao)
#   2. contexto = montar_contexto(resultados)
#   3. messages = [...]                                  # igual ao Dia 29
#   4. resposta = chamar_llm(messages)
#   5. fontes = []
#   6. for r in resultados:
#   7.     if r["fonte"] not in fontes:                  # só adiciona se ainda não está na lista
#   8.         fontes.append(r["fonte"])
#   9. logging.info(f"pergunta={pergunta!r} fontes={fontes}")
#  10. return {"resposta": resposta, "fontes": fontes}
# --- seu código aqui ---
def responder(pergunta, colecao):
    resultados = buscar_chroma(pergunta, colecao)
    contexto = montar_contexto(resultados)
    mensagem_user = f"Contexto:\n{contexto}\n\nPergunta: {pergunta}"
    messages = [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": mensagem_user}]
    resposta = chamar_llm(messages)
    fontes = []
    for r in resultados:
        if r["fonte"] not in fontes:
            fontes.append(r["fonte"])
    logging.info(f"pergunta={pergunta!r} fontes={fontes}")
    return {"resposta": resposta, "fontes": fontes}                    
