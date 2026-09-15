# IncidentRAG dual-environment deployment guide

This guide covers a persistent AWS EC2 demonstration and an optional Vercel frontend. The current Streamlit UI cannot be deployed directly to Vercel. EC2 is the complete deployment: FastAPI, Streamlit, Neo4j, Qdrant, and Redis.

Assumptions:

- Windows PowerShell locally.
- Ubuntu 24.04 LTS on EC2.
- A GitHub repository and a DNS name such as demo.example.com.
- EXECUTION_ENABLED=false and AUTO_EXECUTE_LOW_RISK=false everywhere.
- No AWS resource is created until the owner explicitly approves it.

## 0. Safety rules

- Never commit .env, credentials, private keys, or tokens.
- Never run the application as root.
- Never expose 8000, 8501, 6379, 6333, 6334, 7474, or 7687 publicly.
- Allow SSH only from your fixed public IP as /32.
- Do not create NAT Gateway, RDS, load balancer, or managed databases for this demo.
- Stopping EC2 still leaves EBS and public IPv4 charges.
- Review the existing dirty working tree before editing.

## 1. Repository facts

- Language: Python 3.11+.
- Backend: FastAPI, entry point incidentrag.api.app:app.
- Frontend: Streamlit, entry point src/incidentrag/approval/ui/streamlit_app.py.
- Data services: Neo4j, Qdrant, Redis.
- Optional observability: OpenTelemetry collector.
- API port: 8000.
- UI port: 8501.
- Docker Compose already describes the stack.
- /health and /ready already exist.
- The API binds to 0.0.0.0 in the existing Docker/CLI commands.
- Assessments are in memory and are lost after restart.

The full app is not a Vercel serverless fit because it requires long-lived databases, writable storage, startup initialization, and in-memory state. A separate static/React frontend may be hosted on Vercel and call EC2 over HTTPS.

## 2. Local preflight

Open PowerShell:

    Set-Location E:\IncidentRAG+refine
    git status --short
    git branch --show-current
    git remote -v

If the working tree contains work you do not own, stop and coordinate. Create a safety branch if appropriate:

    git switch -c codex/deployment-preparation

Do not clean the tree with git reset --hard or git checkout --.

Check secrets:

    git check-ignore -v .env
    git ls-files .env
    git ls-files | Select-String -Pattern '(^|/)(.*secret.*|.*credential.*|.*private.*)$'

The first command should show .gitignore. The second should print nothing. If .env was ever committed, rotate its secrets and remove it using the repository's approved history-rewrite procedure.

## 3. Phase 1 — repository preparation

### 3.1 .env.example

Keep placeholders only:

    APP_ENVIRONMENT=production
    PORT=8000
    EXECUTION_ENABLED=false
    AUTO_EXECUTE_LOW_RISK=false
    DEMO_MODE=true
    OPENROUTER_API_KEY=
    OPENAI_API_KEY=
    ANTHROPIC_API_KEY=
    NEO4J_URI=bolt://neo4j:7687
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=replace-with-a-long-random-password
    QDRANT_URL=http://qdrant:6333
    QDRANT_API_KEY=
    REDIS_URL=redis://redis:6379/0
    GITHUB_OWNER=argoproj
    GITHUB_REPO=argo-cd
    GITHUB_TOKEN=
    INCIDENTRAG_API_KEY=replace-with-a-long-random-api-key
    CORS_ALLOWED_ORIGINS=https://demo.example.com
    OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
    OTEL_SERVICE_NAME=incidentrag
    QDRANT_COLLECTION_NAME=incidentrag_chunks
    QDRANT_EMBEDDING_DIM=1536
    DISKCACHE_DIR=/var/lib/incidentrag/cache

Health does not require an LLM key; analysis does.

### 3.2 .gitignore

Ensure these entries exist:

    .env
    .env.*
    !.env.example
    __pycache__/
    .venv/
    .cache/
    *.log
    *.pem
    *.key
    *.tfstate*

