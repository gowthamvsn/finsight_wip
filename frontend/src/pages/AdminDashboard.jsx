import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../App'
import { apiFetch } from '../api/client'
import { useLivePrices } from '../hooks/useLivePrices'
import { useAlertFeed } from '../hooks/useWebSocket'

const CRYPTO_LIMITS = { conservative: 10, moderate: 25, aggressive: 50 }

function cryptoColor(pct, profile) {
  const limit = CRYPTO_LIMITS[profile] ?? 50
  if (pct > limit) return 'text-red-400'
  if (pct > limit - 5) return 'text-amber-400'
  return 'text-gray-300'
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

function SeverityDot({ severity }) {
  const colors = {
    critical: 'bg-red-500',
    high: 'bg-orange-500',
    medium: 'bg-yellow-500',
    low: 'bg-blue-500',
  }
  return <span className={`inline-block w-2 h-2 rounded-full ${colors[severity] || 'bg-gray-500'}`} />
}

export default function AdminDashboard() {
  const { user, token, logout } = useAuth()
  const navigate = useNavigate()
  const [customers, setCustomers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const { isConnected, refreshTick } = useLivePrices()
  const { alerts: liveAlerts } = useAlertFeed()

  function fetchCustomers() {
    apiFetch('/api/customers', {}, token)
      .then(setCustomers)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }

  // Initial load
  useEffect(() => { fetchCustomers() }, [token])

  // Re-fetch when WebSocket signals a price update
  useEffect(() => {
    if (refreshTick > 0) fetchCustomers()
  }, [refreshTick])

  // Fallback: poll every 30s in case WebSocket misses a tick
  useEffect(() => {
    const id = setInterval(fetchCustomers, 30000)
    return () => clearInterval(id)
  }, [token])

  async function handleLogout() {
    try { await apiFetch('/api/auth/logout', { method: 'POST' }, token) } catch {}
    logout()
    navigate('/')
  }

  const totalAUM = customers.reduce((s, c) => s + (c.portfolio_value || 0), 0)
  const totalAlerts = customers.reduce((s, c) => s + (c.open_alert_count || 0), 0)
  const highSevCount = liveAlerts.filter(a => a.severity === 'critical' || a.severity === 'high').length

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Nav */}
      <nav className="bg-gray-900 border-b border-gray-800 px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center">
            <span className="text-sm font-bold">F</span>
          </div>
          <span className="text-lg font-semibold">FinSight</span>
          <span className="text-gray-500 text-sm ml-2">Admin Portal</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-1.5 text-xs text-gray-400">
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400' : 'bg-red-400'}`} />
            {isConnected ? 'Live' : 'Offline'}
          </div>
          <span className="text-sm text-gray-300">{user?.full_name}</span>
          <button
            onClick={handleLogout}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            Logout
          </button>
        </div>
      </nav>

      {/* Metric Cards */}
      <div className="px-6 py-4 grid grid-cols-4 gap-4">
        {[
          { label: 'Total Customers', value: customers.length, color: 'blue' },
          { label: 'Total AUM', value: `$${(totalAUM / 1e6).toFixed(2)}M`, color: 'emerald' },
          { label: 'Open Alerts', value: totalAlerts, color: 'amber' },
          { label: 'High Severity', value: highSevCount, color: 'red' },
        ].map(card => (
          <div key={card.label} className="bg-gray-900 rounded-xl p-4 border border-gray-800">
            <p className="text-xs text-gray-400 uppercase tracking-wide">{card.label}</p>
            <p className={`text-2xl font-bold mt-1 text-${card.color}-400`}>{card.value}</p>
          </div>
        ))}
      </div>

      {/* Main Layout */}
      <div className="px-6 pb-6 flex gap-4">
        {/* Customer Table */}
        <div className="flex-1 bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-800">
            <h2 className="font-semibold text-gray-200">Customers ({customers.length})</h2>
          </div>
          {loading ? (
            <div className="flex items-center justify-center py-16">
              <span className="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin" />
            </div>
          ) : error ? (
            <div className="p-4 text-red-400">{error}</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-800 text-gray-400 text-xs uppercase">
                  <tr>
                    {['#', 'Name', 'Risk', 'Tier', 'Portfolio', 'Net P&L', 'Crypto%', 'Alerts', ''].map(h => (
                      <th key={h} className="px-3 py-2 text-left font-medium">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {customers.map((c, i) => (
                    <tr key={c.customer_id} className="hover:bg-gray-800/50 transition-colors">
                      <td className="px-3 py-2 text-gray-500">{i + 1}</td>
                      <td className="px-3 py-2">
                        <div className="font-medium text-white">{c.first_name} {c.last_name}</div>
                        <div className="text-xs text-gray-500">{c.customer_id}</div>
                      </td>
                      <td className="px-3 py-2"><RiskBadge profile={c.risk_profile} /></td>
                      <td className="px-3 py-2 text-gray-400 capitalize">{c.advisor_tier}</td>
                      <td className="px-3 py-2 font-mono font-medium text-white">
                        ${(c.portfolio_value || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                      </td>
                      <td className={`px-3 py-2 font-mono ${(c.net_pl || 0) >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>
                        {(c.net_pl || 0) >= 0 ? '+' : ''}{(c.net_pl || 0).toLocaleString('en-US', { maximumFractionDigits: 0 })}
                      </td>
                      <td className={`px-3 py-2 font-mono ${cryptoColor(c.crypto_pct || 0, c.risk_profile)}`}>
                        {(c.crypto_pct || 0).toFixed(1)}%
                      </td>
                      <td className="px-3 py-2">
                        {(c.open_alert_count || 0) > 0 && (
                          <span className="bg-red-600 text-white text-xs font-bold rounded-full px-2 py-0.5">
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
        <div className="w-80 bg-gray-900 rounded-xl border border-gray-800 flex flex-col">
          <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
            <h2 className="font-semibold text-gray-200">Live Alerts</h2>
            <span className={`w-2 h-2 rounded-full ${isConnected ? 'bg-emerald-400 animate-pulse' : 'bg-gray-600'}`} />
          </div>
          <div className="flex-1 overflow-y-auto divide-y divide-gray-800">
            {liveAlerts.slice(0, 10).map((alert, i) => {
              const bg =
                alert.severity === 'critical' ? 'bg-red-900/30' :
                alert.severity === 'high'     ? 'bg-orange-900/30' :
                alert.severity === 'medium'   ? 'bg-yellow-900/20' :
                                                'bg-blue-900/20'
              return (
                <div key={alert.alert_id || i} className={`px-3 py-2.5 slide-in ${bg}`}>
                  <div className="flex items-center gap-1.5 mb-1">
                    <SeverityDot severity={alert.severity} />
                    <span className="text-xs font-medium text-gray-200 uppercase">{alert.alert_type}</span>
                    <span className="ml-auto text-xs text-gray-500">{alert.customer_id}</span>
                  </div>
                  <p className="text-xs text-gray-400 line-clamp-2">{alert.description}</p>
                </div>
              )
            })}
            {liveAlerts.length === 0 && (
              <div className="flex items-center justify-center py-8 text-gray-600 text-sm">
                No alerts received yet
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
