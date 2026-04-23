import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { apiFetch } from '../api/client'
import AgentDebate from '../components/AgentDebate'
import LivePriceBadge from '../components/LivePriceBadge'
import { useLivePrices } from '../hooks/useLivePrices'
import TransactionModal from '../components/TransactionModal'
import SpendingDashboard from '../components/SpendingDashboard'

// ─── Utilities ────────────────────────────────────────────────────────────────

function fmt(n, decimals = 0) {
  if (n == null) return '—'
  return Number(n).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  })
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

// ─── Sub-components ──────────────────────────────────────────────────────────

function RiskBadge({ profile }) {
  const colors = {
    conservative: 'bg-blue-100 text-blue-700',
    moderate: 'bg-violet-100 text-violet-700',
    aggressive: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[profile] || 'bg-slate-100 text-slate-600'}`}>
      {profile}
    </span>
  )
}

function SevBadge({ severity }) {
  const colors = {
    critical: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    medium: 'bg-yellow-100 text-yellow-700',
    low: 'bg-sky-100 text-sky-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[severity] || 'bg-slate-100 text-slate-600'}`}>
      {severity}
    </span>
  )
}

function SignalBadge({ signal }) {
  const colors = {
    'strong buy': 'bg-emerald-100 text-emerald-700',
    buy: 'bg-green-100 text-green-700',
    neutral: 'bg-slate-100 text-slate-600',
    caution: 'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs ${colors[signal] || 'bg-slate-100 text-slate-600'}`}>
      {signal}
    </span>
  )
}

// ─── Support Chat Widget ──────────────────────────────────────────────────────

