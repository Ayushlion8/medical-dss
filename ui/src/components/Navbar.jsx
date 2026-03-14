import React from 'react'
import { Activity } from 'lucide-react'
import clsx from 'clsx'

const STEPS = [
  { id: 'upload', label: '1. Upload Image' },
  { id: 'form',   label: '2. Case Form' },
  { id: 'result', label: '3. Analysis' },
]

export default function Navbar({ step }) {
  return (
    <header className="border-b border-navy-700 bg-navy-900/80 backdrop-blur-sm
                       sticky top-0 z-40">
      <div className="max-w-6xl mx-auto px-4 py-3 flex items-center gap-6">
        <div className="flex items-center gap-2 mr-4">
          <div className="bg-teal-500/20 rounded-lg p-1.5">
            <Activity size={20} className="text-teal-400" />
          </div>
          <span className="font-semibold text-white text-sm hidden sm:block">
            Medical DSS
          </span>
        </div>
        <nav className="flex items-center gap-1">
          {STEPS.map((s, i) => (
            <div key={s.id} className="flex items-center gap-1">
              <span className={clsx(
                'text-xs font-medium px-3 py-1.5 rounded-lg transition-colors',
                step === s.id
                  ? 'bg-teal-500/20 text-teal-400'
                  : 'text-slate-500'
              )}>
                {s.label}
              </span>
              {i < STEPS.length - 1 && (
                <span className="text-navy-700 text-xs">›</span>
              )}
            </div>
          ))}
        </nav>
      </div>
    </header>
  )
}
