/**
 * AgentDebate — renders critic agent output.
 * Props:
 *   result   : critic response object (or null)
 *   loading  : bool
 *   onRun    : () => void
 */
export default function AgentDebate({ result, loading, onRun }) {
  const agreementColor = {
    full:    'text-emerald-600',
    partial: 'text-amber-600',
    none:    'text-red-600',
    unknown: 'text-slate-500',
  }

  const confidenceColor = {
    high:   'text-emerald-600',
    medium: 'text-amber-600',
    low:    'text-red-600',
  }

  return (
    <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-slate-800">Agent Debate</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            Portfolio Agent vs Market Agent — reconciled by Critic
          </p>
        </div>
        <button
          onClick={onRun}
          disabled={loading}
          className="bg-violet-700 hover:bg-violet-600 disabled:bg-violet-900 disabled:opacity-60
                     text-white text-xs px-3 py-1.5 rounded-lg transition-colors
                     flex items-center gap-1.5"
        >
          {loading && (
            <span className="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin" />
          )}
          {result ? 'Re-run Debate' : 'Run Agent Debate'}
        </button>
      </div>

      {/* Content */}
      {loading && (
        <div className="p-6 flex items-center gap-3 text-slate-500 text-sm">
          <span className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          Running Portfolio Agent + Market Agent in parallel, then Critic Agent…
        </div>
      )}

      {!loading && !result && (
        <div className="p-6 text-center text-slate-400 text-sm">
          Click "Run Agent Debate" to detect and resolve conflicts between agents.
        </div>
      )}

      {!loading && result && (
        <div className="p-4 space-y-4">
          {/* Meta row */}
          <div className="flex items-center gap-4 text-xs">
            <span className="text-slate-500">
              Agreement:
              <span className={`ml-1 font-semibold ${agreementColor[result.agent_agreement] || 'text-slate-500'}`}>
                {result.agent_agreement}
              </span>
            </span>
            <span className="text-slate-500">
              Critic confidence:
              <span className={`ml-1 font-semibold ${confidenceColor[result.critic_confidence] || 'text-slate-500'}`}>
                {result.critic_confidence}
              </span>
            </span>
            <span className="text-slate-500">
              Conflicts found:
              <span className={`ml-1 font-bold ${result.conflicts_found > 0 ? 'text-amber-600' : 'text-emerald-600'}`}>
                {result.conflicts_found}
              </span>
            </span>
          </div>

          {/* Conflict cards */}
          {result.conflict_details && result.conflict_details.length > 0 && (
            <div className="space-y-2">
              {result.conflict_details.map((c) => (
                <div
                  key={c.ticker}
                  className="border border-amber-200 bg-amber-50 rounded-lg p-3 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-amber-700 text-sm">{c.ticker}</span>
                    <span className="text-xs bg-amber-100 text-amber-700 px-2 py-0.5 rounded">
                      Agents disagree
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-red-50 border border-red-100 rounded p-2">
                      <p className="text-red-600 font-medium mb-0.5">Portfolio Agent</p>
                      <p className="text-slate-700">{c.portfolio_says}</p>
                    </div>
                    <div className="bg-emerald-50 border border-emerald-100 rounded p-2">
                      <p className="text-emerald-600 font-medium mb-0.5">Market Agent</p>
                      <p className="text-slate-700">{c.market_says}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {result.conflicts_found === 0 && (
            <div className="flex items-center gap-2 text-sm text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-lg p-3">
              <span>✓</span>
              Both agents are aligned — no conflicting signals detected.
            </div>
          )}

          {/* Critic final recommendation */}
          {result.final_recommendation && (
            <div className="border-t border-slate-200 pt-3">
              <p className="text-xs text-violet-600 font-medium uppercase tracking-wide mb-2">
                Critic Verdict
              </p>
              <div className="text-sm text-slate-700 leading-relaxed whitespace-pre-wrap bg-slate-50 rounded-lg p-3 border border-slate-200">
                {result.final_recommendation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
