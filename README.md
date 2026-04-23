# FinSight — Multi-Agent Wealth Management Platform

A production-grade wealth management platform combining multiple LLMs, ML models, real-time price feeds, fraud detection, OTP-gated transactions, and a full banking analytics layer — deployed on Azure Kubernetes Service.

**Live URL:** https://finsight-demo.centralus.cloudapp.azure.com

**Demo credentials:**
- Admin: `priya@finsight.com` / `Admin@123`
- Customer: `arjun.meh@gmail.com` / `Customer@123`

---

## Architecture

```
Browser (React 18 + Vite)
    │
    │  HTTP / WebSocket
    ▼
nginx (AKS LoadBalancer) · finsight-demo.centralus.cloudapp.azure.com
    │
    │  /api/*  /ws/*
    ▼
FastAPI (AKS · 2 replicas)
    ├── APScheduler (60s) ──────────────────► yfinance / random-walk fallback
    │                                              │ 14 tickers · price feed
    │   PostgreSQL Trigger Cascade                 ▼
    ├── market_prices ──► portfolio_holdings ──► customer_summary ──► pg_notify
    │                                                                      │
    │                                                              WebSocket push
    │                                                                      │
    ├── 8 AI Agents ────────────────────────────────────────────────► React live tick
    │   ├── Orchestrator      (Azure GPT-4o)
    │   ├── Portfolio         (Claude Haiku)
    │   ├── Market            (Gemini 2.0 Flash + Random Forest)
    │   ├── Critic            (Claude Haiku)
    │   ├── Report            (Claude Haiku)
    │   ├── Support Chat      (Azure GPT-4o)
    │   ├── Spending Analyst  (Azure GPT-4o)
    │   └── Fraud             (Isolation Forest — no LLM)
    │
    ├── Azure PostgreSQL
    ├── Azure Communication Services (OTP email)
    └── Azure Blob Storage (reports)
```

---

## Complete Feature List

### Auth & Access
| Feature | How |
|---|---|
| JWT login | `POST /api/auth/login` → bcrypt verify → signed JWT (HS256, 24h TTL) |
| Role-based access | JWT payload carries `role: admin/customer` → FastAPI `Depends` guard on every route |
| Password hashing | passlib + bcrypt on every stored password, never plaintext |
| Session expiry | 401 response dispatches `auth:logout` window event → React clears session and redirects |

---

### Customer Data
| Feature | How |
|---|---|
| 50 seeded customers | names, emails, risk profiles (conservative/moderate/aggressive), advisor tier (standard/premium/HNI) |
| Customer summary | Computed: portfolio value, net worth, cash balance, allocation % by asset type |
| Risk profile enforcement | Drives agent tone, Critic conflict thresholds, crypto-% UI warnings |

---

### Portfolio & Holdings
| Feature | How |
|---|---|
| Holdings per customer | `portfolio_holdings`: ticker, qty, avg buy price, current price, unrealized P&L |
| Live price flashing | WebSocket price update → React applies `flash-green`/`flash-red` CSS animation for 600ms |
| Unrealized P&L | `(current_price − avg_buy) × qty` — recomputed by DB trigger on every price update |
| Cash balance | CASH row in `portfolio_holdings`; `current_value` = dollar amount held |
| Cash auto-update on trades | `trg_cash_on_txn` AFTER INSERT trigger: buy deducts cost, sell adds proceeds |
| Realized P&L | Computed at sell time: `(sell_price − avg_buy) × qty`, stored in `transactions.realized_pl` |
| P&L vs S&P 500 | Annualised return compared to benchmark; `beating_market` boolean shown in UI |

---

