import { useCallback, useEffect, useRef, useState } from 'react'
import FileUpload from './components/FileUpload'
import LoadingOverlay from './components/LoadingOverlay'
import DataPreview from './components/DataPreview'
import Toast from './components/Toast'
import { extractBillData, generateExcel, getDownloadUrl, getErrorMessage } from './services/api'

/** Application workflow states */
const STEPS = {
  UPLOAD: 'upload',
  EXTRACTING: 'extracting',
  PREVIEW: 'preview',
  GENERATING: 'generating',
  DONE: 'done',
}

export default function App() {
  const [step, setStep] = useState(STEPS.UPLOAD)
  const [progress, setProgress] = useState(0)
  const [sessionId, setSessionId] = useState(null)
  const [extractedData, setExtractedData] = useState({})
  const [fields, setFields] = useState([])
  const [downloadInfo, setDownloadInfo] = useState(null)
  const [toast, setToast] = useState({ message: '', type: 'info' })
  const progressRef = useRef(null)

  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type })
  }, [])

  const clearToast = useCallback(() => {
    setToast({ message: '', type: 'info' })
  }, [])

  // Simulated progress while waiting for AI
  useEffect(() => {
    if (step !== STEPS.EXTRACTING) {
      if (progressRef.current) {
        clearInterval(progressRef.current)
        progressRef.current = null
      }
      return
    }

    setProgress(5)
    progressRef.current = setInterval(() => {
      setProgress((p) => {
        if (p >= 92) return p
        return p + Math.random() * 8
      })
    }, 800)

    return () => {
      if (progressRef.current) clearInterval(progressRef.current)
    }
  }, [step])

  const handleFileSelect = async (file, errorMsg) => {
    if (errorMsg) {
      showToast(errorMsg, 'error')
      return
    }
    if (!file) return

    setStep(STEPS.EXTRACTING)
    setDownloadInfo(null)

    try {
      const result = await extractBillData(file)
      setProgress(100)
      setSessionId(result.session_id)
      setExtractedData(result.extracted_data)
      setFields(result.fields)
      setStep(STEPS.PREVIEW)
      showToast('Bill data extracted successfully! Review and edit if needed.', 'success')
    } catch (err) {
      setStep(STEPS.UPLOAD)
      showToast(getErrorMessage(err), 'error')
    }
  }

  const handleGenerate = async () => {
    if (!sessionId) return

    setStep(STEPS.GENERATING)
    try {
      const result = await generateExcel(sessionId, extractedData)
      setDownloadInfo(result)
      setStep(STEPS.DONE)
      showToast(result.message, 'success')
    } catch (err) {
      setStep(STEPS.PREVIEW)
      showToast(getErrorMessage(err), 'error')
    }
  }

  const handleReset = () => {
    setStep(STEPS.UPLOAD)
    setSessionId(null)
    setExtractedData({})
    setFields([])
    setDownloadInfo(null)
    setProgress(0)
  }

  const isBusy = step === STEPS.EXTRACTING || step === STEPS.GENERATING

  return (
    <div className="min-h-screen">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-slate-100 sticky top-0 z-40">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-primary-600 flex items-center justify-center shadow-md">
            <svg className="w-6 h-6 text-amber-400" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
            </svg>
          </div>
          <div>
            <h1 className="text-lg font-bold text-primary-800 leading-tight">Energybae AI</h1>
            <p className="text-xs text-slate-500">Solar Load Calculator</p>
          </div>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 md:py-12">
        {/* Hero */}
        <section className="text-center mb-10">
          <h2 className="text-3xl md:text-4xl font-extrabold text-slate-900 tracking-tight">
            Energybae AI Solar Calculator
          </h2>
          <p className="mt-3 text-base md:text-lg text-slate-600 max-w-2xl mx-auto">
            Upload your electricity bill and generate a completed solar calculation Excel automatically.
          </p>
        </section>

        {/* Step indicator */}
        <div className="flex items-center justify-center gap-2 mb-8">
          {['Upload', 'Extract', 'Review', 'Download'].map((label, i) => {
            const stepIndex = {
              [STEPS.UPLOAD]: 0,
              [STEPS.EXTRACTING]: 1,
              [STEPS.PREVIEW]: 2,
              [STEPS.GENERATING]: 2,
              [STEPS.DONE]: 3,
            }[step]

            const isActive = i <= stepIndex
            const isCurrent = i === stepIndex

            return (
              <div key={label} className="flex items-center gap-2">
                {i > 0 && (
                  <div className={`w-8 md:w-12 h-0.5 ${isActive ? 'bg-primary-400' : 'bg-slate-200'}`} />
                )}
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors
                      ${isCurrent ? 'bg-primary-600 text-white ring-4 ring-primary-100' :
                        isActive ? 'bg-primary-500 text-white' : 'bg-slate-200 text-slate-500'}`}
                  >
                    {i + 1}
                  </div>
                  <span className={`text-xs hidden sm:block ${isCurrent ? 'text-primary-700 font-semibold' : 'text-slate-400'}`}>
                    {label}
                  </span>
                </div>
              </div>
            )
          })}
        </div>

        {/* Content */}
        {step === STEPS.UPLOAD && (
          <FileUpload onFileSelect={handleFileSelect} disabled={isBusy} />
        )}

        {step === STEPS.EXTRACTING && (
          <LoadingOverlay message="AI is reading your electricity bill..." progress={progress} />
        )}

        {(step === STEPS.PREVIEW || step === STEPS.GENERATING) && (
          <DataPreview
            data={extractedData}
            fields={fields}
            onChange={setExtractedData}
            onGenerate={handleGenerate}
            onReset={handleReset}
            isGenerating={step === STEPS.GENERATING}
          />
        )}

        {step === STEPS.DONE && downloadInfo && (
          <div className="card p-8 md:p-10 text-center">
            <div className="w-16 h-16 mx-auto rounded-2xl bg-emerald-100 flex items-center justify-center mb-5">
              <svg className="w-9 h-9 text-emerald-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h3 className="text-2xl font-bold text-slate-800">Excel Ready!</h3>
            <p className="text-slate-500 mt-2 mb-6">
              Your solar calculation spreadsheet has been generated with formulas intact.
            </p>

            <a
              href={getDownloadUrl(downloadInfo.download_url)}
              download={downloadInfo.filename}
              className="btn-primary inline-flex"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              Download Generated Excel
            </a>

            <p className="text-xs text-slate-400 mt-4">{downloadInfo.filename}</p>

            <button type="button" onClick={handleReset} className="btn-secondary mt-6 mx-auto">
              Process Another Bill
            </button>
          </div>
        )}

        {/* Feature cards — shown on upload step */}
        {step === STEPS.UPLOAD && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-10">
            {[
              {
                icon: '📄',
                title: 'PDF & Images',
                desc: 'Upload MSEDCL bills as PDF, PNG, or JPG',
              },
              {
                icon: '🤖',
                title: 'AI Extraction',
                desc: 'GPT-4 Vision reads every field on your bill',
              },
              {
                icon: '📊',
                title: 'Excel Output',
                desc: 'Formulas preserved — only input cells filled',
              },
            ].map((f) => (
              <div key={f.title} className="card p-5 text-center">
                <span className="text-3xl">{f.icon}</span>
                <h3 className="font-semibold text-slate-800 mt-2">{f.title}</h3>
                <p className="text-sm text-slate-500 mt-1">{f.desc}</p>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="text-center py-8 text-xs text-slate-400">
        Energybae AI Solar Load Calculator &copy; {new Date().getFullYear()}
      </footer>

      <Toast message={toast.message} type={toast.type} onClose={clearToast} />
    </div>
  )
}
