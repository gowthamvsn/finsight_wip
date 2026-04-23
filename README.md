# FinSight — Multi-Agent Wealth Management Platform

A production-grade wealth management platform combining multiple LLMs, ML models, real-time price feeds, fraud detection, and OTP-gated transactions — deployed on Azure Kubernetes Service.

**Live URL:** http://52.230.226.51

**Demo credentials:**
- Admin: `priya@finsight.com` / `Admin@123`
- Customer: `arjun.meh@gmail.com` / `Customer@123`

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
    ├── APScheduler (30s) ──────────────────► yfinance / random-walk fallback
    │                                              │ 14 tickers · price feed
    │   PostgreSQL Trigger Cascade                 ▼
    ├── market_prices ──► portfolio_holdings ──► customer_summary ──► pg_notify
    │                                                                      │
    │                                                              WebSocket push
    │                                                                      │
    ├── 7 AI Agents ────────────────────────────────────────────────► React live tick
    │   ├── Orchestrator    (Azure GPT-4o)
    │   ├── Portfolio       (Claude Haiku)
    │   ├── Market          (Gemini 2.0 Flash)
    │   ├── Critic          (Claude Haiku)
    │   ├── Report          (Claude Haiku)
    │   ├── Support Chat    (Azure GPT-4o)
    │   └── Fraud           (Isolation Forest — no LLM)
    │
    ├── Azure PostgreSQL (wehealthdb)
    ├── Azure Communication Services (OTP email)
    └── Azure Blob Storage (reports)
