#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "=== Déploiement ngrok (Free Inference) ==="

# Vérifier que NGROK_AUTHTOKEN est présent
if [ -z "${NGROK_AUTHTOKEN:-}" ]; then
    if [ -f .env ]; then
        export $(grep -v '^#' .env | xargs)
    fi
fi

if [ -z "${NGROK_AUTHTOKEN:-}" ]; then
    echo "ERREUR : NGROK_AUTHTOKEN manquant. Ajoute-le dans .env."
    exit 1
fi

echo "Démarrage du tunnel ngrok..."
docker compose --profile tunnel up -d --force-recreate ngrok

echo "Attente de l'URL publique (max 30s)..."
URL=""
for i in {1..15}; do
    sleep 2
    URL=$(docker logs inference-ngrok 2>/dev/null | grep -oE 'https://[a-z0-9-]+\.ngrok-free\.app' | head -n1 || true)
    if [ -n "$URL" ]; then
        break
    fi
    # Fallback : tente l'API locale si le port est mappé
    URL=$(python scripts/get_ngrok_url.py 2>/dev/null || true)
    if [ -n "$URL" ]; then
        break
    fi
done

echo ""
if [ -n "$URL" ]; then
    echo "URL publique : $URL"
else
    echo "URL publique : (non récupérée — vérifie les logs ci-dessous)"
fi

echo ""
echo "Logs ngrok en temps réel (Ctrl+C pour quitter) :"
docker logs -f inference-ngrok
