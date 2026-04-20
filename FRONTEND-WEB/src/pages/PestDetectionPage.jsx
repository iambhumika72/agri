import { useState, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { Camera, Upload, Target, AlertTriangle, Leaf, FlaskConical } from 'lucide-react';
import PageHeader from '../components/PageHeader';
import FarmSelector from '../components/FarmSelector';
import LoadingSpinner from '../components/LoadingSpinner';
import ErrorBanner from '../components/ErrorBanner';
import ConfidenceBadge from '../components/ConfidenceBadge';
import SeverityBadge from '../components/SeverityBadge';
import { pestAPI } from '../api/client';

export default function PestDetectionPage() {
  const { t } = useTranslation();
  const [farmId, setFarmId] = useState('');
  const [stream, setStream] = useState(null);
  const [previewUrl, setPreviewUrl] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const videoRef = useRef(null);
  const fileInputRef = useRef(null);

  const startCamera = async () => {
    setError(null);
    try {
      const mediaStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      setStream(mediaStream);
      setPreviewUrl('');
      setResult(null);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
      }
    } catch (err) {
      setError("Could not access camera. Please use file upload.");
    }
  };

  const stopCamera = () => {
    if (stream) {
      stream.getTracks().forEach(t => t.stop());
      setStream(null);
    }
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const canvas = document.createElement('canvas');
    canvas.width = videoRef.current.videoWidth;
    canvas.height = videoRef.current.videoHeight;
    canvas.getContext('2d').drawImage(videoRef.current, 0, 0);
    
    canvas.toBlob((blob) => {
      const url = URL.createObjectURL(blob);
      setPreviewUrl(url);
      stopCamera();
    }, 'image/jpeg', 0.9);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setResult(null);
      stopCamera();
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
    }
  };

  const submitAnalysis = async () => {
    if (!previewUrl) return;
    
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const response = await fetch(previewUrl);
      const blob = await response.blob();
      
      const formData = new FormData();
      formData.append('file', blob, 'capture.jpg');
      formData.append('farm_id', farmId || 'anonymous');

      const data = await pestAPI.detectPest(formData);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const clearForm = () => {
    setPreviewUrl('');
    setResult(null);
    setError(null);
    stopCamera();
  };

  return (
    <div className="max-w-4xl mx-auto space-y-6 pb-24 md:pb-8">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PageHeader 
          titleKey="Pest Detection" 
          descKey="Upload a photo to detect plant diseases." 
          icon={Target} 
        />
        <FarmSelector value={farmId} onChange={setFarmId} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        
        {/* Left Column: Input */}
        <div className="card space-y-4">
          <div className="bg-neutral-100 rounded-xl overflow-hidden aspect-[4/3] flex items-center justify-center relative border border-neutral-200">
            {stream ? (
              <video 
                ref={videoRef} 
                autoPlay 
                playsInline 
                className="w-full h-full object-cover"
              />
            ) : previewUrl ? (
              <img 
                src={previewUrl} 
                alt="Plant preview" 
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="text-center text-neutral-400 p-6">
                <Target className="w-12 h-12 mx-auto mb-3 text-neutral-300" />
                <p>Camera ready. Take or upload a close-up photo.</p>
              </div>
            )}

            {stream && (
              <button 
                onClick={capturePhoto}
                className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-white text-emerald-600 rounded-full px-6 py-2 font-bold shadow-lg border border-emerald-100 hover:bg-emerald-50 transition-colors"
              >
                📸 Capture
              </button>
            )}
          </div>

          {!stream && (
            <div className="flex gap-3">
              <button 
                onClick={startCamera}
                className="flex-1 flex items-center justify-center gap-2 bg-emerald-600 hover:bg-emerald-700 text-white py-3 rounded-lg font-medium transition-colors"
              >
                <Camera className="w-5 h-5" />
                Open Camera
              </button>
              
              <input 
                type="file" 
                ref={fileInputRef}
                accept="image/*" 
                className="hidden" 
                onChange={handleFileUpload}
              />
              
              <button 
                onClick={() => fileInputRef.current?.click()}
                className="flex-1 flex items-center justify-center gap-2 bg-neutral-800 hover:bg-neutral-900 text-white py-3 rounded-lg font-medium transition-colors"
              >
                <Upload className="w-5 h-5" />
                Upload File
              </button>
            </div>
          )}

          {previewUrl && !loading && !result && (
            <div className="flex gap-3 pt-2">
              <button 
                onClick={submitAnalysis}
                className="flex-2 w-full flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white py-3 rounded-lg font-bold transition-colors shadow-md"
              >
                <Target className="w-5 h-5" />
                Analyze Plant
              </button>
              <button 
                onClick={clearForm}
                className="px-4 py-3 bg-neutral-200 text-neutral-700 rounded-lg font-medium hover:bg-neutral-300 transition-colors"
              >
                Clear
              </button>
            </div>
          )}

          {loading && <LoadingSpinner message="Analyzing plant photo..." />}
          {error && <ErrorBanner message={error} />}
        </div>

        {/* Right Column: Results */}
        <div className="flex flex-col gap-4">
          {!result && !loading && (
            <div className="card flex-1 flex flex-col items-center justify-center text-center text-neutral-400 p-8 border-dashed">
              <Leaf className="w-12 h-12 mb-4 text-neutral-300" />
              <p>Results will appear here after analysis.</p>
            </div>
          )}

          {result && (
            <div className="card space-y-5 animate-fadeIn">
              <div className="flex items-center justify-between pb-4 border-b border-neutral-100">
                <ConfidenceBadge 
                  score={result.final_confidence_adjusted} 
                  label={result.confidence_label} 
                />
                <SeverityBadge level={result.vision_analysis.urgency_level === 'immediate' ? 'critical' : 'moderate'} />
              </div>

              <div>
                <h3 className="text-xl font-bold text-neutral-800 capitalize mb-1">
                  {result.vision_analysis.pest_type.replace(/_/g, ' ')}
                </h3>
                <p className="text-sm text-neutral-600 leading-relaxed">
                  {result.vision_analysis.visual_evidence}
                </p>
              </div>

              {result.treatment_plan && (
                <div className="bg-red-50 border border-red-200 rounded-xl p-4 flex items-start gap-3">
                  <AlertTriangle className="w-5 h-5 text-red-600 mt-0.5" />
                  <div>
                    <p className="font-bold text-red-800 mb-1">
                      Act within {result.treatment_plan.act_within_hours / 24} days
                    </p>
                    <p className="text-sm text-red-700">
                      Estimated Cost: {result.treatment_plan.estimated_cost_inr}
                    </p>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="bg-emerald-50 border border-emerald-100 rounded-xl p-4">
                  <div className="flex items-center gap-2 text-emerald-800 font-bold mb-2">
                    <Leaf className="w-4 h-4" /> Organic First
                  </div>
                  <p className="text-sm text-emerald-900">
                    {result.vision_analysis.recommended_action}
                  </p>
                </div>

                <div className="bg-purple-50 border border-purple-100 rounded-xl p-4">
                  <div className="flex items-center gap-2 text-purple-800 font-bold mb-2">
                    <FlaskConical className="w-4 h-4" /> Chemical
                  </div>
                  <p className="text-sm text-purple-900">
                    {result.similar_cases?.[0]?.chemical_treatment || "Consult local officer"}
                  </p>
                </div>
              </div>

              {result.final_confidence_adjusted < 0.5 && (
                <div className="bg-orange-50 text-orange-800 p-3 rounded-lg text-sm font-medium flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" />
                  Low confidence analysis. Please retake photo or consult an expert.
                </div>
              )}
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
