function formatLabel(key) {
  return key.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
}

function ConfidenceBadge({ score }) {
  if (score == null || score === 0) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-600 font-medium">
        <span aria-hidden>⚠</span> Not Found
      </span>
    )
  }
  if (score >= 90) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-green-600 font-medium">
        <span aria-hidden>✅</span> {score}%
      </span>
    )
  }
  if (score >= 70) {
    return (
      <span className="inline-flex items-center gap-1 text-xs text-amber-600 font-medium">
        <span aria-hidden>⚠</span> {score}%
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 text-xs text-red-500 font-medium">
      <span aria-hidden>⚠</span> {score}%
    </span>
  )
}

function formatDisplayValue(value) {
  if (value == null || value === '') return ''
  if (Array.isArray(value) || typeof value === 'object') return JSON.stringify(value, null, 2)
  return String(value)
}

function hasExtractedValue(value) {
  if (value == null || value === '') return false
  if (value === 'Not Available') return true
  if (Array.isArray(value)) return value.length > 0
  if (typeof value === 'object') return Object.keys(value).length > 0
  return true
}

export default function DataPreview({
  data,
  fields,
  fieldConfidence = {},
  solarSummary = {},
  onChange,
  onGenerate,
  onReset,
}) {
  const handleChange = (key, value) => {
    onChange({ ...data, [key]: value === '' ? null : value })
  }

  const previewFields = fields.filter((key) => key !== 'monthly_history')
  const filledCount = previewFields.filter((key) => hasExtractedValue(data[key])).length

  const renderField = (key) => {
    const isComplex = Array.isArray(data[key]) || (typeof data[key] === 'object' && data[key] !== null)
    const score = fieldConfidence[key]

    return (
      <div key={key}>
        <div className="flex items-center justify-between gap-2 mb-1">
          <label htmlFor={key} className="text-xs font-medium text-slate-500">
            {formatLabel(key)}
          </label>
          <ConfidenceBadge score={score} />
        </div>
        {isComplex ? (
          <textarea
            id={key}
            rows={3}
            className="input-field font-mono text-xs resize-y"
            value={formatDisplayValue(data[key])}
            readOnly
          />
        ) : (
          <input
            id={key}
            type="text"
            className="input-field-filled"
            value={formatDisplayValue(data[key])}
            onChange={(e) => handleChange(key, e.target.value)}
          />
        )}
      </div>
    )
  }

  return (
    <div className="card overflow-hidden">
      <div className="px-5 py-4 border-b border-blue-100 flex items-center justify-between gap-4">
        <div>
          <h2 className="font-semibold text-blue-800">Review extracted data</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {filledCount} of {previewFields.length} fields · edit any value before generating Excel
          </p>
        </div>
        <button type="button" onClick={onReset} className="btn-ghost shrink-0">
          New bill
        </button>
      </div>

      <div className="p-5 max-h-[520px] overflow-y-auto">
        <SolarSummaryInline summary={solarSummary} />

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {previewFields.map(renderField)}
        </div>

        {hasExtractedValue(data.monthly_history) && (
          <div className="mt-6">
            <h3 className="section-title">Monthly consumption</h3>
            {renderField('monthly_history')}
          </div>
        )}
      </div>

      <div className="px-5 py-4 border-t border-blue-100 bg-blue-50/40 flex justify-end">
        <button type="button" onClick={onGenerate} className="btn-primary">
          Generate Excel
        </button>
      </div>
    </div>
  )
}

function SolarSummaryInline({ summary }) {
  if (!summary || Object.keys(summary).length === 0) return null

  const {
    monthly_consumption_kwh,
    recommended_solar_capacity_kw,
    estimated_annual_savings_inr,
    estimated_payback_years,
  } = summary

  const formatInr = (v) => (v == null ? '—' : `₹${Number(v).toLocaleString('en-IN')}`)

  return (
    <div className="mb-6 rounded-lg border border-green-200 bg-gradient-to-br from-green-50 to-blue-50 p-4">
      <h3 className="text-sm font-bold text-green-800 mb-3">Solar Assessment Summary</h3>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <p>
          <span className="text-slate-500 text-xs block">Monthly Consumption</span>
          <span className="font-semibold">
            {monthly_consumption_kwh != null ? `${monthly_consumption_kwh} kWh` : '—'}
          </span>
        </p>
        <p>
          <span className="text-slate-500 text-xs block">Recommended Solar Capacity</span>
          <span className="font-semibold">
            {recommended_solar_capacity_kw != null ? `${recommended_solar_capacity_kw} kW` : '—'}
          </span>
        </p>
        <p>
          <span className="text-slate-500 text-xs block">Estimated Annual Savings</span>
          <span className="font-semibold text-green-700">{formatInr(estimated_annual_savings_inr)}</span>
        </p>
        <p>
          <span className="text-slate-500 text-xs block">Estimated Payback Period</span>
          <span className="font-semibold">
            {estimated_payback_years != null ? `${estimated_payback_years} Years` : '—'}
          </span>
        </p>
      </div>
    </div>
  )
}
