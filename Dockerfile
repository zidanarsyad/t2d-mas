FROM python:3.11-slim
WORKDIR /app
COPY agents/requirements.txt /app/agents/requirements.txt
RUN pip install --no-cache-dir -r /app/agents/requirements.txt
RUN useradd --system --uid 10001 --create-home appuser
COPY agents /app/agents
COPY data/schema.sql /app/data/schema.sql
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["uvicorn", "agents.app:app", "--host", "0.0.0.0", "--port", "8000"]
