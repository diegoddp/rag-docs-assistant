# =====================================================================
# avaliar_respostas.py — mede a qualidade da RESPOSTA: rubrica + juiz (Dias 36-37)
# =====================================================================
# Complementa o avaliar.py (que mede a BUSCA). Roda no Docker (usa o Chroma):
#   docker run --rm -v "${PWD}:/app" rag-docs python avaliar_respostas.py
#   docker run --rm -v "${PWD}:/app" -e USAR_MOCK=false -e OPENAI_API_KEY=$env:OPENAI_API_KEY rag-docs python avaliar_respostas.py
#
# Avalia o caminho funil → LLM direto (sem a fila de revisão), porque queremos
# medir a qualidade do que a IA ESCREVERIA — inclusive nas perguntas que, em
# produção, iriam pra revisão humana.

import json
import logging
from rag_lib import (carregar_documentos, chunkar_documentos, criar_colecao, indexar_chroma,
                     funil, gerar_resposta, USAR_MOCK)

MODO = "mock" if USAR_MOCK else "real"
logging.basicConfig(level=logging.INFO, format="%(levelname)-7s %(message)s")

GABARITO = [
    {"pergunta": "quanto tempo demora o reembolso?",           "fatos": ["7 dias"],     "fonte": "financeiro/reembolso.md", "recusa": False},
    {"pergunta": "posso pagar com Pix?",                       "fatos": ["Pix"],        "fonte": "financeiro/pagamento.md", "recusa": False},
    {"pergunta": "que horas o suporte abre?",                  "fatos": ["9h"],         "fonte": "suporte/suporte.md",      "recusa": False},
    {"pergunta": "onde ativo a autenticação em dois fatores?", "fatos": ["Segurança"],  "fonte": "conta/seguranca.md",      "recusa": False},
    {"pergunta": "em quanto tempo respondem um ticket crítico?", "fatos": ["1 hora"],   "fonte": "suporte/politica_atendimento.md", "recusa": False},
    {"pergunta": "qual é a capital da França?",                "fatos": [],             "fonte": None,                      "recusa": True},
    {"pergunta": "vocês vendem passagens aéreas?",             "fatos": [],             "fonte": None,                      "recusa": True},
]


def _arquivo(fonte):
    return fonte.split("#")[0] if fonte else fonte


def responder_para_eval(pergunta, colecao):
    """funil → (recusa | LLM). Devolve resposta, fontes (só o arquivo, sem #n) e o contexto pro juiz."""
    resultados = funil(pergunta, colecao)
    if not resultados:
        return {"resposta": "Não encontrei essa informação.", "fontes": [], "contexto": ""}
    resposta, fontes = gerar_resposta(pergunta, resultados)
    contexto = "\n".join(f"({r['fonte']}) {r['texto']}" for r in resultados)
    return {"resposta": resposta, "fontes": [_arquivo(f) for f in fontes], "contexto": contexto}


# ─────────────────────────────────────────────
# PRONTO — o juiz (Dia 37), JÁ CALIBRADO com a regra de recusa (a pendência do Dia 37)
# ─────────────────────────────────────────────
JUIZ_SISTEMA = (
    "Você é um avaliador rigoroso de respostas de um assistente de suporte. "
    "Você recebe a PERGUNTA do usuário, o CONTEXTO (trechos de documentação) que o "
    "assistente tinha disponível e a RESPOSTA que ele deu. Avalie e responda em JSON. "
    "REGRA: quando o contexto não contém a resposta, dizer 'Não encontrei essa informação' "
    "é a resposta CORRETA e merece nota 5. Só penalize recusa quando o contexto continha a resposta."
)


def chamar_juiz(prompt):
    if USAR_MOCK:
        recusou = "não encontrei" in prompt.lower().split("resposta:")[-1]
        return json.dumps({"correta": not recusou, "aterrada": not recusou, "nota": 2 if recusou else 4,
                           "motivo": "[MOCK] veredito fixo de teste"}, ensure_ascii=False)
    from openai import OpenAI
    r = OpenAI().chat.completions.create(
        model="gpt-4o-mini", temperature=0, response_format={"type": "json_object"},
        messages=[{"role": "system", "content": JUIZ_SISTEMA}, {"role": "user", "content": prompt}])
    return r.choices[0].message.content


