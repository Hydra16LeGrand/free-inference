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
- [ ] Déployer Prometheus pour scraper les métriques vLLM + LiteLLM.
- [ ] Déployer Grafana avec dashboards (VRAM, latence p95, throughput, erreurs).
- [x] Créer les scripts de benchmark local (qualité, latence, throughput).
- [x] Exécuter le benchmark Mistral-7B et valider la qualité française.
- [x] Créer README.md avec documentation d'ajout de modèle.
- [ ] Configurer les alertes (VRAM > 95%, latence > 2s).

## Phase 5 : Accès Internet (ngrok)
- [ ] Démarrer ngrok et récupérer l'URL publique.
- [ ] Remplacer WEBUI_SECRET_KEY par une clé forte (32+ caractères).
- [ ] Changer NGROK_BASIC_AUTH pour un mot de passe fort.
- [ ] Audit sécurité : vérifier que tous les secrets sont renforcés.

## Phase 6 : Multimodalité via LangGraph
- [x] Créer le service `multimodal-api` (Dockerfile, requirements, main.py).
- [x] Implémenter le workflow LangGraph : texte → Mistral-7B (GPU), image → Qwen2-VL (CPU) → réponse unifiée.
- [x] Exposer le modèle multimodal via LiteLLM comme `multimodal-agent`.
- [ ] Déployer Qwen2-VL-2B-Instruct sur CPU (32 Go RAM) pour Vision.
- [ ] Tester end-to-end : upload image + prompt texte dans Open WebUI.

## Phase 7 : Capacités Avancées (CPU)
- [ ] Intégrer `faster-whisper` (STT) pour transcription vocale.
- [ ] Intégrer un modèle OCR (PaddleOCR ou Qwen2-VL natif).
- [ ] Intégrer `bge-m3` (Embedding) pour RAG et recherche sémantique.
- [ ] Connecter ces capacités au workflow LangGraph.

## Phase 8 : Optimisation & Production
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
                            ┌─────┴─────┐
                            ↓           ↓
                     Mistral-7B     Qwen2-VL-2B
                     (GPU)         (CPU, Vision+OCR)
```
