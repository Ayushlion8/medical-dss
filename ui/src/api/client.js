import axios from 'axios'

const api = axios.create({ baseURL: '/api', timeout: 300_000 })

export async function uploadImage(file) {
  const fd = new FormData()
  fd.append('file', file)
  const { data } = await api.post('/upload-image', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data  // { image_id, filename, path }
}

export async function analyzeCase(payload) {
  const { data } = await api.post('/analyze-case', payload)
  return data
}

export async function checkHealth() {
  const { data } = await api.get('/health')
  return data
}

export default api
