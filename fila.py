# =====================================================================
# fila.py — a fila de revisão humana (Dia 39)
# =====================================================================
# Python puro (JSON em disco), testável sem Docker.
#
# ONDE a fila mora: dentro da pasta do banco (PASTA_DB), que no Docker é o
# VOLUME montado com -v. Assim a fila sobrevive ao container reiniciar, igual
# ao índice. Se ficasse em /app solto, cada restart apagaria os pedidos pendentes.

import os
import json

PASTA_DB = os.getenv("PASTA_DB", "chroma_db")
ARQUIVO_FILA = os.getenv("ARQUIVO_FILA", os.path.join(PASTA_DB, "fila_revisao.json"))


# PRONTO — ler a fila inteira (usada pela rota GET /fila e pelos testes)
def ler_fila():
    if not os.path.exists(ARQUIVO_FILA):
        return []
    with open(ARQUIVO_FILA, encoding="utf-8") as f:
        return json.load(f)


# =====================================================================
# LACUNA K — enfileirar, aprovar   [COLE do dia39_human_in_the_loop.py, com 1 linha a mais]
# =====================================================================
# Cole as duas como escreveu. ÚNICA adição, no enfileirar, antes do 2º `with open`
# (o de gravar): garantir que a pasta existe — na 1ª pergunta o Chroma ainda pode
# não ter criado a pasta, e o open("w") não cria pasta sozinho:
#   os.makedirs(os.path.dirname(ARQUIVO_FILA) or ".", exist_ok=True)
# (exist_ok=True = "se já existe, tudo bem, não reclama".)
# --- seu código aqui ---

def enfileirar(pergunta, rascunho, fontes, score):
    fila = []
    if os.path.exists(ARQUIVO_FILA):    
        with open(ARQUIVO_FILA, encoding="utf-8") as f:
            fila = json.load(f)
    novo_id = len(fila) + 1
    fila.append({"id": novo_id, "pergunta": pergunta, "rascunho": rascunho,
                 "fontes": fontes, "score": round(score, 2), "status": "pendente"})
    os.makedirs(os.path.dirname(ARQUIVO_FILA) or ".", exist_ok=True)
    with open(ARQUIVO_FILA, "w", encoding="utf-8") as f:
        json.dump(fila, f, ensure_ascii=False, indent=2)
    return novo_id    

def aprovar(id_item, resposta_final):
    with open(ARQUIVO_FILA, encoding="utf-8") as f:
        fila = json.load(f)
    for item in fila:
            if item["id"] == id_item:
                item["status"] = "aprovado"
                item["resposta_final"] = resposta_final
                with open(ARQUIVO_FILA, "w", encoding="utf-8") as f:
                    json.dump(fila, f, ensure_ascii=False, indent=2)
                return True     
    return False 