### Transactions & OTP Gate
| Feature | How |
|---|---|
| Full transaction history | ticker, type, qty, price, total, timestamp, geo, flagged, realized P&L |
| Pre-insert fraud scoring | Isolation Forest + 6 rule checks run **before** the DB insert; clean = insert, flagged = OTP challenge |
| OTP gate | Suspicious transactions withheld from DB until customer enters 6-digit OTP sent via Azure email |
| OTP store | In-memory dict, 5-minute expiry, single-use, keyed by cryptographically random `challenge_id` |
| Demo mode | `demo_otp` returned in API response so reviewers can complete the flow without a real inbox |
| Transaction modal | 3-step UI: Form → OTP challenge (amber suspicious-activity card) → Confirmed |

---

### Live Prices
| Feature | How |
|---|---|
| Price updates every 60s | APScheduler → yfinance fetch; ±0.3% random walk fallback when Azure IPs are blocked |
| DB trigger cascade | `UPDATE market_prices` → holdings → summary → `pg_notify('dashboard_update')` |
| WebSocket broadcast | asyncpg listens for pg_notify → FastAPI pushes JSON to all connected clients |
| Frontend reconnect | Exponential backoff: 1s → 2s → 4s → 8s → 16s → 30s cap |

---

### 8 AI Agents

| Agent | LLM / Model | Responsibility |
|---|---|---|
| Orchestrator | Azure GPT-4o | Routes queries to sub-agents via LLM reasoning + keyword fallback |
| Portfolio | Claude Haiku | Analyses holdings, risk concentration, rebalancing; full or 50-word snapshot mode |
| Market | Gemini 2.0 Flash + RF | 14-flag Random Forest signals across 800+ tickers; narrative from Gemini |
| Critic | Claude Haiku | Detects Portfolio vs Market conflicts per ticker; issues final arbitration verdict |
| Report | Claude Haiku | Generates 6-section advisory report; saves to Azure Blob Storage |
| Support Chat | Azure GPT-4o | Answers customer questions in context of their own holdings, alerts, transactions, loans |
| Spending Analyst | Azure GPT-4o | Analyses bank transactions, cashflow, savings rate, category breakdowns; snapshot mode |
| Fraud | Isolation Forest (sklearn) | 6 rule checks + ML anomaly score; triggers OTP, alerts, and email — no LLM |

---

### Why 3 LLMs + 2 ML Models

- **Claude Haiku** — portfolio analysis, critic arbitration, report writing. Fast and cost-efficient on structured data tasks.
- **Gemini 2.0 Flash** — market data narrative. 1M-token context handles bulk OHLCV history in a single call.
- **Azure GPT-4o** — orchestration, support chat, spending analysis. Strong multi-turn reasoning and instruction-following.
- **Random Forest** — stock signal predictions. Deterministic and interpretable; 14 binary technical indicator flags; feature importance is auditable.
- **Isolation Forest** — fraud detection. No LLM. Fraud decisions must be reproducible and justifiable in a compliance review.

---

### Wealth Snapshot
| Feature | How |
|---|---|
| Parallel agent run | Portfolio agent + Spending Analyst run simultaneously via `asyncio.gather` with `snapshot=True` |
| 50-word briefs | Each agent trims output to a single-paragraph brief covering one key insight and one action |
| Two-row result card | Portfolio & Loans row + Banking & Cash Flow row displayed side by side |

---

### Banking & Spending Dashboard
| Feature | How |
|---|---|
| Bank accounts | Chase checking/savings for all customers; Citi credit card for moderate/aggressive profiles |
| 90-day transaction history | Salary, rent, utilities, groceries, dining, transport, entertainment, interest |
| Current month cashflow | Income, spending, net cashflow, savings rate — colour-coded thresholds |
| Category breakdown | 16 categories with horizontal bar chart and month-over-month % change |
| 3-month trend chart | Green income bars vs red spending bars side by side per month |
| Interest tracker | Interest earned (savings) vs interest paid (loans) with advisory text |
| AI spending analysis | GPT-4o analyses patterns and gives personalised recommendations |

---

