#!/usr/bin/env python3
"""
Benchmark local pour le modèle Mistral-7B-Instruct-v0.3-AWQ (vLLM).
Mesure la latence, le throughput (tokens/sec) et la qualité sur un panel de tâches.
"""

import time
import statistics
import requests

# --- Configuration ---
BASE_URL = "http://localhost:8000/v1"
API_KEY = "sk-vllm-local-secret"
MODEL_ID = "solidrust/Mistral-7B-Instruct-v0.3-AWQ"
MAX_TOKENS = 256

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

# --- Prompts de test ---
PROMPTS = {
    "raisonnement": "Explique pas à pas : pourquoi le ciel est bleu ? Réponds en 3 étapes.",
    "creativite": "Raconte une blague sur les développeurs en une phrase.",
    "connaissance": "Quelle est la capitale de la Côte d'Ivoire ?",
    "code": "Écris une fonction Python qui calcule la somme des n premiers nombres premiers. Utilise un commentaire docstring.",
    "resume": "Résume ce texte en 10 mots : 'L'intelligence artificielle transforme les industries en automatisant les tâches répétitives et en aidant à la prise de décision.'",
    "francais": "Rédige un message professionnel en français pour demander un rendez-vous à un client ivoirien. Sois chaleureux mais formel. 3 phrases maximum.",
}


def chat(prompt: str, max_tokens: int = MAX_TOKENS) -> dict:
    """Envoie un prompt et retourne la réponse + métriques brutes."""
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "stream": False,
    }

    start = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload)
    elapsed = time.perf_counter() - start

    resp.raise_for_status()
    data = resp.json()

    choice = data["choices"][0]
    usage = data.get("usage", {})

    return {
        "prompt": prompt[:60] + "...",
        "text": choice["message"]["content"].strip(),
        "latency_total_s": round(elapsed, 3),
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0),
        "total_tokens": usage.get("total_tokens", 0),
    }


def benchmark_throughput():
    """Benchmark de throughput : mesure le temps pour générer N tokens."""
    payload = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "Raconte l'histoire de la Côte d'Ivoire en 200 mots."}],
        "max_tokens": 200,
        "stream": False,
    }

    start = time.perf_counter()
    resp = requests.post(f"{BASE_URL}/chat/completions", headers=HEADERS, json=payload)
    elapsed = time.perf_counter() - start
    resp.raise_for_status()

    usage = resp.json().get("usage", {})
    completion_tokens = usage.get("completion_tokens", 1)

    throughput = completion_tokens / elapsed if elapsed > 0 else 0
    return {
        "target_tokens": 200,
        "generated_tokens": completion_tokens,
        "elapsed_s": round(elapsed, 3),
        "throughput_tok_s": round(throughput, 1),
    }


def main():
    print("=" * 70)
    print(f"Benchmark Mistral-7B-Instruct-v0.3-AWQ  |  Endpoint: {BASE_URL}")
    print("=" * 70)

    # 1. Qualité + latence par tâche
    results = []
    print("\n--- 1. Qualité & Latence par tâche ---")
    for task, prompt in PROMPTS.items():
        try:
            r = chat(prompt)
            results.append(r)
            print(f"\n[{task.upper()}]")
            print(f"  Latence : {r['latency_total_s']}s")
            print(f"  Tokens  : {r['prompt_tokens']} prompt / {r['completion_tokens']} completion")
            print(f"  Réponse : {r['text'][:120]}...")
        except Exception as e:
            print(f"\n[{task.upper()}] ERREUR : {e}")

    # 2. Throughput
    print("\n--- 2. Throughput (génération 200 tokens) ---")
    throughput = benchmark_throughput()
    print(f"  Tokens générés : {throughput['generated_tokens']}")
    print(f"  Temps total    : {throughput['elapsed_s']}s")
    print(f"  Throughput     : {throughput['throughput_tok_s']} tokens/sec")

    # 3. Résumé
    if results:
        latencies = [r["latency_total_s"] for r in results]
        print("\n--- 3. Résumé ---")
        print(f"  Latence moyenne  : {statistics.mean(latencies):.3f}s")
        print(f"  Latence médiane  : {statistics.median(latencies):.3f}s")
        print(f"  Latence min/max  : {min(latencies):.3f}s / {max(latencies):.3f}s")

    print("\n" + "=" * 70)
    print("Benchmark terminé.")
    print("=" * 70)


if __name__ == "__main__":
    main()
