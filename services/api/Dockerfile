# Derleme bağlamı depo köküdür: docker build -f services/api/Dockerfile .
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Model önbelleği (Hugging Face) kalıcı volume'a bağlanır; klasör kullanıcıya ait olmalı.
RUN useradd --create-home --uid 1000 evrakyol \
    && mkdir -p /home/evrakyol/.cache \
    && chown evrakyol:evrakyol /home/evrakyol/.cache

# Embedding modeli CPU'da çalışır: PyTorch'un küçük CPU sürümü önce kurulur.
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu

COPY services/api/pyproject.toml ./
COPY services/api/app ./app
RUN pip install ".[embeddings]"

COPY services/api/alembic.ini ./
COPY services/api/alembic ./alembic
# Ortak yapılandırma (işlem türleri, kaynak izin listesi)
COPY config /config
ENV CONFIG_DIR=/config

USER evrakyol
EXPOSE 8000

# Yayında migration'lar ayrı bir adımda (alembic upgrade head) çalıştırılır.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
