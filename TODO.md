# Projet Inference Stack - Plan d'Action

## Phase 1 : Infrastructure de Base
- [x] Valider l'installation des drivers NVIDIA et du Container Toolkit.
- [x] Créer le `Dockerfile` optimisé pour vLLM (12 Go VRAM, quantification AWQ).
- [x] Déployer et configurer vLLM avec Mistral-7B-Instruct-v0.3-AWQ.
- [x] Vérifier le bon fonctionnement de l'API OpenAI-compatible de vLLM. *(Validé, réponses en français OK)*

## Phase 2 : Gateway & Persistance
- [x] Créer `litellm/config.yaml` (routage vLLM, auth master key, spend tracking DB).
- [x] Valider le schéma PostgreSQL (Prisma auto-migrate + script d'init extensions).
- [x] Déployer et configurer LiteLLM Proxy avec routage et logging.
- [x] Tester la chaîne vLLM → LiteLLM → Client.

## Phase 3 : Interface Utilisateur
- [x] Déployer le service Open WebUI via Docker Compose.
- [x] Connecter Open WebUI au proxy LiteLLM.
- [x] Valider l'expérience utilisateur end-to-end.

## Phase 4 : Observabilité
- [x] Déployer Prometheus pour scraper les métriques vLLM + LiteLLM.
- [x] Configurer Grafana avec provisioning automatique (datasource + dashboard).
- [x] Valider les panels du dashboard (données en temps réel).
- [x] Créer les scripts de benchmark local (qualité, latence, throughput).
- [x] Exécuter le benchmark Mistral-7B et valider la qualité française.
- [x] Créer README.md avec documentation d'ajout de modèle.
- [ ] Configurer les alertes (VRAM > 95%, latence > 2s).

## Phase 5 : Accès Internet (ngrok) & User Management
- [x] Configurer le service ngrok avec profil Docker Compose.
- [x] Créer script de récupération d'URL publique `scripts/get_ngrok_url.py`.
- [x] Créer script de déploiement `scripts/deploy_ngrok.sh`.
- [x] Démarrer ngrok et récupérer l'URL publique.
- [x] Remplacer WEBUI_SECRET_KEY par une clé forte (32+ caractères).
- [x] Changer NGROK_BASIC_AUTH pour un mot de passe fort.
- [ ] Audit sécurité final : vérifier que tous les secrets sont renforcés.
- [x] Configurer LiteLLM self-serve (internal_user budget & key generation).
- [x] Créer script d'onboarding admin `scripts/onboard_user.py`.
- [x] Simplifier Open WebUI (désactiver web search, image gen, code exec, folders, etc.).

## Phase 6 : Multimodalité via LangGraph (CPU)
- [x] Créer le service `multimodal-api` (Dockerfile, requirements, main.py).
- [x] Implémenter le workflow LangGraph : texte → Mistral-7B (GPU), image → DocTR OCR (CPU), audio → faster-whisper (CPU).
- [x] Exposer le modèle multimodal via LiteLLM comme `base-mind` (anciennement `multimodal-agent`).
- [x] Charger `bge-m3` pour embeddings (RAG-ready) via endpoint `/v1/embeddings`.
- [x] Centraliser tous les modèles sur LiteLLM (port 4000) : chat + embeddings.
- [x] Tester end-to-end : OCR image + prompt texte (script `test_multimodal.py`).
- [x] Tester end-to-end : STT audio + prompt texte (script `test_multimodal.py`).
- [x] Benchmark OCR et STT : latence et qualité validées.
- [x] Renommer modèles et sécuriser ports/secrets (PR A).
- [x] Robustesse multimodal : connection pool, validation Pydantic, CORS, healthcheck downstream, limite payload (PR B).
- [x] Optimisation performance : `--max-num-seqs 1`, batch writes LiteLLM, rate limiting, scripts corrigés (PR C).

## Phase 6.5 : Prompt Système Expert Ivoirien pour `base-mind`
**Objectif :** Définir, tester et valider un prompt système robuste qui transforme `base-mind` en assistant expert contextualisé pour la Côte d'Ivoire, sans RAG ni web search (pré-RAG).

**Tâches :**
- [x] Rechercher les best practices pour les system prompts sur Mistral-7B (compliance, anti-hallucination, structure).
- [x] Rédiger le prompt système : identité, règles de sécurité, ton, connaissances statiques ivoiriennes, anti-patterns.
- [x] Injecter le prompt dans le template Jinja vLLM (default system prompt si absent côté client).
- [x] Redémarrer vLLM pour charger le nouveau template.
- [x] Tester la compliance : concision, non-verbosité, pas d'auto-présentation.
- [x] Tester la qualité : français, ton, connaissances locales, refus poli hors-scope.
  - [x] Diagnostiquer et corriger le template Jinja (espaces parasites causant charabia/drift anglais).
  - [x] Durcir prompt système (affirmatif/structuré) et forcer temperature=0.2 + max_tokens=256 via LiteLLM et multimodal-api.
  - [x] Créer et exécuter `scripts/test_full_suite.py` (19 tests par modèle) → **19/19 passés** pour `base-mind` et `base-mind`.
- [x] Documenter les limites constatées (drift anglais, hallus, etc.) dans PROGRESS.md.

**Architecture cible `base-mind` vs `base-mind` :**
- `base-mind` : Chat texte pur, GPU direct (vLLM). Prompt système expert ivoirien. Rapide.
- `base-mind-multimodal` : Multimodal (OCR + STT + texte), CPU+GPU via LangGraph. Réutilise `base-mind` en aval pour la génération.
- `base-mind-search` : **Futur** (Phase 9). Intègre web search + prompt système. Sera un modèle séparé dans LiteLLM.

## Phase 7 : N'Zassa Booster — RAG Expert Local
**Concept :** Transforme le modèle `multimodal-agent` en un assistant expert contextualisé. Pas de fine-tuning. Un prompt système solide + récupération de documents locaux via bge-m3.

**Architecture cible :**
```
Documents locaux → Chunking → bge-m3 embed → ChromaDB (persist)
                                                        ↑
Question utilisateur → bge-m3 embed → ChromaDB query (top-k)
                                                        ↓
                                              Prompt Booster (chunks injectés)
                                                        ↓
                                                   Mistral-7B (GPU)
```

**Tâches :**
- [ ] Choisir vector store : ChromaDB in-process (MVP) ou pgvector (production).
- [ ] Implémenter nœud `retrieve` LangGraph (embed question → query top-3 chunks).
- [ ] Construire le Prompt Booster : instructions système + chunks injectés.
- [ ] Endpoint `/v1/ingest` : upload texte/PDF → chunking (500 tokens, overlap 50) → embed + upsert.
- [ ] Tester end-to-end : upload document → question → réponse basée sur document.
- [ ] Benchmark RAG : latence retrieval + latence LLM, qualité citation.

## Phase 8 : Accès Internet (ngrok) & Sécurisation
- [ ] Démarrer ngrok et récupérer l'URL publique.
- [ ] Remplacer WEBUI_SECRET_KEY par une clé forte (32+ caractères).
- [ ] Changer NGROK_BASIC_AUTH pour un mot de passe fort.
- [ ] Audit sécurité : vérifier que tous les secrets sont renforcés.

## Phase 9 : Optimisation & Production
- [ ] Résoudre les dettes techniques (supprimer fallbacks secrets, renforcer sécurité).
- [ ] Optimiser le KV cache (ajuster `--gpu-memory-utilization` et `--max-model-len`).
- [ ] Mise à jour vLLM vers version stable récente (si compatible).
- [ ] Backup automatique PostgreSQL.
- [ ] Documentation finale utilisateur.

## Architecture Cible

```
Internet → ngrok → Open WebUI
                          ↓
                   LiteLLM Proxy (4000)
                          ↓
              ┌───────────┴───────────┐
              ↓                       ↓
       Mistral-7B (GPU)      multimodal-api (CPU)
       12 Go VRAM            32 Go RAM
       Chat / Génération     Orchestrateur LangGraph
                                   ↓
                     ┌─────────────┼─────────────┐
                     ↓             ↓             ↓
               Mistral-7B    DocTR OCR    faster-whisper
               (GPU)         (CPU, OCR)   (CPU, STT)
                     ↑             ↑             ↑
                     └─────────────┴─────────────┘
                                   ↓
                              bge-m3 (CPU)
                              Embeddings / RAG
                                   ↑
                          ChromaDB / pgvector
                          (Vector Store persist)
                                   ↑
                     Documents locaux (PDF, texte, FAQ)
```
