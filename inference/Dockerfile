# Genome Firewall inference service.
# Based on the AMRFinderPlus image so `amrfinder` is a local binary (with its DB
# baked in) — no Docker-in-Docker at runtime.
FROM staphb/ncbi-amrfinderplus:4.2.7-2026-03-24.1

# The base image's system Python is too old for scikit-learn 1.9 / pandas 3.0,
# so provision Python 3.13 with uv (mirrors the verified local env).
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app
COPY requirements.txt .
RUN uv venv --python 3.13 /opt/venv \
    && uv pip install --python /opt/venv/bin/python -r requirements.txt
ENV PATH="/opt/venv/bin:${PATH}"

# Service code + pipeline + models (models/, features/, gf_infer.py, serve.py).
COPY . /app

ENV AMRFINDER_THREADS=4
EXPOSE 8000

# Optional: set INFERENCE_API_TOKEN to require a bearer token on /predict.
# Shell form so ${PORT} (Render, etc.) expands; falls back to 8000 (HF Spaces app_port).
CMD uvicorn serve:app --host 0.0.0.0 --port ${PORT:-8000}
