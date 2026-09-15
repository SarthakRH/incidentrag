# IncidentRAG AWS Lightsail Deployment Guide

This guide explains how to host IncidentRAG on AWS in the most cost-conscious way while keeping the deployment understandable and maintainable.

The recommended deployment is a single Amazon Lightsail Linux instance running Docker Compose. It hosts:

- FastAPI backend
- Streamlit UI
- Neo4j
- Qdrant
- Redis
- Optional OpenTelemetry collector
- Caddy reverse proxy for HTTPS

This is intentionally simpler and cheaper than the existing EKS deployment path in `deploy/README.md`.

## 1. Recommended AWS Architecture

Use one Lightsail instance as the full application host:

```text
User Browser
    |
    | HTTPS :443
    v
Caddy reverse proxy
    |
    | internal Docker network
    v
Streamlit UI ---> FastAPI backend
                    |
                    +--> Neo4j
                    +--> Qdrant
                    +--> Redis
                    +--> GitHub API
                    +--> OpenRouter / model provider
```

Only ports `80`, `443`, and restricted `22` should be open publicly.

Do not expose Neo4j, Qdrant, Redis, or the FastAPI backend directly to the internet.

## 2. Why Lightsail Is The Cheapest Practical Option

The project currently needs several always-on services. Serverless hosting is not a natural fit because Neo4j, Qdrant, Redis, FastAPI, and Streamlit all need runtime state or long-lived processes.

For the lowest practical AWS bill, use:

- Amazon Lightsail instead of EKS.
- Docker Compose instead of Kubernetes.
- Local Docker volumes instead of managed databases.
- A root-owned `.env` file instead of paid secret managers for the first deployment.
- One static IP attached to the instance.
- Manual deploys from SSH until production traffic justifies CI/CD.

Recommended instance size:

- Start with `8 GB RAM / 2 vCPU / 160 GB SSD`.
- Approximate base price: `$44/month` for the Lightsail Linux bundle with public IPv4.
- A `4 GB RAM / 2 vCPU / 80 GB SSD` instance is cheaper at about `$24/month`, but this stack may become memory constrained because Neo4j, Qdrant, Redis, FastAPI, and Streamlit all run on the same host.

Avoid EKS for this cost target. EKS has a control-plane fee of `$0.10/hour`, which is roughly `$73/month` before paying for worker nodes, storage, load balancers, or public IPs.

Current AWS references:

- Lightsail bundle prices: https://aws.amazon.com/lightsail/pricing/
- Lightsail bundle details: https://docs.aws.amazon.com/lightsail/latest/userguide/amazon-lightsail-bundles.html
- Lightsail static IP behavior: https://docs.aws.amazon.com/lightsail/latest/userguide/understanding-static-ip-addresses-in-amazon-lightsail.html
- EKS pricing: https://aws.amazon.com/eks/pricing/

## 3. Prerequisites

You need:

- An AWS account.
- Access to Amazon Lightsail.
- A GitHub token for repository issue access.
- An OpenRouter or model-provider API key.
- Optional: a domain name, for example `incidentrag.example.com`.

Local tools that are helpful:

- Git
- SSH client
- A terminal

You do not need Docker Desktop locally if you build the containers directly on the Lightsail instance.

## 4. Create The Lightsail Instance

1. Open the AWS Console.
2. Go to `Lightsail`.
3. Choose `Create instance`.
4. Select a region close to your users.
   - For India-based use, choose `Mumbai / ap-south-1`.
   - For US-based use, choose the nearest US region.
5. Select `Linux/Unix`.
6. Choose `Ubuntu 24.04 LTS` if available.
7. Choose the `8 GB RAM` bundle.
8. Name the instance:

```text
incidentrag-prod
```

9. Create the instance.

After it starts, create and attach a static IP:

1. In Lightsail, open `Networking`.
2. Choose `Create static IP`.
3. Attach it to `incidentrag-prod`.
4. Name it:

