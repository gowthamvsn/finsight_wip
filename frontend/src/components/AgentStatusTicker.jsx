export default function AgentStatusTicker({ steps }) {
  if (!steps || steps.length === 0) return null
  return (
    <div className="flex flex-wrap items-center gap-2 bg-slate-100 rounded-lg p-3 text-sm">
      {steps.map((step, i) => (
        <div key={i} className="flex items-center gap-1.5">
          {step.status === 'pending' && (
            <span className="w-2 h-2 rounded-full bg-slate-400 inline-block" />
          )}
          {step.status === 'running' && (
            <span className="w-4 h-4 border-2 border-blue-500 border-t-transparent rounded-full inline-block animate-spin" />
          )}
          {step.status === 'complete' && (
            <span className="text-emerald-600">✓</span>
          )}
          {step.status === 'error' && (
            <span className="text-red-600">✗</span>
          )}
          <span className={
            step.status === 'complete' ? 'text-emerald-700' :
            step.status === 'running'  ? 'text-blue-700' :
            step.status === 'error'    ? 'text-red-700' :
            'text-slate-500'
          }>
            {step.name}
            {step.status === 'complete' && step.duration_ms != null && (
              <span className="text-slate-400 ml-1">({step.duration_ms}ms)</span>
            )}
          </span>
          {i < steps.length - 1 && <span className="text-slate-300 mx-1">→</span>}
        </div>
      ))}
    </div>
  )
}
