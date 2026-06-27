import axios from 'axios'

const api = axios.create({
  // Production: leave empty to use Vercel /api proxy → Railway backend
  // Local dev: empty uses Vite proxy in vite.config.js
  baseURL: import.meta.env.VITE_API_URL || '',
  timeout: 120000, // 2 min — Vision API can be slow
  headers: {
    Accept: 'application/json',
  },
})

/**
 * Upload bill file and extract data via OpenAI Vision.
 * @param {File} file - PDF or image file
 * @returns {Promise<{session_id: string, extracted_data: object, fields: string[]}>}
 */
export async function extractBillData(file) {
  const formData = new FormData()
  formData.append('file', file)

  const { data } = await api.post('/api/extract', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

/**
 * Generate Excel from extracted/edited bill data.
 * @param {string} sessionId
 * @param {object} billData
 * @returns {Promise<{filename: string, download_url: string, message: string}>}
 */
export async function generateExcel(sessionId, billData) {
  const { data } = await api.post('/api/generate', {
    session_id: sessionId,
    data: billData,
  })
  return data
}

/**
 * Build full download URL for generated Excel.
 * @param {string} downloadPath - e.g. /api/download/Solar_Output_xxx.xlsx
 */
export function getDownloadUrl(downloadPath) {
  const base = import.meta.env.VITE_API_URL || ''
  return `${base}${downloadPath}`
}

/**
 * Parse axios errors into user-friendly messages.
 * @param {unknown} error
 * @returns {string}
 */
export function getErrorMessage(error) {
  if (axios.isAxiosError(error)) {
    if (error.code === 'ECONNABORTED') {
      return 'Request timed out. The AI is taking longer than expected — please try again.'
    }
    if (!error.response) {
      return 'Network error. Please check your connection and ensure the backend is running.'
    }
    const detail = error.response.data?.detail
    if (typeof detail === 'string') {
      if (detail.includes('Unable to read PDF')) return detail
      if (detail.includes('Consumer Number')) return detail
      if (detail.includes('Bill Amount')) return detail
      if (detail.includes('Image quality')) return detail
      return detail
    }
    if (Array.isArray(detail)) {
      return detail.map((d) => d.msg || JSON.stringify(d)).join(', ')
    }
    if (error.response.status === 413) {
      return 'File is too large. Please upload a smaller PDF or image.'
    }
    if (error.response.status === 422) {
      return 'Could not extract bill data. Try a clearer photo or PDF.'
    }
    return `Server error (${error.response.status}). Please try again.`
  }
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred.'
}

export default api
