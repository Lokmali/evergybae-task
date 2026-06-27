import { useCallback, useRef, useState } from 'react'

const ACCEPT = '.pdf,.png,.jpg,.jpeg'

export default function FileUpload({ onFileSelect, disabled }) {
  const [isDragging, setIsDragging] = useState(false)
  const inputRef = useRef(null)

  const validateFile = useCallback((file) => {
    const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase()
    if (!['.pdf', '.png', '.jpg', '.jpeg'].includes(ext)) {
      throw new Error('Use PDF, PNG, JPG, or JPEG.')
    }
    if (file.size > 20 * 1024 * 1024) {
      throw new Error('File must be under 20 MB.')
    }
    return file
  }, [])

  const handleFile = useCallback(
    (file) => {
      if (!file || disabled) return
      try {
        onFileSelect(validateFile(file))
      } catch (err) {
        onFileSelect(null, err.message)
      }
    },
    [disabled, onFileSelect, validateFile],
  )

  return (
    <div
      onDrop={(e) => { e.preventDefault(); setIsDragging(false); handleFile(e.dataTransfer.files?.[0]) }}
      onDragOver={(e) => { e.preventDefault(); if (!disabled) setIsDragging(true) }}
      onDragLeave={() => setIsDragging(false)}
      onClick={() => !disabled && inputRef.current?.click()}
      className={`upload-zone p-10 text-center ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${isDragging ? 'upload-zone-active' : ''}`}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPT}
        className="hidden"
        disabled={disabled}
        onChange={(e) => handleFile(e.target.files?.[0])}
      />

      <svg className="w-10 h-10 text-blue-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
      </svg>

      <p className="font-semibold text-slate-800">
        {isDragging ? 'Drop file here' : 'Upload electricity bill'}
      </p>
      <p className="text-sm text-slate-500 mt-1">PDF, PNG, or JPG · Max 20 MB</p>

      <button
        type="button"
        disabled={disabled}
        className="btn-primary mt-5"
        onClick={(e) => { e.stopPropagation(); inputRef.current?.click() }}
      >
        Choose file
      </button>
    </div>
  )
}
