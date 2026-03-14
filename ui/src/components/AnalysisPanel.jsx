import React, { useState } from 'react'
import {
  RotateCcw, Download, Eye, EyeOff, BookOpen, AlertTriangle,
  ChevronRight, CheckCircle, XCircle, Activity, Microscope, FileText
} from 'lucide-react'
import clsx from 'clsx'

export default function AnalysisPanel({ result, onReset }) {
  const [showOverlays, setShowOverlays]   = useState(true)
  const [expandedDx, setExpandedDx]       = useState(null)
  const [showCitations, setShowCitations] = useState(false)
  const [showTraces, setShowTraces]       = useState(false)

  if (!result) return null

  const {
    case_id, imaging_findings, differentials, red_flags,
    next_steps, citations, overlays, groundedness, traces,
    report_url, disclaimer,
  } = result

  const citationMap = Object.fromEntries((citations || []).map(c => [c.id, c]))

  return (
    <div className="animate-slide-up space-y-6">
      {/* Header row */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold text-white">Diagnostic Report</h1>
          <p className="text-slate-400 text-sm mt-0.5">Case ID: <code className="font-mono text-teal-400">{case_id}</code></p>
        </div>
        <div className="flex items-center gap-2 flex-wrap">
          <button onClick={() => setShowOverlays(v => !v)} className="btn-ghost flex items-center gap-1.5 text-sm">
            {showOverlays ? <EyeOff size={14} /> : <Eye size={14} />}
            {showOverlays ? 'Hide' : 'Show'} Overlays
          </button>
          {report_url && (
            <a href={`${report_url}.pdf`} download className="btn-primary flex items-center gap-1.5 text-sm">
              <Download size={14} /> Download PDF
            </a>
          )}
          <button onClick={onReset} className="btn-ghost flex items-center gap-1.5 text-sm">
            <RotateCcw size={14} /> New Case
          </button>
        </div>
      </div>

      {/* Disclaimer */}
      <div className="badge-amber py-2 px-4 rounded-xl text-xs w-full justify-start">
        <AlertTriangle size={12} className="shrink-0" />
        {disclaimer}
      </div>

      {/* Red flags */}
      {red_flags?.length > 0 && (
        <div className="card border-red-500/40 bg-red-500/10">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={16} className="text-red-400" />
            <span className="text-sm font-semibold text-red-400 uppercase tracking-wide">Red Flags</span>
          </div>
          <ul className="space-y-1">
            {red_flags.map((rf, i) => (
              <li key={i} className="text-sm text-red-300 flex items-start gap-2">
                <span className="text-red-500 mt-0.5">•</span>{rf}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Imaging findings + overlays */}
      {Object.keys(imaging_findings || {}).length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <Microscope size={16} className="text-teal-400" />
            <h2 className="text-sm font-semibold text-teal-400 uppercase tracking-wider">
              Imaging Findings
            </h2>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {Object.entries(imaging_findings).map(([name, f]) => {
              const overlay = overlays?.find(o => o.overlay_id === f.overlay_id)
              return (
                <div key={name} className="bg-navy-900 rounded-xl p-4 border border-navy-700">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-white">
                      {name.replace(/_/g, ' ')}
                    </span>
                    <ProbBadge prob={f.prob} />
                  </div>
                  {f.description && (
                    <p className="text-xs text-slate-400">{f.description}</p>
                  )}
                  {showOverlays && overlay?.overlay_url && (
                    <img
                      src={overlay.overlay_url}
                      alt={`${name} overlay`}
                      className="mt-3 rounded-lg w-full max-h-48 object-contain bg-black/40"
                    />
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Differentials */}
      <div className="card">
        <div className="flex items-center gap-2 mb-4">
          <Activity size={16} className="text-teal-400" />
          <h2 className="text-sm font-semibold text-teal-400 uppercase tracking-wider">
            Differential Diagnoses
          </h2>
        </div>
        <div className="space-y-3">
          {differentials?.map((dx, i) => {
            const isOpen = expandedDx === i
            const supportCitations = dx.support?.map(s => citationMap[s.snippet_id]).filter(Boolean) || []
            return (
              <div key={i} className={clsx(
                'rounded-xl border transition-all duration-200 overflow-hidden',
                isOpen ? 'border-teal-500/40 bg-teal-500/5' : 'border-navy-700 bg-navy-900'
              )}>
                <button
                  onClick={() => setExpandedDx(isOpen ? null : i)}
                  className="w-full flex items-center gap-3 px-4 py-3 text-left"
                >
                  <span className="text-xs font-bold text-teal-400 w-5 shrink-0">
                    #{dx.probability_rank || i + 1}
                  </span>
                  <div className="flex-1 min-w-0">
                    <span className="text-sm font-medium text-white">{dx.dx}</span>
                    <span className="ml-2 text-xs text-slate-500 font-mono">{dx.icd10}</span>
                  </div>
                  <ChevronRight size={14} className={clsx(
                    'text-slate-500 shrink-0 transition-transform',
                    isOpen && 'rotate-90'
                  )} />
                </button>
                {isOpen && (
                  <div className="px-4 pb-4 space-y-3 animate-fade-in">
                    <p className="text-sm text-slate-300 leading-relaxed">{dx.rationale}</p>
                    {supportCitations.length > 0 && (
                      <div className="space-y-2">
                        <p className="text-xs text-slate-500 font-semibold uppercase">Evidence</p>
                        {supportCitations.map(c => (
                          <div key={c.id} className="bg-navy-800 rounded-lg p-3 border border-navy-700">
                            <div className="flex items-center gap-2 mb-1 flex-wrap">
                              <span className="badge-teal">{c.study_type || 'Study'}</span>
                              <span className="text-xs text-slate-400">{c.source} ({c.year || 'n/d'})</span>
                              {c.pmid && (
                                <a href={c.url} target="_blank" rel="noreferrer"
                                   className="text-xs text-teal-400 hover:underline">
                                  PMID:{c.pmid}
                                </a>
                              )}
                            </div>
                            <p className="text-xs text-slate-300 italic">"{c.quote}"</p>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* Next steps */}
      {next_steps?.length > 0 && (
        <div className="card">
          <div className="flex items-center gap-2 mb-4">
            <ChevronRight size={16} className="text-teal-400" />
            <h2 className="text-sm font-semibold text-teal-400 uppercase tracking-wider">
              Recommended Next Steps
            </h2>
          </div>
          <ul className="space-y-2">
            {next_steps.map((ns, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-slate-300">
                <span className="text-teal-500 mt-0.5 shrink-0">→</span>
                {ns}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Citations panel */}
      <div className="card">
        <button
          onClick={() => setShowCitations(v => !v)}
          className="w-full flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <BookOpen size={16} className="text-teal-400" />
            <h2 className="text-sm font-semibold text-teal-400 uppercase tracking-wider">
              Citations ({citations?.length || 0})
            </h2>
            {groundedness && (
              <span className={clsx(
                'ml-2',
                groundedness.verified ? 'badge-teal' : 'badge-amber'
              )}>
                {groundedness.verified
                  ? <><CheckCircle size={10} /> Verified</>
                  : <><XCircle size={10} /> Partial</>
                }
              </span>
            )}
          </div>
          <ChevronRight size={14} className={clsx(
            'text-slate-500 transition-transform',
            showCitations && 'rotate-90'
          )} />
        </button>
        {showCitations && (
          <div className="mt-4 space-y-3 animate-fade-in">
            {groundedness?.note && (
              <p className="text-xs text-slate-400 italic">{groundedness.note}</p>
            )}
            {citations?.map((c, i) => (
              <div key={c.id}
                className="bg-navy-900 rounded-xl border border-navy-700 p-4">
                <div className="flex items-start justify-between gap-3 mb-2">
                  <div>
                    <span className="text-xs font-mono text-teal-400 mr-2">[{c.id}]</span>
                    <span className="text-sm font-medium text-white">{c.title}</span>
                  </div>
                  <span className="badge-slate shrink-0">{c.study_type || 'Study'}</span>
                </div>
                <p className="text-xs text-slate-400 mb-2">
                  {c.authors} · {c.source} · {c.year}
                  {c.pmid && <> · <a href={c.url} target="_blank" rel="noreferrer"
                    className="text-teal-400 hover:underline">PMID:{c.pmid}</a></>}
                  {c.doi && <> · <span className="font-mono">{c.doi}</span></>}
                </p>
                <blockquote className="text-xs text-slate-300 italic border-l-2 border-teal-500/40 pl-3">
                  "{c.quote}"
                </blockquote>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Agent traces */}
      <div className="card">
        <button
          onClick={() => setShowTraces(v => !v)}
          className="w-full flex items-center justify-between"
        >
          <div className="flex items-center gap-2">
            <FileText size={16} className="text-slate-400" />
            <h2 className="text-sm font-semibold text-slate-400 uppercase tracking-wider">
              Agent Traces ({traces?.length || 0})
            </h2>
          </div>
          <ChevronRight size={14} className={clsx(
            'text-slate-600 transition-transform',
            showTraces && 'rotate-90'
          )} />
        </button>
        {showTraces && (
          <div className="mt-4 overflow-x-auto animate-fade-in">
            <table className="w-full text-xs font-mono">
              <thead>
                <tr className="text-slate-500 border-b border-navy-700">
                  <th className="pb-2 text-left">Agent</th>
                  <th className="pb-2 text-right">ms</th>
                  <th className="pb-2 text-right">Docs retrieved</th>
                </tr>
              </thead>
              <tbody>
                {traces?.map((t, i) => (
                  <tr key={i} className="border-b border-navy-700/50 text-slate-300">
                    <td className="py-1.5">{t.agent}</td>
                    <td className="py-1.5 text-right text-teal-400">{t.duration_ms}</td>
                    <td className="py-1.5 text-right">
                      {t.retrieved_doc_ids?.length ?? '–'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

function ProbBadge({ prob }) {
  if (prob >= 0.75) return <span className="badge-red">{(prob * 100).toFixed(0)}%</span>
  if (prob >= 0.45) return <span className="badge-amber">{(prob * 100).toFixed(0)}%</span>
  return <span className="badge-teal">{(prob * 100).toFixed(0)}%</span>
}