### 3.3 PORT, binding, and health

The server must read PORT with default 8000. Set ENV PORT=8000 in the image and use:

    ENV PORT=8000
    CMD ["sh", "-c", "exec uvicorn incidentrag.api.app:app --host 0.0.0.0 --port $PORT --workers 1"]

Keep the existing CLI --port option. Use one worker because state is in memory.

Required responses:

    GET /health -> HTTP 200
    GET /ready  -> HTTP 200 only when required dependencies are ready; otherwise 503

Keep /health independent of databases. Use /ready for deployment checks.

### 3.4 Local tests and image builds

    uv sync --extra dev
    uv run ruff check src tests
    uv run pytest tests/unit -q --no-cov
    docker build -t incidentrag-api:local .
    docker build -f Dockerfile.ui -t incidentrag-ui:local .

Local smoke test:

    docker compose up -d neo4j qdrant redis
    .\.venv\Scripts\uvicorn.exe incidentrag.api.app:app --host 0.0.0.0 --port 8000

In another PowerShell:

    Invoke-RestMethod http://127.0.0.1:8000/health
    Invoke-WebRequest http://127.0.0.1:8000/ready
    $env:INCIDENTRAG_API_URL = 'http://127.0.0.1:8000'
    .\.venv\Scripts\streamlit.exe run src\incidentrag\approval\ui\streamlit_app.py

Stop local services:

    docker compose down

Review and commit only intended files:

    git diff --check
    git diff -- .env.example .gitignore README.md Dockerfile Dockerfile.ui pyproject.toml src .github
    git status --short
    git add .env.example .gitignore README.md Dockerfile Dockerfile.ui pyproject.toml src .github
    git commit -m "Prepare IncidentRAG for production deployment"
    git push -u origin codex/deployment-preparation

## 4. Phase 2 — AWS design

### 4.1 Recommendation

- Start with t3.micro, x86_64, 2 vCPU, 1 GiB RAM.
- Use Ubuntu Server 24.04 LTS.
- Use an encrypted 20 GiB gp3 root volume; 30 GiB is safer for images/logs.
- If the full stack is unstable or killed by the OOM killer, use t3.small.
- t4g.micro may be cheaper, but validate ARM64 support for every image and optional PyTorch/sentence-transformers dependency first.

### 4.2 Key pair console clicks

1. AWS Console -> choose the target region -> EC2.
2. Left navigation: Network & Security -> Key Pairs.
3. Choose Create key pair.
4. Name it incidentrag-demo.
5. Select ED25519 if supported, otherwise RSA.
6. Select PEM and choose Create key pair.
7. Store the downloaded key outside the repository.

PowerShell:

    icacls "$env:USERPROFILE\Downloads\incidentrag-demo.pem"

WSL/Git Bash:

    chmod 400 ~/Downloads/incidentrag-demo.pem

### 4.3 Security group console clicks

1. EC2 -> Security Groups -> Create security group.
2. Name: incidentrag-demo-sg.
3. Description: Restricted SSH and public HTTPS for IncidentRAG.
4. Select the intended VPC.
5. Inbound SSH TCP 22, source My IP only.
6. Inbound HTTP TCP 80, source 0.0.0.0/0 and ::/0 only if IPv6 is enabled.
7. Inbound HTTPS TCP 443, source 0.0.0.0/0 and ::/0 only if IPv6 is enabled.
8. Do not add rules for API, UI, database, or telemetry ports.
9. Leave outbound access enabled initially for apt, GitHub, and LLM HTTPS traffic.
10. Choose Create security group.

### 4.4 Launch console clicks — approval required

Do not launch until the owner approves creating AWS resources.

1. EC2 -> Instances -> Launch instances.
2. Name: incidentrag-demo.
3. AMI: Ubuntu Server 24.04 LTS, 64-bit x86.
4. Instance type: t3.micro.
5. Key pair: incidentrag-demo.
6. Select the intended VPC and public subnet.
7. Enable Auto-assign public IP.
8. Select incidentrag-demo-sg.
9. Storage: 20 GiB gp3, encrypted, Delete on termination enabled.
10. Leave user data empty; do not paste secrets.
11. Choose Launch instance.

