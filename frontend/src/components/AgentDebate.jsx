/**
 * AgentDebate — renders critic agent output.
 * Props:
 *   result   : critic response object (or null)
 *   loading  : bool
 *   onRun    : () => void
 */
export default function AgentDebate({ result, loading, onRun }) {
  const agreementColor = {
    full:    'text-emerald-400',
    partial: 'text-amber-400',
    none:    'text-red-400',
    unknown: 'text-gray-400',
  }

  const confidenceColor = {
    high:   'text-emerald-400',
    medium: 'text-amber-400',
    low:    'text-red-400',
  }

  return (
    <div className="bg-gray-900 rounded-xl border border-gray-800 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-800 flex items-center justify-between">
        <div>
          <h2 className="font-semibold text-gray-200">Agent Debate</h2>
          <p className="text-xs text-gray-500 mt-0.5">
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
        <div className="p-6 flex items-center gap-3 text-gray-400 text-sm">
          <span className="w-5 h-5 border-2 border-violet-500 border-t-transparent rounded-full animate-spin flex-shrink-0" />
          Running Portfolio Agent + Market Agent in parallel, then Critic Agent…
        </div>
      )}

      {!loading && !result && (
        <div className="p-6 text-center text-gray-500 text-sm">
          Click "Run Agent Debate" to detect and resolve conflicts between agents.
        </div>
      )}

      {!loading && result && (
        <div className="p-4 space-y-4">
          {/* Meta row */}
          <div className="flex items-center gap-4 text-xs">
            <span className="text-gray-500">
              Agreement:
              <span className={`ml-1 font-semibold ${agreementColor[result.agent_agreement] || 'text-gray-400'}`}>
                {result.agent_agreement}
              </span>
            </span>
            <span className="text-gray-500">
              Critic confidence:
              <span className={`ml-1 font-semibold ${confidenceColor[result.critic_confidence] || 'text-gray-400'}`}>
                {result.critic_confidence}
              </span>
            </span>
            <span className="text-gray-500">
              Conflicts found:
              <span className={`ml-1 font-bold ${result.conflicts_found > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
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
                  className="border border-amber-700/50 bg-amber-900/10 rounded-lg p-3 space-y-1.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-amber-300 text-sm">{c.ticker}</span>
                    <span className="text-xs bg-amber-800/60 text-amber-300 px-2 py-0.5 rounded">
                      Agents disagree
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-2 text-xs">
                    <div className="bg-red-900/30 rounded p-2">
                      <p className="text-red-400 font-medium mb-0.5">Portfolio Agent</p>
                      <p className="text-gray-300">{c.portfolio_says}</p>
                    </div>
                    <div className="bg-emerald-900/30 rounded p-2">
                      <p className="text-emerald-400 font-medium mb-0.5">Market Agent</p>
                      <p className="text-gray-300">{c.market_says}</p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {result.conflicts_found === 0 && (
            <div className="flex items-center gap-2 text-sm text-emerald-400 bg-emerald-900/20 rounded-lg p-3">
              <span className="text-emerald-400">✓</span>
              Both agents are aligned — no conflicting signals detected.
            </div>
          )}

          {/* Critic final recommendation */}
          {result.final_recommendation && (
            <div className="border-t border-gray-700 pt-3">
              <p className="text-xs text-violet-400 font-medium uppercase tracking-wide mb-2">
                Critic Verdict
              </p>
              <div className="text-sm text-gray-300 leading-relaxed whitespace-pre-wrap bg-gray-800 rounded-lg p-3">
                {result.final_recommendation}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
