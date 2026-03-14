import React, { useState } from 'react'
import { useForm } from 'react-hook-form'
import { ChevronLeft, Loader2, FlaskConical } from 'lucide-react'
import toast from 'react-hot-toast'
import { analyzeCase } from '../api/client'


export default function CaseFormStep({ images, onBack, onResult }) {
  const { register, handleSubmit, formState: { errors } } = useForm()
  const [loading, setLoading] = useState(false)
  const [agentLog, setAgentLog] = useState([])

  const AGENTS = [
    'Orchestrator',
    'Vision Agent (TorchXRayVision)',
    'Retrieval Agent (BM25 + Vector)',
    'Diagnosis Agent (Gemma)',
    'Citation Verifier',
    'Safety Agent + PDF',
  ]

  const onSubmit = async (data) => {
    setLoading(true)
    setAgentLog([])

    // Animate agent pipeline steps
    for (let i = 0; i < AGENTS.length; i++) {
      await new Promise(r => setTimeout(r, 400 * i))
      setAgentLog(prev => [...prev, AGENTS[i]])
    }

    const caseId = `case-${Date.now()}`
    const payload = {
      case_id: caseId,
      patient_context: {
        age:              parseInt(data.age),
        sex:              data.sex,
        chief_complaint:  data.chief_complaint,
        hpi:              data.hpi || null,
        pmh:              data.pmh ? data.pmh.split(',').map(s => s.trim()) : [],
        allergies:        data.allergies ? data.allergies.split(',').map(s => s.trim()) : [],
        meds:             data.meds ? data.meds.split(',').map(s => s.trim()) : [],
        vitals: {
          BP:   data.bp   || null,
          HR:   data.hr   ? parseInt(data.hr)   : null,
          RR:   data.rr   ? parseInt(data.rr)   : null,
          SpO2: data.spo2 ? parseFloat(data.spo2) : null,
        },
        labs: data.labs ? (() => {
          try { return JSON.parse(data.labs) } catch { return {} }
        })() : {},
      },
      images: images.map(img => ({
        id:       img.image_id || img.id,
        modality: 'CR',
        format:   img.filename?.endsWith('.dcm') ? 'DICOM' : 'PNG',
        uri:      img.uri || img.path,
      })),
      preferences: {
        recency_years: parseInt(data.recency_years) || 5,
        max_citations: parseInt(data.max_citations) || 8,
        show_overlays: true,
      },
    }

    try {
      const result = await analyzeCase(payload)
      setLoading(false)
      onResult(result)
    } catch (e) {
      setLoading(false)
      setAgentLog([])
      toast.error(`Analysis failed: ${e.response?.data?.detail || e.message}`)
    }
  }

  return (
    <div className="max-w-3xl mx-auto animate-fade-in">
      <button onClick={onBack}
        className="flex items-center gap-1 text-slate-400 hover:text-white
                   text-sm mb-6 transition-colors">
        <ChevronLeft size={16} /> Back to Upload
      </button>

      <h1 className="text-2xl font-bold text-white mb-1">Clinical Case Form</h1>
      <p className="text-slate-400 text-sm mb-8">
        Provide clinical context to guide the diagnostic agents.
        <span className="ml-2 badge-teal">{images.length} image(s) attached</span>
      </p>

      <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
        {/* Demographics */}
        <div className="card">
          <h2 className="text-sm font-semibold text-teal-400 mb-4 uppercase tracking-wider">
            Demographics
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">Age *</label>
              <input className="input" type="number" placeholder="64"
                {...register('age', { required: true, min: 0, max: 130 })} />
              {errors.age && <p className="text-red-400 text-xs mt-1">Required</p>}
            </div>
            <div>
              <label className="label">Sex *</label>
              <select className="input" {...register('sex', { required: true })}>
                <option value="">Select…</option>
                <option value="M">Male</option>
                <option value="F">Female</option>
                <option value="Other">Other</option>
              </select>
            </div>
            <div className="col-span-1">
              <label className="label">Chief Complaint *</label>
              <input className="input" placeholder="Acute dyspnea"
                {...register('chief_complaint', { required: true })} />
            </div>
          </div>
          <div className="mt-4">
            <label className="label">History of Present Illness (HPI)</label>
            <textarea className="input resize-none h-20"
              placeholder="64-year-old male with sudden onset dyspnea and pleuritic chest pain…"
              {...register('hpi')} />
          </div>
        </div>

        {/* Vitals */}
        <div className="card">
          <h2 className="text-sm font-semibold text-teal-400 mb-4 uppercase tracking-wider">
            Vitals
          </h2>
          <div className="grid grid-cols-4 gap-4">
            {[
              { name: 'bp',   label: 'BP (mmHg)',  placeholder: '98/60' },
              { name: 'hr',   label: 'HR (bpm)',   placeholder: '120' },
              { name: 'rr',   label: 'RR (/min)',  placeholder: '28' },
              { name: 'spo2', label: 'SpO₂ (%)',   placeholder: '88' },
            ].map(f => (
              <div key={f.name}>
                <label className="label">{f.label}</label>
                <input className="input" placeholder={f.placeholder}
                  {...register(f.name)} />
              </div>
            ))}
          </div>
        </div>

        {/* Medications / PMH / Allergies */}
        <div className="card">
          <h2 className="text-sm font-semibold text-teal-400 mb-4 uppercase tracking-wider">
            History
          </h2>
          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="label">Medications (comma-separated)</label>
              <input className="input" placeholder="metformin, lisinopril"
                {...register('meds')} />
            </div>
            <div>
              <label className="label">PMH (comma-separated)</label>
              <input className="input" placeholder="HTN, DM2"
                {...register('pmh')} />
            </div>
            <div>
              <label className="label">Allergies</label>
              <input className="input" placeholder="penicillin"
                {...register('allergies')} />
            </div>
          </div>
        </div>

        {/* Labs */}
        <div className="card">
          <h2 className="text-sm font-semibold text-teal-400 mb-4 uppercase tracking-wider">
            Labs (JSON)
          </h2>
          <textarea className="input font-mono resize-none h-20 text-xs"
            placeholder='{"D_dimer": 1200, "troponin": 0.03, "WBC": 14.2}'
            {...register('labs')} />
          <p className="text-xs text-slate-500 mt-1">
            Enter as JSON key-value pairs. Leave blank if unavailable.
          </p>
        </div>

        {/* Preferences */}
        <div className="card">
          <h2 className="text-sm font-semibold text-teal-400 mb-4 uppercase tracking-wider">
            Evidence Preferences
          </h2>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="label">Recency (years)</label>
              <select className="input" {...register('recency_years')}>
                <option value="3">Last 3 years</option>
                <option value="5" selected>Last 5 years</option>
                <option value="10">Last 10 years</option>
              </select>
            </div>
            <div>
              <label className="label">Max citations</label>
              <select className="input" {...register('max_citations')}>
                <option value="5">5</option>
                <option value="8" selected>8</option>
                <option value="12">12</option>
              </select>
            </div>
          </div>
        </div>

        {/* Agent progress */}
        {loading && (
          <div className="card border-teal-500/30 animate-fade-in">
            <div className="flex items-center gap-2 mb-4">
              <Loader2 size={16} className="text-teal-400 animate-spin" />
              <span className="text-sm font-semibold text-teal-400">
                Agent Pipeline Running…
              </span>
            </div>
            <div className="space-y-2">
              {AGENTS.map((a, i) => (
                <div key={a} className={`flex items-center gap-2 text-xs transition-all
                  ${agentLog.includes(a) ? 'text-teal-300' : 'text-slate-600'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full shrink-0
                    ${agentLog.includes(a) ? 'bg-teal-400 animate-pulse-dot' : 'bg-slate-700'}`} />
                  {a}
                </div>
              ))}
            </div>
          </div>
        )}

        <button type="submit" disabled={loading} className="btn-primary w-full flex items-center justify-center gap-2">
          {loading
            ? <><Loader2 size={16} className="animate-spin" /> Analyzing…</>
            : <><FlaskConical size={16} /> Run Diagnostic Analysis</>
          }
        </button>
      </form>
    </div>
  )
}
