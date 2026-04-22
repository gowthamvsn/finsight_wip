import { useState, useEffect } from 'react'
import { apiFetch } from '../api/client'

const ALL_TICKERS = ['AAPL','MSFT','NVDA','TSLA','AMZN','GOOGL','META','VTSAX','SPY','QQQ','BTC','ETH','SOL','BNB']

export default function TransactionModal({ customerId, token, onClose, onSuccess }) {
  const [step, setStep] = useState('form')
  const [form, setForm] = useState({ ticker: 'AAPL', txn_type: 'buy', quantity: '', price_per_unit: '', geo_country: 'US' })
  const [holdings, setHoldings] = useState([])
  const [prices, setPrices] = useState({})   // ticker -> live price
  const [otp, setOtp] = useState('')
  const [challengeId, setChallengeId] = useState('')
  const [txnResult, setTxnResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [demoOtp, setDemoOtp] = useState('')
  const [reasons, setReasons] = useState([])

  // Fetch holdings and live prices on open
  useEffect(() => {
    apiFetch(`/api/portfolio/${customerId}`, {}, token)
      .then(data => {
        const held = (data.holdings || [])
          .filter(h => h.asset_type !== 'cash' && parseFloat(h.quantity) > 0)
          .map(h => h.ticker)
        setHoldings(held)
      })
      .catch(() => {})

    apiFetch('/api/portfolio/prices', {}, token)
      .then(data => {
        setPrices(data)
        // Pre-fill price for default ticker (AAPL)
        if (data['AAPL']) {
          setForm(f => ({ ...f, price_per_unit: String(data['AAPL'].toFixed(2)) }))
        }
      })
      .catch(() => {})
  }, [customerId, token])

  // When ticker changes, auto-fill the live price (user can still edit it)
  function handleTickerChange(ticker) {
    const livePrice = prices[ticker]
    setForm(f => ({
      ...f,
      ticker,
      price_per_unit: livePrice ? String(livePrice.toFixed(2)) : f.price_per_unit,
    }))
  }

  // When switching type, reset ticker and fill price
  function handleTypeChange(newType) {
    setForm(f => {
      const availableTickers = newType === 'sell' ? holdings : ALL_TICKERS
      const ticker = availableTickers.includes(f.ticker) ? f.ticker : (availableTickers[0] || '')
      const livePrice = prices[ticker]
      return {
        ...f,
        txn_type: newType,
        ticker,
        price_per_unit: livePrice ? String(livePrice.toFixed(2)) : f.price_per_unit,
      }
    })
  }

  const tickerOptions = form.txn_type === 'sell' ? holdings : ALL_TICKERS

  async function handleSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/transactions', {
        method: 'POST',
        body: JSON.stringify({ ...form, customer_id: customerId, quantity: parseFloat(form.quantity), price_per_unit: parseFloat(form.price_per_unit) }),
      }, token)

      if (data.status === 'requires_otp') {
        setChallengeId(data.challenge_id)
        setReasons(data.reasons || [])
        setTxnResult(data)
        if (data.demo_otp) setDemoOtp(data.demo_otp)
        setStep('otp')
      } else {
        setTxnResult(data)
        setStep('done')
        onSuccess?.()
      }
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleOTPSubmit(e) {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const data = await apiFetch('/api/transactions/confirm', {
        method: 'POST',
        body: JSON.stringify({ challenge_id: challengeId, otp }),
      }, token)
      setTxnResult(data)
      setStep('done')
      onSuccess?.()
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const total = (parseFloat(form.quantity) || 0) * (parseFloat(form.price_per_unit) || 0)

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
      <div className="bg-gray-900 border border-gray-700 rounded-2xl p-6 w-full max-w-md">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-lg font-semibold text-white">
            {step === 'form' && 'New Transaction'}
            {step === 'otp' && 'Verify Transaction'}
            {step === 'done' && 'Transaction Complete'}
          </h2>
          <button onClick={onClose} className="text-gray-500 hover:text-white text-xl">✕</button>
        </div>

        {/* Step 1: Form */}
        {step === 'form' && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Type</label>
                <select
                  value={form.txn_type}
                  onChange={e => handleTypeChange(e.target.value)}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                >
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                </select>
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 block">
                  Ticker {form.txn_type === 'sell' && <span className="text-gray-500">(your holdings)</span>}
                </label>
                {tickerOptions.length === 0 && form.txn_type === 'sell' ? (
                  <div className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-gray-500 text-sm">
                    No holdings
                  </div>
                ) : (
                  <select
                    value={form.ticker}
                    onChange={e => handleTickerChange(e.target.value)}
                    className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                  >
                    {tickerOptions.map(t => <option key={t}>{t}</option>)}
                  </select>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-xs text-gray-400 mb-1 block">Quantity</label>
                <input
                  type="number" step="any" min="0.0001" required
                  value={form.quantity}
                  onChange={e => setForm(f => ({ ...f, quantity: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="0.00"
                />
              </div>
              <div>
                <label className="text-xs text-gray-400 mb-1 flex items-center gap-1.5">
                  Price per unit ($)
                  {prices[form.ticker] && (
                    <span className="text-emerald-400 text-xs font-medium">● live</span>
                  )}
                </label>
                <input
                  type="number" step="any" min="0.01" required
                  value={form.price_per_unit}
                  onChange={e => setForm(f => ({ ...f, price_per_unit: e.target.value }))}
                  className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm"
                  placeholder="0.00"
                />
              </div>
            </div>
            <div>
              <label className="text-xs text-gray-400 mb-1 block">Country (ISO)</label>
              <input
                type="text" maxLength={2}
                value={form.geo_country}
                onChange={e => setForm(f => ({ ...f, geo_country: e.target.value.toUpperCase() }))}
                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm uppercase"
                placeholder="US"
              />
            </div>
            {total > 0 && (
              <div className="bg-gray-800 rounded-lg px-4 py-3 flex justify-between">
                <span className="text-gray-400 text-sm">Total Value</span>
                <span className="text-white font-mono font-bold">${total.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>
              </div>
            )}
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <button
              type="submit" disabled={loading || tickerOptions.length === 0}
              className="w-full bg-blue-600 hover:bg-blue-500 disabled:bg-blue-900 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
            >
              {loading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
              Submit Transaction
            </button>
          </form>
        )}

        {/* Step 2: OTP */}
        {step === 'otp' && (
          <form onSubmit={handleOTPSubmit} className="space-y-4">
            <div className="bg-amber-900/30 border border-amber-700 rounded-lg p-3">
              <p className="text-amber-300 text-sm font-medium mb-2">⚠ Suspicious activity detected</p>
              {reasons.map((r, i) => (
                <p key={i} className="text-amber-200 text-xs">• {r}</p>
              ))}
            </div>
            <div className="bg-gray-800 rounded-lg p-3 text-sm text-gray-300">
              <p className="font-medium text-white mb-1">Transaction summary</p>
              <p>{txnResult?.txn_type?.toUpperCase()} {txnResult?.quantity} {txnResult?.ticker} = <span className="font-mono text-white">${txnResult?.total_value?.toLocaleString()}</span></p>
            </div>
            <p className="text-gray-400 text-sm">An OTP has been sent to the registered email. Enter it below to confirm.</p>
            {demoOtp && (
              <div className="bg-blue-900/40 border border-blue-700 rounded-lg p-2 text-center">
                <p className="text-xs text-blue-400 mb-1">Demo mode — OTP (email not configured):</p>
                <p className="text-2xl font-mono font-bold text-blue-300 tracking-widest">{demoOtp}</p>
              </div>
            )}
            <input
              type="text" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} required
              value={otp}
              onChange={e => setOtp(e.target.value.replace(/\D/g, ''))}
              className="w-full bg-gray-800 border border-gray-700 rounded-lg px-4 py-3 text-white text-2xl font-mono text-center tracking-[0.5em]"
              placeholder="000000"
            />
            {error && <p className="text-red-400 text-sm">{error}</p>}
            <div className="flex gap-2">
              <button
                type="button" onClick={() => { setStep('form'); setOtp(''); setError('') }}
                className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-2.5 rounded-lg text-sm"
              >
                Cancel
              </button>
              <button
                type="submit" disabled={loading || otp.length !== 6}
                className="flex-1 bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-700 text-white py-2.5 rounded-lg font-medium transition-colors flex items-center justify-center gap-2"
              >
                {loading && <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />}
                Verify & Confirm
              </button>
            </div>
          </form>
        )}

        {/* Step 3: Done */}
        {step === 'done' && (
          <div className="text-center space-y-4">
            <div className="w-14 h-14 rounded-full bg-emerald-700 flex items-center justify-center mx-auto text-2xl">✓</div>
            <p className="text-white font-semibold">Transaction Approved</p>
            <p className="text-gray-400 text-sm">{txnResult?.message}</p>
            <div className="bg-gray-800 rounded-lg p-3 text-sm text-left">
              <p className="text-gray-400">Transaction ID: <span className="text-white font-mono">{txnResult?.txn_id}</span></p>
            </div>
            <button onClick={onClose} className="w-full bg-blue-600 hover:bg-blue-500 text-white py-2.5 rounded-lg font-medium">
              Close
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
