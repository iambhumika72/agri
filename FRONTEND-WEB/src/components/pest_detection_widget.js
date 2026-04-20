/**
 * pest_detection_widget.js
 * ========================
 * Vanilla JS widget for AgriSense Pest Detection.
 * Handles camera access, image upload, and result display.
 */

class PestDetectionWidget {
    constructor(containerId, farmId = "anonymous") {
        this.container = document.getElementById(containerId);
        this.farmId = farmId;
        this.stream = null;
        this.init();
    }

    init() {
        this.container.innerHTML = `
            <div id="pest-widget-root" style="font-family: sans-serif; max-width: 500px; border: 1px solid #ccc; border-radius: 12px; padding: 20px; background: #fff; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <h3 style="margin-top: 0; color: #2e7d32;">🌿 Plant Pest Detection</h3>
                <p style="font-size: 0.9em; color: #666;">Take a close-up photo of the affected plant area.</p>
                
                <div id="camera-preview-container" style="width: 100%; height: 300px; background: #eee; border-radius: 8px; position: relative; overflow: hidden; display: flex; align-items: center; justify-content: center;">
                    <video id="pest-video" autoplay playsinline style="width: 100%; height: 100%; object-fit: cover; display: none;"></video>
                    <img id="pest-preview-img" style="width: 100%; height: 100%; object-fit: cover; display: none;" />
                    <div id="placeholder-text">Camera ready</div>
                </div>

                <div style="margin-top: 15px; display: flex; gap: 10px;">
                    <button id="btn-camera" style="flex: 1; padding: 10px; background: #4caf50; color: white; border: none; border-radius: 6px; cursor: pointer;">📸 Open Camera</button>
                    <button id="btn-capture" style="flex: 1; padding: 10px; background: #2196f3; color: white; border: none; border-radius: 6px; cursor: pointer; display: none;">🎯 Capture</button>
                    <input type="file" id="file-input" accept="image/*" style="display: none;" />
                    <button id="btn-upload" style="flex: 1; padding: 10px; background: #9c27b0; color: white; border: none; border-radius: 6px; cursor: pointer;">📁 Upload File</button>
                </div>

                <button id="btn-submit" style="width: 100%; margin-top: 15px; padding: 12px; background: #2e7d32; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; display: none;">Analyze Plant 🌿</button>

                <div id="pest-loading" style="display: none; text-align: center; margin-top: 20px;">
                    <div class="spinner" style="border: 4px solid #f3f3f3; border-top: 4px solid #2e7d32; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                    <p style="margin-top: 10px; font-weight: bold; color: #2e7d32;">Analyzing your plant... 🌿</p>
                </div>

                <div id="pest-result" style="display: none; margin-top: 20px; padding-top: 20px; border-top: 1px solid #eee;"></div>
            </div>
            <style>
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                .badge { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; font-weight: bold; color: white; }
                .badge-high { background: #4caf50; }
                .badge-mod { background: #ffc107; color: #333; }
                .badge-low { background: #f44336; }
                .sev-early { background: #2196f3; }
                .sev-mod { background: #ffc107; color: #333; }
                .sev-severe { background: #ff9800; }
                .sev-crit { background: #f44336; }
                .treatment-card { background: #f9f9f9; padding: 10px; border-radius: 6px; flex: 1; font-size: 0.9em; border: 1px solid #eee; }
            </style>
        `;

        this.bindEvents();
    }

    bindEvents() {
        const btnCamera = this.container.querySelector('#btn-camera');
        const btnCapture = this.container.querySelector('#btn-capture');
        const btnUpload = this.container.querySelector('#btn-upload');
        const btnSubmit = this.container.querySelector('#btn-submit');
        const fileInput = this.container.querySelector('#file-input');
        const video = this.container.querySelector('#pest-video');
        const previewImg = this.container.querySelector('#pest-preview-img');

        btnCamera.onclick = async () => {
            try {
                this.stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
                video.srcObject = this.stream;
                video.style.display = 'block';
                previewImg.style.display = 'none';
                this.container.querySelector('#placeholder-text').style.display = 'none';
                btnCapture.style.display = 'inline-block';
                btnCamera.style.display = 'none';
            } catch (err) {
                alert("Could not access camera. Please use file upload.");
            }
        };

        btnCapture.onclick = () => {
            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            canvas.getContext('2d').drawImage(video, 0, 0);
            const dataUrl = canvas.toDataURL('image/png');
            previewImg.src = dataUrl;
            previewImg.style.display = 'block';
            video.style.display = 'none';
            btnCapture.style.display = 'none';
            btnCamera.style.display = 'inline-block';
            btnSubmit.style.display = 'block';
            if (this.stream) {
                this.stream.getTracks().forEach(track => track.stop());
            }
        };

        btnUpload.onclick = () => fileInput.click();
        
        fileInput.onchange = (e) => {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = (re) => {
                    previewImg.src = re.target.result;
                    previewImg.style.display = 'block';
                    video.style.display = 'none';
                    this.container.querySelector('#placeholder-text').style.display = 'none';
                    btnSubmit.style.display = 'block';
                };
                reader.readAsDataURL(file);
            }
        };

