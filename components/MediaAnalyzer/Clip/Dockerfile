# Use a slim Python image for lightness
FROM python:3.13.3-slim

# Set working directory
WORKDIR /app

# Install system dependencies (needed for OpenCV and general tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copy Clip files
COPY components/MediaAnalyzer/Clip .

# Copy only requirements first to leverage Docker cache
RUN pip install --no-cache-dir -r requirements.txt

# Copy the downloader script and run it
# This "bakes" the model weights into the image layer
RUN python download_model.py && rm download_model.py

# --- Part requested to remain the same ---
# Create folder and copy shared classes
RUN mkdir -p classes
COPY classes/BaseAI.py classes/
COPY classes/Server.py classes/

# Expose port for API server
EXPOSE 8005

# Start FastAPI server
CMD ["python", "Clip.py"]