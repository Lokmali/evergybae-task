import { useCallback, useEffect, useRef, useState } from 'react'

import FileUpload from './components/FileUpload'

import LoadingOverlay from './components/LoadingOverlay'

import DataPreview from './components/DataPreview'

import SolarSummary from './components/SolarSummary'

import Toast from './components/Toast'

import { extractBillData, generateExcel, getDownloadUrl, getErrorMessage } from './services/api'



const STEPS = {

  UPLOAD: 'upload',

  EXTRACTING: 'extracting',

  PREVIEW: 'preview',

  GENERATING: 'generating',

  DONE: 'done',

}



const STEP_LABELS = ['Upload', 'Extract', 'Review', 'Download']



const EXTRACT_PROGRESS_STEPS = [
  'Upload Bill',
  'Reading PDF',
  'AI Extraction',
  'Validating Data',
]

const GENERATE_PROGRESS_STEPS = [
  'Validating Data',
  'Generating Excel',
  'Done',
]



function StepIndicator({ step }) {

  const stepIndex = {

    [STEPS.UPLOAD]: 0,

    [STEPS.EXTRACTING]: 1,

    [STEPS.PREVIEW]: 2,

    [STEPS.GENERATING]: 2,

    [STEPS.DONE]: 3,

  }[step]



  return (

    <ol className="flex items-center justify-center gap-2 sm:gap-4 mb-8">

      {STEP_LABELS.map((label, i) => {

        const done = i < stepIndex

        const current = i === stepIndex

        return (

          <li key={label} className="flex items-center gap-2 sm:gap-4">

            {i > 0 && (

              <span className={`hidden sm:block w-8 h-px ${done ? 'bg-green-400' : 'bg-blue-200'}`} />

            )}

            <span className="flex items-center gap-2">

              <span

                className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold ${

                  current

                    ? 'bg-blue-600 text-white'

                    : done

                      ? 'bg-green-500 text-white'

                      : 'bg-white text-slate-400 border border-blue-200'

                }`}

              >

                {done ? '✓' : i + 1}

              </span>

              <span

                className={`text-xs font-medium hidden sm:inline ${

                  current ? 'text-blue-700' : done ? 'text-green-700' : 'text-slate-400'

                }`}

              >

                {label}

              </span>

            </span>

          </li>

        )

      })}

    </ol>

  )

}



export default function App() {

  const [step, setStep] = useState(STEPS.UPLOAD)

  const [progress, setProgress] = useState(0)

  const [progressStep, setProgressStep] = useState(0)

  const [sessionId, setSessionId] = useState(null)

  const [extractedData, setExtractedData] = useState({})

  const [fieldConfidence, setFieldConfidence] = useState({})

  const [solarSummary, setSolarSummary] = useState({})

  const [fields, setFields] = useState([])

  const [downloadInfo, setDownloadInfo] = useState(null)

  const [toast, setToast] = useState({ message: '', type: 'info' })

  const progressRef = useRef(null)

  const stepRef = useRef(null)



  const showToast = useCallback((message, type = 'info') => {

    setToast({ message, type })

  }, [])



  const clearToast = useCallback(() => {

    setToast({ message: '', type: 'info' })

  }, [])



  useEffect(() => {

    if (step !== STEPS.EXTRACTING && step !== STEPS.GENERATING) {

      if (progressRef.current) {

        clearInterval(progressRef.current)

        progressRef.current = null

      }

      if (stepRef.current) {

        clearInterval(stepRef.current)

        stepRef.current = null

      }

      return

    }



    const steps = step === STEPS.GENERATING ? GENERATE_PROGRESS_STEPS : EXTRACT_PROGRESS_STEPS

    setProgressStep(0)

    setProgress(step === STEPS.GENERATING ? 20 : 8)



    stepRef.current = setInterval(() => {

      setProgressStep((s) => (s < steps.length - 1 ? s + 1 : s))

    }, step === STEPS.EXTRACTING ? 4500 : 1200)



    progressRef.current = setInterval(() => {

      setProgress((p) => (p >= 92 ? p : p + Math.random() * 8))

    }, 700)



    return () => {

      if (progressRef.current) clearInterval(progressRef.current)

      if (stepRef.current) clearInterval(stepRef.current)

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

      setProgressStep(EXTRACT_PROGRESS_STEPS.length)

      setSessionId(result.session_id)

      setExtractedData(result.extracted_data)

      setFieldConfidence(result.field_confidence || {})

      setSolarSummary(result.solar_summary || {})

      setFields(result.fields)

      setStep(STEPS.PREVIEW)

      showToast('Extraction complete.', 'success')

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

      setProgress(100)

      setProgressStep(GENERATE_PROGRESS_STEPS.length)

      setDownloadInfo(result)

      setStep(STEPS.DONE)

      showToast('Excel file ready.', 'success')

    } catch (err) {

      setStep(STEPS.PREVIEW)

      showToast(getErrorMessage(err), 'error')

    }

  }



  const handleReset = () => {

    setStep(STEPS.UPLOAD)

    setSessionId(null)

    setExtractedData({})

    setFieldConfidence({})

    setSolarSummary({})

    setFields([])

    setDownloadInfo(null)

    setProgress(0)

    setProgressStep(0)

  }



  const isBusy = step === STEPS.EXTRACTING || step === STEPS.GENERATING

  const loadingSteps = step === STEPS.GENERATING ? GENERATE_PROGRESS_STEPS : EXTRACT_PROGRESS_STEPS

  const loadingMessage = loadingSteps[progressStep] || loadingSteps[0]



  return (

    <div className="min-h-screen flex flex-col">

      <header className="app-header">

        <div className="max-w-3xl mx-auto px-4 py-4 flex items-center gap-3">

          <div className="w-9 h-9 rounded-lg bg-blue-600 flex items-center justify-center">

            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>

              <path strokeLinecap="round" strokeLinejoin="round" d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />

            </svg>

          </div>

          <div>

            <h1 className="text-sm font-bold text-slate-900">Energybae AI</h1>

            <p className="text-xs text-green-700">Solar Load Calculator</p>

          </div>

        </div>

      </header>



      <main className="flex-1 max-w-3xl w-full mx-auto px-4 py-8">

        {step === STEPS.UPLOAD && (

          <div className="text-center mb-8">

            <h2 className="text-2xl font-bold text-blue-800">MSEDCL Bill to Excel</h2>

            <p className="text-sm text-slate-600 mt-2">

              Upload your electricity bill to fill the solar calculator spreadsheet.

            </p>

          </div>

        )}



        <StepIndicator step={step} />



        {step === STEPS.UPLOAD && (

          <FileUpload onFileSelect={handleFileSelect} disabled={isBusy} />

        )}



        {step === STEPS.EXTRACTING && (

          <LoadingOverlay

            message={loadingMessage}

            progress={progress}

            steps={loadingSteps}

            activeStep={progressStep}

          />

        )}



        {step === STEPS.GENERATING && (

          <LoadingOverlay

            message={loadingMessage}

            progress={progress}

            steps={loadingSteps}

            activeStep={progressStep}

          />

        )}



        {step === STEPS.PREVIEW && (

          <DataPreview

            data={extractedData}

            fields={fields}

            fieldConfidence={fieldConfidence}

            solarSummary={solarSummary}

            onChange={setExtractedData}

            onGenerate={handleGenerate}

            onReset={handleReset}

          />

        )}



        {step === STEPS.DONE && downloadInfo && (

          <div className="card p-8 text-center max-w-md mx-auto">

            <div className="w-14 h-14 rounded-full bg-green-100 text-green-600 flex items-center justify-center mx-auto mb-4">

              <svg className="w-7 h-7" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>

                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />

              </svg>

            </div>

            <h3 className="text-lg font-bold text-slate-900">Download ready</h3>

            <p className="text-sm text-slate-500 mt-1 mb-4">{downloadInfo.filename}</p>



            <SolarSummary summary={solarSummary} />



            <a

              href={getDownloadUrl(downloadInfo.download_url)}

              download={downloadInfo.filename}

              className="btn-primary w-full"

            >

              Download Excel

            </a>

            <button type="button" onClick={handleReset} className="btn-secondary w-full mt-3">

              Upload another bill

            </button>

          </div>

        )}

      </main>



      <footer className="py-4 text-center text-xs text-slate-400">

        MSEDCL electricity bills · Maharashtra

      </footer>



      <Toast message={toast.message} type={toast.type} onClose={clearToast} />

    </div>

  )

}


