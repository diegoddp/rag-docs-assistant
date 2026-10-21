# =====================================================================
# rag_lib.py — a LÓGICA do assistente RAG (sem FastAPI aqui)
# =====================================================================
# Fluxo v2 (Semana 7):
#   docs/<categoria>/*.md → carregar_documentos → chunkar_documentos → indexar_chroma → [Chroma]
#   pergunta (+categoria) → buscar_chroma(k=8, where) → filtrar_por_score → remover_repetidos → [:3]
#                         → montar_contexto → chamar_llm → resposta + fontes
#                         (se o funil devolver vazio: "Não encontrei" SEM chamar o LLM)
#
# Regra de ouro: NADA de chromadb no topo (import dentro de criar_colecao).
# Assim os testes rodam no venv local mesmo com o numpy bloqueado.

import os
import math
import logging

USAR_MOCK = os.getenv("USAR_MOCK", "true").lower() == "true"
PASTA_DOCS = os.getenv("PASTA_DOCS", "docs")
PASTA_DB = os.getenv("PASTA_DB", "chroma_db")
# Parâmetros do funil (Dia 32), configuráveis por ambiente:
K_BUSCA = int(os.getenv("K_BUSCA", "8"))               # over-fetch: quantos pedir ao Chroma
SCORE_MINIMO = float(os.getenv("SCORE_MINIMO", "0.3"))  # corte (no mock quase nada cai; no real 0.3 separa bem)
TOP_FINAL = int(os.getenv("TOP_FINAL", "3"))           # quantos vão pro contexto


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
# LACUNA A — def carregar_documentos(pasta=PASTA_DOCS)   [ADAPTE o seu]
# =====================================================================
# Os docs agora ficam em SUBPASTAS, e o nome da subpasta é a CATEGORIA:
#   docs/conta/senha.md  →  {"fonte": "conta/senha.md", "categoria": "conta", "texto": ...}
# A estrutura de pastas vira metadata (Dia 33) sem ninguém digitar etiqueta.
# É um for DENTRO de outro for (Dia 31): o de fora anda nas subpastas, o de
# dentro nos arquivos de cada uma.
# Passos:
#   1. documentos = []
#   2. for categoria in sorted(os.listdir(pasta)):              # "conta", "financeiro", "suporte"
#   3.     caminho_cat = os.path.join(pasta, categoria)
#   4.     if not os.path.isdir(caminho_cat):                   # pula o que não for pasta
#   5.         continue
#   6.     for nome in sorted(os.listdir(caminho_cat)):
#   7.         if not nome.endswith(".md"):
#   8.             continue
#   9.         with open(os.path.join(caminho_cat, nome), encoding="utf-8") as f:
#  10.             texto = f.read()
#  11.         documentos.append({"fonte": f"{categoria}/{nome}", "categoria": categoria, "texto": texto})
#  12. return documentos
# --- seu código aqui (substitua a versão antiga) ---
def carregar_documentos(pasta=PASTA_DOCS):
    documentos = []
    for categoria in sorted(os.listdir(pasta)):
        caminho_cat = os.path.join(pasta, categoria)
        if not os.path.isdir(caminho_cat):
            continue
        for nome in sorted(os.listdir(caminho_cat)):
            if not nome.endswith(".md"):
                continue
            with open(os.path.join(caminho_cat, nome), encoding="utf-8") as f:
                texto = f.read()
            documentos.append({"fonte": f"{categoria}/{nome}", "categoria": categoria, "texto": texto})
    return documentos                


# =====================================================================
# LACUNA B — chunk_por_paragrafo + chunkar_documentos   [COLE do dia31_chunking.py]
# =====================================================================
# Cole as duas como escreveu. UMA adaptação em chunkar_documentos: o dict de
# saída precisa carregar a categoria também (senão o filtro do Dia 33 não
# funciona nos pedaços):
#   saida.append({"fonte": f"{doc['fonte']}#{i}", "categoria": doc["categoria"], "texto": pedaco})
# --- seu código aqui ---
def chunk_por_paragrafo(texto):
    partes = texto.split("\n\n")
    return [p.strip() for p in partes if p.strip()]

def chunkar_documentos(documentos):
    saida = []
    for doc in documentos:
        pedacos = chunk_por_paragrafo(doc["texto"])
        for i, pedaco in enumerate(pedacos):
            saida.append({"fonte": f"{doc['fonte']}#{i}", "categoria": doc["categoria"], "texto": pedaco}
)
    return saida    


