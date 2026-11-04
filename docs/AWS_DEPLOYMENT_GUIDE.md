# AWS Deployment Guide for Saath

This guide walks you through deploying **Saath** to AWS. Two deployment paths are supported depending on your requirements and budget:

| Feature | Method 1: EC2 + Docker Compose (Recommended) | Method 2: CloudFormation (ECS + ALB + RDS) |
| :--- | :--- | :--- |
| **Setup Time** | **10 minutes** | 25–35 minutes |
| **AWS Cost** | **Free Tier ($0/mo)** or ~$5–$10/mo (`t3.small`) | ~$45–$60/mo (ALB + NAT Gateway + RDS) |
| **Complexity** | Low (Single VM, 1-command bootstrap) | Medium-High (ECR, VPC, Multi-AZ Subnets) |
| **Best For** | **Hackathons, Live Judging & Fast Demos** | Enterprise Production Scaling |

---

## Method 1: Fast EC2 Deployment (Recommended)

This method deploys both the Next.js frontend and FastAPI backend inside lightweight Docker containers on a single Ubuntu EC2 instance with persistent SQLite storage.

### Step 1: Launch an EC2 Instance on AWS Console
1. Log in to your [AWS Management Console](https://console.aws.amazon.com/ec2).
2. Go to **EC2** → Click **Launch Instance**.
3. Configure the instance:
   - **Name:** `saath-demo`
   - **AMI:** **Ubuntu Server 24.04 LTS (HVM)**, SSD Volume Type (x86_64).
   - **Instance Type:** `t3.small` (2 vCPU, 2 GiB RAM) or `t3.micro` (Free Tier).
   - **Key Pair:** Select an existing key pair or click **Create new key pair** (download `.pem`).
4. **Network Settings (Security Group):**
   - Click **Edit** and ensure these inbound rules are added:
     | Type | Port | Protocol | Source | Purpose |
     | :--- | :--- | :--- | :--- | :--- |
     | SSH | `22` | TCP | `0.0.0.0/0` (or My IP) | Terminal access |
     | HTTP | `80` | TCP | `0.0.0.0/0` | Web access |
     | HTTPS | `443` | TCP | `0.0.0.0/0` | Webhook delivery (SSL) |
     | Custom TCP | `3000` | TCP | `0.0.0.0/0` | Next.js Web Board |
     | Custom TCP | `8000` | TCP | `0.0.0.0/0` | FastAPI Backend |
5. Click **Launch Instance**.

---

### Step 2: Connect & Run 1-Click Bootstrap Script
1. Open your terminal and connect via SSH:
   ```bash
   ssh -i your-key.pem ubuntu@<EC2-PUBLIC-IP>
   ```

2. Run the Saath bootstrap command:
   ```bash
   curl -sSL https://raw.githubusercontent.com/PrathameshTawar/meta-hackthon-top-2000-all-over-the-world/main/infra/deploy-ec2.sh | bash
   ```
   *This automatically updates Ubuntu, installs Docker & Docker Compose, clones the repository, and creates `.env`.*

---

### Step 3: Configure Environment Variables
1. Navigate into the app folder:
   ```bash
   cd ~/saath
   nano .env
   ```
2. Set your production keys:
   ```env
   # Admin secret for Web Board access
   ADMIN_SECRET=your_secure_admin_secret_here

   # Meta Muse Spark API
   LLM_BASE_URL=https://api.meta.ai/v1
   LLM_API_KEY=your_meta_api_key_here
   MUSE_SPARK_MODEL=muse-spark-1.3

   # Next.js API URL (Point to your EC2 Public IP)
   NEXT_PUBLIC_API_URL=http://<EC2-PUBLIC-IP>:8000

   # Messaging Webhooks (Optional for live bot testing)
   WHATSAPP_TOKEN=...
   WHATSAPP_PHONE_NUMBER_ID=...
   WHATSAPP_VERIFY_TOKEN=...
   WHATSAPP_APP_SECRET=...
   TELEGRAM_BOT_TOKEN=...
   TELEGRAM_WEBHOOK_SECRET=...
   ```
3. Save and exit (`Ctrl+O`, `Enter`, `Ctrl+X`).

---

### Step 4: Restart & Verify
```bash
sudo docker compose down
sudo docker compose up -d --build
```

Verify status:
```bash
sudo docker compose ps
curl http://localhost:8000/healthz
```

**Your app is now live:**
- **Web Board UI:** `http://<EC2-PUBLIC-IP>:3000`
- **Backend API:** `http://<EC2-PUBLIC-IP>:8000`
- **Interactive Swagger Docs:** `http://<EC2-PUBLIC-IP>:8000/docs`

---

### Step 5: (Optional) Adding HTTPS for WhatsApp & Telegram Webhooks
Both WhatsApp Cloud API and Telegram require an HTTPS URL with a valid SSL certificate for webhooks.

You can set up free automated SSL in 2 minutes using **Caddy**:
```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

Create `/etc/caddy/Caddyfile`:
```caddy
your-domain.com {
    # Reverse proxy Web Board
    reverse_proxy /api/* localhost:8000
    reverse_proxy /webhook/* localhost:8000
    reverse_proxy /chat/* localhost:8000
    reverse_proxy /artifacts/* localhost:8000
    reverse_proxy /tasks/* localhost:8000
    reverse_proxy /health/* localhost:8000
    reverse_proxy /* localhost:3000
}
```
Reload Caddy:
```bash
sudo systemctl restart caddy
```
*Caddy automatically issues a Let's Encrypt SSL certificate.*

---

## Method 2: CloudFormation Production Architecture (ECS Fargate + RDS + ALB)

Use this method if you want a serverless AWS infrastructure using the committed CloudFormation template in [`infra/saath-aws.yaml`](../infra/saath-aws.yaml).

### Prerequisites:
- AWS CLI configured locally (`aws configure`).
- Docker installed locally or access to AWS CloudShell.

### Step 1: Create Amazon ECR Repositories
```bash
aws ecr create-repository --repository-name saath-backend --region us-east-1
aws ecr create-repository --repository-name saath-frontend --region us-east-1
```

### Step 2: Build & Push Images to ECR
```bash
# Log in to ECR
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

# Build & Push Backend
docker build -t saath-backend:latest ./backend
docker tag saath-backend:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/saath-backend:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/saath-backend:latest

# Build & Push Frontend
docker build -t saath-frontend:latest ./frontend
docker tag saath-frontend:latest ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/saath-frontend:latest
docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/saath-frontend:latest
```

### Step 3: Deploy CloudFormation Stack
1. Go to **AWS CloudFormation** in the AWS Console.
2. Click **Create stack** → **With new resources (standard)**.
3. Choose **Upload a template file** and select `infra/saath-aws.yaml`.
4. Enter Stack details:
   - **Stack name:** `saath-production`
   - **BackendImage:** `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/saath-backend:latest`
   - **FrontendImage:** `<ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/saath-frontend:latest`
   - **DBPassword:** `<Strong-Master-Password>`
   - **AdminSecret:** `<Your-Admin-Token>`
   - **LLMApiKey:** `<Your-Meta-API-Key>`
5. Click **Next** → Acknowledge IAM capabilities → Click **Submit**.

CloudFormation provisions:
- Custom VPC (2 Public Subnets, 2 Private Subnets, Internet Gateway, NAT Gateway).
- Application Load Balancer routing port 80/443 to Frontend (port 3000) and `/api/*` / `/webhook/*` to Backend (port 8000).
- Amazon RDS PostgreSQL database (`db.t4g.micro`).
- Amazon ECS Fargate cluster with health checks and auto-restart.

The deployment takes ~12–15 minutes. Once complete, check the **Outputs** tab for the ALB DNS URL.

