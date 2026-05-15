#!/usr/bin/env python3
"""
Récupère l'URL publique ngrok en interrogeant l'API locale depuis
l'intérieur du conteneur (plus fiable que le port mapping hôte).
Usage :
  python scripts/get_ngrok_url.py
"""
import subprocess
import json
import sys

CONTAINER_NAME = "inference-ngrok"


def main():
    try:
        result = subprocess.run(
            [
                "docker", "exec", CONTAINER_NAME,
                "wget", "-qO-", "http://127.0.0.1:4040/api/tunnels",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=True,
        )
        data = json.loads(result.stdout)
        for tunnel in data.get("tunnels", []):
            url = tunnel.get("public_url")
            if url:
                print(url)
                return
        print("Aucun tunnel actif trouvé.", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"Erreur docker exec : {e.stderr or e.stdout}", file=sys.stderr)
        print("Astuce : ngrok doit être démarré.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Erreur : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
