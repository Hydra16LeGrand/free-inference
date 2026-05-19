#!/usr/bin/env python3
"""
Génère une clé API LiteLLM pour un utilisateur existant.
Usage: source .env && python scripts/generate_key.py user@example.com
"""
import os
import sys
import json
import urllib.request
import urllib.error

LITELLM_URL = os.environ.get("LITELLM_URL", "http://127.0.0.1:4000")
MASTER_KEY = os.environ.get("LITELLM_MASTER_KEY")

def generate_key(user_id: str, models: list, budget: float | None = None):
    payload = {
        "user_id": user_id,
        "models": models,
        "metadata": {"note": "Auto-generated key"},
    }
    if budget is not None and budget > 0:
        payload["max_budget"] = budget

    req = urllib.request.Request(
        f"{LITELLM_URL}/key/generate",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {MASTER_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return data
    except urllib.error.HTTPError as e:
        return {"error": f"{e.code}: {e.read().decode()}"}
    except Exception as e:
        return {"error": str(e)}


def main():
    if not MASTER_KEY:
        print("ERROR: LITELLM_MASTER_KEY not set", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) < 2:
        print("Usage: python scripts/generate_key.py <user_email> [--budget 0]")
        sys.exit(1)

    user_id = sys.argv[1]
    budget = None
    if "--budget" in sys.argv:
        idx = sys.argv.index("--budget")
        if idx + 1 < len(sys.argv):
            budget = float(sys.argv[idx + 1])

    # Modèles par défaut accessibles
    models = ["base-mind", "bge-m3"]

    result = generate_key(user_id, models, budget)
    if "error" in result:
        print(f"ERROR: {result['error']}", file=sys.stderr)
        sys.exit(1)

    print(f"Clé API générée pour {user_id}:")
    print(f"  Key: {result.get('key', 'N/A')}")
    print(f"  Budget: {'unlimited' if budget is None or budget == 0 else f'${budget}/month'}")
    print(f"  Models: {', '.join(models)}")


if __name__ == "__main__":
    main()
