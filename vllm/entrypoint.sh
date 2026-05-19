#!/bin/sh
# Entrypoint wrapper for configurable model launch
set -e

# Defaults
MODEL="${VLLM_MODEL:-solidrust/Mistral-7B-Instruct-v0.3-AWQ}"
QUANT="${VLLM_QUANTIZATION:-awq}"
MAX_LEN="${VLLM_MAX_MODEL_LEN:-6144}"
API_KEY="${VLLM_API_KEY:-sk-vllm-local-secret}"
TEMPLATE="${VLLM_CHAT_TEMPLATE:-/configs/chat_template.jinja}"

exec python3 -m vllm.entrypoints.openai.api_server \
  --model "${MODEL}" \
  --quantization "${QUANT}" \
  --max-model-len "${MAX_LEN}" \
  --gpu-memory-utilization 0.90 \
  --tensor-parallel-size 1 \
  --dtype half \
  --enforce-eager \
  --max-num-seqs 1 \
  --enable-prefix-caching \
  --chat-template "${TEMPLATE}" \
  --api-key "${API_KEY}"
