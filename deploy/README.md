# Deploy IncidentRAG to AWS staging

This release runs the FastAPI backend and Streamlit console on an existing Amazon EKS
cluster. Only the Streamlit service is exposed through the ALB ingress. Streamlit calls the
FastAPI service over the cluster network and reads the shared API key from the Kubernetes
Secret, so operators do not paste an API key into the page.

The chart expects reachable Neo4j, Qdrant, Redis, and OpenTelemetry endpoints. Provision
those services before installing the chart. Keep Qdrant and Neo4j on private endpoints and
allow traffic from the EKS worker-node or pod security groups.

## 1. Install and verify the tools

Install AWS CLI v2, Docker Desktop, Terraform 1.6+, kubectl, and Helm 3. Verify the AWS
identity and connect kubectl to your existing EKS cluster:

```powershell
aws sts get-caller-identity
aws eks update-kubeconfig --region YOUR_REGION --name YOUR_EKS_CLUSTER
kubectl get nodes
```

The cluster also needs AWS Load Balancer Controller and External Secrets Operator. Create
an `aws-secrets-manager` `ClusterSecretStore` whose AWS identity can read the application
secret. The official EKS command reference explains how `update-kubeconfig` selects the
AWS identity: https://docs.aws.amazon.com/cli/latest/reference/eks/update-kubeconfig.html

## 2. Create ECR repositories and the Secrets Manager entry

```powershell
cd D:\incidentrag\deploy\terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
terraform output
```

Terraform creates two immutable ECR repositories and the
`incidentrag-staging/application` Secrets Manager entry. In the AWS console, open that
secret, choose **Retrieve secret value**, then **Edit**, and store this JSON with real
values:

```json
{
  "OPENROUTER_API_KEY": "YOUR_OPENROUTER_KEY",
  "GITHUB_TOKEN": "YOUR_READ_ONLY_GITHUB_TOKEN",
  "INCIDENTRAG_API_KEY": "A_LONG_RANDOM_SHARED_SECRET",
  "NEO4J_PASSWORD": "YOUR_NEO4J_PASSWORD",
  "QDRANT_API_KEY": "YOUR_QDRANT_KEY_IF_REQUIRED"
}
```

Do not commit that JSON or put secret values in Helm values, Terraform variables, shell
history, screenshots, or GitHub Actions variables. AWS documents JSON secret values here:
https://docs.aws.amazon.com/secretsmanager/latest/userguide/reference_secret_json_structure.html

## 3. Build and push the two images

Run these commands from `D:\incidentrag`. Replace the placeholders with Terraform outputs
and use a unique tag such as the Git commit SHA.

```powershell
$Region = "YOUR_REGION"
$ApiRepository = "YOUR_API_ECR_REPOSITORY_URL"
$UiRepository = "YOUR_UI_ECR_REPOSITORY_URL"
$ImageTag = git rev-parse --short HEAD
$Registry = ($ApiRepository -split '/')[0]

aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry
docker build -t "${ApiRepository}:${ImageTag}" .
docker push "${ApiRepository}:${ImageTag}"
docker build -f Dockerfile.ui -t "${UiRepository}:${ImageTag}" .
docker push "${UiRepository}:${ImageTag}"
```

AWS's ECR push guide documents the same login, tag, and push flow:
https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html

## 4. Configure staging

Copy `deploy/values-staging.example.yaml` to `deploy/values-staging.yaml`. Replace every
`CHANGE_ME` value. Set the private service URLs, ECR repository URLs, immutable image tag,
public hostname, and ACM certificate ARN. Keep `executionEnabled: "false"`.

The External Secrets Operator must materialize a Kubernetes Secret named
`incidentrag-secrets`. Check it after deployment with `kubectl get secret`; do not print
its contents.

## 5. Validate and install

```powershell
cd D:\incidentrag
helm lint deploy/helm/incidentrag --values deploy/values-staging.yaml
helm template incidentrag deploy/helm/incidentrag --values deploy/values-staging.yaml | kubectl apply --dry-run=server -f -
helm upgrade --install incidentrag deploy/helm/incidentrag `
  --namespace incidentrag --create-namespace `
  --values deploy/values-staging.yaml `
  --wait --timeout 15m
```

The Helm hook indexes the bundled runbooks in Qdrant after installation. It is idempotent
because chunk and vector IDs are deterministic.

## 6. Verify the release

```powershell
kubectl get pods,jobs,ingress -n incidentrag
kubectl rollout status deployment/incidentrag-incidentrag -n incidentrag
kubectl rollout status deployment/incidentrag-incidentrag-ui -n incidentrag
kubectl logs deployment/incidentrag-incidentrag -n incidentrag --tail=100
kubectl port-forward service/incidentrag-incidentrag 8000:8000 -n incidentrag
```

While the port-forward is running, verify `http://localhost:8000/health` and
`http://localhost:8000/ready`. Then open the HTTPS hostname from the staging values file,
search for `repo-server`, select an issue, and click **Analyze selected issue**. A passing
smoke test shows a completed assessment on that page with a diagnosis, confidence,
evidence, investigation steps, and remediation guarded by human approval.

If the UI reports HTTP 503, inspect the API logs and verify pod egress to
`api.github.com:443` and `openrouter.ai:443`. If the assessment contains no evidence,
inspect the runbook hook job and confirm that the Qdrant collection contains points.

## Optional GitHub Actions deployment

The manual `Deploy AWS staging` workflow uses OIDC. Configure the GitHub environment named
`staging` with secret `AWS_DEPLOY_ROLE_ARN` and variables `AWS_REGION`, `EKS_CLUSTER`,
`API_REPOSITORY`, `UI_REPOSITORY`, `SECRET_REMOTE_KEY`, `QDRANT_URL`, `NEO4J_URI`,
`REDIS_URL`, `OTEL_ENDPOINT`, `APP_HOST`, and `ACM_CERTIFICATE_ARN`. Review the manual
staging deployment before enabling this workflow.