```text
incidentrag-prod-ip
```

Keep the static IP attached. Attached Lightsail static IPs do not add a separate charge, but unattached static IPs can be billed.

## 5. Configure Firewall Ports

In the Lightsail instance networking tab, allow:

- `HTTP`, TCP `80`, from `0.0.0.0/0`
- `HTTPS`, TCP `443`, from `0.0.0.0/0`
- `SSH`, TCP `22`, only from your current public IP if possible

Remove public access for:

- `8000`
- `8501`
- `7474`
- `7687`
- `6333`
- `6334`
- `6379`
- `4317`
- `4318`
- `8888`

Those should stay private inside Docker.

## 6. Point DNS To Lightsail

If you have a domain, create an `A` record:

```text
incidentrag.example.com -> YOUR_LIGHTSAIL_STATIC_IP
```

Use your DNS provider, Route 53, Cloudflare, GoDaddy, or wherever the domain is managed.

Wait until DNS resolves before enabling HTTPS. You can test it from your computer:

```powershell
nslookup incidentrag.example.com
```

If you do not have a domain yet, you can still run the app over HTTP using the Lightsail IP. For a real deployment, use a domain so Caddy can issue a trusted HTTPS certificate.

## 7. Connect To The Instance

From the Lightsail console, you can use the browser SSH button.

Or connect from your terminal:

```powershell
ssh ubuntu@YOUR_LIGHTSAIL_STATIC_IP
```

If you downloaded a Lightsail SSH key, specify it:

```powershell
ssh -i C:\path\to\LightsailDefaultKey.pem ubuntu@YOUR_LIGHTSAIL_STATIC_IP
```

## 8. Install Docker And Git On The Instance

Run these commands on the Lightsail instance:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg git ufw

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

. /etc/os-release
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $VERSION_CODENAME stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

sudo usermod -aG docker ubuntu
```

Log out and back in so the `ubuntu` user can run Docker without `sudo`.

Verify Docker:

```bash
docker version
docker compose version
```

## 9. Copy Or Clone The Project

Create the deployment directory:

```bash
sudo mkdir -p /opt/incidentrag
sudo chown ubuntu:ubuntu /opt/incidentrag
cd /opt/incidentrag
```

If the project is in GitHub, clone it:

```bash
git clone YOUR_REPOSITORY_URL .
```

If the project is not pushed to GitHub yet, copy it from your local machine:

```powershell
scp -r E:\IncidentRAG+refine ubuntu@YOUR_LIGHTSAIL_STATIC_IP:/opt/incidentrag
```

If you use `scp`, make sure the files land directly under `/opt/incidentrag` and not under a nested `/opt/incidentrag/IncidentRAG+refine` directory.

## 10. Create The Production Environment File

On the Lightsail instance:

```bash
cd /opt/incidentrag
cp .env.example .env
chmod 600 .env
```

Edit the file:

```bash
nano .env
```

Set production values. The exact keys depend on your current `.env.example`, but expect values like:

```bash
OPENROUTER_API_KEY=your_openrouter_key
GITHUB_TOKEN=your_read_only_github_token
INCIDENTRAG_API_KEY=generate_a_long_random_value

NEO4J_URI=bolt://neo4j:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=change_this_password

