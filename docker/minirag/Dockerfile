FROM ghcr.io/astral-sh/uv:0.6.14-python3.10-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    libavif-dev pkg-config \
    libjpeg-dev \
    gcc unzip zip \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    libffi-dev \
    curl \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY scr/requirements.txt .
RUN uv pip install -r requirements.txt --system

# Downloading NLTK
RUN python3 - <<EOF
import nltk
nltk.download("punkt")
nltk.download("punkt_tab")
nltk.download("averaged_perceptron_tagger_eng")
nltk.download("stopwords")
EOF

COPY scr/ .

RUN mkdir -p /app/models/db_schems/kwituni/
COPY docker/minirag/alembic.ini /app/models/db_schems/kwituni/
COPY docker/minirag/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]

