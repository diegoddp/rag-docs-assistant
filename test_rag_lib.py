# =====================================================================
# test_rag_lib.py — testes da lógica (rodam em MOCK, sem Docker, sem custo)
# =====================================================================
# Rodar no venv da RAIZ (python-estudos/.venv, que tem pytest):
#   python -m pytest -v
# Estes testes NÃO tocam no Chroma. Testam as peças puras: ler arquivos,
# chunking, filtros e montar contexto.

from rag_lib import (carregar_documentos, chunk_por_paragrafo, chunkar_documentos,
                     filtrar_por_score, remover_repetidos, montar_contexto)


# PRONTO (atualizado pra v2) — docs/ tem 3 subpastas e 8 arquivos .md
def test_carrega_todos_os_docs_com_categoria():
    docs = carregar_documentos("docs")
    assert len(docs) == 8
    assert docs[0]["fonte"] == "conta/seguranca.md"      # sorted: "conta" < "financeiro" < "suporte"
    assert docs[0]["categoria"] == "conta"
    assert "texto" in docs[0]


# PRONTO (atualizado pra v2) — ignora arquivos que não são .md dentro da subpasta
def test_ignora_arquivos_que_nao_sao_md(tmp_path):
    (tmp_path / "geral").mkdir()
    (tmp_path / "geral" / "um.md").write_text("conteudo md", encoding="utf-8")
    (tmp_path / "geral" / "dois.txt").write_text("conteudo txt", encoding="utf-8")
    docs = carregar_documentos(tmp_path)
    assert len(docs) == 1
    assert docs[0]["fonte"] == "geral/um.md"


# PRONTO
def test_montar_contexto_formato():
    resultados = [
        {"fonte": "a.md", "texto": "primeiro", "score": 0.9},
        {"fonte": "b.md", "texto": "segundo", "score": 0.8},
    ]
    assert montar_contexto(resultados) == "(a.md) primeiro\n(b.md) segundo"


# PRONTO — o funil (Dia 32)
def test_filtrar_e_remover_repetidos():
    resultados = [
        {"fonte": "a.md#0", "texto": "x", "score": 0.9},
        {"fonte": "a.md#0", "texto": "x", "score": 0.9},     # repetido
        {"fonte": "b.md#0", "texto": "y", "score": 0.1},     # score baixo
    ]
    assert len(filtrar_por_score(resultados, 0.3)) == 2
    assert len(remover_repetidos(resultados)) == 2
    assert len(remover_repetidos(filtrar_por_score(resultados, 0.3))) == 1


# EXERCÍCIO — escreva 1 teste:  def test_chunk_por_paragrafo_separa_e_limpa()
#   Passos:
#     1. texto = "primeiro parágrafo\n\n  segundo parágrafo  \n\n\n"
#     2. pedacos = chunk_por_paragrafo(texto)
#     3. assert pedacos == ["primeiro parágrafo", "segundo parágrafo"]    # 2 pedaços, sem espaços nas pontas, sem vazio no fim
# --- seu código aqui ---
def test_chunk_por_paragrafo_separa_e_limpa():
    texto = "primeiro parágrafo\n\n  segundo parágrafo  \n\n\n"
    pedacos = chunk_por_paragrafo(texto)
    assert pedacos == ["primeiro parágrafo", "segundo parágrafo"] 
    


# EXERCÍCIO — escreva 1 teste:  def test_chunkar_documentos_mantem_categoria()
#   Passos:
#     1. docs = [{"fonte": "s/p.md", "categoria": "s", "texto": "a\n\nb"}]
#     2. pedacos = chunkar_documentos(docs)
#     3. assert len(pedacos) == 2
#     4. assert pedacos[0]["fonte"] == "s/p.md#0"
#     5. assert pedacos[1]["categoria"] == "s"
# --- seu código aqui ---
def test_chunkar_documentos_mantem_categoria():
    docs = [{"fonte": "s/p.md", "categoria": "s", "texto": "a\n\nb"}]
    pedacos = chunkar_documentos(docs)
    assert len(pedacos) == 2
    assert pedacos[0]["fonte"] == "s/p.md#0"
    assert pedacos[1]["categoria"] == "s"
