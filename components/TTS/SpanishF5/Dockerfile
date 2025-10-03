# Use Python 3.10 (required by F5-TTS)
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install git, ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    git ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install F5-TTS as pip package (for inference)
RUN pip install --no-cache-dir git+https://github.com/jpgallegoar/Spanish-F5.git

# Install dependencies
COPY components/TTS/SpanishF5/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build arg to control torch installation
ARG INSTALL_TORCH_CUDA126=true

# Conditionally install CUDA PyTorch 12.6
RUN if [ "$INSTALL_TORCH_CUDA126" = "true" ]; then \
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu126 ; \
else \
pip install torch torchaudio ; \
fi

# Copy SpanishF5 files
COPY components/TTS/SpanishF5/ .

# Create folder and copy shared classes
RUN mkdir -p classes
COPY classes/BaseAI.py classes/
COPY classes/Server.py classes/

# Expose port for API server
EXPOSE 8004

# Start FastAPI server
CMD ["python", "SpanishF5.py"]