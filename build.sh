#!/bin/bash
set -e

if [ -z "$1" ] || [ "$1" = "all" ]; then
  echo "Building all images..."
  docker build -t openrouter -f ./components/LM/OpenRouter/Dockerfile .
  # docker build -t chatterbox -f ./components/TTS/Chatterbox/Dockerfile .
  # docker build -t openvoice -f ./components/TTS/OpenVoice/Dockerfile .
else
  echo "Building image for: $1"
  docker build -t "$1-ai" ./components/$1
fi
