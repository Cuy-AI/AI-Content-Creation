# Use Python 3.13
FROM python:3.13

# Set working directory
WORKDIR /app

# Install system dependencies (ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy OpenRouter files
COPY components/Editor/Whisper/ .

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
EXPOSE 8001

# Start FastAPI server
CMD ["python", "Whisper.py"]
