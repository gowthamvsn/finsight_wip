import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { apiFetch } from '../api/client'
import AgentStatusTicker from '../components/AgentStatusTicker'
import AgentDebate from '../components/AgentDebate'
import LivePriceBadge from '../components/LivePriceBadge'
import { useLivePrices } from '../hooks/useLivePrices'
import SpendingDashboard from '../components/SpendingDashboard'


function fmt(n, decimals = 0) {
  if (n == null) return '—'
  return Number(n).toLocaleString('en-US', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })
}

function fmtUSD(n) {
  return n == null ? '—' : `$${fmt(n)}`
}

function ago(ts) {
  if (!ts) return ''
  const d = (Date.now() - new Date(ts)) / 1000
  if (d < 60) return `${Math.round(d)}s ago`
  if (d < 3600) return `${Math.round(d / 60)}m ago`
  return `${Math.round(d / 3600)}h ago`
}

function RiskBadge({ profile }) {
  const colors = {
    conservative: 'bg-blue-900 text-blue-300',
    moderate: 'bg-purple-900 text-purple-300',
    aggressive: 'bg-red-900 text-red-300',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[profile] || 'bg-gray-700 text-gray-300'}`}>
      {profile}
    </span>
  )
}

function SignalBadge({ signal }) {
  const colors = {
    'strong buy': 'bg-emerald-900 text-emerald-300',
    buy: 'bg-green-900 text-green-300',
    neutral: 'bg-gray-700 text-gray-300',
    caution: 'bg-red-900 text-red-300',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[signal] || 'bg-gray-700 text-gray-300'}`}>
      {signal}
    </span>
  )
}

