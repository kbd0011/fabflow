FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential git curl \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && mv /root/.local/bin/uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
COPY configs ./configs
RUN uv venv --python 3.12 && uv pip install -e .

EXPOSE 8501
CMD [".venv/bin/streamlit", "run", "src/fabflow/dashboard/app.py", "--server.address=0.0.0.0"]
