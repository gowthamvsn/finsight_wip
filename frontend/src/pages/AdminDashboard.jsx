import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { apiFetch } from '../api/client'
import { useLivePrices } from '../hooks/useLivePrices'
import { useAlertFeed } from '../hooks/useWebSocket'

const CRYPTO_LIMITS = { conservative: 10, moderate: 25, aggressive: 50 }

function cryptoColor(pct, profile) {
  const limit = CRYPTO_LIMITS[profile] ?? 50
  if (pct > limit)     return 'text-red-600 font-semibold'
  if (pct > limit - 5) return 'text-amber-600'
  return 'text-slate-600'
}

function RiskBadge({ profile }) {
  const colors = {
    conservative: 'bg-blue-100 text-blue-700',
    moderate:     'bg-violet-100 text-violet-700',
    aggressive:   'bg-red-100 text-red-700',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium ${colors[profile] || 'bg-slate-100 text-slate-600'}`}>
      {profile}
    </span>
  )
}

function TierBadge({ tier }) {
  const colors = {
    elite:    'bg-amber-100 text-amber-700',
    premium:  'bg-emerald-100 text-emerald-700',
    standard: 'bg-slate-100 text-slate-600',
  }
  return (
    <span className={`px-2 py-0.5 rounded text-xs font-medium capitalize ${colors[tier] || 'bg-slate-100 text-slate-600'}`}>
      {tier}
    </span>
  )
}

function SeverityDot({ severity }) {
  const colors = {
    critical: 'bg-red-500',
    high:     'bg-orange-500',
    medium:   'bg-yellow-500',
    low:      'bg-blue-400',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[severity] || 'bg-slate-400'}`} />
}

function fmtK(n) {
  if (!n) return '—'
  return n >= 1000 ? `$${(n / 1000).toFixed(0)}k` : `$${n}`
}

// ── Leaderboard card ─────────────────────────────────────────────────────────

