# AI-BugFixer backend image — installs toolchains for all 10 practice languages
# (python, javascript, typescript, java, c, cpp, csharp, go, rust, php)
# Build:  docker build -t ai-bugfixer-backend .
# Run:    docker run -p 8000:8000 --env-file .env ai-bugfixer-backend

FROM python:3.11-slim

# --- system toolchains -------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        default-jdk \
        golang-go \
        php-cli \
        curl \
        ca-certificates \
        gnupg \
    && rm -rf /var/lib/apt/lists/*

# Node.js 22.x (needed for JavaScript + TypeScript --experimental-strip-types)
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Rust
ENV CARGO_HOME=/opt/cargo RUSTUP_HOME=/opt/rustup PATH=/opt/cargo/bin:$PATH
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain stable

# .NET SDK (C#) — comment this block out if you don't need C# and want a smaller/faster image
RUN curl -sSL https://dot.net/v1/dotnet-install.sh | bash -s -- --channel 8.0 --install-dir /opt/dotnet
ENV PATH=/opt/dotnet:$PATH DOTNET_CLI_TELEMETRY_OPTOUT=1

# --- OCR engine used by backend/ai/ocr.py -------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

# --- python deps ---------------------------------------------------------
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
