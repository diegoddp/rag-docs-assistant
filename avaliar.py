# =====================================================================
# avaliar.py — mede a qualidade da BUSCA contra um gabarito (Dia 34)
# =====================================================================
# Roda no Docker (usa o Chroma). A pasta inteira montada, pra usar o código atual:
#   docker run --rm -v "${PWD}:/app" rag-docs python avaliar.py
#   docker run --rm -v "${PWD}:/app" -e USAR_MOCK=false -e OPENAI_API_KEY=$env:OPENAI_API_KEY rag-docs python avaliar.py
# Imprime acerto@1 / acerto@3 e salva avaliacao_<modo>.json. Os números vão pro README.

import json
import logging
from rag_lib import (carregar_documentos, chunkar_documentos, criar_colecao, indexar_chroma,
                     buscar_chroma, filtrar_por_score, remover_repetidos,
                     USAR_MOCK, SCORE_MINIMO, TOP_FINAL)

MODO = "mock" if USAR_MOCK else "real"
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

# Gabarito: pergunta como o usuário faria + o ARQUIVO que deveria vir em 1º.
# Como agora indexamos pedaços ("suporte/politica_atendimento.md#2"), a
# comparação ignora o "#n": qualquer pedaço do arquivo certo conta como acerto.
GABARITO = [
    {"pergunta": "quero meu dinheiro de volta",                  "esperada": "financeiro/reembolso.md"},
    {"pergunta": "esqueci minha senha, e agora?",                "esperada": "conta/senha.md"},
    {"pergunta": "como deixo minha conta mais segura?",          "esperada": "conta/seguranca.md"},
    {"pergunta": "posso pagar com Pix?",                         "esperada": "financeiro/pagamento.md"},
    {"pergunta": "não quero mais o serviço, como saio?",         "esperada": "financeiro/plano.md"},
    {"pergunta": "vocês atendem no sábado?",                     "esperada": "suporte/suporte.md"},
    {"pergunta": "como baixo uma planilha com meus dados?",      "esperada": "suporte/dados.md"},
    {"pergunta": "em quanto tempo respondem um ticket crítico?", "esperada": "suporte/politica_atendimento.md"},
    {"pergunta": "não gostei da resposta do suporte, e agora?",  "esperada": "suporte/politica_atendimento.md"},
    {"pergunta": "onde mando sugestão de funcionalidade?",       "esperada": "suporte/politica_atendimento.md"},
]


def buscar_funil(pergunta, colecao):
    """A mesma busca que o responder usa (sem o LLM), pra avaliar exatamente o que vai pro contexto."""
    r = buscar_chroma(pergunta, colecao)
    r = filtrar_por_score(r, SCORE_MINIMO)
    r = remover_repetidos(r)
    return r[:TOP_FINAL]


def _arquivo(fonte):
    """'suporte/politica_atendimento.md#2' -> 'suporte/politica_atendimento.md'"""
    return fonte.split("#")[0]


# =====================================================================
# LACUNA I — posicao_da_fonte, avaliar_busca, resumo   [COLE do dia34_qualidade.py]
# =====================================================================
# Três adaptações:
#   - em posicao_da_fonte, compare  _arquivo(r["fonte"]) == esperada   (ignora o #n)
#   - em avaliar_busca, use  buscar_funil(item["pergunta"], indice)  no lugar de buscar(...)
#     e proteja o top1: se a lista vier vazia (funil cortou tudo), top1 = {"fonte": "-", "score": 0.0}
#       top1 = resultados[0] if resultados else {"fonte": "-", "score": 0.0}
#   - resumo: igual
# --- seu código aqui ---
def posicao_da_fonte(resultados, esperada):
    for i, r in enumerate(resultados): 
        if _arquivo(r["fonte"]) == esperada:
            return i + 1  
    return None 

def avaliar_busca(gabarito, indice):
    avaliacoes = []
    for item in gabarito:
        resultados = buscar_funil(item["pergunta"], indice)
        posicao = posicao_da_fonte(resultados, item["esperada"])
        top1 = resultados[0] if resultados else {"fonte": "-", "score": 0.0}
        if posicao == 1:
            logging.info(f"OK    {item['pergunta']!r} -> {top1['fonte']} ({top1['score']:.2f})")
        else:
            logging.warning(f"ERROU {item['pergunta']!r} -> veio {top1['fonte']}, esperava {item['esperada']} (posicao {posicao})")
        avaliacoes.append({"pergunta": item["pergunta"], "esperada": item["esperada"],
                           "veio": top1["fonte"], "posicao": posicao, "score_top1": top1["score"]})
    return avaliacoes    

def resumo(avaliacoes):
    total = len(avaliacoes)
    top1 = 0
    top3 = 0
    for a in avaliacoes:
        if a["posicao"] == 1:
            top1 += 1
        if a["posicao"] is not None: 
            top3 += 1
    return {"modo": MODO, "total": total, "acerto_top1": top1, "acerto_top3": top3,
            "taxa_top1": top1 / total, "taxa_top3": top3 / total}




if __name__ == "__main__":
    colecao = criar_colecao()
    if colecao.count() == 0:
        docs = carregar_documentos()
        indexar_chroma(chunkar_documentos(docs), colecao)
    print(f"=== avaliando a busca em modo {MODO.upper()} ({colecao.count()} pedacos) ===")
    avaliacoes = avaliar_busca(GABARITO, colecao)
    r = resumo(avaliacoes)
    print()
    print(f"acerto@1: {r['acerto_top1']}/{r['total']}  ({r['taxa_top1']:.0%})")
    print(f"acerto@3: {r['acerto_top3']}/{r['total']}  ({r['taxa_top3']:.0%})")
    with open(f"avaliacao_{MODO}.json", "w", encoding="utf-8") as f:
        json.dump({"resumo": r, "detalhes": avaliacoes}, f, ensure_ascii=False, indent=2)
    print(f"salvo em avaliacao_{MODO}.json")