```

---

## Complete Feature List

### Auth & Access
| Feature | How |
|---|---|
| JWT login | `/api/auth/login` → bcrypt verify → signed JWT (HS256) |
| Role-based access | JWT payload has `role: admin/customer` → FastAPI `Depends` guard on every route |
| Password hashing | `passlib` + `bcrypt` on every stored password, never plaintext |
| Token expiry | 8-hour TTL; 401 response dispatches `auth:logout` event → React clears session |

---

### Customer Data
| Feature | How |
|---|---|
| 50 seeded customers | SQL seed: names, emails, risk profiles (conservative/moderate/aggressive), tier (standard/premium/HNI) |
| Customer summary view | Computed: portfolio value, net worth, cash balance, allocation % by asset type |
| Risk profile enforcement | Stored in `customers` table; drives agent tone, Critic thresholds, and UI crypto-% warnings |

---

### Portfolio & Holdings
| Feature | How |
|---|---|
| Holdings per customer | `portfolio_holdings` table: ticker, qty, avg buy price, current price, unrealized P&L |
| Live price flashing | WebSocket price update → React adds `flash-green`/`flash-red` CSS class for 600ms then removes it |
| Unrealized P&L | `(current_price − avg_buy) × qty` — recomputed by DB trigger on every price update |
| Cash balance | CASH row in `portfolio_holdings`; `current_value` = dollar amount held |
| Cash auto-update on trades | `trg_cash_on_txn` AFTER INSERT trigger: buy deducts `total_value`, sell adds `total_value` |
| Realized P&L | Computed at sell time: `(sell_price − avg_buy) × qty`, stored in `transactions.realized_pl` |

---

### Transactions
| Feature | How |
|---|---|
| Full transaction history | `transactions` table: ticker, type, qty, price, total, timestamp, geo, flagged, realized P&L |
| 524 seeded transactions | Historical closed-position pairs (60 days back) + recent activity (30 days) |
| Historical trade pairs | Buy 45–62 days ago + matching sell 18–40 days ago; trigger auto-flows P&L into cash |
| Buy/sell/transfer types | `txn_type` column; trigger only acts on buy/sell, ignores transfer |
| Flagged suspicious transactions | 8% of recent seed marked `flagged=TRUE` with late-night hours + non-US geo |
| Orphan transaction cleanup | Script removes any recent transaction whose ticker is not in the customer's current holdings |

---

### Live Prices
| Feature | How |
|---|---|
| Price updates every 30s | APScheduler job → `_random_walk_prices()` applies ±0.3% random walk to current DB prices |
| yfinance primary / random-walk fallback | Azure datacenter IPs blocked by Yahoo → falls back to random walk on existing prices |
| DB trigger cascade | `UPDATE market_prices` → `trg_price_to_holdings` → `trg_holdings_to_summary` → `pg_notify('dashboard_update')` |
| WebSocket broadcast | asyncpg listens for `pg_notify` → FastAPI broadcasts JSON to all connected clients |
| Frontend reconnect | Exponential backoff: 1s → 2s → 4s → 8s → 30s max cap |

---

### AI Agents
| Feature | How |
|---|---|
| Portfolio Agent | Reads holdings + transactions → Azure GPT-4o → narrative risk + rebalancing analysis |
| Market Agent | yfinance OHLCV (or DB confidence fallback) → per-ticker confidence score + buy/sell/hold signal |
| Critic Agent | Runs Portfolio + Market in parallel via `asyncio.gather` → detects conflicts (`pl_pct < −15%` AND `confidence > 70%`) → Claude Haiku arbitrates with a final verdict |
| Agent Debate UI | Per-ticker conflict cards (portfolio signal vs market signal side by side) + violet Critic verdict box |
| Support Chat | Customer floating widget → POST `/api/agent/support` → Azure GPT-4o answers in context of their holdings |
| Report Generator | Portfolio + Market analysis → Claude Haiku formats PDF → stored in Azure Blob Storage, URL returned |
| Fraud Agent | Isolation Forest on transaction features (amount, hour, geo, velocity) → sets `flagged=TRUE` + inserts alert |
| AgentStatusTicker component | Shows each agent step with `pending/running/complete/error` states, spinner, and duration in ms |

---

### Alerts & Fraud
| Feature | How |
|---|---|
| Fraud alert creation | Isolation Forest scores each new transaction → outlier score above threshold → alert row inserted |
| Real-time alert feed | WebSocket `/ws/alerts` → React prepends new alerts to sidebar, max 50 kept in state |
| Alert severity badges | low/medium/high/critical → color-coded badge, slide-in CSS animation on arrival |
| Admin alert metrics | Dashboard cards show total open alerts + high-severity count aggregated across all customers |

---

### Loans
| Feature | How |
|---|---|
| Loan records | `loans` table: type, outstanding balance, rate%, EMI, due date, status |
| Overdue row highlight | `status = 'overdue'` → red table row styling in UI |

---

### News
| Feature | How |
|---|---|
| Per-holding news | NewsAPI.org queried per ticker (primary) → Gemini 2.0 Flash generates article summary (fallback) |
| One article per holding | Displayed as card with headline, source, published date |

---

### Admin Dashboard
| Feature | How |
|---|---|
| 50-customer table | `GET /api/customers` → rows sorted by portfolio value descending |
| AUM + 4 metric cards | Total customers, total AUM, open alerts, high-severity alerts — aggregated from `customer_summary` |
| Crypto % limit warnings | Amber if within 5% of limit, red if exceeded (conservative=10%, moderate=25%, aggressive=50%) |
| Live portfolio value ticks | WebSocket `dashboard_update` → matching customer row flashes green/red |
| Navigate to customer | "View" button → `/admin/customer/:id` → full CustomerDetail page |

---

### Customer Portfolio Page
| Feature | How |
|---|---|
| 4 metric cards | Portfolio Value, Net Worth, Net P&L, Cash Balance — fetched from `customer_summary` |
| P&L breakdown table | Gross gains, interest paid, net P&L, vs S&P500 benchmark |
| Holdings table | Ticker, type, qty, avg buy, current price, value, unrealized P&L% with green/red colouring |
| ML Predictions section | Confidence bar per ticker + signal badge + narrative text; calls `POST /api/agent/market/:id` |
| Agent Debate section | Runs Critic Agent → shows Portfolio vs Market conflict cards + verdict |
| Loans table | Outstanding, rate%, EMI, due date, overdue rows in red |
| Recent alerts | Last 5 open alerts with severity badge |
| Support Chat widget | Floating bubble bottom-right → opens panel → POST to support agent → shows response |

---

### Security
| Feature | How |
|---|---|
| Prompt injection blocking | `sanitize_query()` strips control chars, rejects banned phrases, enforces 2000-char max |
| Customer data isolation | Every DB query scoped to `customer_id`; customers cannot access other customers' data |
| OTP gate | Transactions above $50k or from high-risk countries trigger email OTP via Azure Communication Services |
| Locked agent system prompts | Agents cannot be re-instructed via user input to change role or leak system context |
| Kubernetes secrets | Credentials stored in `kubectl create secret`, never in Git or Docker image |

---

### Automated Tests (10 tests, zero external deps)
| Test | What it checks |
|---|---|
| `test_sanitize_query_clean_input` | Clean query passes through unchanged |
| `test_sanitize_query_blocks_prompt_injection` | Banned phrases raise `ValueError` |
| `test_sanitize_query_blocks_too_long` | >2000 chars rejected |
| `test_sanitize_query_strips_control_characters` | Null bytes + control chars stripped silently |
| `test_validate_customer_id` | `CUS-NNNN` passes; lowercase/wrong prefix/short digit fails |
| `test_jwt_create_and_verify` | Token round-trip: create → decode → payload matches |
| `test_jwt_invalid_token_raises` | Tampered token raises HTTP 401 |
| `test_password_hash_and_verify` | Correct password verifies; wrong password fails |
| `test_critic_conflict_detection` | Full conflict matrix: NVDA(−55.7%) + AAPL(−92.8%) flagged, BTC(+105%) + MSFT(+12.3%) not |
| `test_random_walk_stays_within_bounds` | 50 iterations, each price stays within ±0.3% and stays positive |

Run with: `cd backend && pytest tests/test_core.py -v`

---

## The 7 Agents

| Agent | LLM / Model | Why this choice | Responsibility |
|-------|------------|-----------------|---------------|
| Orchestrator | Azure GPT-4o | Strong reasoning, tool routing | Routes requests to sub-agents, decides which agents to invoke |
| Portfolio | Claude Haiku | Fast, cost-efficient, structured output | Analyses holdings, risk concentration, rebalancing suggestions |
| Market | Gemini 2.0 Flash | 1M-token context, handles large market data | Scans tickers, generates signal narratives from bulk price history |
| Critic | Claude Haiku | Impartial arbitration, concise output | Detects Portfolio vs Market conflicts, issues final recommendation |
| Report | Claude Haiku | Concise writing, instruction-following | Synthesises portfolio data into readable advisor report PDF |
| Support Chat | Azure GPT-4o | Conversational, multi-turn memory | Answers natural-language customer questions about their portfolio |
| Fraud | Isolation Forest (sklearn) | Deterministic, auditable, no hallucination risk | Detects anomalous transactions; rule-based OTP triggers for high-risk events |

---

## Why 3 LLMs + 2 ML Models

- **Claude Haiku** — portfolio analysis, critic arbitration, report writing. Chosen for speed and cost efficiency on structured data tasks.
- **Gemini 2.0 Flash** — market data narrative. Its 1M-token context window processes bulk OHLCV history in a single call.
- **Azure GPT-4o** — orchestration and support chat. Strong multi-turn reasoning and instruction-following.
- **Random Forest** — stock signal predictions. Deterministic and interpretable; feature importance is auditable.
- **Isolation Forest** — fraud detection. No LLM. Fraud decisions must be reproducible and justifiable in a compliance review.

---

## PostgreSQL Trigger Cascade

```
APScheduler (30s)
  → _random_walk_prices() or yfinance
  → UPDATE market_prices.price_usd
  → trg_price_to_holdings   : UPDATE portfolio_holdings (current_price, current_value, unrealized_pl)
  → trg_holdings_to_summary : UPSERT customer_summary (portfolio_value, net_worth, allocation %)
  → trg_summary_to_ws       : pg_notify('dashboard_update')
  → asyncpg listener        : broadcast JSON to all WebSocket clients
  → React useLivePrices     : flash green/red on changed values