Record instance ID and public DNS/IP. Watch for EC2 compute, EBS, public IPv4, Elastic IP, snapshots, CloudWatch, ECR, data transfer, and accidental NAT Gateway/RDS/load balancer costs.

## 5. Phase 3 — EC2 deployment

### 5.1 Connect

PowerShell:

    ssh -i "$env:USERPROFILE\Downloads\incidentrag-demo.pem" ubuntu@YOUR_EC2_PUBLIC_IP

### 5.2 Install Ubuntu packages

    sudo apt-get update
    sudo DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
    sudo apt-get install -y ca-certificates curl git nginx certbot python3-certbot-nginx ufw unattended-upgrades
    sudo dpkg-reconfigure --priority=low unattended-upgrades

### 5.3 Host firewall

Replace YOUR_PUBLIC_IP with your current public IPv4:

    sudo ufw default deny incoming
    sudo ufw default allow outgoing
    sudo ufw allow from YOUR_PUBLIC_IP/32 to any port 22 proto tcp
    sudo ufw allow 80/tcp
    sudo ufw allow 443/tcp
    sudo ufw --force enable
    sudo ufw status verbose

Do not enable UFW until the SSH rule is correct.

### 5.4 Install Docker

    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo tee /etc/apt/keyrings/docker.asc >/dev/null
    sudo chmod a+r /etc/apt/keyrings/docker.asc
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu UBUNTU_CODENAME stable" | sudo tee /etc/apt/sources.list.d/docker.list >/dev/null
    sudo apt-get update
    sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    sudo systemctl enable --now docker
    docker --version
    docker compose version

Replace UBUNTU_CODENAME with the value from:

    . /etc/os-release && echo "$VERSION_CODENAME"

### 5.5 Non-root user and directories

    sudo useradd --create-home --shell /bin/bash incidentrag
    sudo usermod -aG docker incidentrag
    sudo install -d -o incidentrag -g incidentrag -m 0750 /var/www/portfolio-app
    sudo install -d -o incidentrag -g incidentrag -m 0750 /var/lib/incidentrag
    sudo install -d -o root -g incidentrag -m 0750 /etc/incidentrag
    sudo usermod --lock incidentrag

The Docker group grants significant host control. A hardened setup should replace it with a narrowly scoped root-owned deployment helper.

### 5.6 Checkout and releases

As incidentrag:

    sudo -iu incidentrag
    mkdir -p /var/www/portfolio-app/releases
    cd /var/www/portfolio-app
    git clone YOUR_GITHUB_REPOSITORY_URL current
    cd current

For a release directory:

    RELEASE=REPLACE_WITH_UTC_TIMESTAMP_AND_COMMIT
    mkdir -p /var/www/portfolio-app/releases/RELEASE
    git archive HEAD | tar -x -C /var/www/portfolio-app/releases/RELEASE
    ln -sfn /var/www/portfolio-app/releases/RELEASE /var/www/portfolio-app/current

### 5.7 Secure production environment

As root:

    sudo install -o root -g incidentrag -m 0640 /dev/null /etc/incidentrag/incidentrag.env
    sudoedit /etc/incidentrag/incidentrag.env

Set:

    APP_ENVIRONMENT=production
    PORT=8000
    STREAMLIT_PORT=8501
    EXECUTION_ENABLED=false
    AUTO_EXECUTE_LOW_RISK=false
    DEMO_MODE=true
    OPENROUTER_API_KEY=REPLACE_ME
    GITHUB_TOKEN=
    NEO4J_USER=neo4j
    NEO4J_PASSWORD=REPLACE_ME_WITH_LONG_RANDOM_VALUE
    INCIDENTRAG_API_KEY=REPLACE_ME_WITH_LONG_RANDOM_VALUE
    CORS_ALLOWED_ORIGINS=https://demo.example.com