# =====================================================================
# PRONTO — criar_colecao (Dia 29) com nome NOVO
# =====================================================================
# Mudamos o que vai no metadata (agora tem categoria) e o que é um "documento"
# (agora é um pedaço). A coleção antiga ("ajuda_mock") tem dados no formato
# velho. Em vez de misturar, criamos uma coleção nova — "ajuda_v2". É o que se
# faz em banco quando o formato muda: migração, não remendo.
def criar_colecao():
    import chromadb
    client = chromadb.PersistentClient(path=PASTA_DB)
    nome = "ajuda_v2_mock" if USAR_MOCK else "ajuda_v2_real"
    return client.get_or_create_collection(name=nome, metadata={"hnsw:space": "cosine"})


# =====================================================================
# LACUNA C — def indexar_chroma(documentos, colecao)   [ADAPTE o seu — é o Ex1 do Dia 33]
# =====================================================================
# Única mudança: o metadata de cada pedaço leva fonte E categoria:
#   metadatas.append({"fonte": doc["fonte"], "categoria": doc["categoria"]})
# --- seu código aqui (substitua a versão antiga) ---
def indexar_chroma(documentos, colecao):
    ids, textos, vetores, metadatas = [], [], [], []
    for i, doc in enumerate(documentos):
        ids.append(f"doc{i}")
        textos.append(doc["texto"])
        vetores.append(embedding(doc["texto"]))
        metadatas.append({"fonte": doc["fonte"], "categoria": doc["categoria"]})
    colecao.add(ids=ids, documents=textos, embeddings=vetores, metadatas=metadatas)


# =====================================================================
# LACUNA D — def buscar_chroma(pergunta, colecao, categoria=None, k=K_BUSCA)   [é o Ex2 do Dia 33]
# =====================================================================
# Mudanças em relação ao seu: (1) parâmetro categoria opcional → where;
# (2) k padrão vira K_BUSCA (over-fetch); (3) o dict de saída leva categoria.
# Passos: iguais ao buscar_filtrado do Dia 33 — pode colar e renomear.
# --- seu código aqui (substitua a versão antiga) ---
def buscar_chroma(pergunta, colecao, categoria=None, k=K_BUSCA):
    filtro = None
    if categoria:
        filtro = {"categoria": categoria}
    res = colecao.query(query_embeddings=[embedding(pergunta)], n_results=k, where=filtro)
    resultados = []
    for texto, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        resultados.append({"fonte": meta["fonte"], "categoria": meta["categoria"], "texto": texto, "score": 1 - dist})
    return resultados

# =====================================================================
# LACUNA E — filtrar_por_score + remover_repetidos   [COLE do dia32_retrieval.py, sem mudar]
# =====================================================================
# --- seu código aqui ---
def filtrar_por_score(resultados, minimo=0.3):
    return [r for r in resultados if r["score"] >= minimo]

def remover_repetidos(resultados):
    vistos = []
    saida = []
    for r in resultados:
        if r["texto"] not in vistos:
            vistos.append(r["texto"])
            saida.append(r)
    return saida


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
# LACUNA F — def responder(pergunta, colecao, categoria=None)   [ADAPTE o seu — é o funil do Dia 32]
# =====================================================================
# Mudanças em relação ao seu responder:
#   1. resultados = buscar_chroma(pergunta, colecao, categoria=categoria)   # k já é K_BUSCA
#   2. resultados = filtrar_por_score(resultados, SCORE_MINIMO)
#   3. resultados = remover_repetidos(resultados)
#   4. resultados = resultados[:TOP_FINAL]
#   5. if not resultados:                                                   # funil vazio → não chama o LLM
#   6.     logging.warning(f"sem contexto para {pergunta!r}")
#   7.     return {"resposta": "Não encontrei essa informação.", "fontes": []}
#   8. ...daqui pra baixo igual ao seu (contexto, messages, chamar_llm, fontes, return)
# --- seu código aqui (substitua a versão antiga) ---
def responder(pergunta, colecao, categoria=None):
    resultados = buscar_chroma(pergunta, colecao, categoria=categoria)
    resultados = filtrar_por_score(resultados, SCORE_MINIMO)
    resultados = remover_repetidos(resultados)
    resultados = resultados[:TOP_FINAL]
    if not resultados:
        logging.warning(f"sem contexto para {pergunta!r}")
        return {"resposta": "Não encontrei essa informação.", "fontes": []}
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


# #####################################################################
# v3 — DIA 40: guardrails + rotas (automático / revisão / recusa)
# #####################################################################
# O main.py passa a chamar `atender` em vez de `responder`. O responder acima
# continua aí (não apague — ele documenta a v2), mas ninguém chama mais ele.
#
#   pergunta → [checar_entrada] → funil → [decidir_rota] → recusa
#                                                        → automático (LLM responde)
#                                                        → revisão (LLM rascunha → fila → humano aprova)

