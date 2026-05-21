# Déploiement — Free Inference en ligne

Ce guide explique comment rendre Free Inference accessible depuis Internet avec un nom de domaine propre, via Cloudflare Tunnel.

## Architecture

```
[Internet] → [Cloudflare] → [Cloudflare Tunnel] → [Nginx] → [Services Docker]
                                      ↑
                              Ton PC local (GPU)
```

**Sous-domaines :**
- `tondomaine.com` → Landing page (présentation)
- `chat.tondomaine.com` → Open WebUI
- `api.tondomaine.com` → LiteLLM Proxy (API clés)
- `dash.tondomaine.com` → Grafana (admin)

**Sécurité :**
- Prometheus reste en `127.0.0.1` (pas exposé)
- vLLM reste sur le réseau Docker interne (jamais public)
- Rate limiting Nginx + Cloudflare DDoS protection

---

## Étape 1 — Prérequis

1. **Domaine** acheté sur Hostinger (ou autre registrar)
2. **Compte Cloudflare** (gratuit sur [cloudflare.com](https://cloudflare.com))
3. **Ton PC** avec GPU NVIDIA, Docker et Docker Compose installés

---

## Étape 2 — Configurer Cloudflare

### 2.1 Ajouter ton domaine à Cloudflare

1. Va sur [dash.cloudflare.com](https://dash.cloudflare.com)
2. Clique **Add a Site**, entre ton domaine
3. Sélectionne le plan **Free**
4. Cloudflare te donnera deux **nameservers** (ex: `bob.ns.cloudflare.com`, `lara.ns.cloudflare.com`)

### 2.2 Changer les nameservers chez Hostinger

1. Connecte-toi à ton compte Hostinger
2. Va dans **Domaines** > **Gestion DNS** (ou **Nameservers**)
3. Remplace les nameservers Hostinger par ceux de Cloudflare
4. Attends 5–60 minutes que la propagation DNS se fasse

### 2.3 Créer le Tunnel Cloudflare

1. Dans Cloudflare dashboard, va sur **Zero Trust** > **Access** > **Tunnels**
2. Clique **Create a tunnel**
3. Choisis **Cloudflared**
4. Donne un nom : `free-inference-tunnel`
5. Copie le **Tunnel Token** (c'est la valeur pour `CLOUDFLARE_TUNNEL_TOKEN`)

### 2.4 Configurer les routes publiques

Dans l'interface du tunnel, ajoute 4 **Public Hostnames** :

| Subdomain | Domain | Service Type | URL |
|---|---|---|---|
| `@` | `tondomaine.com` | HTTP | `http://nginx:80` |
| `chat` | `tondomaine.com` | HTTP | `http://nginx:80` |
| `api` | `tondomaine.com` | HTTP | `http://nginx:80` |
| `dash` | `tondomaine.com` | HTTP | `http://nginx:80` |

> Nginx utilise le header `Host` pour router vers le bon service. Tout passe par le même port 80 de Nginx.

---

## Étape 3 — Configurer Free Inference

### 3.1 Éditer `.env`

```bash
cp .env.example .env
nano .env
```

Ajoute ou modifie :
```env
CLOUDFLARE_TUNNEL_TOKEN=eyJh...  # Le token copié dans Cloudflare
```

### 3.2 Personnaliser Nginx

Ouvre `nginx/conf.d/default.conf` et remplace **les 4 occurrences** de `tondomaine.com` par ton vrai domaine.

```bash
sed -i 's/tondomaine.com/mon-domaine.com/g' nginx/conf.d/default.conf
```

### 3.3 Personnaliser la landing page

Ouvre `landing/index.html` et modifie les liens :
- `https://chat.tondomaine.com` → ton vrai sous-domaine
- `https://api.tondomaine.com` → ton vrai sous-domaine
- `https://dash.tondomaine.com` → ton vrai sous-domaine

---

## Étape 4 — Lancer

```bash
docker compose up -d
```

Les nouveaux services (`nginx`, `cloudflared`) démarrent automatiquement.

Vérifie que tout est vert :
```bash
docker compose ps
```

---

## Étape 5 — Vérifier

Attends 1–2 minutes que Cloudflare Tunnel s'établisse, puis teste :

```bash
# Landing page
curl -I https://tondomaine.com

# API (doit retourner 401 sans clé)
curl -I https://api.tondomaine.com/v1/models

# WebUI
curl -I https://chat.tondomaine.com
```

---

## Dépannage

### Le tunnel ne se connecte pas
```bash
docker logs inference-cloudflared
```
Vérifie que le token est correct et que le domaine est bien actif sur Cloudflare.

### Nginx renvoie 502 Bad Gateway
```bash
docker logs inference-nginx
docker compose ps
```
Vérifie que les services cibles (open-webui, litellm, grafana) sont bien `healthy`.

### Les sous-domaines ne répondent pas
Attends que le DNS se propage (jusqu'à 24h, souvent 5 min). Vérifie avec :
```bash
nslookup chat.tondomaine.com
```
Doit retourner une IP Cloudflare.

---

## Prochaines étapes suggérées

- **HTTPS auto** : Cloudflare gère déjà le SSL (HTTPS) entre l'utilisateur et Cloudflare. Le trafic Tunnel→Nginx est chiffré par le tunnel lui-même. Pas besoin de certificat Let's Encrypt local.
- **Firewall Cloudflare** : Dans le dashboard Cloudflare, active **Bot Fight Mode** et configure des règles de rate limiting supplémentaires.
- **Authentication** : Pour `dash.tondomaine.com`, active **Cloudflare Access** (Zero Trust) pour forcer une authentification email/Google avant d'accéder à Grafana.
