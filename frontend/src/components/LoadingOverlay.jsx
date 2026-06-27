/**
 * Animated loading overlay shown during AI extraction.
 */
export default function LoadingOverlay({ message, progress }) {
  const steps = [
    { label: 'Uploading bill', threshold: 10 },
    { label: 'Converting PDF (if needed)', threshold: 30 },
    { label: 'AI reading your bill', threshold: 60 },
    { label: 'Extracting fields', threshold: 85 },
    { label: 'Preparing preview', threshold: 100 },
  ]

  const activeStep = steps.findIndex((s) => progress < s.threshold)
  const currentStep = activeStep === -1 ? steps.length - 1 : activeStep

  return (
    <div className="card p-8 md:p-10">
      <div className="flex flex-col items-center gap-6">
        {/* Spinner */}
        <div className="relative w-20 h-20">
          <div className="absolute inset-0 rounded-full border-4 border-primary-100" />
          <div className="absolute inset-0 rounded-full border-4 border-primary-600 border-t-transparent animate-spin" />
          <div className="absolute inset-0 flex items-center justify-center">
            <svg className="w-8 h-8 text-primary-600 animate-pulse-slow" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
            </svg>
          </div>
        </div>

        <div className="text-center">
          <h3 className="text-xl font-bold text-slate-800">{message || 'Processing your bill...'}</h3>
          <p className="text-sm text-slate-500 mt-1">This may take 15–60 seconds</p>
        </div>

        {/* Progress bar */}
        <div className="w-full max-w-md">
          <div className="h-2 bg-slate-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary-500 to-accent-500 rounded-full transition-all duration-500 ease-out"
              style={{ width: `${Math.min(progress, 100)}%` }}
            />
          </div>
          <p className="text-xs text-slate-400 mt-2 text-right">{Math.round(progress)}%</p>
        </div>

        {/* Step indicators */}
        <ul className="w-full max-w-md space-y-2">
          {steps.map((step, i) => (
            <li
              key={step.label}
              className={`flex items-center gap-3 text-sm transition-colors ${
                i < currentStep
                  ? 'text-accent-600'
                  : i === currentStep
                    ? 'text-primary-700 font-medium'
                    : 'text-slate-400'
              }`}
            >
              {i < currentStep ? (
                <svg className="w-5 h-5 text-accent-500 shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path
                    fillRule="evenodd"
                    d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z"
                    clipRule="evenodd"
                  />
                </svg>
              ) : i === currentStep ? (
                <div className="w-5 h-5 shrink-0 rounded-full border-2 border-primary-500 border-t-transparent animate-spin" />
              ) : (
                <div className="w-5 h-5 shrink-0 rounded-full border-2 border-slate-200" />
              )}
              {step.label}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
