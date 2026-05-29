# Hugging Face Space (Docker SDK) — runs the FabFlow Streamlit dashboard.
# The DuckDB warehouse is built on first load by the app (running the study).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    HOME=/app \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 7860
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0"]
