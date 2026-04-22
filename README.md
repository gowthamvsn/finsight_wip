# FinSight — Multi-Agent Wealth Management Platform

A production-grade wealth management platform combining multiple LLMs, ML models, real-time price feeds, fraud detection, and OTP-gated transactions — deployed on Azure Kubernetes Service.

**Live URL:** http://52.230.226.51

**Demo credentials:**
- Admin: `priya@finsight.com` / `Admin@123`
- Customer: `arjun@example.com` / `Customer@123`

---

## Architecture

```
Browser (React 18 + Vite)
    │
    │  HTTP/WebSocket
    ▼
nginx (LoadBalancer · 52.230.226.51)
    │
    │  /api/*  /ws/*
    ▼
FastAPI (AKS · 2 replicas)
    ├── APScheduler (60s) ──────────────────► yfinance
    │                                              │ 14 tickers · 1m bars
    │   PostgreSQL Trigger Cascade                 ▼
    ├── market_prices ──► portfolio_holdings ──► customer_summary ──► pg_notify
    │                                                                      │
    │                                                              WebSocket push
    │                                                                      │
    ├── 6 AI Agents ────────────────────────────────────────────────► React live tick
    │   ├── Orchestrator    (Azure GPT-4o)
    │   ├── Portfolio       (Claude Haiku)
    │   ├── Market          (Gemini 2.0 Flash)
    │   ├── Report          (Claude Haiku)
    │   ├── Support Chat    (Azure GPT-4o)
    │   └── Fraud           (Isolation Forest — no LLM)
    │
    ├── Azure PostgreSQL (wehealthdb)
    ├── Azure Communication Services (OTP email)
    └── Azure Blob Storage (reports)
```

---

## The 6 Agents

| Agent | LLM / Model | Why this choice | Responsibility |
|-------|------------|-----------------|---------------|
| Orchestrator | Azure GPT-4o | Strong reasoning, tool routing | Routes requests to sub-agents, decides which agents to invoke |
| Portfolio | Claude Haiku | Fast, cost-efficient, structured output | Analyse holdings, risk concentration, rebalancing suggestions |
| Market | Gemini 2.0 Flash | 1M-token context, handles large market data | Scan 780+ tickers, generate signal narratives from bulk price history |
| Report | Claude Haiku | Concise writing, instruction-following | Synthesise portfolio data into readable advisor report |
| Support Chat | Azure GPT-4o | Conversational, memory within session | Answer natural-language customer questions about their portfolio |
| Fraud | Isolation Forest (sklearn) | Deterministic, auditable, no hallucination risk | Detect anomalous transactions; rule-based OTP triggers for high-risk events |

---

## Why 3 LLMs + 2 ML Models

- **Claude Haiku** — portfolio analysis and report writing. Chosen for speed and cost efficiency on structured data tasks. Runs on every agent request.
- **Gemini 2.0 Flash** — market data narrative. Its 1M-token context window is necessary to process 780 tickers of OHLCV history in a single call without chunking.
- **Azure GPT-4o** — conversational reasoning and orchestration. The orchestrator and support chat benefit from GPT-4o's instruction-following and multi-turn reasoning.
- **Random Forest** — stock signal predictions. Deterministic and interpretable. Judges can ask "why did this ticker get a buy signal?" and get a feature-importance answer.
- **Isolation Forest** — fraud detection. Intentionally no LLM. Fraud decisions must be auditable and reproducible. An LLM-based fraud flag would be unjustifiable in a compliance review.

---

## Security

- bcrypt password hashing (never store plaintext)
- JWT authentication with `admin` vs `customer` role isolation
- Every API query scoped to `customer_id` — customers can only see their own data
- OTP challenge gate for transactions above $50,000 or originating from high-risk countries
- Prompt injection guardrails (`utils/guardrails.py`) on all LLM inputs
- Locked agent system prompts — agents cannot be instructed to change their role
- Kubernetes secrets via `kubectl create secret` — no credentials in Git
- `AZURE_CREDENTIALS` passed only through GitHub Actions secrets

---

## PostgreSQL Trigger Cascade

Every 60 seconds the APScheduler fetches 1-minute yfinance bars for 14 tickers and writes them to `market_prices`. Four chained PostgreSQL triggers propagate the update automatically:

```
yfinance (1m bars)
  → UPDATE market_prices.price_usd
  → trg_price_to_holdings: UPDATE portfolio_holdings (current_price, current_value, unrealized_pl)
  → trg_holdings_to_summary: UPSERT customer_summary (portfolio_value, net_worth, net_pl, allocation %)
  → trg_summary_to_ws: pg_notify('dashboard_update')
  → FastAPI listener: broadcast to all WebSocket clients
  → React useLivePrices: refreshTick++ → useEffect re-fetches portfolio API
```

No polling on the frontend. The React page only re-renders when the database actually changes.

---

## Local Setup

```bash
# 1. Prerequisites: Python 3.11, Node 18, PostgreSQL

# 2. Clone
git clone https://github.com/gowthamvsn/finsight_wip.git
cd finsight_wip

# 3. Backend
cd backend
pip install -r requirements.txt
cp .env.example .env
# Fill in DATABASE_URL, JWT_SECRET, API keys
uvicorn main:app --reload --port 8000

# 4. Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

---

## Azure Deployment

```bash
# Login
az login
az acr build --registry fincontaineregistry --image finsight-backend:latest ./backend
az acr build --registry fincontaineregistry --image finsight-frontend:latest ./frontend

# Get cluster credentials
az aks get-credentials --resource-group MenoWE --name finkubernetes

# Create namespace + secrets
kubectl create namespace finsight
kubectl create secret generic finsight-secrets --from-env-file=./backend/.env -n finsight

# Deploy
kubectl apply -f k8s/
kubectl rollout status deployment/backend -n finsight
kubectl rollout status deployment/frontend -n finsight

# Get IP
kubectl get service frontend-service -n finsight
```

---

## High Availability Demo

```bash
# Show 4 running pods
kubectl get pods -n finsight

# Kill one backend pod (app still serves traffic via second replica)
kubectl delete pod <backend-pod-name> -n finsight

# Watch Kubernetes self-heal in real time (~20 seconds)
kubectl get pods -n finsight -w

# Switch to browser — app remains responsive throughout recovery
```

---

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`) triggers on every push to `main`:
1. `az acr build` — builds and pushes both images to ACR
2. `kubectl apply` — applies k8s manifests
3. `kubectl set image` — rolling update with zero downtime
4. `kubectl rollout status` — waits for all pods healthy before marking success

Requires GitHub secrets: `AZURE_CREDENTIALS`, `AZURE_REGISTRY_NAME`, `AZURE_RESOURCE_GROUP`, `AZURE_AKS_CLUSTER`
