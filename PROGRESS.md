# Journal de Bord - Inference Stack

## 2026-05-10 — Phase 6.5 : Validation Finale 19/19 Qualité API

**Problème constaté :** La suite de tests `scripts/test_full_suite.py` affichait 17/19, puis 18/19, avec deux échecs persistants :
1. `base-mind` B5 (résumé) → réponse remplacée par `"Salut."` à cause d'une détection de salutation trop laxiste.
2. `ivoire-mind` D1 (prompt vide) → auto-présentation car le template Jinja n'avait pas d'exemple pour message vide.

**Racine :**
1. Le post-processor `multimodal-api/main.py` utilisait `any(w in lower_user for w in _SALUTATION_KEYWORDS)`. Le mot-clé `"hi"` matchait en sous-chaîne dans `"machine"`, `"chimique"`, etc., déclenchant à tort le raccourcissement forcé.
2. Le template Jinja ne fournissait aucun few-shot pour un `content` vide, laissant Mistral-7B halluciner une auto-présentation par défaut.

**Solution :**
1. Remplacement de la détection naïve par une regex avec word-boundaries : `_SALUTATION_RE = re.compile(r"(?i)\b(salut|bonjour|coucou|hey|hello|hi)\b")`.
2. Ajout d'un exemple vide dans le template Jinja : `Question='' -> Réponse='Je n'ai pas compris.'`.

**Résultat :** Suite complète relancée → **19/19 passés** pour `ivoire-mind` et `base-mind`. Les devs utilisant l'API LiteLLM (port 4000) ou le playground Open WebUI ont maintenant une expérience prévisible et contrôlée.

## 2026-05-09 — Phase 6.5 : Correction Template Jinja (Charabia & Drift Anglais)

**Problème constaté :** `ivoire-mind` génère du charabia, `base-mind` dérive en anglais sur le playground Open WebUI.

**Racine :** Le template Jinja `vllm_chat_template.jinja` était truffé d'espaces et sauts de ligne hors des balises Jinja. Ces whitespaces sont rendus littéralement dans le prompt final et tokenisés comme du bruit par vLLM. Sur un prompt court le modèle compensait, sur des conversations multi-turn ou des prompts riches il déraillait complètement.

**Solution :**
1. Réécriture du template avec `{%- ... -%}` (strip whitespace avant/après chaque bloc) pour garantir un prompt compact et conforme au format Mistral-7B-Instruct-v0.3.
2. Création de `scripts/test_quality.py` : panel de 6 prompts (salutation, raisonnement, culture locale, refus, conversation, résumé) avec vérification automatique de charabia, drift anglais, cohérence sémantique et auto-présentation.

**Commande de redémarrage nécessaire :**
```bash
docker compose up -d --force-recreate vllm
```
Puis exécuter `python scripts/test_quality.py`.

## 2026-05-09 (suite) — Phase 6.5 : Durcissement Prompt Système & Paramètres par Défaut

**Problème constaté :** Malgré le template corrigé, le modèle génère encore des réponses verbeuses, auto-présentatrices, et en français cassé (ex: "Je suis optimisé pour...", "rizosn").

**Analyse :** Le prompt système était formulé en négatif ("Tu ne te présentes JAMAIS"). Les LLMs, et particulièrement les modèles alignés avec RLHF, ignorent souvent les interdictions pour suivre leur comportement d'assistant "helpful" par défaut. De plus, la température par défaut (~0.7) laisse trop de liberté créative.

**Solution :**
1. **Prompt système affirmatif et structuré** dans `vllm_chat_template.jinja` et `multimodal-api/main.py`. 5 règles numérotées positives : "Réponds directement", "Sois concis", "Ne dis jamais...".
2. **`temperature: 0.2`** et **`max_tokens: 256`** forçés par défaut dans `litellm/config.yaml` (ivoire-mind) et dans `multimodal-api/main.py` (base-mind). Le client peut override, mais la baseline est stricte.

**Commandes de redémarrage nécessaires :**
```bash
docker compose up -d --force-recreate vllm litellm multimodal-api
```
Puis exécuter `python scripts/test_quality.py`.

## 2026-05-06 — Phase 4 : Grafana Provisioning Automatique

**Problème :** Grafana démarrait vide (datasource Prometheus manuel à créer, dashboard à importer à la main).

**Solution :** Mise en place du provisioning as-code.

1. **Datasource auto-configuré :** `grafana/provisioning/datasources/prometheus.yml` pointe vers `http://prometheus:9090`.
2. **Dashboard auto-chargé :** `grafana/provisioning/dashboards/dashboard.yml` scanne `/var/lib/grafana/dashboards` et charge `inference-stack.json` (7 panels : VRAM gauge, requêtes, throughput, latence p95, erreurs, RAM, request rate).
3. **docker-compose.yml mis à jour :** Volumes read-only montés pour datasources, dashboards provider, et dashboards JSON. Sécurité renforcée (signup désactivé, gravatar off).

**Commande de redémarrage :**
```bash
docker compose up -d --force-recreate grafana
```

**À valider après redémarrage :**
- `http://127.0.0.1:3100` → login admin / password `.env GF_SECURITY_ADMIN_PASSWORD`
- Dashboard "Inference Stack" visible directement dans "General"
- 7 panels avec données (vLLM, LiteLLM, multimodal-api doivent être UP dans Prometheus).
