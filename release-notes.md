# Free Inference v1.0.0

Moteur d'inference LLM local et open-source, conçu pour les entreprises et développeurs.

## 🚀 Fonctionnalités

- **Inference GPU** : vLLM + Mistral-7B-Instruct-v0.3-AWQ (4-bit, ~4.2 GB VRAM)
- **Gateway API** : LiteLLM Proxy avec authentification, clés API, budgets et rate limiting
- **Multimodal** : OCR (DocTR), Speech-to-Text (Whisper), Embeddings (bge-m3) — tout en CPU
- **Interface Chat** : Open WebUI simplifiée et francisée
- **Monitoring** : Prometheus + Grafana intégrés
- **Configuration centralisée** : modèle LLM, quantification, template Jinja via un seul fichier `.env`

## 📋 Requirements

| Composant | Minimum |
|---|---|
| OS | Linux (Ubuntu 22.04+) |
| GPU | NVIDIA 12 GB VRAM (RTX 3060/4060 ou supérieur) |
| RAM | 16 GB |
| Disque | 30 GB libres |

## ⚡ Démarrage rapide

```bash
git clone https://github.com/Hydra16LeGrand/free-inference.git
cd free-inference
cp .env.example .env
# Éditer .env avec vos tokens et clés
docker compose up -d
```

Accès : `http://localhost:3000` (WebUI), `http://localhost:4000` (API)

## 📚 Documentation

- [README.md](./README.md) — Installation complète et architecture
- [API_USAGE.md](./API_USAGE.md) — Endpoints et exemples d'appels

## 🔧 Scripts utilitaires

- `scripts/backup_db.sh` — Sauvegarde PostgreSQL
- `scripts/benchmark.py` — Test de charge
- `scripts/onboard_user.py` — Création d'utilisateurs
- `scripts/generate_key.py` — Génération de clés API

## 📦 Stack technique

- **vLLM** : moteur d'inference GPU
- **LiteLLM** : gateway API
- **LangGraph** : orchestration multimodale
- **PostgreSQL** : métadonnées et billing
- **Prometheus + Grafana** : observabilité
- **Docker Compose** : déploiement unifié

---

**License** : MIT
**Auteur** : Amara Baradji
