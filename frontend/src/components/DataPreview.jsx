/**
 * Editable preview of AI-extracted bill fields before Excel generation.
 */
export default function DataPreview({ data, fields, onChange, onGenerate, onReset, isGenerating }) {
  const formatLabel = (key) =>
    key
      .replace(/_/g, ' ')
      .replace(/\b\w/g, (c) => c.toUpperCase())

  const handleChange = (key, value) => {
    onChange({ ...data, [key]: value === '' ? null : value })
  }

  // Show known fields first, then any extra fields from AI
  const knownSet = new Set(fields)
  const extraKeys = Object.keys(data).filter((k) => !knownSet.has(k))
  const displayFields = [...fields, ...extraKeys]

  const filledCount = Object.values(data).filter((v) => v != null && v !== '').length

  return (
    <div className="card overflow-hidden">
      <div className="px-6 py-5 border-b border-slate-100 bg-gradient-to-r from-primary-50 to-emerald-50">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
          <div>
            <h2 className="text-xl font-bold text-slate-800">Extracted Bill Data</h2>
            <p className="text-sm text-slate-500 mt-0.5">
              Review and edit values before generating your Excel file
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded-full bg-accent-100 text-accent-700 text-xs font-medium">
                {filledCount} fields extracted
              </span>
            </p>
          </div>
          <button type="button" onClick={onReset} className="btn-secondary text-sm py-2 px-4">
            Upload New Bill
          </button>
        </div>
      </div>

      <div className="p-6 max-h-[420px] overflow-y-auto">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {displayFields.map((key) => (
            <div key={key}>
              <label htmlFor={key} className="block text-xs font-semibold text-slate-500 uppercase tracking-wide mb-1">
                {formatLabel(key)}
              </label>
              <input
                id={key}
                type="text"
                className="input-field"
                value={data[key] ?? ''}
                placeholder="Not found on bill"
                onChange={(e) => handleChange(key, e.target.value)}
              />
            </div>
          ))}
        </div>
      </div>

      <div className="px-6 py-5 border-t border-slate-100 bg-slate-50/50 flex flex-col sm:flex-row gap-3 sm:justify-end">
        <button
          type="button"
          onClick={onGenerate}
          disabled={isGenerating}
          className="btn-primary"
        >
          {isGenerating ? (
            <>
              <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Generating Excel...
            </>
          ) : (
            <>
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              Generate Excel
            </>
          )}
        </button>
      </div>
    </div>
  )
}
