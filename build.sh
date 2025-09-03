#!/bin/bash
set -e

# Load .env variables if present
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

if [ -z "$1" ] || [ "$1" = "all" ]; then
  echo "Building all images..."
  docker build -t openrouter \
    -f ./components/LM/OpenRouter/Dockerfile . 

  docker build -t chatterbox \
    --build-arg INSTALL_TORCH_CUDA124=${INSTALL_TORCH_CUDA124:-false} \
    -f ./components/TTS/Chatterbox/Dockerfile .
else
  echo "Building image for: $1"
  if [ "$1" = "openrouter" ]; then
    docker build -t openrouter \
      -f ./components/LM/OpenRouter/Dockerfile .
  elif [ "$1" = "chatterbox" ]; then
    docker build -t chatterbox \
      --build-arg INSTALL_TORCH_CUDA124=${INSTALL_TORCH_CUDA124:-false} \
      -f ./components/TTS/Chatterbox/Dockerfile .
  else 
    echo "Image $1 was not recognized"
  fi
fi
