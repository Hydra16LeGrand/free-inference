#!/usr/bin/env python3
"""
Script de benchmark end-to-end pour le pipeline complet :
vLLM (Llama-3-8B) → LiteLLM Proxy → Client.
Mesure la latence ajoutée par le proxy, le tracking DB, et le throughput global.
"""

import time
import statistics
import requests

BASE_URL_VLLM = "http://localhost:8000/v1"
BASE_URL_LITELLM = "http://localhost:4000/v1"
API_KEY_VLLM = "sk-vllm-local-secret"
API_KEY_LITELLM = "sk-litellm-master-secret"
MODEL_ID = "casperhansen/llama-3-8b-instruct-awq"
PROMPT = "Explique en 5 lignes pourquoi le ciel est bleu."
MAX_TOKENS = 100
RUNS = 3


def measure(endpoint: str, api_key: str) -> dict:
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": PROMPT}],
        "max_tokens": MAX_TOKENS,
        "stream": False,
    }
    start = time.perf_counter()
    resp = requests.post(f"{endpoint}/chat/completions", headers=headers, json=payload)
    elapsed = time.perf_counter() - start
    resp.raise_for_status()
    usage = resp.json().get("usage", {})
    return {
        "elapsed_s": elapsed,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
    }


def main():
    print("=" * 70)
    print("Benchmark Pipeline : vLLM vs LiteLLM Proxy")
    print("=" * 70)

    # vLLM direct
    vllm_times = [measure(BASE_URL_VLLM, API_KEY_VLLM)["elapsed_s"] for _ in range(RUNS)]
    print(f"\nvLLM Direct  : {statistics.mean(vllm_times):.3f}s (moyenne sur {RUNS} runs)")

    # LiteLLM proxy
    llm_times = [measure(BASE_URL_LITELLM, API_KEY_LITELLM)["elapsed_s"] for _ in range(RUNS)]
    print(f"LiteLLM Proxy: {statistics.mean(llm_times):.3f}s (moyenne sur {RUNS} runs)")

    overhead = statistics.mean(llm_times) - statistics.mean(vllm_times)
    print(f"Overhead proxy : {overhead:.3f}s ({overhead/statistics.mean(vllm_times)*100:.1f}%)")

    print("=" * 70)


if __name__ == "__main__":
    main()
