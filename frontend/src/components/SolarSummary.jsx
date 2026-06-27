function formatInr(value) {
  if (value == null) return '—'
  return `₹${Number(value).toLocaleString('en-IN')}`
}

export default function SolarSummary({ summary }) {
  if (!summary || Object.keys(summary).length === 0) return null

  const {
    monthly_consumption_kwh,
    recommended_solar_capacity_kw,
    estimated_annual_savings_inr,
    estimated_payback_years,
  } = summary

  return (
    <div className="mb-6 rounded-lg border border-green-200 bg-gradient-to-br from-green-50 to-blue-50 p-5">
      <h3 className="text-sm font-bold text-green-800 mb-3">Solar Assessment Summary</h3>
      <dl className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-sm">
        <div>
          <dt className="text-slate-500 text-xs">Monthly Consumption</dt>
          <dd className="font-semibold text-slate-800">
            {monthly_consumption_kwh != null ? `${monthly_consumption_kwh} kWh` : '—'}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500 text-xs">Recommended Solar Capacity</dt>
          <dd className="font-semibold text-slate-800">
            {recommended_solar_capacity_kw != null ? `${recommended_solar_capacity_kw} kW` : '—'}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500 text-xs">Estimated Annual Savings</dt>
          <dd className="font-semibold text-green-700">
            {formatInr(estimated_annual_savings_inr)}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500 text-xs">Estimated Payback Period</dt>
          <dd className="font-semibold text-slate-800">
            {estimated_payback_years != null ? `${estimated_payback_years} Years` : '—'}
          </dd>
        </div>
      </dl>
    </div>
  )
}