QDRANT_URL=http://qdrant:6333
REDIS_URL=redis://redis:6379/0
INCIDENTRAG_API_URL=http://api:8000
```

Generate a strong shared API key:

```bash
openssl rand -hex 32
```

Do not commit `.env`. Do not paste secret values into screenshots, shell history, GitHub Actions logs, or chat.

For lowest cost, a locked-down `.env` file is acceptable for a small private deployment. For stronger production security later, move secrets into AWS Secrets Manager or SSM Parameter Store.

## 11. Create A Production Docker Compose File

Create a production-only compose file on the server:

```bash
nano docker-compose.prod.yml
```

Paste:

```yaml
services:
  caddy:
    image: caddy:2-alpine
    container_name: incidentrag-caddy
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/caddy/Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - ui
    restart: unless-stopped

  neo4j:
    image: neo4j:5.15-community
    container_name: incidentrag-neo4j
    environment:
      NEO4J_AUTH: "neo4j/${NEO4J_PASSWORD}"
      NEO4J_PASSWORD: "${NEO4J_PASSWORD}"
      NEO4J_PLUGINS: '["apoc"]'
      NEO4J_dbms_security_procedures_unrestricted: "apoc.*"
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD-SHELL", "cypher-shell -u neo4j -p \"$${NEO4J_PASSWORD}\" 'RETURN 1'"]
      interval: 15s
      timeout: 10s
      retries: 10
    restart: unless-stopped

  qdrant:
    image: qdrant/qdrant:v1.11.0
    container_name: incidentrag-qdrant
    volumes:
      - qdrant_data:/qdrant/storage
    restart: unless-stopped

  redis:
    image: redis:7.2-alpine
    container_name: incidentrag-redis
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 10
    restart: unless-stopped

  api:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: incidentrag-api
    env_file: .env
    environment:
      NEO4J_URI: bolt://neo4j:7687
      QDRANT_URL: http://qdrant:6333
      REDIS_URL: redis://redis:6379/0
    depends_on:
      neo4j:
        condition: service_healthy
      qdrant:
        condition: service_started
      redis:
        condition: service_healthy
    restart: unless-stopped

  ui:
    build:
      context: .
      dockerfile: Dockerfile.ui
    container_name: incidentrag-ui
    env_file: .env
    environment:
      INCIDENTRAG_API_URL: http://api:8000
    depends_on:
      - api
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
  neo4j_data:
  neo4j_logs:
  qdrant_data:
  redis_data:
```

This file intentionally does not publish database ports.

## 12. Create The Caddy HTTPS Config

Create the Caddy directory:

```bash
mkdir -p deploy/caddy
nano deploy/caddy/Caddyfile
```

If you have a domain, paste:

```caddyfile
incidentrag.example.com {
    encode gzip
    reverse_proxy ui:8501
}
```

Replace `incidentrag.example.com` with your real hostname.

If you do not have a domain yet and only want temporary HTTP access by IP, paste:

```caddyfile
:80 {
    encode gzip
    reverse_proxy ui:8501
}
```

The domain version is strongly preferred because Caddy can automatically issue and renew HTTPS certificates.

## 13. Start The Application

From `/opt/incidentrag`:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Check containers:

```bash
docker compose -f docker-compose.prod.yml ps
```

Watch startup logs:

```bash
docker compose -f docker-compose.prod.yml logs -f --tail=100
```

The first build can take several minutes on a small instance.

## 14. Validate The Deployment

Check the backend from inside the Docker network:

```bash
docker compose -f docker-compose.prod.yml exec api curl -f http://localhost:8000/health
```

Check the UI container:

```bash
docker compose -f docker-compose.prod.yml exec ui python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8501/_stcore/health').status)"
```

Open the app:

```text
https://incidentrag.example.com
```

or, for temporary IP-only HTTP:

```text
http://YOUR_LIGHTSAIL_STATIC_IP
```

Then run a smoke test:

1. Search for `repo-server`.
2. Select one returned incident.
3. Start analysis.
4. Confirm the assessment graph renders.
5. Confirm the result includes diagnosis, evidence, and remediation text.

## 15. Troubleshooting

If the site does not load:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs caddy --tail=100
docker compose -f docker-compose.prod.yml logs ui --tail=100
```

If the UI loads but says the backend is unavailable:

```bash
docker compose -f docker-compose.prod.yml logs api --tail=200
docker compose -f docker-compose.prod.yml exec api curl -v http://localhost:8000/health
```

If analysis fails:

```bash
docker compose -f docker-compose.prod.yml logs api --tail=300
```

