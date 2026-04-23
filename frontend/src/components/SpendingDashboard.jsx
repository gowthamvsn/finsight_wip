import { useState, useEffect } from 'react'
import { apiFetch } from '../api/client'
import AgentStatusTicker from './AgentStatusTicker'

// ── helpers ───────────────────────────────────────────────────────────────────

function fmtUSD(n) {
  if (n == null) return '—'
  const abs = Math.abs(n)
  const str = abs.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  return (n < 0 ? '-' : '') + '$' + str
}

function fmtPct(n) {
  return n == null ? '—' : `${n > 0 ? '+' : ''}${n}%`
}

const CAT_COLORS = {
  groceries:      { bar: 'bg-green-500',   badge: 'bg-green-100 text-green-700'   },
  dining:         { bar: 'bg-amber-500',   badge: 'bg-amber-100 text-amber-700'   },
  transport:      { bar: 'bg-blue-500',    badge: 'bg-blue-100 text-blue-700'     },
  utilities:      { bar: 'bg-slate-400',   badge: 'bg-slate-100 text-slate-600'   },
  entertainment:  { bar: 'bg-purple-500',  badge: 'bg-purple-100 text-purple-700' },
  healthcare:     { bar: 'bg-teal-500',    badge: 'bg-teal-100 text-teal-700'     },
  shopping:       { bar: 'bg-orange-500',  badge: 'bg-orange-100 text-orange-700' },
  travel:         { bar: 'bg-cyan-500',    badge: 'bg-cyan-100 text-cyan-700'     },
  rent:           { bar: 'bg-red-500',     badge: 'bg-red-100 text-red-700'       },
  insurance:      { bar: 'bg-rose-500',    badge: 'bg-rose-100 text-rose-700'     },
  subscription:   { bar: 'bg-violet-500',  badge: 'bg-violet-100 text-violet-700' },
  salary:         { bar: 'bg-emerald-500', badge: 'bg-emerald-100 text-emerald-700'},
  interest_earned:{ bar: 'bg-lime-500',    badge: 'bg-lime-100 text-lime-700'     },
  interest_paid:  { bar: 'bg-pink-500',    badge: 'bg-pink-100 text-pink-700'     },
  investment:     { bar: 'bg-indigo-500',  badge: 'bg-indigo-100 text-indigo-700' },
  other:          { bar: 'bg-slate-400',   badge: 'bg-slate-100 text-slate-500'   },
}

function catColor(cat, type) {
  return (CAT_COLORS[cat] || CAT_COLORS.other)[type]
}

// ── sub-components ────────────────────────────────────────────────────────────

