# =====================================================================
# metricas.py — o que a API expõe pro Prometheus (Dia 42)
# =====================================================================
# Python puro (prometheus_client): roda e testa no seu PC, sem Docker.
# Separado do main.py pelo mesmo motivo do guardrails.py: lógica testável
# longe do FastAPI e do Chroma.

from prometheus_client import Counter, Gauge, Histogram
from fila import ler_fila

# =====================================================================
# LACUNA Q — declarar PERGUNTAS e LATENCIA   [ADAPTE o Dia 41 — 1 mudança só]
# =====================================================================
# PERGUNTAS: igual ao Dia 41, cole sem mudar.
# LATENCIA: igual ao Dia 41 COM UMA MUDANÇA — ganha o label rota, porque
#   "bloqueado" leva 5 ms e "automatico" leva 2 s: misturar os dois num só
#   histograma esconde quem está lento. O label entra como 3º argumento, igual
#   ao do Counter. Linha-alvo completa:
#     LATENCIA = Histogram("rag_latencia_segundos", "Tempo para atender uma pergunta",
#                          ["rota"], buckets=[0.05, 0.5, 1, 2, 3, 5])
# (O FILA do Dia 41 NÃO vem: ele está pronto lá embaixo, de um jeito diferente.)
# --- seu código aqui ---
PERGUNTAS = Counter("rag_perguntas_total", "Perguntas recebidas, por rota", ["rota"])
LATENCIA = Histogram("rag_latencia_segundos", "Tempo para atender uma pergunta",
                     ["rota"], buckets=[0.05, 0.5, 1, 2, 3, 5])


# ─────────────────────────────────────────────
# PRONTO — a fila como Gauge "calculado na hora da leitura"
# ─────────────────────────────────────────────
# No Dia 41 você fazia FILA.inc() e FILA.dec() na mão. Aqui seria frágil: se o
# container reinicia, o Gauge volta pra 0 mas a fila no disco (volume) continua
# com itens pendentes — o número mentiria. set_function diz ao Gauge: "não guarde
# valor; toda vez que o Prometheus perguntar, chame esta função e devolva o que
# ela der". A FONTE DA VERDADE continua sendo o arquivo da fila.
FILA = Gauge("rag_fila_pendentes", "Itens pendentes na fila de revisao humana")
FILA.set_function(lambda: sum(1 for item in ler_fila() if item["status"] == "pendente"))


# =====================================================================
# LACUNA R — def registrar_pergunta(rota, segundos)   [ADAPTE o registrar do Dia 41]
# =====================================================================
# Duas mudanças em relação ao seu registrar:
#   1. LATENCIA agora tem label → LATENCIA.labels(rota=rota).observe(segundos)
#   2. as 2 linhas do FILA.inc() SAEM (a fila se calcula sozinha, veja acima)
# Fica com 2 linhas de corpo.
# --- seu código aqui ---
def registrar_pergunta(rota, segundos):
    PERGUNTAS.labels(rota=rota).inc()
    LATENCIA.labels(rota=rota).observe(segundos)