function SevBadge({ severity }) {
  const colors = {
    critical: 'bg-red-900 text-red-300',
    high: 'bg-orange-900 text-orange-300',
    medium: 'bg-yellow-900 text-yellow-300',
    low: 'bg-blue-900 text-blue-300',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[severity] || 'bg-gray-700 text-gray-300'}`}>
      {severity}
    </span>
  )
}

export default function CustomerDetail() {
  const { id } = useParams()
  const { token } = useAuth()
  const navigate = useNavigate()
  const { refreshTick } = useLivePrices()
  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // Agent state — one slot per agent type so they don't overwrite each other
  const [agentState, setAgentState] = useState({
    portfolio: { steps: [], result: '', running: false },
    market:    { steps: [], result: '', running: false },
    report:    { steps: [], result: '', running: false },
  })
  const [predictions, setPredictions] = useState(null)
  const [predLoading, setPredLoading] = useState(false)
  const [showRawRF, setShowRawRF] = useState(false)
  const [rawRF, setRawRF] = useState(null)
  const [debateResult, setDebateResult] = useState(null)
  const [debateLoading, setDebateLoading] = useState(false)
  const [activeTab, setActiveTab] = useState('portfolio')

  useEffect(() => {
    apiFetch(`/api/portfolio/${id}`, {}, token)
      .then(data => { setPortfolio(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [id, token, refreshTick])

  function setAgent(type, patch) {
    setAgentState(prev => ({ ...prev, [type]: { ...prev[type], ...patch } }))
  }

  async function runAgent(type) {
    const map = {
      portfolio: { name: 'Portfolio Agent', path: `/api/agent/portfolio/${id}` },
      market:    { name: 'Market Agent',    path: `/api/agent/market/${id}` },
      report:    { name: 'Report Agent',    path: `/api/agent/report/${id}` },
    }
    const agent = map[type]
    setAgent(type, {
      running: true,
      result: '',
      steps: [
        { name: 'Orchestrator', status: 'complete', duration_ms: 80 },
        { name: agent.name, status: 'running', duration_ms: null },
      ],
    })
    const t0 = Date.now()
    try {
      const data = await apiFetch(agent.path, { method: 'POST' }, token)
      const ms = Date.now() - t0
      if (data.error) {
        setAgent(type, {
          running: false,
          steps: [
            { name: 'Orchestrator', status: 'complete', duration_ms: 80 },
            { name: agent.name, status: 'error', duration_ms: ms },
          ],
          result: `Error: ${data.error}${data.detail ? '\n\nDetail: ' + data.detail : ''}`,
        })
        return
      }
      const completeSteps = [
        { name: 'Orchestrator', status: 'complete', duration_ms: 80 },
        { name: agent.name, status: 'complete', duration_ms: ms },
      ]
      if (type === 'market') {
        setPredictions(data)
        if (data.raw_rf_top10) setRawRF(data.raw_rf_top10)
        setAgent(type, { running: false, steps: completeSteps, result: data.narrative || '' })
      } else if (type === 'portfolio') {
        setAgent(type, { running: false, steps: completeSteps, result: data.analysis || JSON.stringify(data, null, 2) })
      } else {
        setAgent(type, {
          running: false,
          steps: completeSteps,
          result: data.report_preview
            ? `Report ${data.report_id} saved.\n\n${data.report_preview}`
            : `Report ${data.report_id || 'unknown'} generated`,
        })
      }
    } catch (e) {
      setAgent(type, {
        running: false,
        steps: [
          { name: 'Orchestrator', status: 'complete', duration_ms: 80 },
          { name: agent.name, status: 'error', duration_ms: null },
        ],
        result: `Error: ${e.message}`,
      })
    }
  }

  async function runDebate() {
    setDebateLoading(true)
    try {
      const data = await apiFetch(`/api/agent/critic/${id}`, { method: 'POST' }, token)
      setDebateResult(data.critic)
      // Also populate predictions if market data came back
      if (data.market?.portfolio_predictions) {
        setPredictions(data.market)
        if (data.market.raw_rf_top10) setRawRF(data.market.raw_rf_top10)
      }
    } catch (e) {
      setDebateResult({ conflicts_found: 0, conflict_details: [], final_recommendation: `Error: ${e.message}`, agent_agreement: 'unknown', critic_confidence: 'low' })
    } finally {
      setDebateLoading(false)
    }
  }

  async function refreshPredictions() {
    setPredLoading(true)
    try {
      const data = await apiFetch(`/api/agent/market/${id}`, { method: 'POST' }, token)
      setPredictions(data)
      if (data.raw_rf_top10) setRawRF(data.raw_rf_top10)
    } catch {}
    finally { setPredLoading(false) }
  }

  if (loading) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center">
      <span className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
  if (error) return (
    <div className="min-h-screen bg-gray-950 flex items-center justify-center text-red-400">{error}</div>
  )
  if (!portfolio) return null

  const { summary, holdings, transactions, loans, alerts } = portfolio
  const initials = `${summary.first_name?.[0] || ''}${summary.last_name?.[0] || ''}`

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Nav */}
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center gap-4">
        <button
          onClick={() => navigate('/admin')}
          className="text-gray-400 hover:text-white text-sm transition-colors"
        >
          ← Back
        </button>
        <span className="text-gray-600">|</span>
        <span className="text-sm text-gray-400">Customer Detail</span>
      </nav>

      <div className="px-6 py-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-gray-900 rounded-xl p-6 border border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-blue-700 flex items-center justify-center text-xl font-bold">
              {initials}
            </div>
            <div>
              <h1 className="text-2xl font-bold">{summary.first_name} {summary.last_name}</h1>
              <div className="flex items-center gap-2 mt-1">
                <RiskBadge profile={summary.risk_profile} />
                <span className="text-xs bg-gray-700 text-gray-300 px-2 py-0.5 rounded capitalize">
                  {summary.advisor_tier}
                </span>
                <span className="text-xs text-gray-500">{id}</span>
              </div>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={() => runAgent('report')}
              className="bg-purple-700 hover:bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              Generate Report
            </button>
          </div>
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 border-b border-gray-800">
          {[
            { id: 'portfolio', label: 'Portfolio' },
            { id: 'banking',   label: '🏦 Banking & Spending' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-400'
                  : 'border-transparent text-gray-500 hover:text-gray-300'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'banking' && (
          <SpendingDashboard customerId={id} token={token} />
        )}

        {activeTab === 'portfolio' && <>

        {/* 4 Metric Cards */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Portfolio Value', value: fmtUSD(summary.portfolio_value), color: 'blue' },
            { label: 'Net Worth',       value: fmtUSD(summary.net_worth),       color: 'emerald' },
            { label: 'Net P&L',         value: fmtUSD(summary.net_pl),          color: (summary.net_pl || 0) >= 0 ? 'emerald' : 'red' },
            { label: 'Cash Balance',    value: fmtUSD(summary.cash_balance),    color: 'gray' },
          ].map(card => (
            <div key={card.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
              <p className="text-xs text-gray-400 uppercase tracking-wide">{card.label}</p>
              <p className={`text-2xl font-bold mt-1 text-${card.color}-400 font-mono`}>{card.value}</p>
            </div>
          ))}
        </div>

        {/* P&L Breakdown + Recent Alerts */}
        <div className="grid grid-cols-2 gap-4">
          {/* P&L Breakdown */}
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <h2 className="font-semibold mb-4 text-gray-200">P&L Breakdown</h2>
            <div className="space-y-2 text-sm">
              {[
                {
                  label: 'Gross investment gains',
                  value: (summary.unrealized_pl || 0) + (summary.realized_pl || 0),
                },
                {
                  label: 'Loan interest paid YTD',
                  value: -(summary.interest_paid_ytd || 0),
                },
                {
                  label: 'Net P&L',
                  value: summary.net_pl || 0,
                  bold: true,
                },
              ].map(row => (
                <div
                  key={row.label}
                  className={`flex justify-between ${row.bold ? 'border-t border-gray-700 pt-2 font-semibold' : ''}`}
                >
                  <span className="text-gray-400">{row.label}</span>
                  <span className={`font-mono ${row.value >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                    {row.value >= 0 ? '+' : ''}{fmtUSD(row.value)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between border-t border-gray-700 pt-2 text-xs">
                <span className="text-gray-400">vs S&P 500</span>
                <span className={`font-mono ${(summary.annualized_return_pct || 0) > (summary.sp500_return_pct || 0) ? 'text-emerald-400' : 'text-red-400'}`}>
                  {(summary.annualized_return_pct || 0).toFixed(1)}% vs {(summary.sp500_return_pct || 0).toFixed(1)}%
                  {' '}{(summary.annualized_return_pct || 0) > (summary.sp500_return_pct || 0) ? '▲ Beating' : '▼ Lagging'}
                </span>
              </div>
            </div>
          </div>

          {/* Recent Alerts */}
          <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
            <h2 className="font-semibold mb-4 text-gray-200">Recent Alerts</h2>
            {alerts.length === 0 ? (
              <p className="text-gray-500 text-sm">No open alerts</p>
            ) : (
              <div className="space-y-2">
                {alerts.slice(0, 5).map(a => (
                  <div key={a.alert_id} className="flex items-start gap-2 text-sm">
                    <SevBadge severity={a.severity} />
                    <div className="flex-1 min-w-0">
                      <p className="text-gray-300 text-xs line-clamp-1">{a.description}</p>
                      <p className="text-gray-500 text-xs">{ago(a.detected_at)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Holdings Table */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="font-semibold text-gray-200">Holdings</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                <tr>
                  {['Ticker', 'Type', 'Qty', 'Avg Buy', 'Current Price', 'Value', 'Unreal P&L%'].map(h => (
                    <th key={h} className="px-4 py-2 text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-800">
                {(holdings || []).filter(h => h.asset_type !== 'cash').map(h => (
                  <tr key={h.ticker} className="hover:bg-gray-800/40">
                    <td className="px-4 py-2 font-bold text-blue-400">{h.ticker}</td>
                    <td className="px-4 py-2 text-gray-400 capitalize text-xs">{h.asset_type}</td>
                    <td className="px-4 py-2 font-mono text-gray-300">{h.quantity}</td>
                    <td className="px-4 py-2 font-mono text-gray-400">${fmt(h.avg_buy_price, 2)}</td>
                    <td className="px-4 py-2">
                      <LivePriceBadge price={h.current_price} change1d={h.change_1d_pct} />
                    </td>
                    <td className="px-4 py-2 font-mono text-white">${fmt(h.current_value)}</td>
                    <td className={`px-4 py-2 font-mono ${(h.unrealized_pl_pct || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                      {(h.unrealized_pl_pct || 0) >= 0 ? '+' : ''}{fmt(h.unrealized_pl_pct, 2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* ML Predictions */}
        <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-gray-200">AI Market Predictions</h2>
              <p className="text-xs text-gray-500">Random Forest · 14 binary flag features · scores may skew high on synthetic training data</p>
            </div>
            <button
              onClick={refreshPredictions}
              disabled={predLoading}
              className="bg-blue-700 hover:bg-blue-600 disabled:bg-blue-900 text-white text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
            >
              {predLoading && (
                <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
              )}
              Refresh Predictions
            </button>
          </div>
          {predictions ? (
            <div className="p-4 space-y-3">
              {(predictions.portfolio_predictions || []).map(p => (
                <div key={p.ticker} className="flex items-center gap-3">
                  <span className="w-16 font-bold text-blue-400 text-sm">{p.ticker}</span>
                  <div className="flex-1 bg-gray-800 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${p.confidence}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-xs text-gray-400 font-mono">{p.confidence}%</span>
                  <SignalBadge signal={p.signal} />
                  <span className="text-xs text-gray-500">{p.flags_fired} flags</span>
                </div>
              ))}
              {predictions.narrative && (
                <div className="mt-4 p-3 bg-gray-800 rounded-lg text-sm text-gray-300 leading-relaxed">
                  {predictions.narrative}
                </div>
              )}
              {predictions.universe_scanned > 0 && (
                <p className="text-xs text-gray-500">Universe scanned: {predictions.universe_scanned} tickers</p>
              )}
              {/* Raw RF Output */}
              {rawRF && (
                <div className="mt-3 border-t border-gray-700 pt-3">
                  <button
                    onClick={() => setShowRawRF(v => !v)}
                    className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                  >
                    {showRawRF ? '▼' : '▶'} Raw RF Model Output (top 10 universe scores)
                  </button>
                  {showRawRF && (
                    <div className="mt-2 overflow-x-auto">
                      <table className="w-full text-xs font-mono">
                        <thead className="text-gray-500">
                          <tr>
                            <th className="text-left py-1 pr-3">Ticker</th>
                            <th className="text-left py-1 pr-3">Raw Prob</th>
                            <th className="text-left py-1 pr-3">Calibrated</th>
                            <th className="text-left py-1 pr-3">Flags/14</th>
                            <th className="text-left py-1 text-gray-600">RSI&lt;30</th>
                            <th className="text-left py-1 text-gray-600">MACD+</th>
                            <th className="text-left py-1 text-gray-600">&gt;EMA50</th>
                            <th className="text-left py-1 text-gray-600">HighVol</th>
                            <th className="text-left py-1 text-gray-600">EPS+</th>
                            <th className="text-left py-1 text-gray-600">GKVol</th>
                            <th className="text-left py-1 text-gray-600">ATR+</th>
                            <th className="text-left py-1 text-gray-600">&gt;BBLow</th>
                            <th className="text-left py-1 text-gray-600">StochX</th>
                            <th className="text-left py-1 text-gray-600">ADX&gt;20</th>
                            <th className="text-left py-1 text-gray-600">ROC&gt;2</th>
                            <th className="text-left py-1 text-gray-600">CCI</th>
                            <th className="text-left py-1 text-gray-600">OBV↑</th>
                            <th className="text-left py-1 text-gray-600">BB↑</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-800">
                          {rawRF.map(r => (
                            <tr key={r.ticker} className="hover:bg-gray-800/40">
                              <td className="py-1 pr-3 text-blue-400 font-bold">{r.ticker}</td>
                              <td className="py-1 pr-3 text-red-400">{r.raw_prob.toFixed(4)}</td>
                              <td className={`py-1 pr-3 ${r.cal_prob > 0.75 ? 'text-amber-400' : 'text-emerald-400'}`}>
                                {r.cal_prob?.toFixed(4) ?? '—'}
                              </td>
                              <td className="py-1 pr-3 text-gray-400">{r.flags_fired}/14</td>
                              {Object.values(r.flags).map((v, i) => (
                                <td key={i} className={`py-1 pr-1 ${v ? 'text-emerald-400' : 'text-gray-700'}`}>{v}</td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                      <p className="text-xs text-gray-600 mt-1">Raw = RF output on training data (memorized). Calibrated = temperature-scaled T=3.0 (what's shown in UI).</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="p-6 text-center text-gray-500 text-sm">
              Click "Refresh Predictions" to load AI market analysis
            </div>
          )}
        </div>

        {/* Agent Debate */}
        <AgentDebate result={debateResult} loading={debateLoading} onRun={runDebate} />

        {/* Loans */}
        {(loans || []).length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-800">
              <h2 className="font-semibold text-gray-200">Loans</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                  <tr>
                    {['Type', 'Outstanding', 'Rate%', 'EMI/mo', 'Next Due', 'Status'].map(h => (
                      <th key={h} className="px-4 py-2 text-left">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {loans.map((l, i) => (
                    <tr key={i} className={l.status === 'overdue' ? 'bg-red-900/20' : ''}>
                      <td className="px-4 py-2 capitalize text-gray-300">{l.loan_type}</td>
                      <td className="px-4 py-2 font-mono text-white">${fmt(l.outstanding_balance)}</td>
                      <td className="px-4 py-2 font-mono text-amber-400">{l.interest_rate_pct}%</td>
                      <td className="px-4 py-2 font-mono text-gray-300">${fmt(l.emi_monthly)}</td>
                      <td className="px-4 py-2 text-gray-400 text-xs">
                        {l.next_due_date?.split('T')[0] || '—'}
                      </td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          l.status === 'overdue' ? 'bg-red-800 text-red-200' :
                          l.status === 'active'  ? 'bg-green-900 text-green-300' :
                                                   'bg-gray-700 text-gray-300'
                        }`}>
                          {l.status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Recent Transactions */}
        {(transactions || []).length > 0 && (
          <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-800">
              <h2 className="font-semibold text-gray-200">Recent Transactions</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                  <tr>
                    {['Ticker', 'Type', 'Qty', 'Price', 'Total', 'Date', 'Flag'].map(h => (
                      <th key={h} className="px-4 py-2 text-left">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {transactions.slice(0, 10).map((t, i) => (
                    <tr key={i} className={t.flagged ? 'bg-red-900/10' : ''}>
                      <td className="px-4 py-2 font-bold text-blue-400">{t.ticker}</td>
                      <td className={`px-4 py-2 font-medium ${t.txn_type === 'buy' ? 'text-emerald-400' : 'text-red-400'}`}>
                        {t.txn_type?.toUpperCase()}
                      </td>
                      <td className="px-4 py-2 font-mono text-gray-300">{t.quantity}</td>
                      <td className="px-4 py-2 font-mono text-gray-400">${fmt(t.price_at_txn, 2)}</td>
                      <td className="px-4 py-2 font-mono text-white">${fmt(t.total_value)}</td>
                      <td className="px-4 py-2 text-gray-500 text-xs">
                        {t.txn_timestamp ? new Date(t.txn_timestamp).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-2">
                        {t.flagged && (
                          <span className="bg-red-800 text-red-200 text-xs px-1.5 py-0.5 rounded">⚑</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Agent Control Panel */}
        <div className="bg-gray-900 rounded-xl p-5 border border-gray-800">
          <h2 className="font-semibold mb-4 text-gray-200">Agent Control Panel</h2>
          <div className="flex gap-3 mb-4">
            {[
              { label: 'Run Portfolio Analysis', type: 'portfolio', colorClass: 'bg-blue-700 hover:bg-blue-600' },
              { label: 'Get Market Predictions', type: 'market',    colorClass: 'bg-emerald-700 hover:bg-emerald-600' },
              { label: 'Generate Report',         type: 'report',   colorClass: 'bg-purple-700 hover:bg-purple-600' },
            ].map(btn => (
              <button
                key={btn.type}
                onClick={() => runAgent(btn.type)}
                disabled={agentState[btn.type].running}
                className={`flex-1 ${btn.colorClass} disabled:opacity-50 text-white py-2 px-4 rounded-lg text-sm font-medium transition-colors flex items-center justify-center gap-2`}
              >
                {agentState[btn.type].running && (
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                {btn.label}
              </button>
            ))}
          </div>
          {/* Independent result pane per agent */}
          {['portfolio', 'market', 'report'].map(type => {
            const a = agentState[type]
            if (a.steps.length === 0) return null
            const labels = { portfolio: 'Portfolio Analysis', market: 'Market Predictions', report: 'Report' }
            const colors = { portfolio: 'border-blue-700', market: 'border-emerald-700', report: 'border-purple-700' }
            return (
              <div key={type} className={`mt-3 border-l-2 ${colors[type]} pl-3`}>
                <p className="text-xs text-gray-500 mb-1 uppercase tracking-wide">{labels[type]}</p>
                <AgentStatusTicker steps={a.steps} />
                {a.result && (
                  <div className="mt-2 p-3 bg-gray-800 rounded-lg text-sm text-gray-300 leading-relaxed whitespace-pre-wrap">
                    {a.result}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        </> /* end portfolio tab */}
      </div>
    </div>
  )
}
