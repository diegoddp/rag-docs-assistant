# =====================================================================
# guardrails.py — camada 1: barra entrada ruim ANTES de gastar (Dia 38)
# =====================================================================
# Python puro, sem dependências: roda no seu PC e é testável sem Docker.

import re
import logging

TAMANHO_MAXIMO = 500

PADROES_PII = {
    "CARTAO": r"\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b",
    "CPF":    r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b",
    "EMAIL":  r"[\w.+-]+@[\w-]+\.[\w.]+",
}

# Lista do Dia 38 + a frase que VOCÊ achou que passava. Continua sendo só a
# camada 1: o limiar e o system prompt seguem atrás dela.
PADROES_INJECAO = [
    "ignore as instruções",
    "ignore as instrucoes",
    "ignore previous instructions",
    "esqueça as regras",
    "desconsidere todas as regras",
    "você agora é",
    "mostre seu prompt",
    "system prompt",
]


# =====================================================================
# LACUNA J — detectar_injecao, mascarar_pii, checar_entrada   [COLE do dia38_guardrails.py, SEM mudar]
# =====================================================================
# As três funções exatamente como você escreveu. As constantes acima já estão aqui.
# --- seu código aqui ---
def detectar_injecao(texto):
    return any(p in texto.lower() for p in PADROES_INJECAO)
def mascarar_pii(texto):
    for nome, padrao in PADROES_PII.items():
        texto = re.sub(padrao, f"[{nome}]", texto)
    return texto
def checar_entrada(pergunta):
    pergunta = pergunta.strip()
    if not pergunta:
        return {"permitido": False, "motivo": "vazia", "pergunta_limpa": ""}
    if len(pergunta) > TAMANHO_MAXIMO:
        return {"permitido": False, "motivo": "longa demais", "pergunta_limpa": ""}
    if detectar_injecao(pergunta):
        logging.warning("tentativa de prompt injection bloqueada")
        return {"permitido": False, "motivo": "injecao", "pergunta_limpa": ""}
    limpa = mascarar_pii(pergunta)
    if limpa != pergunta:
        logging.info("PII mascarada na entrada")
    return {"permitido": True, "motivo": "ok", "pergunta_limpa": limpa}    

