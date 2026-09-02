# Dockerfile for TikTok Studio Pro
FROM python:3.11-slim

# Install system dependencies including FFmpeg, fonts, curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    fonts-dejavu-core \
    fonts-freefont-ttf \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY config.py server.py ./
COPY src/ ./src/
COPY ui/ ./ui/
COPY assets/ ./assets/
COPY data/accounts.example.json data/settings.example.json ./data/
COPY docs/ ./docs/
COPY n8n/ ./n8n/

# Create required runtime directories
RUN mkdir -p data storage/inputs storage/outputs storage/temp storage/logs input_sources output_product bin

# Initialize default configurations if not present
RUN cp data/accounts.example.json data/accounts.json && \
    cp data/settings.example.json data/settings.json

# Expose default HTTP server port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/api/settings || exit 1

# Start the web server
CMD ["python", "server.py"]
