import React, { useState } from 'react'
import Banner from './components/Banner'
import Navbar from './components/Navbar'
import UploadStep from './components/UploadStep'
import CaseFormStep from './components/CaseFormStep'
import AnalysisPanel from './components/AnalysisPanel'

export default function App() {
  const [step, setStep]       = useState('upload')   // upload | form | result
  const [images, setImages]   = useState([])          // [{image_id, filename, uri}]
  const [result, setResult]   = useState(null)

  return (
    <div className="min-h-screen flex flex-col">
      <Banner />
      <Navbar step={step} />
      <main className="flex-1 max-w-6xl mx-auto w-full px-4 py-8">
        {step === 'upload' && (
          <UploadStep
            onDone={(imgs) => { setImages(imgs); setStep('form') }}
          />
        )}
        {step === 'form' && (
          <CaseFormStep
            images={images}
            onBack={() => setStep('upload')}
            onResult={(r) => { setResult(r); setStep('result') }}
          />
        )}
        {step === 'result' && (
          <AnalysisPanel
            result={result}
            onReset={() => { setImages([]); setResult(null); setStep('upload') }}
          />
        )}
      </main>
    </div>
  )
}
