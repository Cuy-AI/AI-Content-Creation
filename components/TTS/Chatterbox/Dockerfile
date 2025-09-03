# Use Python 3.13
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install git (needed for cloning repos)
RUN apt-get update && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

# Clone and install chatterbox
RUN git clone https://github.com/resemble-ai/chatterbox.git /tmp/chatterbox \
    && pip install --no-cache-dir -e /tmp/chatterbox

# Copy OpenRouter files
COPY components/TTS/Chatterbox/ .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Build arg to control torch installation
ARG INSTALL_TORCH_CUDA124=false

# Conditionally install CUDA PyTorch 12.4 (My machine needs a special torch installation)
RUN if [ "$INSTALL_TORCH_CUDA124" = "true" ]; then \
      pip uninstall -y torch torchvision torchaudio && \
      pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124 ; \
    fi

# Create folder and copy shared classes
RUN mkdir -p classes
COPY classes/BaseAI.py classes/
COPY classes/Server.py classes/

# Expose port for API server
EXPOSE 8002

# Start FastAPI server
CMD ["python", "Chatterbox.py"]
