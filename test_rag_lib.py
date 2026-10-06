# =====================================================================
# test_rag_lib.py — testes da lógica (rodam em MOCK, sem Docker, sem custo)
# =====================================================================
# Rodar no venv da RAIZ (python-estudos/.venv, que tem pytest):
#   python -m pytest -v
# Estes testes NÃO tocam no Chroma (por isso rodam no seu PC mesmo com o
# numpy bloqueado). Testam as peças puras: ler arquivos e montar contexto.

from rag_lib import carregar_documentos, montar_contexto


# EXEMPLO PRONTO — a pasta docs/ tem 7 arquivos .md
def test_carrega_todos_os_docs():
    docs = carregar_documentos("docs")                 # Act
    assert len(docs) == 7                              # Assert
    assert docs[0]["fonte"].endswith(".md")
    assert "texto" in docs[0]


# EXEMPLO PRONTO — montar_contexto põe a fonte entre parênteses, um por linha
def test_montar_contexto_formato():
    resultados = [
        {"fonte": "a.md", "texto": "primeiro", "score": 0.9},
        {"fonte": "b.md", "texto": "segundo", "score": 0.8},
    ]
    contexto = montar_contexto(resultados)
    assert contexto == "(a.md) primeiro\n(b.md) segundo"


# EXERCÍCIO — escreva 1 teste:  def test_ignora_arquivos_que_nao_sao_md()
#   Ideia: criar uma pasta temporária com 1 arquivo .md e 1 arquivo .txt,
#   chamar carregar_documentos nela e afirmar que só veio 1 documento.
#   O pytest te EMPRESTA uma pasta temporária se a função de teste receber
#   um parâmetro chamado  tmp_path  (é um recurso dele — "fixture").
#   Passos:
#     1. def test_ignora_arquivos_que_nao_sao_md(tmp_path):
#     2.     (tmp_path / "um.md").write_text("conteudo md", encoding="utf-8")
#     3.     (tmp_path / "dois.txt").write_text("conteudo txt", encoding="utf-8")
#     4.     docs = carregar_documentos(tmp_path)
#     5.     assert len(docs) == 1
#     6.     assert docs[0]["fonte"] == "um.md"
# --- seu código aqui ---
def test_ignora_arquivos_que_nao_sao_md(tmp_path):
    (tmp_path / "um.md").write_text("conteudo md", encoding="utf-8")      # Arrange
    (tmp_path / "dois.txt").write_text("conteudo txt", encoding="utf-8")
    docs = carregar_documentos(tmp_path)                                  # Act
    assert len(docs) == 1                                                 # Assert
    assert docs[0]["fonte"] == "um.md"
