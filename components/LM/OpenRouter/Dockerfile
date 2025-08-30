# Use Python 3.13
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Copy OpenRouter files
COPY components/LM/OpenRouter/ .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Check requirements
RUN pip list

# Create folder and copy shared classes
RUN mkdir -p classes
COPY classes/BaseAI.py classes/
COPY classes/Server.py classes/

# Expose port for API server
EXPOSE 8000

# Start FastAPI server
CMD ["python", "OpenRouter.py"]