Generate random values without putting them in shell history:

    openssl rand -hex 32

Never put secrets in Dockerfiles, Compose YAML, command-line arguments, GitHub variables, or Git history.

### 5.8 Production Compose

    cd /var/www/portfolio-app/current
    cp docker-compose.yml docker-compose.prod.yml

Edit docker-compose.prod.yml:

- Remove host port mappings for Neo4j, Qdrant, Redis, and OpenTelemetry.
- Bind API/UI only to 127.0.0.1:8000 and 127.0.0.1:8501.
- Replace the development Neo4j password with the environment-file value.
- Use /etc/incidentrag/incidentrag.env as the env_file where required.
- Keep named persistent volumes.
- Keep restart: unless-stopped.
- Keep one API worker.

Validate:

    docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml config

Build/start:

    cd /var/www/portfolio-app/current
    docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml build
    docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml up -d neo4j qdrant redis
    docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml up -d api ui
    docker compose -f docker-compose.prod.yml ps
    docker compose -f docker-compose.prod.yml logs --tail=100 api

### 5.9 systemd

Create /etc/systemd/system/incidentrag.service:

    [Unit]
    Description=IncidentRAG production Docker Compose stack
    Requires=docker.service
    After=docker.service network-online.target

    [Service]
    Type=oneshot
    RemainAfterExit=yes
    WorkingDirectory=/var/www/portfolio-app/current
    ExecStart=/usr/bin/docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml up -d
    ExecStop=/usr/bin/docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml down
    TimeoutStartSec=0

    [Install]
    WantedBy=multi-user.target

Enable:

    sudo systemctl daemon-reload
    sudo systemctl enable --now incidentrag.service
    sudo systemctl status incidentrag.service --no-pager

### 5.10 Nginx