### Admin Dashboard
| Feature | How |
|---|---|
| 50-customer table | Sorted by portfolio value descending; buy/sell volume and txn count per customer |
| 6 metric cards | Total customers, AUM, open alerts, high-severity, buy volume 30d, sell volume 30d |
| Leaderboard | Top 5 spenders, top 5 savers by savings rate, top 5 portfolios by value |
| Live portfolio ticks | WebSocket `dashboard_update` → matching customer row flashes green/red |
| Real-time alert sidebar | `/ws/alerts` WebSocket → last 10 alerts colour-coded by severity with slide-in animation |
| Demo fraud trigger | Admin-only button inserts a BTC transfer from Nigeria at 02:00 UTC and runs the full fraud pipeline live |

---

### Alerts & Fraud
| Feature | How |
|---|---|
| 6 fraud rules | Large txn (>$50k), night crypto (23:00–06:00), high-risk geo (NG/RU/CN/IR/KP), rapid txn (3+ in 10min), conservative + crypto >$5k, overdue loan + buy >$10k |
| ML anomaly scoring | Isolation Forest on 5 transaction features; score > 0.7 fires `ml_anomaly` alert |
| Pre-insert OTP gate | Fraud scoring runs before any DB insert; flagged transactions never enter the DB without OTP confirmation |
| Email alerts | Azure Communication Services sends fraud and risk alert emails; all demo emails routed to ops mailbox |
| Real-time alert feed | `/ws/alerts` → React prepends new alerts, deduplicates by `alert_id`, caps at 50 |

---

### ML Predictions (Market Agent)
| Feature | How |
|---|---|
| Random Forest model | Trained on 800+ US tickers with 14 binary technical indicator flags |
| 14 indicator flags | SMA cross, EMA cross, RSI overbought/oversold, MACD signal, Bollinger band touch, volume spike, ATR, ADX, Stochastic, CCI, Williams %R, OBV trend, price momentum |
| Temperature calibration | Raw RF probabilities scaled with T=3.0 to reduce overconfidence |
| Universe cache | 24h disk-backed pkl cache of last-row flags for all tickers; rebuilt daily at 13:30 UTC |
| Narrative | Gemini 2.0 Flash generates a paragraph; falls back to Azure GPT-4o if Gemini unavailable |
| UI display | Confidence bar per ticker, buy/sell/hold signal badge, raw RF output table with all 14 flags (collapsible) |

---

### Agent Debate (Critic)
| Feature | How |
|---|---|
| Conflict detection | `unrealized_pl_pct < −15%` (portfolio says reduce) AND `market_confidence > 70%` (market says buy) |
| Parallel execution | Portfolio agent + Market agent run via `asyncio.gather`; Critic receives both results |
| Conflict cards | Per-ticker cards showing Portfolio signal vs Market signal side by side (amber styling) |
| Critic verdict | Claude Haiku produces a final recommendation with confidence score and agreement level |

---

### Security
| Feature | How |
|---|---|
| Prompt injection blocking | `sanitize_query()` rejects 13 banned phrases, strips control characters, enforces 2000-char limit |
| Customer data isolation | Every DB query scoped to `customer_id`; customers cannot access other customers' data |
| OTP gate | High-risk transactions require email OTP confirmation before DB insert |
| Locked system prompts | Agent system prompts cannot be overridden via user input |
| Kubernetes secrets | All credentials stored in `kubectl create secret`, never in Git or Docker image |

---

