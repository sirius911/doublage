# Image de l'application Doublage, construite avec Podman :
#   podman build -t doublage -f Containerfile .
FROM docker.io/library/python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# PyTorch en version processeur uniquement (évite ~3 Go de bibliothèques CUDA).
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY pyproject.toml SPEC.md ./
COPY doublage ./doublage
RUN pip install --no-cache-dir ".[tts]"

# Utilisateur sans privilèges.
RUN useradd --create-home --uid 1000 doublage && mkdir -p /data && chown doublage /data
USER doublage

ENV DOUBLAGE_DATA_DIR=/data \
    HF_HOME=/home/doublage/.cache/huggingface
EXPOSE 8000
CMD ["doublage", "serveur", "--hote", "0.0.0.0", "--port", "8000"]
