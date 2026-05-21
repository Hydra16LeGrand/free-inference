# Free Inference — Infrastructure d'Inference LLM Open-Source

**Alternative on-premise à OpenAI API.** Moteur d'inference locale avec gateway multi-tenant, multimodal (OCR, STT, embeddings) et observabilité intégrée.

## Pourquoi Free Inference ?

Les solutions existantes (Ollama, LM Studio) excellent pour **lancer un modèle local**. Free Inference va plus loin : elle fournit **l'infrastructure complète autour** — gateway API, authentification, billing, monitoring, multimodal — prête pour un usage en production.

| | Ollama | LM Studio | **Free Inference** |
|---|---|---|---|
| Scope | Lancer un modèle | GUI desktop + chat | **Infrastructure production-ready** |
| API Gateway | Non | Non | **✅ LiteLLM (auth, clés, budgets)** |
| Multimodal | Texte seul | Texte seul | **✅ OCR + STT + Embeddings** |
| Observabilité | Non | Basique | **✅ Prometheus + Grafana** |
| Multi-tenant | Non | Non | **✅ Utilisateurs, rôles, budgets** |
| Déploiement | CLI local | Desktop | **✅ Docker Compose + Cloudflare** |

## Architecture

```
Internet → Cloudflare Tunnel → Nginx (80)
                                      │
            ┌───────────┬─────────────┼─────────────┐
            ↓           ↓             ↓             ↓
      Landing Page   Open WebUI   LiteLLM API   Grafana
      (Static)       (Chat)       (Gateway)     (Metrics)
            │           │             │             │
            └───────────┴─────────────┴─────────────┘
                                      │
                            ┌─────────┴─────────┐
                            ↓                   ↓
                        vLLM (GPU)      Multimodal API (CPU)
                        Mistral 7B      OCR + STT + Embeddings
                        12 Go VRAM      CPU
```

## Stack Technique

- **vLLM** : Moteur d'inference GPU (Mistral-7B-Instruct-v0.3-AWQ, 4-bit)
- **LiteLLM Proxy** : Gateway API (auth, clés API, rate limiting, budgets)
- **PostgreSQL** : Persistance métadonnées et logs de consommation
- **LangGraph** : Orchestrateur multimodal (texte + image + audio)
- **DocTR** : OCR sur CPU
- **faster-whisper** : Speech-to-Text (STT) sur CPU
- **bge-m3** : Embeddings multilingues sur CPU
- **Open WebUI** : Interface chat simplifiée
- **Prometheus + Grafana** : Observabilité
- **Nginx + Cloudflare Tunnel** : Reverse proxy + accès public sécurisé

## Quick Start

1. **Copier le template `.env` :**
   ```bash
   cp .env.example .env
   # Editer .env avec vos vraies valeurs (DOMAIN, CLOUDFLARE_TUNNEL_TOKEN, etc.)
   ```

2. **Démarrer la stack :**
   ```bash
   docker compose up -d
   ```

3. **Vérifier les services :**
   ```bash
   docker compose ps
   ```

4. **Accès (local) :**
   - Open WebUI : `http://localhost:3000`
   - Grafana : `http://localhost:3100`
   - Prometheus : `http://localhost:9090` (interne uniquement)

## Modèles exposés

| Alias LiteLLM | Backend | Rôle |
|---|---|---|
| `base-mind` | vLLM (GPU) | Chat texte, raisonnement, français |
| `bge-m3` | multimodal-api (CPU) | Embeddings multilingues |

## Configuration du Modèle LLM

Toute la configuration passe par `.env` :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `VLLM_MODEL` | HuggingFace ID | `solidrust/Mistral-7B-Instruct-v0.3-AWQ` |
| `VLLM_QUANTIZATION` | Type de quantification | `awq`, `gptq`, `none` |
| `VLLM_MAX_MODEL_LEN` | Taille max de contexte | `6144` |
| `WHISPER_MODEL_SIZE` | Modèle STT | `small`, `medium`, `large` |
| `EMBED_MODEL` | Modèle embeddings | `BAAI/bge-m3` |

**Procédure (3 étapes) :**

1. Modifier `.env` :
   ```bash
   VLLM_MODEL=TheBloke/Mistral-7B-Instruct-v0.2-AWQ
   VLLM_QUANTIZATION=awq
   VLLM_MAX_MODEL_LEN=8192
   ```

2. Adapter le template Jinja (`vllm_chat_template.jinja`) au format du nouveau modèle.

3. Relancer :
   ```bash
   docker compose up -d --force-recreate vllm
   ```

## Déploiement Public (Cloudflare)

Voir [DEPLOYMENT.md](DEPLOYMENT.md) pour le guide complet :
- Sous-domaines : `tondomaine.com`, `chat.tondomaine.com`, `api.tondomaine.com`, `dash.tondomaine.com`
- HTTPS automatique via Cloudflare
- Rate limiting Nginx intégré

## Scripts Utilitaires

| Script | Usage |
|---|---|
| `scripts/backup_db.sh` | Sauvegarde PostgreSQL (14 jours de rétention) |
| `scripts/benchmark.py` | Test de charge (latence, throughput, erreurs) |
| `scripts/onboard_user.py` | Création d'utilisateur LiteLLM |
| `scripts/generate_key.py` | Génération de clé API |

## Benchmarks (Mistral-7B AWQ, 12 Go VRAM)

| Scénario | Latence moyenne | p95 | Tokens/sec |
|---|---|---|---|
| Séquentiel (1 req) | ~688 ms | 1.6 s | **50.0** |
| 5 requêtes // | ~2.9 s | 3.3 s | **12.6** |
| 20 requêtes // | ~8.5 s | 12.5 s | **4.2** |

*Sweet spot : ~5 utilisateurs simultanés pour garder une latence < 3s.*

## Sécurité

- **vLLM** : jamais exposé publiquement (réseau Docker interne uniquement)
- **Prometheus** : `127.0.0.1` uniquement
- **LiteLLM** : auth par clé API + rate limiting + budgets par utilisateur
- **Grafana** : mot de passe admin requis
- **Nginx** : rate limiting général + zone API stricte

## Licence

MIT License — voir [LICENSE](LICENSE).
