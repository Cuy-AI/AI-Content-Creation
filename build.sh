#!/bin/bash
set -e

if [ -z "$1" ] || [ "$1" = "all" ]; then
  echo "Building all images..."
  docker build -t openrouter -f ./components/LM/OpenRouter/Dockerfile .
  # docker build -t lmstudio -f ./components/LM/LMStudio/Dockerfile .       # This will not run on a Docker container
  # docker build -t chatterbox -f ./components/TTS/Chatterbox/Dockerfile .
  # docker build -t openvoice -f ./components/TTS/OpenVoice/Dockerfile .
else
  echo "Building image for: $1"
  if [ "$1" = "openrouter" ]; then
    docker build -t openrouter -f ./components/LM/OpenRouter/Dockerfile .
  # elif [ "$1" = "lmstudio" ]; then
  #   docker build -t lmstudio -f ./components/LM/LMStudio/Dockerfile .
  else 
    echo "Image $1 was not recognized"
  fi
fi