function SupportChat({ customerId, token }) {
  const [open, setOpen] = useState(false)
  const [messages, setMessages] = useState([
    { role: 'assistant', text: 'Hi! I\'m your Portfolio Assistant. Ask me anything about your investments.' },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    if (open && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, open])

  async function handleSend() {
    const query = input.trim()
    if (!query || loading) return
    setInput('')
    setMessages(prev => [...prev, { role: 'user', text: query }])
    setLoading(true)
    setMessages(prev => [...prev, { role: 'assistant', text: '…', analyzing: true }])
    try {
      const data = await apiFetch('/api/agent/support', {
        method: 'POST',
        body: JSON.stringify({ query, customer_id: customerId }),
      }, token)
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: 'assistant', text: data.response || 'No response received.', source: data.source || null },
      ])
    } catch (e) {
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: 'assistant', text: `Error: ${e.message}`, error: true },
      ])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 flex flex-col items-end gap-3">
      {/* Chat Panel */}
      {open && (
        <div className="w-80 bg-white border border-slate-200 rounded-2xl shadow-2xl flex flex-col overflow-hidden"
             style={{ height: '420px' }}>
          {/* Header */}
          <div className="bg-blue-700 px-4 py-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-white font-semibold text-sm">Portfolio Assistant</span>
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
            </div>
            <button
              onClick={() => setOpen(false)}
              className="text-blue-200 hover:text-white text-lg leading-none"
            >
              ×
            </button>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto p-3 space-y-2 bg-slate-50">
            {messages.map((msg, i) => (
              <div
                key={i}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div className={`max-w-[85%] rounded-xl px-3 py-2 text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-blue-600 text-white'
                    : msg.error
                      ? 'bg-red-50 text-red-700'
                      : 'bg-slate-100 text-slate-800'
                }`}>
                  {msg.analyzing ? (
                    <span className="flex items-center gap-1.5 text-slate-500 italic">
                      <span className="w-3 h-3 border-2 border-gray-400 border-t-transparent rounded-full animate-spin" />
                      Analyzing…
                    </span>
                  ) : (
                    <>
                      {msg.text}
                      {msg.source && (
                        <div className="mt-1.5 pt-1.5 border-t border-slate-200 text-xs text-blue-600 flex items-center gap-1">
                          <span className="font-medium">Source:</span> {msg.source}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t border-slate-200 bg-white flex gap-2">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask about your portfolio…"
              disabled={loading}
              className="flex-1 bg-slate-100 border border-slate-200 rounded-lg px-3 py-2 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-50"
            />
            <button
              onClick={handleSend}
              disabled={loading || !input.trim()}
              className="bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 disabled:cursor-not-allowed text-white px-3 py-2 rounded-lg text-sm font-medium transition-colors"
            >
              Send
            </button>
          </div>
        </div>
      )}

      {/* Toggle Button */}
      <button
        onClick={() => setOpen(!open)}
        className="w-14 h-14 bg-blue-600 hover:bg-blue-500 text-white rounded-full shadow-lg flex items-center justify-center text-2xl transition-colors"
        title="Portfolio Assistant"
      >
        {open ? '×' : '💬'}
      </button>
    </div>
  )
}

// ─── Main Page ────────────────────────────────────────────────────────────────

export default function CustomerPortfolio() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()
  const { isConnected, refreshTick } = useLivePrices()

  const [portfolio, setPortfolio] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [predictions, setPredictions] = useState(null)
  const [predLoading, setPredLoading] = useState(false)
  const [showTxn, setShowTxn] = useState(false)
  const [activeTab, setActiveTab] = useState('portfolio')
  const [analysis, setAnalysis] = useState(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [snapshot, setSnapshot] = useState(null)
  const [snapshotLoading, setSnapshotLoading] = useState(false)
  const [news, setNews] = useState([])
  const [newsLoading, setNewsLoading] = useState(false)
  const [debateResult, setDebateResult] = useState(null)
  const [debateLoading, setDebateLoading] = useState(false)

  const customerId = user?.user_id

  useEffect(() => {
    if (!customerId) return
    apiFetch(`/api/portfolio/${customerId}`, {}, token)
      .then(data => { setPortfolio(data); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [customerId, token, refreshTick])

  useEffect(() => {
    if (!customerId || !token) return
    setNewsLoading(true)
    apiFetch(`/api/portfolio/${customerId}/news`, {}, token)
      .then(data => setNews(data.news || []))
      .catch(() => setNews([]))
      .finally(() => setNewsLoading(false))
  }, [customerId, token])

  async function loadSnapshot() {
    setSnapshotLoading(true)
    try {
      const data = await apiFetch(`/api/agent/wealth-snapshot/${customerId}`, { method: 'POST' }, token)
      setSnapshot(data)
    } catch (e) {
      setSnapshot({ portfolio: `Error: ${e.message}`, banking: '' })
    } finally {
      setSnapshotLoading(false)
    }
  }

  async function loadAnalysis() {
    setAnalysisLoading(true)
    try {
      const data = await apiFetch(`/api/agent/portfolio/${customerId}`, { method: 'POST' }, token)
      setAnalysis(data.analysis || data.result || data.summary || JSON.stringify(data))
    } catch (e) {
      setAnalysis(`Error: ${e.message}`)
    } finally {
      setAnalysisLoading(false)
    }
  }

  async function runDebate() {
    setDebateLoading(true)
    try {
      const data = await apiFetch(`/api/agent/critic/${customerId}`, { method: 'POST' }, token)
      setDebateResult(data.critic)
      if (data.market?.portfolio_predictions) setPredictions(data.market)
    } catch (e) {
      setDebateResult({ conflicts_found: 0, conflict_details: [], final_recommendation: `Error: ${e.message}`, agent_agreement: 'unknown', critic_confidence: 'low' })
    } finally {
      setDebateLoading(false)
    }
  }

  async function loadPredictions() {
    setPredLoading(true)
    try {
      const data = await apiFetch(`/api/agent/market/${customerId}`, { method: 'POST' }, token)
      setPredictions(data)
    } catch (e) {
      console.error('Predictions error:', e.message)
    } finally {
      setPredLoading(false)
    }
  }

  async function handleLogout() {
    try { await apiFetch('/api/auth/logout', { method: 'POST' }, token) } catch {}
    logout()
    navigate('/')
  }

  if (loading) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <span className="w-10 h-10 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
    </div>
  )
  if (error) return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center text-red-400 text-center p-8">
      <div>
        <p className="text-xl mb-2">Failed to load portfolio</p>
        <p className="text-sm text-slate-400">{error}</p>
      </div>
    </div>
  )
  if (!portfolio) return null

  const { summary, holdings, transactions, loans, alerts } = portfolio
  const initials = `${summary.first_name?.[0] || ''}${summary.last_name?.[0] || ''}`

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Nav */}
      <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-sm font-bold">F</span>
          </div>
          <span className="text-lg font-semibold">FinSight</span>
          <span className="text-slate-400 text-sm ml-1">My Portfolio</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`} />
            {isConnected ? 'Live' : 'Offline'}
          </div>
          <span className="text-sm text-slate-700">{user?.full_name}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-slate-500 hover:text-slate-800 transition-colors"
          >
            Logout
          </button>
        </div>
      </nav>

      <div className="px-6 py-6 max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="bg-white rounded-xl p-6 border border-slate-200 flex items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-blue-700 flex items-center justify-center text-xl font-bold text-white">
            {initials}
          </div>
          <div className="flex-1">
            <h1 className="text-2xl font-bold">{summary.first_name} {summary.last_name}</h1>
            <div className="flex items-center gap-2 mt-1">
              <RiskBadge profile={summary.risk_profile} />
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded capitalize">
                {summary.advisor_tier}
              </span>
              <span className="text-xs text-slate-400">{customerId}</span>
            </div>
          </div>
          <button
            onClick={() => setShowTxn(true)}
            className="bg-emerald-700 hover:bg-emerald-600 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            + New Transaction
          </button>
        </div>

        {/* Wealth Snapshot */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-800">Wealth Snapshot</h2>
              <p className="text-xs text-slate-400 mt-0.5">Portfolio + Banking · 2 agents in parallel</p>
            </div>
            <button
              onClick={loadSnapshot}
              disabled={snapshotLoading}
              className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-xs px-4 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
            >
              {snapshotLoading && <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              {snapshot ? 'Refresh' : 'Get Wealth Snapshot'}
            </button>
          </div>

          {snapshotLoading && !snapshot && (
            <div className="px-5 py-6 flex items-center gap-3 text-slate-500 text-sm">
              <span className="w-4 h-4 border-2 border-indigo-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
              Running portfolio &amp; banking agents in parallel…
            </div>
          )}

          {snapshot && (
            <div className="divide-y divide-slate-100">
              <div className="px-5 py-4 flex gap-3">
                <span className="text-lg flex-shrink-0">📊</span>
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Portfolio &amp; Loans</p>
                  <p className="text-sm text-slate-700 leading-relaxed">{snapshot.portfolio}</p>
                </div>
              </div>
              <div className="px-5 py-4 flex gap-3">
                <span className="text-lg flex-shrink-0">🏦</span>
                <div>
                  <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">Banking &amp; Cash Flow</p>
                  <p className="text-sm text-slate-700 leading-relaxed">{snapshot.banking}</p>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Tab Navigation */}
        <div className="flex gap-1 border-b border-slate-200">
          {[
            { id: 'portfolio', label: 'Portfolio' },
            { id: 'banking',   label: '🏦 Banking & Spending' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab.id
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-slate-400 hover:text-slate-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'banking' && (
          <SpendingDashboard customerId={customerId} token={token} />
        )}

        {activeTab === 'portfolio' && <>

        {/* 4 Metric Cards */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {[
            { label: 'Portfolio Value', value: fmtUSD(summary.portfolio_value), color: 'blue' },
            { label: 'Net Worth',       value: fmtUSD(summary.net_worth),       color: 'emerald' },
            { label: 'Net P&L',         value: fmtUSD(summary.net_pl),          color: (summary.net_pl || 0) >= 0 ? 'emerald' : 'red' },
            { label: 'Cash Balance',    value: fmtUSD(summary.cash_balance),    color: 'gray' },
          ].map(card => (
            <div key={card.label} className="bg-white rounded-xl p-4 border border-slate-200">
              <p className="text-xs text-slate-500 uppercase tracking-wide">{card.label}</p>
              <p className={`text-2xl font-bold mt-1 text-${card.color}-600 font-mono`}>{card.value}</p>
            </div>
          ))}
        </div>

        {/* P&L + Actions + News + Analysis — 2-column grid */}
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">

          {/* P&L Breakdown */}
          <div className="bg-white rounded-xl p-5 border border-slate-200">
            <h2 className="font-semibold mb-4 text-slate-800">P&L Breakdown</h2>
            <div className="space-y-2 text-sm">
              {[
                { label: 'Gross investment gains', value: (summary.unrealized_pl || 0) + (summary.realized_pl || 0) },
                { label: 'Loan interest paid YTD', value: -(summary.interest_paid_ytd || 0) },
                { label: 'Net P&L', value: summary.net_pl || 0, bold: true },
              ].map(row => (
                <div key={row.label} className={`flex justify-between ${row.bold ? 'border-t border-slate-200 pt-2 font-semibold' : ''}`}>
                  <span className="text-slate-500">{row.label}</span>
                  <span className={`font-mono ${row.value >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {row.value >= 0 ? '+' : ''}{fmtUSD(row.value)}
                  </span>
                </div>
              ))}
              <div className="flex justify-between border-t border-slate-200 pt-2 text-xs">
                <span className="text-slate-500">vs S&P 500</span>
                <span className={`font-mono ${(summary.annualized_return_pct || 0) > (summary.sp500_return_pct || 0) ? 'text-emerald-600' : 'text-red-600'}`}>
                  {(summary.annualized_return_pct || 0).toFixed(1)}% vs {(summary.sp500_return_pct || 0).toFixed(1)}%
                  {' '}{(summary.annualized_return_pct || 0) > (summary.sp500_return_pct || 0) ? '▲ Beating' : '▼ Lagging'}
                </span>
              </div>
            </div>
          </div>

          {/* Actions Needed */}
          <div className="bg-white rounded-xl p-5 border border-slate-200">
            <h2 className="font-semibold mb-4 text-slate-800">Actions Needed</h2>
            {(() => {
              const actions = []
              const now = Date.now()
              ;(loans || []).forEach(l => {
                if (!l.next_due_date) return
                const due = new Date(l.next_due_date)
                const daysLeft = Math.ceil((due - now) / 86400000)
                if (l.status === 'overdue') {
                  actions.push({ type: 'overdue', label: `${l.loan_type} EMI overdue`, sub: `$${fmt(l.emi_monthly)}/mo outstanding`, color: 'red' })
                } else if (daysLeft <= 30) {
                  actions.push({ type: 'due', label: `${l.loan_type} payment due`, sub: `$${fmt(l.emi_monthly)} due in ${daysLeft} day${daysLeft !== 1 ? 's' : ''}`, color: daysLeft <= 7 ? 'amber' : 'blue' })
                }
              })
              ;(alerts || []).filter(a => a.severity === 'critical' || a.severity === 'high').slice(0, 2).forEach(a => {
                actions.push({ type: 'alert', label: a.alert_type?.replace(/_/g, ' '), sub: a.description, color: 'orange' })
              })
              if (actions.length === 0) return <p className="text-slate-400 text-sm">No immediate actions required</p>
              return (
                <div className="space-y-2">
                  {actions.map((a, i) => (
                    <div key={i} className={`flex items-start gap-3 p-2.5 rounded-lg bg-${a.color}-50 border border-${a.color}-200`}>
                      <span className={`mt-0.5 w-2 h-2 rounded-full bg-${a.color}-500 flex-shrink-0`} />
                      <div className="min-w-0">
                        <p className={`text-sm font-medium text-${a.color}-700 capitalize`}>{a.label}</p>
                        <p className="text-xs text-slate-500 line-clamp-2">{a.sub}</p>
                      </div>
                    </div>
                  ))}
                </div>
              )
            })()}
          </div>

          {/* Market News */}
          <div className="bg-white rounded-xl p-5 border border-slate-200">
            <h2 className="font-semibold mb-4 text-slate-800">Market News</h2>
            {newsLoading ? (
              <div className="flex items-center gap-2 text-slate-400 text-sm">
                <span className="w-4 h-4 border-2 border-gray-500 border-t-transparent rounded-full animate-spin" />
                Loading news…
              </div>
            ) : news.length === 0 ? (
              <p className="text-slate-400 text-sm">No news available for your holdings</p>
            ) : (
              <div className="space-y-3">
                {news.slice(0, 5).map((n, i) => (
                  <div key={i} className="flex items-start gap-2">
                    <span className="mt-1 text-xs font-bold text-blue-600 w-12 flex-shrink-0">{n.ticker}</span>
                    <div className="min-w-0">
                      {n.link ? (
                        <a href={n.link} target="_blank" rel="noreferrer"
                           className="text-xs text-slate-700 hover:text-blue-700 line-clamp-2 leading-relaxed">
                          {n.title}
                        </a>
                      ) : (
                        <p className="text-xs text-slate-700 line-clamp-2">{n.title}</p>
                      )}
                      <p className="text-xs text-slate-400 mt-0.5">{n.publisher} · {n.published_at ? new Date(n.published_at * 1000).toLocaleDateString() : ''}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Portfolio Analysis */}
          <div className="bg-white rounded-xl p-5 border border-slate-200">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold text-slate-800">Portfolio Analysis</h2>
              <button
                onClick={loadAnalysis}
                disabled={analysisLoading}
                className="bg-blue-700 hover:bg-blue-600 disabled:bg-blue-900 text-white text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
              >
                {analysisLoading && <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                {analysis ? 'Refresh' : 'Run Analysis'}
              </button>
            </div>
            {analysis ? (
              <p className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap">{analysis}</p>
            ) : (
              <p className="text-slate-400 text-sm">{analysisLoading ? 'Analysing your portfolio…' : 'Click "Run Analysis" to get AI-powered insights on your portfolio.'}</p>
            )}
          </div>

        </div>

        {/* Holdings Table */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200">
            <h2 className="font-semibold text-slate-800">My Holdings</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-100 text-slate-500 text-xs uppercase">
                <tr>
                  {['Ticker', 'Type', 'Qty', 'Avg Buy', 'Current Price', 'Value', 'Unreal P&L%'].map(h => (
                    <th key={h} className="px-4 py-2 text-left">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {(holdings || []).filter(h => h.asset_type !== 'cash').map(h => (
                  <tr key={h.ticker} className="hover:bg-slate-100/40">
                    <td className="px-4 py-2 font-bold text-blue-600">{h.ticker}</td>
                    <td className="px-4 py-2 text-slate-500 capitalize text-xs">{h.asset_type}</td>
                    <td className="px-4 py-2 font-mono text-slate-700">{h.quantity}</td>
                    <td className="px-4 py-2 font-mono text-slate-500">${fmt(h.avg_buy_price, 2)}</td>
                    <td className="px-4 py-2">
                      <LivePriceBadge price={h.current_price} change1d={h.change_1d_pct} />
                    </td>
                    <td className="px-4 py-2 font-mono text-slate-800">${fmt(h.current_value)}</td>
                    <td className={`px-4 py-2 font-mono ${(h.unrealized_pl_pct || 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                      {(h.unrealized_pl_pct || 0) >= 0 ? '+' : ''}{fmt(h.unrealized_pl_pct, 2)}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* AI Market Predictions */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
            <div>
              <h2 className="font-semibold text-slate-800">AI Market Predictions</h2>
              <p className="text-xs text-slate-400">Random Forest Model · 14 technical indicators</p>
            </div>
            {!predictions && (
              <button
                onClick={loadPredictions}
                disabled={predLoading}
                className="bg-blue-700 hover:bg-blue-600 disabled:bg-blue-900 text-white text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
              >
                {predLoading && (
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                Load Predictions
              </button>
            )}
            {predictions && (
              <button
                onClick={loadPredictions}
                disabled={predLoading}
                className="bg-slate-200 hover:bg-slate-300 disabled:opacity-50 text-slate-700 text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
              >
                {predLoading && (
                  <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
                )}
                Refresh
              </button>
            )}
          </div>
          {predictions ? (
            <div className="p-4 space-y-3">
              {(predictions.portfolio_predictions || []).map(p => (
                <div key={p.ticker} className="flex items-center gap-3">
                  <span className="w-16 font-bold text-blue-600 text-sm">{p.ticker}</span>
                  <div className="flex-1 bg-slate-100 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${p.confidence}%` }}
                    />
                  </div>
                  <span className="w-10 text-right text-xs text-slate-500 font-mono">{p.confidence}%</span>
                  <SignalBadge signal={p.signal} />
                  {p.flags_fired != null && (
                    <span className="text-xs text-slate-400">{p.flags_fired} flags</span>
                  )}
                </div>
              ))}
              {predictions.narrative && (
                <div className="mt-4 p-3 bg-slate-100 rounded-lg text-sm text-slate-700 leading-relaxed">
                  {predictions.narrative}
                </div>
              )}
              {predictions.universe_scanned > 0 && (
                <p className="text-xs text-slate-400">Universe scanned: {predictions.universe_scanned} tickers</p>
              )}
            </div>
          ) : (
            <div className="p-6 text-center text-slate-400 text-sm">
              {predLoading
                ? 'Loading AI market analysis…'
                : 'Click "Load Predictions" to view AI-powered market insights'}
            </div>
          )}
        </div>

        {/* Agent Debate */}
        <AgentDebate result={debateResult} loading={debateLoading} onRun={runDebate} />

        {/* Loans */}
        {(loans || []).length > 0 && (
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200">
              <h2 className="font-semibold text-slate-800">My Loans</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100 text-slate-500 text-xs uppercase">
                  <tr>
                    {['Type', 'Outstanding', 'Rate%', 'EMI/mo', 'Next Due', 'Status'].map(h => (
                      <th key={h} className="px-4 py-2 text-left">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {loans.map((l, i) => (
                    <tr key={i} className={l.status === 'overdue' ? 'bg-red-50' : ''}>
                      <td className="px-4 py-2 capitalize text-slate-700">{l.loan_type}</td>
                      <td className="px-4 py-2 font-mono text-slate-800">${fmt(l.outstanding_balance)}</td>
                      <td className="px-4 py-2 font-mono text-amber-600">{l.interest_rate_pct}%</td>
                      <td className="px-4 py-2 font-mono text-slate-700">${fmt(l.emi_monthly)}</td>
                      <td className="px-4 py-2 text-slate-500 text-xs">
                        {l.next_due_date?.split('T')[0] || '—'}
                      </td>
                      <td className="px-4 py-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          l.status === 'overdue' ? 'bg-red-100 text-red-700' :
                          l.status === 'active'  ? 'bg-green-100 text-green-700' :
                                                   'bg-slate-100 text-slate-600'
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
          <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-200">
              <h2 className="font-semibold text-slate-800">Recent Transactions</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-100 text-slate-500 text-xs uppercase">
                  <tr>
                    {['Ticker', 'Type', 'Qty', 'Price', 'Total', 'Date', 'Flag'].map(h => (
                      <th key={h} className="px-4 py-2 text-left">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {transactions.slice(0, 10).map((t, i) => (
                    <tr key={i} className={t.flagged ? 'bg-red-50' : ''}>
                      <td className="px-4 py-2 font-bold text-blue-400">{t.ticker}</td>
                      <td className={`px-4 py-2 font-medium ${t.txn_type === 'buy' ? 'text-emerald-600' : 'text-red-600'}`}>
                        {t.txn_type?.toUpperCase()}
                      </td>
                      <td className="px-4 py-2 font-mono text-slate-700">{t.quantity}</td>
                      <td className="px-4 py-2 font-mono text-slate-500">${fmt(t.price_at_txn, 2)}</td>
                      <td className="px-4 py-2 font-mono text-slate-800">${fmt(t.total_value)}</td>
                      <td className="px-4 py-2 text-slate-400 text-xs">
                        {t.txn_timestamp ? new Date(t.txn_timestamp).toLocaleDateString() : '—'}
                      </td>
                      <td className="px-4 py-2">
                        {t.flagged && (
                          <span className="bg-red-100 text-red-700 text-xs px-1.5 py-0.5 rounded">⚑</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Bottom padding so chat button doesn't cover content */}
        <div className="h-20" />

        </> /* end portfolio tab */}
      </div>

      {/* Transaction Modal */}
      {showTxn && (
        <TransactionModal
          customerId={customerId}
          token={token}
          onClose={() => setShowTxn(false)}
          onSuccess={() => {
            setShowTxn(false)
            apiFetch(`/api/portfolio/${customerId}`, {}, token).then(setPortfolio).catch(() => {})
          }}
        />
      )}

      {/* Support Chat Widget */}
      <SupportChat customerId={customerId} token={token} />
    </div>
  )
}
