import { useEffect, useRef, useState } from 'react'

export default function LivePriceBadge({ price, change1d }) {
  const prevRef = useRef(price)
  const [flashClass, setFlashClass] = useState('')

  useEffect(() => {
    if (price !== prevRef.current) {
      const cls = price > prevRef.current ? 'flash-green' : 'flash-red'
      setFlashClass(cls)
      prevRef.current = price
      const t = setTimeout(() => setFlashClass(''), 600)
      return () => clearTimeout(t)
    }
  }, [price])

  const up = (change1d ?? 0) >= 0
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-sm font-mono ${flashClass}`}>
      <span className="text-slate-800">
        ${price != null ? Number(price).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '—'}
      </span>
      {change1d != null && (
        <span className={up ? 'text-emerald-600' : 'text-red-600'}>
          {up ? '▲' : '▼'}{Math.abs(change1d).toFixed(2)}%
        </span>
      )}
    </span>
  )
}
