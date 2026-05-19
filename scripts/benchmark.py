#!/usr/bin/env python3
"""
Benchmark de charge pour l'API LiteLLM (base-mind).
Mesure latence moyenne, p95, p99, taux d'erreur et tokens/sec.
Usage: source .env && python scripts/benchmark.py
"""
import os
import sys
import json
import time
import statistics
import urllib.request
import concurrent.futures
from dataclasses import dataclass

LITELLM_URL = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

PROMPTS = [
    "Salut, comment vas-tu ?",
    "Explique en deux phrases pourquoi le ciel est bleu.",
    "Quelle est la capitale politique de la Côte d'Ivoire ?",
    "Résume en 20 mots : l'intelligence artificielle transforme les industries.",
    "Quel est le plat traditionnel le plus célèbre de la Côte d'Ivoire ?",
]


@dataclass
class Result:
    ok: bool
    latency_ms: float
    tokens: int
    error: str = ""


def _chat(prompt: str) -> Result:
    payload = {
        "model": "base-mind",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "temperature": 0.3,
    }
    req = urllib.request.Request(
        f"{LITELLM_URL}/v1/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {MASTER_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read())
            latency = (time.perf_counter() - start) * 1000
            tokens = data["usage"]["completion_tokens"]
            return Result(ok=True, latency_ms=latency, tokens=tokens)
    except Exception as e:
        latency = (time.perf_counter() - start) * 1000
        return Result(ok=False, latency_ms=latency, tokens=0, error=str(e))


def run_sequential(n: int) -> list[Result]:
    results = []
    for i in range(n):
        prompt = PROMPTS[i % len(PROMPTS)]
        r = _chat(prompt)
        results.append(r)
        time.sleep(0.5)
    return results


def run_parallel(concurrency: int, total: int) -> list[Result]:
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as ex:
        futures = [ex.submit(_chat, PROMPTS[i % len(PROMPTS)]) for i in range(total)]
        for f in concurrent.futures.as_completed(futures):
            results.append(f.result())
    return results


def _report(label: str, results: list[Result]):
    ok = [r for r in results if r.ok]
    errors = [r for r in results if not r.ok]
    latencies = [r.latency_ms for r in ok]
    tokens = sum(r.tokens for r in ok)
    total_time_sec = sum(r.latency_ms for r in results) / 1000

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"  Requêtes totales : {len(results)}")
    print(f"  Succès           : {len(ok)} ({len(ok)/len(results)*100:.1f}%)")
    print(f"  Erreurs          : {len(errors)}")
    if errors:
        for e in errors[:3]:
            print(f"    -> {e.error[:80]}")
    if latencies:
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        avg = statistics.mean(latencies)
        print(f"  Latence moyenne  : {avg:.1f} ms")
        print(f"  Latence p95      : {p95:.1f} ms")
        print(f"  Latence p99      : {p99:.1f} ms")
        print(f"  Tokens générés   : {tokens}")
        if total_time_sec > 0:
            print(f"  Tokens/sec       : {tokens/total_time_sec:.1f}")


def main():
    if not MASTER_KEY:
        print("ERROR: LITELLM_MASTER_KEY not set", file=sys.stderr)
        sys.exit(1)

    print("Benchmark Inference Stack — base-mind")
    print(f"Endpoint : {LITELLM_URL}")

    # 1. Warm-up (single request)
    print("\n[Warm-up] 1 requête...")
    _chat("Bonjour.")

    # 2. Sequential test
    print("\n[Séquentiel] 10 requêtes, 1 par 1...")
    seq = run_sequential(10)
    _report("Séquentiel (10 requêtes)", seq)

    # 3. Parallel test
    for conc in [5, 10, 20]:
        print(f"\n[Parallèle] {conc} workers, 30 requêtes...")
        par = run_parallel(conc, 30)
        _report(f"Parallèle ({conc} workers, 30 requêtes)", par)

    print("\nBenchmark terminé.")


if __name__ == "__main__":
    main()
