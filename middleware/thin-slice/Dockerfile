FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install stripe psycopg2-binary --no-cache-dir --upgrade -r requirements.txt

COPY main.py .

COPY index.html .

ENV DGF_DEBUG=0

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
