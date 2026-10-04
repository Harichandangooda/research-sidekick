# Minimal deployment

Run commands from the repository root. Examples use PowerShell; the Docker,
kubectl and Helm commands also work in other shells.

```text
Internet -> nginx Ingress
              | /api (prefix stripped) -> backend-service:8000 -> Backend Deployment
              |                                                   | mysql-service:3306 -> MySQL StatefulSet -> PVC
              |                                                   | chroma-service:8000 -> Chroma StatefulSet -> PVC
              + / -> frontend-service:80 -> Frontend Deployment (Nginx)
```

The browser uses the same host for the UI and `/api`. Ingress rewrites
`/api/auth/login` to `/auth/login`; UI paths retain their original path.
`API_ROOT_PATH=/api` makes FastAPI's generated docs use the external prefix.
The Ingress requires the nginx controller and its regex/rewrite annotations.

## Images and resources

| Component | Image | Resource |
| --- | --- | --- |
| Frontend | `research-sidekick-frontend:0.1.0` | Deployment, ClusterIP Service |
| Backend | `research-sidekick-backend:0.1.0` | Deployment, ClusterIP Service, ConfigMap, external Secret |
| MySQL | `mysql:8.4.11` | One-replica StatefulSet, ClusterIP Service, external Secret, 2Gi PVC |
| Chroma | `chromadb/chroma:1.5.9` | One-replica StatefulSet, ClusterIP Service, 2Gi PVC |

The frontend builds React with Node `22.16.0-alpine` and serves the build with
Nginx `1.28.0-alpine`. The backend uses Python `3.12.12-slim-bookworm`, uv
`0.11.8`, frozen `uv.lock` dependencies, and one Uvicorn worker on port 8000.
The locked Chroma Python client matches the server's `1.5.9` version.
No frontend ConfigMap is needed: `/api` is compiled into its static bundle.
To change that URL, rebuild with `--build-arg REACT_APP_API_BASE_URL=/api`.

Backend liveness (`/health/live`) checks only the process. Readiness
(`/health/ready`) runs `SELECT 1` and a Chroma HTTP heartbeat with a three-second
timeout; failures return 503. Liveness runs without waiting for a worker thread,
and the embedding library loads once on first use rather than during API startup,
including when several PDFs are uploaded concurrently.
The existing `/health` endpoint remains available. MySQL may still be initializing
when the backend first starts; Kubernetes restarts the backend until it can connect.

All four Services are ClusterIP. Pods discover `mysql-service` and
`chroma-service` through Kubernetes DNS in their namespace; for example,
`mysql-service.research-sidekick.svc.cluster.local`. The backend connects using
these service names, never Pod IPs. Browser requests go through Ingress because
cluster DNS names are not accessible to browsers outside the cluster.

## Configuration and persistence

`backend-config` supplies `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_DATABASE`,
`CHROMA_HOST`, `CHROMA_PORT`, `API_ROOT_PATH`, `JWT_ALGORITHM` and
`JWT_EXPIRE_MINUTES`. Credentials come from `mysql-secret` and `backend-secret`.
The backend receives the MySQL application password, not the root password.
Environment values take precedence over a local `.env` file.

MySQL stores users, sessions, messages, paper text/metadata, reports and retry
records in `/var/lib/mysql`. Chroma stores chunks and embeddings in `/data`,
the image's configured persistence path. StatefulSet claim templates create
`data-mysql-0` and `data-chromadb-0`. The cluster must have a default StorageClass;
Minikube normally provides one. These PVCs are retained when Pods are recreated
and by default when StatefulSets or the Helm release are removed.

MySQL environment credentials/database initialize an **empty** volume only.
Changing the Secret later does not change MySQL accounts automatically.
Changing `MYSQL_DATABASE` on a populated PVC requires deliberate database setup.
This phase creates the MySQL schema but does not migrate existing SQLite records
or an existing local Chroma index. Keep those local files if you need them later.

Uploads currently stay in memory (with possible temporary multipart spooling).
Extracted PDF text and metadata persist in MySQL; embeddings persist in Chroma.
Original PDF bytes are **not retained**, so original-file download/recovery is a
known limitation. No PDF filesystem storage redesign is included.

## Start Minikube and build images

Start Docker Desktop with Linux containers first, then:

```powershell
minikube start --driver=docker --cpus=4 --memory=8192
minikube addons enable ingress
kubectl config use-context minikube
kubectl get storageclass
docker build -t research-sidekick-backend:0.1.0 -f backend/Dockerfile .
docker build -t research-sidekick-frontend:0.1.0 -f frontend/research-sidekick/Dockerfile .
minikube image load research-sidekick-backend:0.1.0
minikube image load research-sidekick-frontend:0.1.0
```

The Python/ML dependencies make the backend image relatively large. The embedding
model downloads on first use and needs outbound network access; its container
cache is ephemeral. OpenAI requests also need network access and a valid API key.
For a remote cluster, push the two application images to a registry and update
their image references in YAML or Helm values.

## Create real Secrets locally (both deployment methods)

