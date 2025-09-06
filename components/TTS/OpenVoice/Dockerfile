# OpenVoice uses python 3.9.13 
FROM python:3.9.13 

# Set working directory
WORKDIR /app

# Install system dependencies (git, wget, unzip, ffmpeg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git wget unzip ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Clone and install OpenVoice
RUN git clone https://github.com/myshell-ai/OpenVoice.git /tmp/OpenVoice \
    && pip install --no-cache-dir -e /tmp/OpenVoice

# Download and extract checkpoints (unzips into OpenVoice/checkpoints)
RUN wget -O /tmp/checkpoints_1226.zip https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_1226.zip \
    && unzip /tmp/checkpoints_1226.zip -d /tmp/OpenVoice \
    && rm /tmp/checkpoints_1226.zip

# Download and extract checkpoints_v2 (unzips into OpenVoice/checkpoints_v2)
RUN wget -O /tmp/checkpoints_v2_0417.zip https://myshell-public-repo-host.s3.amazonaws.com/openvoice/checkpoints_v2_0417.zip \
    && unzip /tmp/checkpoints_v2_0417.zip -d /tmp/OpenVoice \
    && rm /tmp/checkpoints_v2_0417.zip

# Install MeloTTS + download unidic models
RUN pip install --no-cache-dir git+https://github.com/myshell-ai/MeloTTS.git \
    && python -m unidic download

# Install NLTK data required by MeloTTS / g2p_en
RUN python -m nltk.downloader -d /usr/local/nltk_data averaged_perceptron_tagger_eng punkt

# Copy OpenVoice files
COPY components/TTS/OpenVoice/ .

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
EXPOSE 8003

# Start FastAPI server
CMD ["python", "OpenVoice.py"]
