import { useCallback, useRef, useState } from 'react'

const ACCEPTED_TYPES = {
  'application/pdf': ['.pdf'],
  'image/png': ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
}

const ACCEPT_STRING = '.pdf,.png,.jpg,.jpeg'

/**
 * Drag-and-drop file upload zone for electricity bills.
 */
export default function FileUpload({ onFileSelect, disabled }) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  const validateFile = useCallback((file) => {
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    const valid = ['.pdf', '.png', '.jpg', '.jpeg'].includes(ext)
    if (!valid) {
      throw new Error('Invalid file type. Please upload PDF, PNG, JPG, or JPEG.')
    }
    if (file.size > 20 * 1024 * 1024) {
      throw new Error('File too large. Maximum size is 20 MB.')
    }
    return file
  }, [])

  const handleFile = useCallback(
    (file) => {
      if (!file || disabled) return
      try {
        const valid = validateFile(file)
        onFileSelect(valid)
      } catch (err) {
        onFileSelect(null, err.message)
      }
    },
    [disabled, onFileSelect, validateFile],
  )

  const onDrop = useCallback(
    (e) => {
      e.preventDefault()
      setIsDragging(false)
      const file = e.dataTransfer.files?.[0]
      handleFile(file)
    },
    [handleFile],
  )

  const onDragOver = (e) => {
    e.preventDefault()
    if (!disabled) setIsDragging(true)
  }

  const onDragLeave = () => setIsDragging(false)

  return (
    <div
      onDrop={onDrop}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`
        relative cursor-pointer rounded-2xl border-2 border-dashed p-10 md:p-14
        transition-all duration-300 text-center
        ${disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-primary-400 hover:bg-primary-50/50'}
        ${isDragging ? 'border-primary-500 bg-primary-50 scale-[1.01]' : 'border-slate-300 bg-slate-50/80'}
      `}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT_STRING}
        className="hidden"
        disabled={disabled}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      <div className="flex flex-col items-center gap-4">
        {/* Upload icon */}
        <div
          className={`w-16 h-16 rounded-2xl flex items-center justify-center
            ${isDragging ? 'bg-primary-100' : 'bg-white shadow-md'}`}
        >
          <svg
            className="w-8 h-8 text-primary-600"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            strokeWidth={1.5}
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
            />
          </svg>
        </div>

        <div>
          <p className="text-lg font-semibold text-slate-700">
            {isDragging ? 'Drop your bill here' : 'Drag & drop your electricity bill'}
          </p>
          <p className="text-sm text-slate-500 mt-1">
            or click to browse — PDF, PNG, JPG, JPEG (max 20 MB)
          </p>
        </div>

        <button
          type="button"
          disabled={disabled}
          className="btn-primary mt-2"
          onClick={(e) => {
            e.stopPropagation()
            inputRef.current?.click()
          }}
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          Upload Bill
        </button>
      </div>
    </div>
  )
}

export { ACCEPTED_TYPES }