from guardrails import checar_entrada
from fila import enfileirar

# Mock e real têm escalas de score diferentes (Dia 32/39) — padrão diferente por modo.
LIMIAR_AUTO = float(os.getenv("LIMIAR_AUTO", "0.89" if USAR_MOCK else "0.55"))


# ─────────────────────────────────────────────
# PRONTO — o funil e o caminho feliz do seu responder, separados em 2 peças
# (é o mesmo código do seu responder, só que reutilizável por atender e pelo avaliar_respostas)
# ─────────────────────────────────────────────
def funil(pergunta, colecao, categoria=None):
    resultados = buscar_chroma(pergunta, colecao, categoria=categoria)
    resultados = filtrar_por_score(resultados, SCORE_MINIMO)
    resultados = remover_repetidos(resultados)
    return resultados[:TOP_FINAL]


def gerar_resposta(pergunta, resultados):
    """Devolve DUAS coisas (tupla, Dia 36): o texto da resposta e a lista de fontes sem repetição."""
    contexto = montar_contexto(resultados)
    messages = [{"role": "system", "content": SISTEMA},
                {"role": "user", "content": f"Contexto:\n{contexto}\n\nPergunta: {pergunta}"}]
    resposta = chamar_llm(messages)
    fontes = []
    for r in resultados:
        if r["fonte"] not in fontes:
            fontes.append(r["fonte"])
    return resposta, fontes


# =====================================================================
# LACUNA L — def decidir_rota(resultados)   [COLE do dia39_human_in_the_loop.py, SEM mudar]
# =====================================================================
# --- seu código aqui ---
def decidir_rota(resultados):
    if not resultados:
        return "recusa"
    if resultados[0]["score"] >= LIMIAR_AUTO:
        return "automatico"
    return "revisao"


# =====================================================================
# LACUNA M — def atender(pergunta, colecao, categoria=None)   [NOVO — junta os Dias 38 e 39]
# =====================================================================
# Devolve SEMPRE um dict com 3 chaves: "resposta", "fontes", "rota".
# Passos (um por linha — escreva todos, na ordem):
#   1. entrada = checar_entrada(pergunta)
#   2. if not entrada["permitido"]:
#   3.     return {"resposta": "Não posso processar essa pergunta.", "fontes": [], "rota": "bloqueado"}
#   4. pergunta = entrada["pergunta_limpa"]                       # daqui pra frente, SÓ a versão sem PII
#   5. resultados = funil(pergunta, colecao, categoria=categoria)
#   6. rota = decidir_rota(resultados)
#   7. if rota == "recusa":
#   8.     return {"resposta": "Não encontrei essa informação.", "fontes": [], "rota": rota}
#   9. resposta, fontes = gerar_resposta(pergunta, resultados)    # desempacota a tupla
#  10. if rota == "automatico":
#  11.     return {"resposta": resposta, "fontes": fontes, "rota": rota}
#  12. id_fila = enfileirar(pergunta, resposta, fontes, resultados[0]["score"])
#  13. logging.info(f"enviado pra revisao: #{id_fila} score={resultados[0]['score']:.2f}")
#  14. return {"resposta": f"Sua pergunta foi encaminhada a um especialista. Protocolo #{id_fila}.",
#              "fontes": [], "rota": rota}
# Confira no fim: são QUATRO returns, um por rota (bloqueado, recusa, automatico, revisao).
# --- seu código aqui ---
def atender(pergunta, colecao, categoria=None):
    entrada = checar_entrada(pergunta)
    if not entrada["permitido"]:
        return {"resposta": "Não posso processar essa pergunta.", "fontes": [], "rota": "bloqueado"}
    pergunta = entrada["pergunta_limpa"]
    resultados = funil(pergunta, colecao, categoria=categoria)
    rota = decidir_rota(resultados)
    if rota == "recusa":
        return {"resposta": "Não encontrei essa informação.", "fontes": [], "rota": rota}
    resposta, fontes = gerar_resposta(pergunta, resultados)
    if rota == "automatico":
        return {"resposta": resposta, "fontes": fontes, "rota": rota}
    id_fila = enfileirar(pergunta, resposta, fontes, resultados[0]["score"])
    logging.info(f"enviado pra revisao: #{id_fila} score={resultados[0]['score']:.2f}")
    return {"resposta": f"Sua pergunta foi encaminhada a um especialista. Protocolo #{id_fila}.",
            "fontes": [], "rota": rota}