### Automated Tests
| Test | Covers |
|---|---|
| `test_sanitize_query_clean_input` | Clean query passes through unchanged |
| `test_sanitize_query_blocks_prompt_injection` | Banned phrases raise ValueError |
| `test_sanitize_query_blocks_too_long` | Input >2000 chars rejected |
| `test_sanitize_query_strips_control_characters` | Null bytes and control chars stripped silently |
| `test_validate_customer_id` | `CUS-NNNN` passes; wrong format fails |
| `test_jwt_create_and_verify` | Token round-trip: create → decode → payload matches |
| `test_jwt_invalid_token_raises` | Tampered token raises HTTP 401 |
| `test_password_hash_and_verify` | Correct password verifies; wrong password fails |
| `test_critic_conflict_detection` | NVDA(−55.7%) + AAPL(−92.8%) flagged; BTC(+105%) + MSFT(+12.3%) not flagged |
| `test_random_walk_stays_within_bounds` | 50 iterations, each price within ±0.3% and always positive |

```bash
cd backend && pytest tests/test_core.py -v
```

---

## PostgreSQL Trigger Cascade

```
APScheduler (60s)
  → yfinance or ±0.3% random walk
  → UPDATE market_prices
  → trg_price_to_holdings   : recalculates unrealized P&L in portfolio_holdings
  → trg_holdings_to_summary : UPSERTs customer_summary (portfolio_value, allocation %)
  → trg_summary_to_ws       : pg_notify('dashboard_update')
  → asyncpg listener         : broadcasts JSON to all WebSocket clients
  → React useLivePrices      : flashes green/red on changed values

INSERT INTO transactions (buy/sell)
  → trg_cash_on_txn          : updates CASH holding (buy deducts cost, sell adds proceeds)

UPDATE customer_summary (crypto_pct)
  → trg_risk_breach          : inserts risk_breach alert if crypto% exceeds profile limit
```

No frontend polling. Pages re-render only when the database actually changes.

---

## Local Setup

```bash
# Prerequisites: Python 3.10+, Node 18, PostgreSQL

# Clone
git clone https://github.com/gowthamvsn/finsight_wip.git
cd finsight_wip

# Backend
cd backend
pip install -r requirements.txt
# Copy .env.example to .env and fill in your keys
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000

# Run tests
cd backend && pytest tests/test_core.py -v
```

---

## Azure Deployment

```bash
az login

# Build and push images to Azure Container Registry
az acr build --registry fincontaineregistry --image finsight-backend:latest --no-logs ./backend
az acr build --registry fincontaineregistry --image finsight-frontend:latest --no-logs ./frontend

# Configure kubectl
az aks get-credentials --resource-group MenoWE --name finkubernetes

# First-time: create namespace and secrets
kubectl create namespace finsight
kubectl create secret generic finsight-secrets --from-env-file=./backend/.env -n finsight
kubectl apply -f k8s/

# Rolling update (zero downtime)
kubectl set image deployment/backend backend=fincontaineregistry.azurecr.io/finsight-backend:latest -n finsight
kubectl set image deployment/frontend frontend=fincontaineregistry.azurecr.io/finsight-frontend:latest -n finsight
kubectl rollout restart deployment/backend -n finsight
kubectl rollout restart deployment/frontend -n finsight
kubectl rollout status deployment/backend -n finsight
kubectl rollout status deployment/frontend -n finsight
```

---

## High Availability

```bash
# Show running pods (2 replicas each)
kubectl get pods -n finsight

# Kill one backend pod — app keeps serving via second replica
kubectl delete pod <backend-pod-name> -n finsight

# Watch Kubernetes self-heal (~20 seconds)
kubectl get pods -n finsight -w
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, React Router 6, Vite 5, Tailwind CSS |
| Backend | FastAPI, asyncpg, APScheduler, Pydantic v2 |
| Database | Azure PostgreSQL Flexible Server, pg_notify triggers |
| AI / ML | Claude Haiku, Gemini 2.0 Flash, Azure GPT-4o, scikit-learn RF + Isolation Forest |
| Infrastructure | Azure Kubernetes Service, Azure Container Registry, Azure Blob Storage |
| Auth | JWT (HS256), bcrypt, role-based FastAPI Depends guards |
| Email | Azure Communication Services |
| CI/CD | GitHub Actions (`.github/workflows/deploy.yml`) on push to main |