function LeaderboardCard({ title, icon, rows, renderRow }) {
  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-2">
        <span className="text-lg">{icon}</span>
        <h3 className="text-sm font-semibold text-slate-700">{title}</h3>
      </div>
      <div className="divide-y divide-slate-50">
        {rows.map((row, i) => (
          <div key={row.customer_id} className="px-4 py-2.5 flex items-center gap-3">
            <span className={`text-xs font-bold w-5 text-center ${i === 0 ? 'text-amber-500' : 'text-slate-400'}`}>
              {i + 1}
            </span>
            <div className="flex-1 min-w-0">
              {renderRow(row)}
            </div>
          </div>
        ))}
        {rows.length === 0 && (
          <div className="px-4 py-4 text-xs text-slate-400 text-center">No data</div>
        )}
      </div>
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────

export default function AdminDashboard() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()
  const [customers, setCustomers]     = useState([])
  const [leaderboard, setLeaderboard] = useState(null)
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState('')
  const { isConnected, refreshTick }  = useLivePrices()
  const { alerts: liveAlerts }        = useAlertFeed()

  function fetchAll() {
    Promise.all([
      apiFetch('/api/customers', {}, token),
      apiFetch('/api/banking/leaderboard', {}, token),
    ])
      .then(([custs, lb]) => { setCustomers(custs); setLeaderboard(lb) })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  useEffect(() => { fetchAll() }, [token])
  useEffect(() => { if (refreshTick > 0) apiFetch('/api/customers', {}, token).then(setCustomers).catch(() => {}) }, [refreshTick])
  useEffect(() => { const id = setInterval(() => apiFetch('/api/customers', {}, token).then(setCustomers).catch(() => {}), 30000); return () => clearInterval(id) }, [token])

  async function handleLogout() {
    try { await apiFetch('/api/auth/logout', { method: 'POST' }, token) } catch {}
    logout(); navigate('/')
  }

  const totalAUM      = customers.reduce((s, c) => s + (c.portfolio_value || 0), 0)
  const totalAlerts   = customers.reduce((s, c) => s + (c.open_alert_count || 0), 0)
  const highSevCount  = liveAlerts.filter(a => a.severity === 'critical' || a.severity === 'high').length
  const totalBuy30d   = customers.reduce((s, c) => s + (c.buy_volume_30d  || 0), 0)
  const totalSell30d  = customers.reduce((s, c) => s + (c.sell_volume_30d || 0), 0)

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">

      {/* Nav */}
      <nav className="bg-white border-b border-slate-200 px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-sm font-bold text-white">F</span>
          </div>
          <span className="text-lg font-semibold text-slate-800">FinSight</span>
          <span className="text-slate-400 text-sm ml-2">Admin Portal</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500' : 'bg-red-400'}`} />
            {isConnected ? 'Live' : 'Offline'}
          </div>
          <span className="text-sm text-slate-600">{user?.full_name}</span>
          <button onClick={handleLogout} className="text-sm text-slate-400 hover:text-slate-700 transition-colors">
            Logout
          </button>
        </div>
      </nav>

      {/* Metric Cards */}
      <div className="px-6 py-4 grid grid-cols-3 gap-4 sm:grid-cols-6">
        {[
          { label: 'Total Customers', value: customers.length,                          color: 'text-blue-600'    },
          { label: 'Total AUM',       value: `$${(totalAUM / 1e6).toFixed(2)}M`,        color: 'text-emerald-600' },
          { label: 'Open Alerts',     value: totalAlerts,                               color: 'text-amber-600'   },
          { label: 'High Severity',   value: highSevCount,                              color: 'text-red-600'     },
          { label: 'Buy Volume 30d',  value: `$${(totalBuy30d  / 1e6).toFixed(2)}M`,   color: 'text-emerald-600' },
          { label: 'Sell Volume 30d', value: `$${(totalSell30d / 1e6).toFixed(2)}M`,   color: 'text-rose-600'    },
        ].map(card => (
          <div key={card.label} className="bg-white rounded-xl p-4 border border-slate-200 shadow-sm">
            <p className="text-xs text-slate-400 uppercase tracking-wide">{card.label}</p>
            <p className={`text-xl font-bold mt-1 ${card.color}`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Leaderboard */}
      {leaderboard && (
        <div className="px-6 pb-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
          <LeaderboardCard
            title="Top 5 Spenders This Month"
            icon="💸"
            rows={leaderboard.top_spenders}
            renderRow={r => (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-800 leading-tight">{r.name}</p>
                  <TierBadge tier={r.advisor_tier} />
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-red-600">{fmtK(r.monthly_spending)}</p>
                  <p className="text-xs text-slate-400">spending</p>
                </div>
              </div>
            )}
          />
          <LeaderboardCard
            title="Top 5 Savers This Month"
            icon="🏦"
            rows={leaderboard.top_savers}
            renderRow={r => (
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-slate-800 leading-tight">{r.name}</p>
                  <TierBadge tier={r.advisor_tier} />
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-emerald-600">{r.savings_rate}%</p>
                  <p className="text-xs text-slate-400">savings rate</p>
                </div>
              </div>
            )}
          />
          <LeaderboardCard
            title="Top 5 Portfolios"
            icon="📈"
            rows={leaderboard.top_portfolios}
            renderRow={r => (
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-medium text-slate-800 leading-tight">{r.name}</p>
                  <RiskBadge profile={r.risk_profile} />
                </div>
                <div className="text-right">
                  <p className="text-sm font-bold text-blue-600">
                    ${(r.portfolio_value / 1000).toFixed(0)}k
                  </p>
                  <p className={`text-xs font-medium ${r.net_pl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                    {r.net_pl >= 0 ? '+' : ''}{fmtK(Math.abs(r.net_pl))} P&L
                  </p>
                </div>
              </div>
            )}
          />
        </div>
      )}

      {/* Main Layout */}
      <div className="px-6 pb-6 flex gap-4">

        {/* Customer Table */}
        <div className="flex-1 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-100">
            <h2 className="font-semibold text-slate-700">All Customers ({customers.length})</h2>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <span className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : error ? (
            <div className="p-4 text-red-600 text-sm">{error}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-500 text-xs uppercase border-b border-slate-100">
                  <tr>
                    {['#','Name','Risk','Tier','Portfolio','Net P&L','Crypto%','Buy 30d','Sell 30d','Txns','Alerts',''].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {customers.map((c, i) => (
                    <tr key={c.customer_id} className="hover:bg-slate-50 transition-colors">
                      <td className="px-3 py-2 text-slate-400 text-xs">{i + 1}</td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-slate-800">{c.first_name} {c.last_name}</div>
                        <div className="text-xs text-slate-400">{c.customer_id}</div>
                      </td>
                      <td className="px-3 py-2"><RiskBadge profile={c.risk_profile} /></td>
                      <td className="px-3 py-2"><TierBadge tier={c.advisor_tier} /></td>
                      <td className="px-3 py-2 font-mono font-semibold text-slate-800">
                        ${(c.portfolio_value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                      </td>
                      <td className={`px-3 py-2 font-mono font-medium ${(c.net_pl || 0) >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                        {(c.net_pl || 0) >= 0 ? '+' : ''}{(c.net_pl || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                      </td>
                      <td className={`px-3 py-2 font-mono text-sm ${cryptoColor(c.crypto_pct || 0, c.risk_profile)}`}>
                        {(c.crypto_pct || 0).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 font-mono text-emerald-600 text-xs">
                        {(c.buy_volume_30d || 0) > 0 ? fmtK(c.buy_volume_30d) : '—'}
                      </td>
                      <td className="px-3 py-2 font-mono text-rose-600 text-xs">
                        {(c.sell_volume_30d || 0) > 0 ? fmtK(c.sell_volume_30d) : '—'}
                      </td>
                      <td className="px-3 py-2 text-slate-500 text-xs text-center">
                        {c.txn_count_30d || 0}
                      </td>
                      <td className="px-3 py-2">
                        {(c.open_alert_count || 0) > 0 && (
                          <span className="bg-red-100 text-red-700 text-xs font-bold rounded-full px-2 py-0.5">
                            {c.open_alert_count}
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        <button
                          onClick={() => navigate(`/admin/customer/${c.customer_id}`)}
                          className="bg-blue-600 hover:bg-blue-700 text-white text-xs px-3 py-1 rounded-lg transition-colors"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Alert Sidebar */}
        <div className="w-72 bg-white rounded-xl border border-slate-200 shadow-sm flex flex-col">
          <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
            <h2 className="font-semibold text-slate-700 text-sm">Live Alerts</h2>
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`} />
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-slate-50">
            {liveAlerts.slice(0, 10).map((alert, i) => {
              const bg =
                alert.severity === 'critical' ? 'bg-red-50 border-l-2 border-red-400' :
                alert.severity === 'high'     ? 'bg-orange-50 border-l-2 border-orange-400' :
                alert.severity === 'medium'   ? 'bg-yellow-50 border-l-2 border-yellow-400' :
                                                'bg-sky-50 border-l-2 border-sky-400'
              return (
                <div key={alert.alert_id || i} className={`px-3 py-2.5 slide-in ${bg}`}>
                  <div className="flex items-center gap-1.5 mb-0.5">
                    <SeverityDot severity={alert.severity} />
                    <span className="text-xs font-semibold text-slate-700 uppercase tracking-wide">{alert.alert_type?.replace('_', ' ')}</span>
                    <span className="ml-auto text-xs text-slate-400">{alert.customer_id}</span>
                  </div>
                  <p className="text-xs text-slate-500 line-clamp-2">{alert.description}</p>
                </div>
              )
            })}
            {liveAlerts.length === 0 && (
              <div className="flex items-center justify-center py-8 text-slate-400 text-sm">
                No alerts yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
