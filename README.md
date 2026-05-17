# Free Inference — Stack d'Inférence LLM Multimodale 100% Locale

## Vue d'ensemble

Plateforme d'inférence LLM **open source** et **100% locale** pour le chat, la vision, la voix et l'OCR.

**Matériel requis :**
- GPU NVIDIA 12 Go VRAM (RTX 4080/3080 Ti ou équivalent)
- CPU 32 Go RAM minimum (24 Go si allégé)
- Docker + NVIDIA Container Toolkit

**Stack :**
- **vLLM** : Moteur d'inférence GPU (Mistral-7B-Instruct-v0.3-AWQ)
- **LiteLLM Proxy** : Gateway de routage, tracking de tokens, quotas, auth
- **PostgreSQL** : Persistance des logs de consommation
- **Open WebUI** : Interface utilisateur
- **LangGraph** : Orchestrateur multimodal (texte + image + voix)
- **Qwen2-VL-2B** : Modèle de vision sur CPU (OCR, description d'image)
- **faster-whisper** : Reconnaissance vocale sur CPU
- **bge-m3** : Embeddings multilingues sur CPU
- **Prometheus + Grafana** : Observabilité
- **ngrok** : Tunnel sécurisé pour accès Internet

## Architecture

```
Internet → ngrok → Open WebUI (3000)
                          ↓
                   LiteLLM Proxy (4000)
                          ↓
              ┌───────────┴───────────┐
              ↓                       ↓
       base-mind (GPU)      base-mind-multimodal (CPU)
       Chat / Génération     Orchestrateur LangGraph
       12 Go VRAM            32 Go RAM
                                   ↓
                            ┌─────┴─────┐
                            ↓           ↓
                     base-mind      DocTR OCR
                     (GPU)           (CPU, OCR)
                            ↑           ↑
                            └─────┬─────┘
                                  ↓
                           faster-whisper (CPU, STT)
                                  ↓
                              bge-m3 (CPU)
                              Embeddings / RAG
```

**Workflow multimodal :**
1. User envoie texte + image via Open WebUI.
2. LangGraph détecte le type de contenu.
3. Texte → `base-mind` (GPU) pour la réponse.
4. Image → DocTR OCR / Qwen2-VL-2B (CPU) pour extraction/description.
5. LangGraph fusionne les résultats et retourne une réponse unifiée au format OpenAI.
6. LiteLLM expose le modèle `base-mind-multimodal` comme n'importe quel modèle LLM.

## Quick Start

1. **Copier le template `.env` :**
   ```bash
   cp .env.example .env
   # Editer .env avec vos vraies valeurs
   ```

2. **Démarrer la stack de base :**
   ```bash
   docker compose up -d vllm postgres litellm open-webui
   ```

3. **Vérifier les services :**
   ```bash
   docker ps
   ```

4. **Accès :**
   - Open WebUI : `http://localhost:3000`
   - Grafana : `http://localhost:3100`
   - Prometheus : `http://localhost:9090`

## Modèles exposés

| Modèle LiteLLM | Backend | Rôle |
|---|---|---|
| `base-mind` | vLLM (GPU) | Chat texte pur, rapide, concis en français |
| `base-mind-multimodal` | multimodal-api (CPU+GPU) | OCR + STT + vision + texte |
| `bge-m3` | multimodal-api (CPU) | Embeddings multilingues |

## Ajouter un Modèle

### Remplacer Mistral-7B par un autre modèle GPU

1. **Modifier `docker-compose.yml` (service `vllm`) :**
   ```yaml
   command: >
     --model solidrust/Mistral-7B-Instruct-v0.3-AWQ
     --quantization awq
     --max-model-len 8192
     --gpu-memory-utilization 0.90
     --tensor-parallel-size 1
     --dtype half
     --enforce-eager
     --enable-prefix-caching
     --api-key ${VLLM_API_KEY:-sk-vllm-local-secret}
   ```

2. **Modifier `litellm/config.yaml` :**
   ```yaml
   model_list:
     - model_name: base-mind
       litellm_params:
         model: hosted_vllm/solidrust/Mistral-7B-Instruct-v0.3-AWQ
         api_base: http://vllm:8000/v1
         api_key: os.environ/VLLM_API_KEY
   ```

3. **Recréer le conteneur :**
   ```bash
   docker compose up -d --no-deps --force-recreate vllm
   docker compose up -d --no-deps --force-recreate litellm
   docker compose restart open-webui
   ```

## Modèles Supportés

### GPU (12 Go VRAM)
- **Mistral-7B-Instruct-v0.3-AWQ** (actuel) : Chat général, code, raisonnement.
- *Empreinte : ~7 Go VRAM. Marge : ~4 Go pour KV cache.*

### CPU (32 Go RAM)
- **Qwen2-VL-2B-Instruct** : Vision + OCR + description d'image.
- **faster-whisper** : Transcription vocale (STT).
- **bge-m3** : Embeddings multilingues (RAG, recherche sémantique).
- *Empreinte totale CPU : ~6-8 Go RAM.*

## Contraintes KV Cache

Le KV cache est la mémoire intermédiaire stockée pendant la génération.

| Modèle | Contexte | Poids | KV Cache | Overhead | **Total VRAM** | Marge sous 12 Go |
|---|---|---|---|---|---|---|
| Mistral-7B-AWQ | 8192 | 4.1 Go | ~1 Go | ~2 Go | **~7.1 Go** | **~4.9 Go** |
| Mistral-7B-AWQ | 16384 | 4.1 Go | ~2 Go | ~2 Go | **~8.1 Go** | **~3.9 Go** |

**Règles :**
- `--max-model-len 8192` : sécurisé pour batch=1, risqué pour batch=2.
- `--max-model-len 16384` : possible mais surveiller la VRAM en temps réel.
- Batch > 2 : OOM probable.

## Variables d'Environnement

| Variable | Description | Exemple |
|----------|-------------|---------|
| `POSTGRES_USER` | Utilisateur PostgreSQL | `litellm` |
| `POSTGRES_PASSWORD` | Mot de passe PostgreSQL | *(fort)* |
| `VLLM_API_KEY` | Clé API vLLM | `sk-vllm-secret` |
| `LITELLM_MASTER_KEY` | Clé maître LiteLLM | `sk-litellm-master` |
| `LITELLM_SALT_KEY` | Clé de chiffrement DB | `sk-litellm-salt` |
| `WEBUI_SECRET_KEY` | Clé de session WebUI | *(32+ caractères)* |
| `NGROK_AUTHTOKEN` | Token ngrok | `2Xxxxxx...` |
| `NGROK_BASIC_AUTH` | Auth basique ngrok | `user:password` |
| `GF_SECURITY_ADMIN_USER` | Login Grafana | `admin` |
| `GF_SECURITY_ADMIN_PASSWORD` | Password Grafana | *(fort)* |

## Benchmarks

### Benchmark du modèle

```bash
python3 scripts/benchmark_llama8b.py
```

Mesure : latence par tâche, throughput (tokens/sec), qualité des réponses.

### Benchmark du pipeline

```bash
python3 scripts/benchmark_pipeline.py
```

Mesure : overhead ajouté par LiteLLM Proxy vs accès direct vLLM.

### Tests qualité

```bash
source .env && python scripts/test_quality.py
source .env && python scripts/test_full_suite.py
```

## Sécurisation pour Accès Internet (ngrok)

1. **Configurer `.env` :**
   ```bash
   NGROK_AUTHTOKEN=2XXXXXXXXXXXX
   NGROK_BASIC_AUTH=user:password_fort
   WEBUI_SECRET_KEY=chaine_aleatoire_32_caracteres_minimum
   ```

2. **Démarrer ngrok :**
   ```bash
   docker compose --profile tunnel up -d ngrok
   ```

3. **Récupérer l'URL :**
   ```bash
   docker logs inference-ngrok
   ```

4. **Accès :** `https://xxx.ngrok-free.app` (login/password demandé).

## Dettes Techniques (À résoudre)

1. **Secrets avec fallback** : Supprimer `${VAR:-default}` dans `docker-compose.yml`.
2. **WEBUI_SECRET_KEY faible** : Remplacer par une chaîne aléatoire forte.
3. **Rate-limiting** : Ajouter Nginx/Traefik devant ngrok.
4. **Backup PostgreSQL** : `pg_dump` automatisé.
5. **Alertes Prometheus** : Configurer Alertmanager (VRAM > 95%, latence > 2s).

## Roadmap

1. **Phase 5 :** ngrok + sécurisation des secrets.
2. **Phase 6 :** Multimodal LangGraph (Qwen2-VL-2B CPU).
3. **Phase 7 :** faster-whisper (STT), OCR, bge-m3 (Embedding).
4. **Phase 8 :** RAG avec vector store (ChromaDB / pgvector).
5. **Phase 9 :** Optimisation KV cache, production-ready.

## Licence

MIT License — voir [LICENSE](LICENSE).
