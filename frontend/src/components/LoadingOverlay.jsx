const DEFAULT_STEPS = ['Processing…']

export default function LoadingOverlay({ message, progress, steps = DEFAULT_STEPS, activeStep = 0 }) {
  return (
    <div className="card p-10 text-center">
      <div className="w-10 h-10 border-2 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-5" />
      <p className="font-medium text-slate-800">{message}</p>

      {steps.length > 1 && (
        <ul className="mt-5 max-w-xs mx-auto text-left space-y-2">
          {steps.map((label, i) => {
            const done = i < activeStep
            const current = i === activeStep && activeStep < steps.length
            return (
              <li
                key={label}
                className={`text-xs flex items-center gap-2 ${
                  current ? 'text-blue-700 font-medium' : done ? 'text-green-600' : 'text-slate-400'
                }`}
              >
                <span className="w-4 text-center">{done ? '✓' : current ? '●' : '○'}</span>
                {label}
              </li>
            )
          })}
        </ul>
      )}

      <div className="mt-5 max-w-xs mx-auto">
        <div className="h-1.5 bg-blue-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all duration-500"
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
        <p className="text-xs text-slate-400 mt-2">{Math.round(Math.min(progress, 100))}%</p>
      </div>
    </div>
  )
}
