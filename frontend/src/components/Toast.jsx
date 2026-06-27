import { useEffect } from 'react'

export default function Toast({ message, type = 'info', onClose }) {
  useEffect(() => {
    if (!message) return
    const timer = setTimeout(onClose, 4000)
    return () => clearTimeout(timer)
  }, [message, onClose])

  if (!message) return null

  const styles = {
    success: 'border-green-300 bg-green-50 text-green-800',
    error: 'border-red-200 bg-red-50 text-red-800',
    info: 'border-blue-200 bg-blue-50 text-blue-800',
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-sm">
      <div className={`rounded-lg border px-4 py-3 text-sm shadow-lg ${styles[type] || styles.info}`}>
        <div className="flex items-start justify-between gap-3">
          <p>{message}</p>
          <button onClick={onClose} className="opacity-60 hover:opacity-100 shrink-0" aria-label="Dismiss">
            ×
          </button>
        </div>
      </div>
    </div>
  )
}