Point the DNS A record demo.example.com to the EC2 public IP. Create /etc/nginx/sites-available/incidentrag:

    server {
        listen 80;
        listen [::]:80;
        server_name demo.example.com;
        client_max_body_size 2m;

        location / {
            proxy_pass http://127.0.0.1:8501;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection "upgrade";
            proxy_read_timeout 3600;
        }

        location /api/ {
            proxy_pass http://127.0.0.1:8000/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

Enable:

    sudo ln -sfn /etc/nginx/sites-available/incidentrag /etc/nginx/sites-enabled/incidentrag
    sudo rm -f /etc/nginx/sites-enabled/default
    sudo nginx -t
    sudo systemctl reload nginx

If Streamlit calls the API directly, configure INCIDENTRAG_API_URL=https://demo.example.com and verify the browser request paths.

### 5.11 HTTPS

After DNS resolves:

    sudo certbot --nginx -d demo.example.com
    sudo systemctl status certbot.timer --no-pager
    sudo certbot renew --dry-run

Choose the HTTP-to-HTTPS redirect option. Verify:

    curl -fsS https://demo.example.com/health
    curl -fsS https://demo.example.com/ready

## 6. Phase 4 — Vercel

### 6.1 Scope

Recommended now: use EC2 for the complete demo. If a separate static/React frontend is added, Vercel can host it and call the EC2 API.

Never expose OPENROUTER_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, NEO4J_PASSWORD, QDRANT_API_KEY, REDIS_URL, or INCIDENTRAG_API_KEY to the browser.

### 6.2 Vercel console clicks

1. Vercel dashboard -> Add New -> Project.
2. Import the GitHub repository or frontend repository.
3. Select the frontend root if this is a monorepo.
4. Confirm the detected framework.
5. Set the production build command, such as npm run build.
6. Set the framework's output directory.
7. Project Settings -> Environment Variables.
8. Add only a public API URL, such as NEXT_PUBLIC_API_BASE_URL=https://demo.example.com.
9. Select Production/Preview/Development as appropriate.
10. Choose Deploy.

Vite variables normally use VITE_. Next.js browser-visible variables normally use NEXT_PUBLIC_. Treat both as public.

### 6.3 CORS

On EC2:

    CORS_ALLOWED_ORIGINS=https://your-project.vercel.app,https://your-custom-domain.example
    sudo systemctl restart incidentrag.service

Do not embed a shared API key in frontend JavaScript. Use user/session authentication for browser access, or keep the Streamlit UI server-side on EC2.

## 7. Phase 5 — GitHub Actions to EC2

### 7.1 Deployment key

Local PowerShell:

    ssh-keygen -t ed25519 -C "github-actions-incidentrag" -f "$env:USERPROFILE\.ssh\incidentrag_actions"

Install the public key for ubuntu on EC2. Do not use your personal SSH key.

### 7.2 GitHub Secrets console clicks

1. Repository -> Settings.
2. Secrets and variables -> Actions.
3. Secrets -> New repository secret.
4. Add EC2_HOST, EC2_USER=ubuntu, EC2_SSH_KEY, and EC2_HEALTHCHECK_URL=https://demo.example.com/health.
5. Add EC2_APP_DIR=/var/www/portfolio-app under Variables if desired.

### 7.3 Deployment helper

Create /usr/local/sbin/incidentrag-deploy as root, mode 0750, group ubuntu:

    #!/usr/bin/env bash
    set -Eeuo pipefail
    APP_ROOT=/var/www/portfolio-app
    REPO=/var/www/portfolio-app/current
    cd "$REPO"
    git fetch --prune origin
    git checkout --force "$1"
    docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml build api ui
    docker compose --env-file /etc/incidentrag/incidentrag.env -f docker-compose.prod.yml up -d api ui
    systemctl restart incidentrag.service
    curl --fail --silent --show-error --max-time 30 http://127.0.0.1:8000/health

Validate the argument in a hardened version. Add narrowly scoped sudo:

    ubuntu ALL=(root) NOPASSWD: /usr/local/sbin/incidentrag-deploy *

### 7.4 Workflow

Create .github/workflows/deploy-ec2.yml:

    name: Deploy IncidentRAG to EC2
    on:
      workflow_dispatch:
      push:
        branches: [main]
    permissions:
      contents: read
    jobs:
      deploy:
        runs-on: ubuntu-latest
        environment: production
        steps:
          - uses: actions/checkout@v4
          - uses: actions/setup-python@v5
            with:
              python-version: "3.12"
          - run: pip install ".[dev]"
          - run: pytest tests/unit -q --no-cov
          - run: docker build -t incidentrag-api:test .
          - run: docker build -f Dockerfile.ui -t incidentrag-ui:test .
          - name: Deploy over SSH
            uses: appleboy/ssh-action@v1.2.0
            with:
              host: ${{ secrets.EC2_HOST }}
              username: ${{ secrets.EC2_USER }}
              key: ${{ secrets.EC2_SSH_KEY }}
              script: sudo /usr/local/sbin/incidentrag-deploy ${{ github.sha }}
          - name: Post-deployment health check
            run: curl --fail --silent --show-error --retry 10 --retry-delay 5 "${{ secrets.EC2_HEALTHCHECK_URL }}"

Review the workflow before enabling it and ensure no command prints secrets.

### 7.5 Rollback

    cd /var/www/portfolio-app/current
    git log --oneline --decorate -10
    sudo /usr/local/sbin/incidentrag-deploy KNOWN_GOOD_COMMIT_SHA
    curl --fail https://demo.example.com/health

If a container fails:

    docker compose -f /var/www/portfolio-app/current/docker-compose.prod.yml ps
    docker compose -f /var/www/portfolio-app/current/docker-compose.prod.yml logs --tail=200 api
    sudo systemctl restart incidentrag.service

## 8. Phase 6 — budget and monitoring

### 8.1 Budget console clicks

1. Billing and Cost Management -> Budgets.
2. Choose Create budget.
3. Choose Use a template or Customize.
4. Select a monthly cost budget.
5. Set an account-appropriate amount.
6. Add actual and forecast alerts at 50%, 80%, and 100%.
7. Add an email recipient and confirm the subscription.
8. Choose Create budget.

Budgets notify; they do not automatically stop resources.

### 8.2 CloudWatch alarms

Recommended alarms:

- EC2 CPU high for 15 minutes.
- EC2 status check failed.
- EBS burst balance low where applicable.
- Disk usage high, using the CloudWatch agent if filesystem metrics are needed.
- Instance stopped/terminated notification through EventBridge if desired.

Keep CloudWatch log retention at 7–30 days.

### 8.3 Stop/start

Console:

1. EC2 -> Instances.
2. Select incidentrag-demo.
3. Instance state -> Stop instance -> Stop.

CLI:

    aws ec2 stop-instances --instance-ids i-XXXXXXXXXXXX --region YOUR_REGION
    aws ec2 start-instances --instance-ids i-XXXXXXXXXXXX --region YOUR_REGION
    curl.exe -fsS https://demo.example.com/health

Stopping does not remove EBS, snapshots, public IPv4, or other attached-resource charges.

## 9. Monthly cleanup

- Review Billing -> Cost Explorer by service and region.
- Confirm EC2 is stopped outside demonstrations.
- Delete unattached EBS volumes after verification.
- Delete obsolete EBS snapshots.
- Release unused Elastic IPs.
- Review public IPv4 allocations.
- Remove old ECR images and repositories.
- Review CloudWatch log groups and retention.
- Remove unused security groups, keys, IAM roles, and instance profiles.
- Confirm no NAT Gateway, load balancer, RDS, or managed database exists accidentally.
- Review GitHub Actions minutes and artifacts.
- Rotate deployment keys and application secrets.
- Test Neo4j, Qdrant, and Redis backup/restore.

## 10. Troubleshooting

    sudo systemctl status incidentrag.service nginx docker --no-pager
    docker ps
    docker stats --no-stream
    free -h
    df -h
    docker compose -f /var/www/portfolio-app/current/docker-compose.prod.yml logs --tail=200 api
    curl -v http://127.0.0.1:8000/health
    curl -v http://127.0.0.1:8000/ready
    sudo nginx -t
    sudo journalctl -u nginx -n 100 --no-pager
    sudo certbot certificates
    sudo certbot renew --dry-run
    docker compose -f /var/www/portfolio-app/current/docker-compose.prod.yml ps
    docker compose -f /var/www/portfolio-app/current/docker-compose.prod.yml logs --tail=100 neo4j qdrant redis

Common failures:

- SSH timeout: wrong security-group source IP, no public route, or UFW enabled before the SSH rule.
- Nginx 502: API/UI stopped or Nginx points to the wrong port.
- /health works but /ready is 503: Qdrant or pipeline initialization is unavailable.
- OOM: disable optional reranking, stop optional services, or resize to t3.small.
- CORS error: add the exact HTTPS browser origin and restart the API.
- Lost assessments: expected after restart because the store is in memory.
- Vercel timeout: expected if the full FastAPI app initializes unreachable local services.

## 11. Final acceptance checklist

    [ ] No secrets are tracked or present in image layers.
    [ ] API runs as a non-root container user.
    [ ] SSH is restricted to one trusted /32 source.
    [ ] Only ports 80 and 443 are public.
    [ ] /health returns 200 over HTTPS.
    [ ] /ready returns 200 with dependencies available.
    [ ] EXECUTION_ENABLED=false.
    [ ] Nginx and Certbot renewal work.
    [ ] systemd starts and restarts the required services.
    [ ] GitHub Actions uses Secrets and a dedicated deploy key.
    [ ] Post-deployment health checks run.
    [ ] Rollback has been tested.
    [ ] AWS Budget alerts are configured.
    [ ] Stop/start has been tested.
    [ ] No unnecessary billable resource exists.
    [ ] Vercel is used only for a compatible frontend.
