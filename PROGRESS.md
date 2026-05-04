# Journal de Projet - Inference Stack

## 2026-05-02 : Initialisation du Projet

**Décision :** Création de l'architecture de base et du plan de déploiement. Le projet vise un prototype local robuste (12 Go VRAM, 32 Go RAM).
**Architecture validée :** vLLM + LiteLLM + PostgreSQL + Open WebUI + Prometheus + Grafana + ngrok.
**Livrables créés :**
- `TODO.md` : Plan de travail structuré en 8 phases.
- `docker-compose.yml` : Orchestration des 7 services.
- `.env.example` : Template centralisé pour la gestion des secrets.
- Structure de dossiers : `vllm/`, `postgres/`, `litellm/`, `prometheus/`, `scripts/`, `models/`, `shared/`.

## 2026-05-02 : Phase 1 - Audit Infrastructure (Agent: vllm-gpu-optimizer)

**Résultat :** Environnement GPU validé.
- GPU : RTX 4080 Laptop (12 Go), driver 580.126.09, CUDA 13.0.
- Config vLLM auditée : cohérente pour 12 Go VRAM.
- **Empreinte VRAM estimée (Mistral-7B AWQ, 8192 ctx) :** ~7 Go sous tension (poids 4.1 Go + KV cache 1 Go + overhead 2 Go), laissant ~4 Go de marge.

## 2026-05-02 : Phase 2 - Configuration LiteLLM & PostgreSQL (Agent: litellm-billing-guardian)

**Résultat :** PostgreSQL et LiteLLM opérationnels.
- PostgreSQL démarré sur le port hôte `5433` (fix conflit).
- LiteLLM proxy démarré sur `localhost:4000`.
- Chaîne vLLM → LiteLLM testée avec succès.

## 2026-05-03 : Phase 3 - Intégration Open WebUI (Agent: ai-gateway-deployer)

**Résultat :** Open WebUI opérationnel sur `localhost:3000`.
- Interface accessible, compte admin créé.
- Chaîne complète validée : User → Open WebUI → LiteLLM → vLLM → Réponse.

## 2026-05-03 : Phase 4 - Audit Sécurité & Tunnel ngrok (Agent: ai-gateway-deployer)

**Corrections appliquées :**
- ngrok : wrapper shell conditionnel pour éviter les flags vides.
- vLLM : alignement des fallbacks secrets.
- LiteLLM : clé `os.environ/VLLM_API_KEY` (plus de hardcoding).
- **Dettes identifiées :** 10 fallbacks secrets, WEBUI_SECRET_KEY faible, pas de rate-limiting.

## 2026-05-03 : Benchmark & Scripts

**Scripts créés :**
- `scripts/benchmark_llama8b.py` : Benchmark qualité/latence/throughput.
- `scripts/benchmark_pipeline.py` : Benchmark overhead LiteLLM Proxy.
- `README.md` : Documentation complète.

**Résultat benchmark Mistral-7B :**
- Throughput : 45.3 tokens/sec
- Latence médiane : 1.26s
- **Jugement :** Suffisant pour chat, insuffisant pour tâches complexes. Français correct mais pas natif.

## 2026-05-04 : Pivot Architecture - 100% Local Multimodal

**Décision :** Abandon de RunPod (budget). Architecture 100% locale avec 12 Go VRAM + 32 Go RAM.
**Nouvelle vision :**
- **GPU (12 Go VRAM) :** Mistral-7B-Instruct-v0.3-AWQ pour chat et génération.
- **CPU (32 Go RAM) :** Qwen2-VL-2B-Instruct pour vision, faster-whisper pour STT, bge-m3 pour embedding.
- **LangGraph :** Orchestrateur multimodal simulant un LLM unifié.
- **Accessibilité :** ngrok pour exposition Internet publique.

## 2026-05-04 : Phase 1 - Validation Finale Mistral-7B

**Résultat :** Modèle Mistral-7B-Instruct-v0.3-AWQ opérationnel.
- Cache : 3.9 Go, conteneur healthy.
- Réponse test : "Je suis un assistant intellectuel créé par les humains pour leur fournir des informations et des services." (Français correct).
- Latence : rapide (test direct < 2s).
- Chaîne complète validée : User → LiteLLM (4000) → vLLM (8000) → Mistral-7B → Réponse.

## 2026-05-04 : Benchmark Mistral-7B Complet

**Script :** `scripts/benchmark_mistral7b.py` (renommé depuis `benchmark_llama8b.py`).
**Résultats :**
- Throughput : **51.3 tokens/sec** (+13% vs précédent run à 45.3).
- Latence médiane : **1.699s** (moyenne 2.539s, min 0.455s, max 5.513s).

**Qualité par tâche :**
- Raisonnement : Correct (effet Rayleigh en 3 étapes), latence 5.5s.
- Créativité : Blague en français, latence 0.9s.
- Connaissance : Capitale = Yamoussoukro (mais mentionne confusion avec Cité administrative).
- Code : Fonction Python + docstring générée, latence 5.0s.
- Résumé : **ÉCHEC** — réponse en anglais malgré prompt français. Le modèle dérive parfois sur les tâches de reformulation.
- Français : Message professionnel chaleureux/formel parfait, latence 1.9s.

**Jugement :** Francophone très correct pour chat et rédaction. Le drift anglais sur le résumé est un biais connu des modèles Mistral entraînés majoritairement sur corpus anglais. Acceptable pour le prototype, à surveiller en production.

## Notes de Transfert

**Stack actuelle :**
- vLLM (8000) → LiteLLM (4000) → Open WebUI (3000) → PostgreSQL (5433).
- Prometheus (9090) + Grafana (3100) configurés, en attente de démarrage.
- ngrok configuré, en attente de token et démarrage.
- Mistral-7B : opérationnel, benchmarké, qualité validée (français natif acceptable).

## 2026-05-04 : Commit Initial sur GitHub

**Action :** Initialisation du dépôt Git et push sur `https://github.com/Hydra16LeGrand/ivorian_inference.git`.
- `.gitignore` créé : exclut `.claude/`, `.env`, `venv/`.
- 15 fichiers commités (architecture complète, benchmarks, docs).
- Branche `main` poussée avec succès.

**Prochaine étape :** Phase 6 (Multimodal LangGraph) comme demandé.
