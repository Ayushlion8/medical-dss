import React, { useState, useCallback } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, ImageIcon, FileText, X, CheckCircle, ShieldAlert } from 'lucide-react'
import toast from 'react-hot-toast'
import clsx from 'clsx'
import { uploadImage } from '../api/client'

const ACCEPTED = {
  'image/png':  ['.png'],
  'image/jpeg': ['.jpg', '.jpeg'],
  'application/octet-stream': ['.dcm'],
  'application/dicom':        ['.dcm'],
}

export default function UploadStep({ onDone }) {
  const [files, setFiles]     = useState([])   // raw File objects
  const [uploads, setUploads] = useState([])   // [{image_id, filename, uri, status}]
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback((accepted) => {
    setFiles(prev => [...prev, ...accepted])
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop, accept: ACCEPTED, multiple: true,
  })

  const removeFile = (idx) => setFiles(f => f.filter((_, i) => i !== idx))

  const handleUpload = async () => {
    if (!files.length) return toast.error('Add at least one image.')
    setUploading(true)
    const results = []
    for (const file of files) {
      try {
        const res = await uploadImage(file)
        results.push({ ...res, uri: res.path, status: 'ok' })
      } catch (e) {
        toast.error(`Upload failed: ${file.name}`)
        results.push({ image_id: null, filename: file.name, status: 'error' })
      }
    }
    setUploads(results)
    setUploading(false)
    const ok = results.filter(r => r.status === 'ok')
    if (ok.length) {
      toast.success(`${ok.length} image(s) uploaded`)
    }
  }

  const handleContinue = () => {
    const ok = uploads.filter(r => r.status === 'ok')
    if (!ok.length) return toast.error('Upload images first.')
    onDone(ok.map(r => ({
      id: r.image_id,
      image_id: r.image_id,
      filename: r.filename,
      uri: r.path,
    })))
  }

  return (
    <div className="max-w-2xl mx-auto animate-fade-in">
      <h1 className="text-2xl font-bold text-white mb-1">Upload Chest X-Ray</h1>
      <p className="text-slate-400 text-sm mb-6">
        DICOM (.dcm), PNG, or JPEG accepted. Images are processed locally
        and never stored beyond your session.
      </p>

      {/* De-identification warning */}
      <div className="flex items-start gap-3 bg-amber-400/10 border border-amber-400/30
                      rounded-xl p-4 mb-6 text-amber-300 text-sm">
        <ShieldAlert size={16} className="mt-0.5 shrink-0" />
        <span>
          <strong>De-identification required.</strong> Ensure all patient identifiers
          (name, DOB, MRN, accession number) have been removed from images and metadata
          before uploading. Never upload PHI.
        </span>
      </div>

      {/* Drop zone */}
      <div {...getRootProps()} className={clsx(
        'border-2 border-dashed rounded-2xl p-10 text-center cursor-pointer',
        'transition-all duration-200',
        isDragActive
          ? 'border-teal-500 bg-teal-500/10'
          : 'border-navy-700 hover:border-teal-600 bg-navy-800/40'
      )}>
        <input {...getInputProps()} />
        <Upload size={36} className={clsx(
          'mx-auto mb-3 transition-colors',
          isDragActive ? 'text-teal-400' : 'text-slate-500'
        )} />
        <p className="text-sm font-medium text-slate-300">
          {isDragActive ? 'Drop files here…' : 'Drag & drop images, or click to browse'}
        </p>
        <p className="text-xs text-slate-500 mt-1">DICOM, PNG, JPEG · max 50 MB per file</p>
      </div>

      {/* File list */}
      {files.length > 0 && (
        <ul className="mt-4 space-y-2">
          {files.map((f, i) => {
            const up = uploads.find(u => u.filename === f.name)
            return (
              <li key={i} className="flex items-center gap-3 card py-3 px-4">
                {f.name.endsWith('.dcm')
                  ? <FileText size={16} className="text-teal-400 shrink-0" />
                  : <ImageIcon size={16} className="text-teal-400 shrink-0" />
                }
                <span className="text-sm text-slate-300 flex-1 truncate">{f.name}</span>
                <span className="text-xs text-slate-500">
                  {(f.size / 1024 / 1024).toFixed(1)} MB
                </span>
                {up?.status === 'ok' && <CheckCircle size={14} className="text-teal-400" />}
                {!up && (
                  <button onClick={() => removeFile(i)}
                    className="text-slate-600 hover:text-red-400 transition-colors">
                    <X size={14} />
                  </button>
                )}
              </li>
            )
          })}
        </ul>
      )}

      {/* Actions */}
      <div className="flex gap-3 mt-6">
        {uploads.length === 0 ? (
          <button onClick={handleUpload} disabled={!files.length || uploading}
            className="btn-primary flex-1">
            {uploading ? 'Uploading…' : `Upload ${files.length || ''} Image(s)`}
          </button>
        ) : (
          <button onClick={handleContinue} className="btn-primary flex-1">
            Continue to Case Form →
          </button>
        )}
      </div>
    </div>
  )
}
