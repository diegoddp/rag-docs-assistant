FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# A chave da OpenAI NAO vai na imagem. Entra em tempo de execucao com -e.
# O banco de vetores (chroma_db/) persiste fora do container com -v.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
