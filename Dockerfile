FROM python:3.11-slim

# ── System dependencies ────────────────────────────────────────────────────
# libxml2 / libxslt: required by lxml for DTD validation
# ffmpeg:            required by MoviePy for video processing (Prompt 3+)
# gcc:               C-extension build support
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev \
    libxslt-dev \
    ffmpeg \
    gcc \
    imagemagick \
    && rm -rf /var/lib/apt/lists/*

# Fix ImageMagick security policy to allow MoviePy text rendering
RUN find /etc -name "policy.xml" -path "*ImageMagick*" -exec sed -i 's/domain="path" rights="none" pattern="@\*"/domain="path" rights="read|write" pattern="@\*"/g' {} +

WORKDIR /app

# ── Python dependencies (cached layer) ────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────
COPY . .

# ── Default command (overridden by docker-compose for worker) ─────────────
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