INSERT INTO transactions (buy/sell)
  → trg_cash_on_txn         : UPDATE portfolio_holdings CASH row (current_value ± total_value)
```

No polling on the frontend. Pages re-render only when the database actually changes.

---

## Local Setup

```bash
# 1. Prerequisites: Python 3.10+, Node 18, PostgreSQL

# 2. Clone
git clone https://github.com/gowthamvsn/finsight_wip.git
cd finsight_wip

# 3. Backend
cd backend
pip install -r requirements.txt
# Create .env with DATABASE_URL, JWT_SECRET, API keys (see .env.example)
uvicorn main:app --reload --port 8000

# 4. Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000

# 5. Run tests
cd backend
pytest tests/test_core.py -v
```

---

## Azure Deployment

```bash
az login
az acr build --registry fincontaineregistry --image finsight-backend:latest ./backend
az acr build --registry fincontaineregistry --image finsight-frontend:latest ./frontend

az aks get-credentials --resource-group MenoWE --name finkubernetes

kubectl create namespace finsight
kubectl create secret generic finsight-secrets --from-env-file=./backend/.env -n finsight

kubectl apply -f k8s/
kubectl rollout status deployment/backend -n finsight
kubectl rollout status deployment/frontend -n finsight

kubectl get service frontend-service -n finsight
```

---

## High Availability Demo

```bash
# Show running pods
kubectl get pods -n finsight

# Kill one backend pod — app keeps serving via second replica
kubectl delete pod <backend-pod-name> -n finsight

# Watch Kubernetes self-heal (~20 seconds)
kubectl get pods -n finsight -w
```

---

## CI/CD

GitHub Actions (`.github/workflows/deploy.yml`) triggers on every push to `main`:
1. `az acr build` — builds and pushes both Docker images to ACR
2. `kubectl apply` — applies k8s manifests
3. `kubectl set image` — rolling update with zero downtime
4. `kubectl rollout status` — waits for all pods healthy before marking success

Requires GitHub secrets: `AZURE_CREDENTIALS`, `AZURE_REGISTRY_NAME`, `AZURE_RESOURCE_GROUP`, `AZURE_AKS_CLUSTER`