        btnSubmit.onclick = () => this.submitAnalysis();
    }

    async submitAnalysis() {
        const previewImg = this.container.querySelector('#pest-preview-img');
        const loading = this.container.querySelector('#pest-loading');
        const resultDiv = this.container.querySelector('#pest-result');
        const btnSubmit = this.container.querySelector('#btn-submit');

        loading.style.display = 'block';
        resultDiv.style.display = 'none';
        btnSubmit.disabled = true;

        try {
            const blob = await (await fetch(previewImg.src)).blob();
            const formData = new FormData();
            formData.append('file', blob, 'capture.png');
            formData.append('farm_id', this.farmId);

            const response = await fetch('/farmer-input/pest/detect', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) throw new Error("Analysis failed.");

            const data = await response.json();
            this.displayResult(data);
        } catch (err) {
            resultDiv.innerHTML = `<p style="color: red;">Error: ${err.message}</p>`;
            resultDiv.style.display = 'block';
        } finally {
            loading.style.display = 'none';
            btnSubmit.disabled = false;
        }
    }

    displayResult(data) {
        const resultDiv = this.container.querySelector('#pest-result');
        const va = data.vision_analysis;
        const meta = data.preprocessing_metadata;
        const lz = meta.lesion_zones;

        const confClass = data.final_confidence_adjusted >= 0.7 ? 'badge-high' : 
                         (data.final_confidence_adjusted >= 0.5 ? 'badge-mod' : 'badge-low');
        
        const sevClass = va.urgency_level === 'immediate' ? 'sev-crit' : 
                        (va.affected_area_pct > 30 ? 'sev-severe' : 'sev-mod');

        resultDiv.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <span class="badge ${confClass}">${data.confidence_label}</span>
                <span class="badge ${sevClass}">${va.urgency_level.toUpperCase()}</span>
            </div>

            <h4 style="margin: 15px 0 5px 0; font-size: 1.2em;">
                <b>${va.pest_type.replace('_', ' ').toUpperCase()}</b> 
                <span style="color: #666; font-weight: normal; font-size: 0.9em;">(${va.pest_type})</span>
            </h4>

            <p style="font-size: 0.9em; color: #444; line-height: 1.4;">${va.visual_evidence}</p>

            <div style="background: #e8f5e9; padding: 10px; border-radius: 6px; margin: 10px 0;">
                <p style="margin: 0; font-weight: bold; color: #2e7d32;">📅 Act within ${data.vision_analysis.urgency_level === 'immediate' ? '1' : '3'} days</p>
            </div>

            <div style="display: flex; gap: 10px; margin-top: 15px;">
                <div class="treatment-card">
                    <h5 style="margin: 0 0 5px 0; color: #4caf50;">🌿 Organic</h5>
                    <p style="margin: 0;">${va.recommended_action}</p>
                </div>
                <div class="treatment-card">
                    <h5 style="margin: 0 0 5px 0; color: #f44336;">🧪 Chemical</h5>
                    <p style="margin: 0;">${data.similar_cases[0]?.chemical_treatment || "Consult local officer"}</p>
                </div>
            </div>

            ${!va.photo_quality_sufficient ? `
                <div style="margin-top: 15px; background: #fff8e1; border: 1px solid #ffc107; padding: 10px; border-radius: 6px; font-size: 0.85em;">
                    ⚠️ <b>Low Photo Quality:</b> ${va.retake_suggestion}
                </div>
            ` : ''}

            <p style="margin-top: 15px; font-size: 0.8em; color: #888;">
                <b>Pre-analysis:</b> ${meta.dominant_symptom.replace('_', ' ')} detected over ${meta.lesion_zones.total_affected_pct.toFixed(1)}% area.
            </p>

            ${data.final_confidence_adjusted < 0.5 ? `
                <p style="margin-top: 10px; color: #f44336; font-size: 0.85em; font-weight: bold;">⚠️ Low confidence — consult your local agriculture officer.</p>
            ` : ''}
        `;
        resultDiv.style.display = 'block';
    }
}

// Example usage:
// const pestWidget = new PestDetectionWidget('widget-container', 'FARM_123');
