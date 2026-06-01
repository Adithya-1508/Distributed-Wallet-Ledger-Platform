# Deploy on Kubernetes (k3s)

These manifests run the whole platform on a single-node **k3s** cluster - the
free path is Oracle Cloud's Always-Free **Ampere A1 ARM** VM (up to 4 OCPU /
24 GB RAM). No managed cloud services required; everything (Postgres, Redpanda,
Redis, the API, the workers, the scheduled jobs) runs in-cluster.

## What's here

| File | Resources |
|------|-----------|
| `config.yaml` | ConfigMap (Kafka/Redis URLs) + Secret (DATABASE_URL, JWT_SECRET) |
| `postgres.yaml` | Postgres Deployment + PVC + Service |
| `redpanda.yaml` | Redpanda (Kafka-API) Deployment + Service |
| `redis.yaml` | Redis Deployment + Service |
| `migrate-job.yaml` | Job: `alembic upgrade head` |
| `api.yaml` | FastAPI Deployment (liveness `/health`, readiness `/health/ready`) + Service |
| `workers.yaml` | publisher / notification-consumer / analytics-consumer Deployments |
| `cronjobs.yaml` | reconciliation + analytics-snapshot CronJobs (the k8s-native DAGs) |

All app workloads use one image, `wallet-ledger:latest`, overriding the command.

## 1. Provision (Oracle free tier)

1. Create an **Always-Free Ampere A1** instance (Ubuntu). Pick a quieter region
   if the ARM shape is "out of capacity".
2. Open the API port in the VCN security list if you want external access.
3. Install k3s: `curl -sfL https://get.k3s.io | sh -` then
   `sudo k3s kubectl get nodes`.

## 2. Build the image on the node and import it into k3s

k3s uses containerd, so a local Docker image must be imported (no registry needed):

```bash
docker build -t wallet-ledger:latest .
docker save wallet-ledger:latest | sudo k3s ctr images import -
```

(Or push to a registry - Docker Hub / GHCR / Oracle OCIR - and set the image
reference + `imagePullPolicy: Always` in the manifests.)

## 3. Deploy (order matters)

```bash
kubectl apply -f k8s/config.yaml
kubectl apply -f k8s/postgres.yaml -f k8s/redpanda.yaml -f k8s/redis.yaml
kubectl wait --for=condition=ready pod -l app=postgres --timeout=120s

kubectl apply -f k8s/migrate-job.yaml
kubectl wait --for=condition=complete job/wallet-migrate --timeout=120s

kubectl apply -f k8s/api.yaml -f k8s/workers.yaml -f k8s/cronjobs.yaml
```

## 4. Verify

```bash
kubectl get pods                       # all Running; wallet-migrate Completed
kubectl port-forward svc/wallet-api 8000:80
curl localhost:8000/health             # {"status":"ok"}
curl localhost:8000/health/ready       # {"status":"ready","db":"ok"}
```

For real external access, expose `wallet-api` via the bundled Traefik ingress or
change its Service to `type: NodePort`.

> ⚠️ Edit `config.yaml` first - set a real `JWT_SECRET` and DB password. The
> values shipped here are local-dev defaults.