```powershell
kubectl apply -f k8s/namespace.yaml
Copy-Item deployment/backend.env.example deployment/backend.env
Copy-Item deployment/mysql.env.example deployment/mysql.env
uv run python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Edit the two `.env` copies with your own JWT secret, OpenAI key and MySQL passwords.
These local copies are Git-ignored; never commit real credentials. Then:

```powershell
kubectl -n research-sidekick create secret generic backend-secret --from-env-file=deployment/backend.env
kubectl -n research-sidekick create secret generic mysql-secret --from-env-file=deployment/mysql.env
```

`k8s/backend/secret.example.yaml` and `k8s/mysql/secret.example.yaml` document the
same Secret shapes. Do not apply their placeholder values. The Helm chart
references these external Secrets and contains no credentials or Secret template.

## Deploy raw YAML

Apply explicit paths so example Secrets are excluded:

```powershell
kubectl apply -f k8s/backend/configmap.yaml
kubectl apply -f k8s/mysql/service.yaml -f k8s/mysql/statefulset.yaml
kubectl apply -f k8s/chromadb/service.yaml -f k8s/chromadb/statefulset.yaml
kubectl apply -f k8s/backend/service.yaml -f k8s/backend/deployment.yaml
kubectl apply -f k8s/frontend/service.yaml -f k8s/frontend/deployment.yaml
kubectl apply -f k8s/ingress.yaml
kubectl -n research-sidekick rollout status deployment/backend --timeout=300s
kubectl -n research-sidekick rollout status deployment/frontend --timeout=300s
```

## Deploy Helm (alternative to raw YAML)

Use a fresh namespace installation; raw YAML resources and Helm resources have
the same names and should not be installed together. There is one release per
namespace. Namespace creation belongs to Helm's `--create-namespace`, so the
chart contains no Namespace template.

```powershell
helm lint ./helm/research-sidekick
helm template research-sidekick ./helm/research-sidekick --namespace research-sidekick
helm package ./helm/research-sidekick
helm install research-sidekick ./research-sidekick-0.1.0.tgz --namespace research-sidekick --create-namespace
helm upgrade research-sidekick ./research-sidekick-0.1.0.tgz --namespace research-sidekick
helm uninstall research-sidekick --namespace research-sidekick
```

Edit `values.yaml` or supply `--values deployment/local-values.yaml` for image
repositories/tags, Deployment replica counts, Service ports, storage sizes,
frontend/backend resources, ingress host/paths and non-sensitive configuration.
Service ports can vary; container listening ports remain 80/8000/3306/8000.
Changing the API prefix requires matching ingress regex, `config.apiRootPath`
and a rebuilt frontend API URL. MySQL and Chroma always have one replica.
Keep the backend at one replica for the current process-local chat serialization.
Restart the backend after configuration or Secret changes:

```powershell
kubectl -n research-sidekick rollout restart deployment/backend
```

## Access and verify

On Windows with the Docker driver, use a port-forward to the Ingress controller
to avoid relying on direct access to the Minikube node IP:

```powershell
kubectl -n ingress-nginx rollout status deployment/ingress-nginx-controller --timeout=300s
kubectl -n ingress-nginx port-forward service/ingress-nginx-controller 8080:80
```

Add `127.0.0.1 research-sidekick.local` to your hosts file, then open
`http://research-sidekick.local:8080`. Without a hosts edit, verify in another terminal:

```powershell
curl.exe -H "Host: research-sidekick.local" http://127.0.0.1:8080/
curl.exe -H "Host: research-sidekick.local" http://127.0.0.1:8080/api/health/live
curl.exe -H "Host: research-sidekick.local" http://127.0.0.1:8080/api/health/ready
curl.exe -H "Host: research-sidekick.local" http://127.0.0.1:8080/api/openapi.json
kubectl -n research-sidekick get pods,services,ingress,pvc
kubectl -n research-sidekick logs deployment/backend
kubectl -n research-sidekick describe pod mysql-0
kubectl -n research-sidekick get events --sort-by=.lastTimestamp
```

Register, create a session and upload a text-based PDF to verify the application
flow. To verify persistence independently of paid API calls or embedding downloads:

```powershell
python deployment/verify_persistence.py research-sidekick
```

The script writes isolated MySQL and Chroma markers, deletes `mysql-0` and
`chromadb-0`, waits for replacement Pods, verifies the same rows/documents and
PVC UIDs, then removes its markers. It deliberately interrupts the two databases;
run it against your local test installation. Existing application data is retained.
Do not delete PVCs or the namespace when testing persistence.

## Validation

```powershell
helm template research-sidekick ./helm/research-sidekick --namespace research-sidekick --output-dir .validation/helm
uv run python deployment/validate_manifests.py k8s .validation/helm
kubeconform -strict -summary -kubernetes-version 1.34.0 k8s .validation/helm
uv run python -m unittest discover -s tests -v
```

Checks performed in this workspace: Helm lint/render/package; Kubernetes 1.34
schema validation of raw and rendered resources; exact default-chart/raw parity;
selectors, Service/Pod ports, DNS configuration, Secret references, PVC mounts,
probe endpoints and ingress rewrite behavior. All 43 backend tests and 17 frontend
tests passed, the React production build succeeded, Python compilation passed
and `uv lock --check` passed. Custom namespace/Service-port rendering also passed.

Both Docker images were built successfully and the application was deployed to
Minikube. All four Pods were running; backend readiness and the corrected discovery
schema were verified inside the deployed backend. The research flow through Ingress
was confirmed working by the user. StatefulSet persistence through Pod recreation
still needs the verification script above. TLS, backups, data migration and durable
original PDF storage remain later phases.

Image behavior references: [MySQL official image](https://hub.docker.com/_/mysql/),
[Chroma 1.5.9 Docker persistence configuration](https://github.com/chroma-core/chroma/blob/1.5.9/rust/frontend/sample_configs/docker_single_node.yaml).
