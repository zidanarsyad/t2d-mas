FROM python:3.11-slim
WORKDIR /app
COPY agents/requirements.txt /app/agents/requirements.txt
RUN pip install --no-cache-dir -r /app/agents/requirements.txt
RUN useradd --system --uid 10001 --create-home appuser
COPY agents /app/agents
# Small shared modules the agents reuse: the autonomy gate, the GraphSAGE reference
# calculation and the NAPFD metric (no heavy ML dependencies are pulled in).
COPY triage/__init__.py triage/gate.py /app/triage/
COPY rca/__init__.py rca/numerics.py /app/rca/
COPY eval/__init__.py eval/metrics.py /app/eval/
COPY data/schema.sql /app/data/schema.sql
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
EXPOSE 8000
CMD ["uvicorn", "agents.app:app", "--host", "0.0.0.0", "--port", "8000"]