function MetricCard({ label, value, sub, color }) {
  return (
    <div className="bg-white rounded-xl p-4 border border-slate-200">
      <p className="text-xs text-slate-400 uppercase tracking-wide mb-1">{label}</p>
      <p className={`text-xl font-bold ${color || 'text-slate-800'}`}>{value}</p>
      {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
    </div>
  )
}

function AccountCard({ acc }) {
  const typeLabel = {
    checking:    'Checking',
    savings:     'Savings',
    credit_card: 'Credit Card',
    investment:  'Investment',
    mortgage:    'Mortgage',
  }
  const isNeg = parseFloat(acc.balance) < 0
  return (
    <div className="bg-white rounded-xl p-4 border border-slate-200 flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
          {acc.bank_name}
        </span>
        <span className="text-xs bg-slate-100 text-slate-500 px-2 py-0.5 rounded">
          {typeLabel[acc.account_type] || acc.account_type}
        </span>
      </div>
      <p className={`text-lg font-bold ${isNeg ? 'text-red-600' : 'text-slate-800'}`}>
        {fmtUSD(parseFloat(acc.balance))}
      </p>
      <p className="text-xs text-slate-400">Account {acc.account_number}</p>
      {acc.interest_rate && (
        <p className="text-xs text-slate-400">
          Rate: <span className="text-slate-700">{acc.interest_rate}% APR</span>
        </p>
      )}
    </div>
  )
}

function SpendingBar({ item, maxSpent }) {
  const pct = maxSpent > 0 ? (item.total_spent / maxSpent) * 100 : 0
  return (
    <div className="flex items-center gap-3 py-1.5">
      <span className="text-xs text-slate-500 w-28 shrink-0 capitalize">
        {item.category.replace('_', ' ')}
      </span>
      <div className="flex-1 bg-slate-100 rounded-full h-2 overflow-hidden">
        <div
          className={`h-2 rounded-full ${catColor(item.category, 'bar')}`}
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
      <span className="text-xs text-slate-700 w-24 text-right shrink-0">
        {fmtUSD(item.total_spent)}{' '}
        <span className="text-slate-400">({item.pct_of_spending}%)</span>
      </span>
      {item.vs_last_month !== 0 && (
        <span className={`text-xs w-14 text-right shrink-0 ${item.vs_last_month > 0 ? 'text-red-600' : 'text-green-600'}`}>
          {fmtPct(item.vs_last_month)}
        </span>
      )}
    </div>
  )
}

const BAR_MAX_PX = 96

function MonthlyTrendBars({ trend }) {
  if (!trend || trend.length === 0) return null
  const maxVal = Math.max(...trend.flatMap(t => [t.income, t.spending]), 1)
  return (
    <div className="flex items-end gap-6">
      {trend.map(t => {
        const incH  = Math.max(4, Math.round((t.income   / maxVal) * BAR_MAX_PX))
        const expH  = Math.max(4, Math.round((t.spending / maxVal) * BAR_MAX_PX))
        return (
          <div key={t.period} className="flex-1 flex flex-col items-center gap-2">
            <div className="flex items-end gap-1 w-full" style={{ height: BAR_MAX_PX }}>
              <div
                className="flex-1 bg-emerald-600 rounded-t cursor-default"
                style={{ height: incH }}
                title={`Income: ${fmtUSD(t.income)}`}
              />
              <div
                className="flex-1 bg-red-600 rounded-t cursor-default"
                style={{ height: expH }}
                title={`Spending: ${fmtUSD(t.spending)}`}
              />
            </div>
            <span className="text-xs text-slate-400">{t.period}</span>
          </div>
        )
      })}
    </div>
  )
}

// ── main component ────────────────────────────────────────────────────────────

export default function SpendingDashboard({ customerId, token }) {
  const [accounts, setAccounts]       = useState([])
  const [summary, setSummary]         = useState(null)
  const [txns, setTxns]               = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState('')
  const [analyzing, setAnalyzing]     = useState(false)
  const [analysisSteps, setAnalysisSteps] = useState([])
  const [analysis, setAnalysis]       = useState('')
  const [analysisError, setAnalysisError] = useState('')

  useEffect(() => {
    if (!customerId || !token) return
    setLoading(true)
    Promise.all([
      apiFetch(`/api/banking/${customerId}/accounts`, {}, token),
      apiFetch(`/api/banking/${customerId}/spending-summary`, {}, token),
      apiFetch(`/api/banking/${customerId}/transactions?limit=20`, {}, token),
    ])
      .then(([accs, sum, ts]) => {
        setAccounts(accs)
        setSummary(sum)
        setTxns(ts)
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [customerId, token])

  async function handleAnalyze() {
    setAnalyzing(true)
    setAnalysis('')
    setAnalysisError('')
    setAnalysisSteps([
      { name: 'Spending Analyst', status: 'running', duration_ms: null },
      { name: 'GPT-4o — analyzing 90 days of data', status: 'pending', duration_ms: null },
    ])
    const t0 = Date.now()
    try {
      setAnalysisSteps([
        { name: 'Spending Analyst', status: 'complete', duration_ms: 10 },
        { name: 'GPT-4o — analyzing 90 days of data', status: 'running', duration_ms: null },
      ])
      const result = await apiFetch(`/api/banking/${customerId}/analyze-spending`, { method: 'POST' }, token)
      setAnalysisSteps([
        { name: 'Spending Analyst', status: 'complete', duration_ms: 10 },
        { name: 'GPT-4o — analyzing 90 days of data', status: 'complete', duration_ms: result.duration_ms || Date.now() - t0 },
      ])
      setAnalysis(result.analysis || '')
      if (result.error) setAnalysisError(result.error)
    } catch (e) {
      setAnalysisSteps(s => s.map(st => ({ ...st, status: st.status === 'running' ? 'error' : st.status })))
      setAnalysisError(e.message)
    } finally {
      setAnalyzing(false)
    }
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 text-slate-400">Loading banking data…</div>
  )
  if (error) return (
    <div className="text-red-600 text-sm p-4">{error}</div>
  )

  const spendingCats = (summary?.by_category || []).filter(c => c.total_spent > 0)
  const maxSpent = spendingCats.length > 0 ? Math.max(...spendingCats.map(c => c.total_spent)) : 1

  const srColor = summary?.savings_rate >= 30
    ? 'text-green-700'
    : summary?.savings_rate >= 15 ? 'text-amber-600' : 'text-red-600'

  return (
    <div className="space-y-6">

      {/* Simulated data disclaimer */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg px-4 py-3 text-xs text-blue-700 flex items-start gap-2">
        <span className="mt-0.5">ℹ</span>
        <span>
          Bank transaction data is <strong>simulated</strong> for demonstration purposes.
          Account balances, spending patterns, and transaction history are generated to reflect
          realistic financial behavior. The LLM trend analysis and visualizations are real.
        </span>
      </div>

      {/* SECTION 1 — Account Cards */}
      <div>
        <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">Linked Accounts</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {accounts.map(acc => <AccountCard key={acc.account_id} acc={acc} />)}
        </div>
      </div>

      {/* SECTION 2 — Monthly cashflow summary */}
      {summary && (
        <div>
          <h3 className="text-sm font-semibold text-slate-500 uppercase tracking-wide mb-3">
            This Month — {summary.period}
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <MetricCard label="Monthly Income"   value={fmtUSD(summary.total_income)}   color="text-emerald-700" />
            <MetricCard label="Monthly Spending" value={fmtUSD(summary.total_spending)} color="text-red-600" />
            <MetricCard label="Net Cashflow"     value={fmtUSD(summary.net_cashflow)}
              color={summary.net_cashflow >= 0 ? 'text-emerald-700' : 'text-red-600'} />
            <MetricCard label="Savings Rate"     value={`${summary.savings_rate}%`}     color={srColor}
              sub={summary.savings_rate >= 30 ? 'Excellent' : summary.savings_rate >= 15 ? 'Moderate' : 'Low — review spending'} />
          </div>
        </div>
      )}

      {/* SECTION 3 — Spending by category */}
      {spendingCats.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Spending by Category</h3>
          <div className="space-y-0.5">
            {spendingCats.map(item => (
              <SpendingBar key={item.category} item={item} maxSpent={maxSpent} />
            ))}
          </div>
        </div>
      )}

      {/* SECTION 4 — 3-month trend */}
      {summary?.monthly_trend?.length > 0 && (
        <div className="bg-white rounded-xl p-5 border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">3-Month Cashflow Trend</h3>
          <div className="flex gap-4 text-xs text-slate-400 mb-3">
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-emerald-600 inline-block"/>Income</span>
            <span className="flex items-center gap-1"><span className="w-3 h-3 rounded bg-red-600 inline-block"/>Spending</span>
          </div>
          <MonthlyTrendBars trend={summary.monthly_trend} />
        </div>
      )}

      {/* SECTION 5 — Interest tracker */}
      {summary && (
        <div className="bg-white rounded-xl p-5 border border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700 mb-4">Interest Tracker (last 3 months)</h3>
          <div className="flex gap-6 flex-wrap">
            <div>
              <p className="text-xs text-slate-400 mb-1">Interest Earned</p>
              <p className="text-xl font-bold text-green-700">{fmtUSD(summary.interest_earned_ytd)}</p>
            </div>
            <div>
              <p className="text-xs text-slate-400 mb-1">Interest Paid</p>
              <p className="text-xl font-bold text-red-600">{fmtUSD(summary.interest_paid_ytd)}</p>
            </div>
            <div className="self-end pb-1">
              {summary.interest_earned_ytd >= summary.interest_paid_ytd
                ? <span className="text-xs text-green-700">✓ You are earning more interest than you are paying</span>
                : <span className="text-xs text-amber-700">⚠ Consider paying down credit card debt to reduce interest paid</span>
              }
            </div>
          </div>
        </div>
      )}

      {/* SECTION 6 — AI Spending Analysis */}
      <div className="bg-white rounded-xl p-5 border border-slate-200">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-slate-700">AI Spending Analysis</h3>
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="text-xs bg-blue-600 hover:bg-blue-700 disabled:bg-blue-900 disabled:cursor-not-allowed text-white px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
          >
            {analyzing && <span className="w-3 h-3 border border-white border-t-transparent rounded-full animate-spin"/>}
            {analyzing ? 'Analyzing…' : 'Analyze My Spending Trends'}
          </button>
        </div>

        {analysisSteps.length > 0 && <AgentStatusTicker steps={analysisSteps} />}

        {analysis && (
          <div className="mt-4 bg-slate-50 rounded-lg p-4 text-sm text-slate-700 leading-relaxed whitespace-pre-wrap border border-slate-200">
            {analysis}
          </div>
        )}

        {analysisError && !analysis && (
          <p className="text-xs text-red-600 mt-2">{analysisError}</p>
        )}

        {!analysis && !analyzing && !analysisSteps.length && (
          <p className="text-sm text-slate-400">
            Click the button above to get a personalized GPT-4o analysis of your spending patterns,
            savings opportunities, and interest optimization.
          </p>
        )}
      </div>

      {/* SECTION 7 — Recent bank transactions */}
      <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
        <div className="px-5 py-3 border-b border-slate-200">
          <h3 className="text-sm font-semibold text-slate-700">Recent Bank Transactions</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-slate-100 text-slate-500 text-xs uppercase">
              <tr>
                {['Date', 'Merchant', 'Category', 'Amount', 'Dir'].map(h => (
                  <th key={h} className="px-4 py-2 text-left">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {txns.map(t => (
                <tr key={t.txn_id} className="hover:bg-slate-100/50 transition-colors">
                  <td className="px-4 py-2 text-slate-400 text-xs whitespace-nowrap">
                    {t.txn_date ? new Date(t.txn_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '—'}
                  </td>
                  <td className="px-4 py-2 text-slate-700 max-w-[150px] truncate">
                    {t.merchant || t.description}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-2 py-0.5 rounded capitalize ${catColor(t.category, 'badge')}`}>
                      {t.category.replace('_', ' ')}
                    </span>
                  </td>
                  <td className={`px-4 py-2 font-mono font-semibold ${t.txn_direction === 'credit' ? 'text-emerald-700' : 'text-red-600'}`}>
                    {t.txn_direction === 'credit' ? '+' : '-'}${parseFloat(t.amount).toLocaleString('en-US', { minimumFractionDigits: 2 })}
                  </td>
                  <td className="px-4 py-2">
                    <span className={`text-xs px-1.5 py-0.5 rounded ${t.txn_direction === 'credit' ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-600'}`}>
                      {t.txn_direction}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  )
}
