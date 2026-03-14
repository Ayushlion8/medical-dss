import React from 'react'
import { AlertTriangle } from 'lucide-react'

export default function Banner() {
  return (
    <div className="bg-amber-400/10 border-b border-amber-400/30 py-2 px-4
                    flex items-center justify-center gap-2 text-amber-400 text-xs font-medium">
      <AlertTriangle size={13} />
      Research &amp; Education Only — Not a Medical Device — Not for Clinical Use
    </div>
  )
}