Common causes:

- Missing or invalid `OPENROUTER_API_KEY`.
- Missing or invalid `GITHUB_TOKEN`.
- DNS has not propagated yet.
- Lightsail firewall does not allow ports `80` and `443`.
- `.env` points to `localhost` instead of Docker service names.
- Neo4j password in `.env` does not match `NEO4J_AUTH`.
- Instance is too small and containers are being killed due to memory pressure.

Check memory:

```bash
free -h
docker stats
```

If memory is consistently tight, resize to the next Lightsail bundle.

## 16. Update The Application

When you make code changes:

```bash
cd /opt/incidentrag
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

If you copied the project manually instead of using Git, copy the changed files again, then rebuild.

## 17. Backup Strategy

At minimum, create Lightsail snapshots before major changes:

1. Open Lightsail.
2. Select `incidentrag-prod`.
3. Go to `Snapshots`.
4. Choose `Create snapshot`.

Suggested naming:

```text
incidentrag-prod-before-release-YYYY-MM-DD
```

For a lightweight file-level backup, archive the Docker volumes:

```bash
mkdir -p ~/incidentrag-backups
docker run --rm \
  -v incidentrag_neo4j_data:/neo4j:ro \
  -v incidentrag_qdrant_data:/qdrant:ro \
  -v incidentrag_redis_data:/redis:ro \
  -v ~/incidentrag-backups:/backup \
  alpine sh -c "tar czf /backup/incidentrag-volumes-$(date +%F).tgz /neo4j /qdrant /redis"
```

Snapshots are simpler. File-level backups are useful if you later move to another host.

## 18. Cost Controls

Immediately create an AWS Budget:

1. Open `AWS Billing and Cost Management`.
2. Go to `Budgets`.
3. Create a monthly cost budget.
4. Set the budget amount to something like `$60`.
5. Add email alerts at `50%`, `80%`, and `100%`.

Keep costs low by:

- Using one Lightsail instance.
- Avoiding EKS until traffic or team needs justify it.
- Avoiding NAT Gateways.
- Avoiding managed Neo4j, managed Redis, and managed vector DBs at the start.
- Keeping database ports private.
- Deleting unused snapshots.
- Deleting unattached static IPs.
- Stopping or deleting test instances when not needed.

## 19. Security Checklist

Before sharing the URL:

- Use HTTPS with a real domain.
- Keep only ports `80`, `443`, and restricted `22` open.
- Use a read-only GitHub token when possible.
- Use a strong `INCIDENTRAG_API_KEY`.
- Keep `.env` permissions at `600`.
- Do not expose Neo4j, Qdrant, Redis, or FastAPI publicly.
- Do not commit `.env`.
- Run OS updates regularly:

```bash
sudo apt-get update
sudo apt-get upgrade -y
```

## 20. Stop Or Remove The Deployment

Stop the app without deleting data:

```bash
cd /opt/incidentrag
docker compose -f docker-compose.prod.yml down
```

Stop and remove app containers, networks, and volumes:

```bash
cd /opt/incidentrag
docker compose -f docker-compose.prod.yml down -v
```

Only use `down -v` if you intentionally want to delete Neo4j, Qdrant, and Redis data.

To stop AWS billing for the instance, delete the Lightsail instance and unattached static IPs from the AWS console. Stopped Lightsail instances can still incur charges.

## 21. When To Move Beyond This Setup

Stay on Lightsail while:

- You have one small team using the app.
- Traffic is low or moderate.
- Manual deployments are acceptable.
- Occasional downtime during updates is acceptable.

Move to ECS, App Runner, or EKS later if:

- You need high availability.
- You need separate production and staging environments.
- You need automated deployments with rollback.
- You need managed databases.
- You need stronger IAM-based secret management.
- You have enough usage to justify the added monthly cost.

For the current IncidentRAG project, Lightsail plus Docker Compose is the most cost-effective AWS hosting path.