# =====================================================================
# LACUNA P — fatos_faltando e avaliar_item (Dia 36), montar_prompt_juiz e julgar (Dia 37)   [COLE, SEM mudar]
# =====================================================================
# As QUATRO como você escreveu (o avaliar_item chama o fatos_faltando, então ele vem junto).
# (chamar_juiz e JUIZ_SISTEMA já estão acima.)
# --- seu código aqui ---
def fatos_faltando(resposta, fatos):
    return [f for f in fatos if f.lower() not in resposta.lower()]
def avaliar_item(item, saida):
    resposta = saida["resposta"]
    recusou = "não encontrei" in resposta.lower()
    faltando = fatos_faltando(resposta, item["fatos"]) 
    fonte_ok = item["fonte"] in saida["fontes"]
    if item["recusa"]:
        aprovado = recusou
    else:
        aprovado = (not recusou) and (not faltando) and fonte_ok   
    return {"pergunta": item["pergunta"], "aprovado": aprovado, "recusou": recusou,
            "fatos_faltando": faltando, "fonte_ok": fonte_ok, "resposta": resposta[:80]}

def montar_prompt_juiz(pergunta, contexto, resposta):
    return f"""PERGUNTA: {pergunta}

CONTEXTO:
{contexto if contexto else "(vazio — nenhum trecho foi encontrado)"}

RESPOSTA: {resposta}

Avalie a RESPOSTA e devolva um JSON com exatamente estas chaves:
- "correta": true se a resposta responde corretamente à pergunta com base no contexto (ou recusa corretamente quando o contexto não cobre a pergunta); false caso contrário
- "aterrada": true se tudo que a resposta afirma está no contexto (nada inventado); false se inventou algo
- "nota": inteiro de 1 a 5
- "motivo": uma frase curta explicando a nota"""

def julgar(pergunta, contexto, resposta):
    prompt = montar_prompt_juiz(pergunta, contexto, resposta)
    texto = chamar_juiz(prompt)        
    try:
        dados = json.loads(texto)
    except json.JSONDecodeError:
        logging.error(f"juiz devolveu JSON invalido: {texto[:80]}")
        return {"correta": False, "aterrada": False, "nota": 0, "motivo": "JSON invalido"}
    for chave in ["correta", "aterrada", "nota", "motivo"]:
        if chave not in dados:
            logging.error(f"juiz esqueceu a chave {chave}")
            return {"correta": False, "aterrada": False, "nota": 0, "motivo": f"faltou {chave}"}
    return dados   

if __name__ == "__main__":
    colecao = criar_colecao()
    if colecao.count() == 0:
        indexar_chroma(chunkar_documentos(carregar_documentos()), colecao)
    print(f"=== evals de RESPOSTA em modo {MODO.upper()} ===")
    linhas = []
    for item in GABARITO:
        saida = responder_para_eval(item["pergunta"], colecao)
        rubrica = avaliar_item(item, saida)
        veredito = julgar(item["pergunta"], saida["contexto"], saida["resposta"])
        juiz_aprova = veredito["correta"] and veredito["nota"] >= 4
        concordam = rubrica["aprovado"] == juiz_aprova
        nivel = logging.info if concordam else logging.warning
        nivel(f"{'OK ' if concordam else 'DIV'} rubrica={rubrica['aprovado']} juiz={juiz_aprova} nota={veredito['nota']} | {item['pergunta']!r}")
        linhas.append({"pergunta": item["pergunta"], "rubrica": rubrica["aprovado"], "juiz": juiz_aprova,
                       "nota": veredito["nota"], "motivo": veredito["motivo"], "resposta": saida["resposta"][:120]})
    n = len(linhas)
    print()
    print(f"rubrica aprovou: {sum(l['rubrica'] for l in linhas)}/{n}")
    print(f"juiz aprovou   : {sum(l['juiz'] for l in linhas)}/{n}")
    print(f"concordam      : {sum(l['rubrica'] == l['juiz'] for l in linhas)}/{n}")
    print(f"nota media juiz: {sum(l['nota'] for l in linhas) / n:.1f}")
    with open(f"avaliacao_respostas_{MODO}.json", "w", encoding="utf-8") as f:
        json.dump(linhas, f, ensure_ascii=False, indent=2)
    print(f"salvo em avaliacao_respostas_{MODO}.json")
