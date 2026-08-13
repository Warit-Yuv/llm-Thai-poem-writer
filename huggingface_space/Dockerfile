# Hugging Face Spaces (free tier) — Docker image for the Klon Pad Rhyme Checker.
#
# Streamlit is no longer offered as a first-class Space SDK, so the app is
# hosted as a Docker Space that runs Streamlit. Hardware is still selectable
# in the Space settings (CPU basic on the free tier).
FROM python:3.11-slim

# Build tools in case a dependency only ships a source distribution
# (e.g. python-crfsuite pulled in by pythainlp).
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install dependencies first so image rebuilds reuse the cached layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code, static component, and assets.
COPY . .

EXPOSE 7860

# HF Spaces exposes the app on port 7860.
CMD ["streamlit", "run", "app.py", "--server.port=7860", "--server.address=0.0.0.0", "--server.headless=true"]
