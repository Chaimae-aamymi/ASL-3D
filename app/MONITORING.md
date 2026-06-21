# Monitoring ASL-3D — Prometheus, Loki, Grafana

## Démarrage rapide

```powershell
cd app
docker compose up -d prometheus loki promtail grafana
# App locale (métriques) :
python app.py
```

| Service    | URL                         | Identifiants      |
|-----------|-----------------------------|-------------------|
| Grafana   | http://localhost:3000       | admin / admin     |
| Prometheus| http://localhost:9090       | —                 |
| Loki      | http://localhost:3100/ready | —                 |
| Métriques | http://127.0.0.1:5000/metrics | —             |

Dashboard provisionné : **ASL-3D — Vue d'ensemble**

## Architecture

- **Prometheus** scrape `/metrics` sur `app:5000` (Docker) ou `host.docker.internal:5000` (app sur Windows).
- **Promtail** envoie les logs des conteneurs `asl3d-*` vers **Loki**.
- **Grafana** utilise les datasources Prometheus + Loki (fichiers dans `grafana/provisioning/`).

## Vérifier que tout fonctionne

```powershell
# Métriques Flask
curl http://127.0.0.1:5000/metrics

# Prometheus cible UP
# Status → Targets → asl3d-app-host ou asl3d-app-docker = UP

# Loki prêt
curl http://localhost:3100/ready

# Logs dans Grafana → Explore → Loki → {job="asl3d"}
```

## Erreurs fréquentes

| Symptôme | Cause | Solution |
|----------|--------|----------|
| Target **DOWN** dans Prometheus | App non lancée ou mauvaise cible | Lancer `python app.py` ; vérifier le job `asl3d-app-host` |
| Loki **crash** au démarrage | Ancienne config (`boltdb-shipper`, `enforce_metric_name`) | Utiliser `loki-config.yml` fourni (Loki 2.9) |
| Grafana **Datasource error** | Prometheus/Loki pas prêts | `docker compose ps` ; attendre `healthy` |
| Pas de logs dans Loki | Promtail 2.9 + Docker API 1.44 | Image `grafana/promtail:3.3.2` (voir docker-compose) |
| `client version 1.42 is too old` dans logs promtail | Même cause | `docker compose pull promtail && docker compose up -d promtail` |
| Pas de logs dans Loki | Promtail absent ou socket Docker | `docker compose up promtail` ; Docker Desktop actif |
| `503` sur `/metrics` | `prometheus-client` non installé | `pip install prometheus-client` |

## Métriques exposées

- `asl3d_requests_total{method, endpoint}`
- `asl3d_request_duration_seconds{endpoint}`
- `asl3d_active_tasks{task_type}` — `sfm` | `yolo`
- `asl3d_projects_total`

## Stack complète avec l'app en Docker

```powershell
docker compose up -d --build
```

Prometheus utilisera alors la cible `asl3d-app-docker` (`app:5000`).
