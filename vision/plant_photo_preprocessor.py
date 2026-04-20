"""
vision/plant_photo_preprocessor.py
==================================
OpenCV-based preprocessing for farmer-uploaded close-up plant photos.
Cleans images and extracts visual features before Gemini analysis.
"""

import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Tuple, Optional

import cv2
import numpy as np

log = logging.getLogger(__name__)

class PlantPhotoPreprocessor:
    def __init__(self):
        log.info("PlantPhotoPreprocessor initialized")

    def load_and_validate(self, image_bytes: bytes, filename: str) -> np.ndarray:
        """Decode bytes to OpenCV BGR image and validate metadata."""
        ext = filename.split(".")[-1].lower()
        if ext not in ["jpg", "jpeg", "png", "webp"]:
            raise ValueError(f"Unsupported format: {ext}")

        size_mb = len(image_bytes) / (1024 * 1024)
        if size_mb < 0.001 or size_mb > 20.0:
            raise ValueError("File too small/large (1KB-20MB allowed)")

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        if img is None:
            raise ValueError("Failed to decode image.")

        h, w = img.shape[:2]
        if h < 224 or w < 224:
            raise ValueError("Image too low resolution for analysis (min 224x224)")

        mean_val = np.mean(img)
        if mean_val < 10 or mean_val > 245:
            raise ValueError("Image appears blank — please retake photo")

        log.info(f"Loaded {filename}: {w}x{h}, {size_mb:.2f}MB")
        return img

    def preprocess(self, image: np.ndarray) -> np.ndarray:
        """Apply color correction, sharpening, and contrast enhancement."""
        # Step 1: Auto white balance (Gray World Assumption)
        img_float = image.astype(np.float32)
        avg_b = np.mean(img_float[:, :, 0])
        avg_g = np.mean(img_float[:, :, 1])
        avg_r = np.mean(img_float[:, :, 2])
        avg_all = (avg_b + avg_g + avg_r) / 3.0
        
        img_float[:, :, 0] *= (avg_all / avg_b)
        img_float[:, :, 1] *= (avg_all / avg_g)
        img_float[:, :, 2] *= (avg_all / avg_r)
        image = np.clip(img_float, 0, 255).astype(np.uint8)

        # Step 2: Sharpen
        kernel = cv2.GaussianBlur(image, (0, 0), 3)
        image = cv2.addWeighted(image, 1.5, kernel, -0.5, 0)

        # Step 3: CLAHE contrast enhancement
        lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        cl = clahe.apply(l)
        limg = cv2.merge((cl, a, b))
        image = cv2.cvtColor(limg, cv2.COLOR_LAB2BGR)

        # Step 4: Resize to 1024x1024 max with padding
        h, w = image.shape[:2]
        scale = 1024 / max(h, w)
        if scale < 1.0:
            new_w, new_h = int(w * scale), int(h * scale)
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)
        
        # Padding
        h, w = image.shape[:2]
        top = (1024 - h) // 2
        bottom = 1024 - h - top
        left = (1024 - w) // 2
        right = 1024 - w - left
        image = cv2.copyMakeBorder(image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=[255, 255, 255])

        log.info("Preprocessing steps completed (WB, Sharpen, CLAHE, Resize)")
        return image

    def detect_leaf_region(self, image: np.ndarray) -> Tuple[np.ndarray, dict]:
        """Isolate main plant/leaf from background."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        # Green-to-yellow mask
        lower = np.array([25, 40, 40])
        upper = np.array([85, 255, 255])
        mask = cv2.inRange(hsv, lower, upper)
        
        kernel = np.ones((15, 15), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=2)
        
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours or cv2.contourArea(max(contours, key=cv2.contourArea)) < (image.size * 0.05 / 3):
            log.warning("No clear plant detected — using full image")
            return image, {"leaf_detected": False}
        
        best_cnt = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(best_cnt)
        
        # Add padding
        pad = 10
        y1, y2 = max(0, y - pad), min(image.shape[0], y + h + pad)
        x1, x2 = max(0, x - pad), min(image.shape[1], x + w + pad)
        
        cropped = image[y1:y2, x1:x2]
        metadata = {
            "leaf_detected": True,
            "leaf_area_pct": (cv2.contourArea(best_cnt) / (image.shape[0] * image.shape[1])) * 100,
            "bounding_box": {"x": x, "y": y, "w": w, "h": h},
            "contour_count": len(contours)
        }
        return cropped, metadata

    def detect_lesion_zones(self, image: np.ndarray) -> dict:
        """Find brown spots, white patches, and necrotic zones."""
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        total_pixels = image.shape[0] * image.shape[1]
        
        # Brown/Yellow
        mask_by = cv2.inRange(hsv, np.array([10, 60, 60]), np.array([30, 255, 255]))
        # White
        mask_white = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 40, 255]))
        # Necrotic (Dark)
        mask_nec = cv2.inRange(hsv, np.array([0, 0, 0]), np.array([180, 60, 80]))
        
        res = {
            "brown_yellow_pct": (cv2.countNonZero(mask_by) / total_pixels) * 100,
            "white_patch_pct": (cv2.countNonZero(mask_white) / total_pixels) * 100,
            "necrotic_pct": (cv2.countNonZero(mask_nec) / total_pixels) * 100,
        }
        res["total_affected_pct"] = res["brown_yellow_pct"] + res["white_patch_pct"] + res["necrotic_pct"]
        
        # Combined mask for blob count
        combined = cv2.bitwise_or(mask_by, mask_white)
        combined = cv2.bitwise_or(combined, mask_nec)
        conts, _ = cv2.findContours(combined, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        res["lesion_blob_count"] = len([c for c in conts if cv2.contourArea(c) > 10])
        
        # Dominant symptom
        max_pct = max(res["brown_yellow_pct"], res["white_patch_pct"], res["necrotic_pct"])
        if max_pct < 2.0:
            res["dominant_symptom"] = "none"
        elif max_pct == res["brown_yellow_pct"]:
            res["dominant_symptom"] = "brown_yellow_spots"
        elif max_pct == res["white_patch_pct"]:
            res["dominant_symptom"] = "white_patches"
        else:
            res["dominant_symptom"] = "necrotic_lesions"
            
        return res

    def save_processed_image(self, image: np.ndarray, farm_id: str, filename: str) -> str:
        """Save to local storage and return path."""
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_name = f"{farm_id}_{ts}_{filename}"
        out_dir = Path("preprocessing/composites/user_uploads")
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / out_name
        cv2.imwrite(str(out_path), image)
        return str(out_path)

    def run_full_pipeline(self, image_bytes: bytes, filename: str, farm_id: str) -> Tuple[str, dict]:
        """Execute full preprocessing flow."""
        metadata = {
            "original_size": (0, 0),
            "processed_size": (0, 0),
            "leaf_detected": False,
            "leaf_area_pct": 0.0,
            "lesion_zones": {},
            "dominant_symptom": "none"
        }
        
        try:
            # 1. Load
            img = self.load_and_validate(image_bytes, filename)
            metadata["original_size"] = (img.shape[1], img.shape[0])
            
            # 2. Preprocess
            img = self.preprocess(img)
            metadata["processed_size"] = (img.shape[1], img.shape[0])
            
            # 3. Leaf Detection
            leaf_img, leaf_meta = self.detect_leaf_region(img)
            metadata.update(leaf_meta)
            
            # 4. Lesion Analysis
            lesion_res = self.detect_lesion_zones(leaf_img)
            metadata["lesion_zones"] = lesion_res
            metadata["dominant_symptom"] = lesion_res["dominant_symptom"]
            
            # 5. Save
            saved_path = self.save_processed_image(img, farm_id, filename)
            return saved_path, metadata
            
        except Exception as e:
            log.error(f"Preprocessing failed at some step: {e}")
            # Fallback: save raw if possible
            try:
                nparr = np.frombuffer(image_bytes, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                if img is None:
                    return "", metadata
                saved_path = self.save_processed_image(img, farm_id, filename)
                return saved_path, metadata
            except Exception:
                return "", metadata

if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    if len(sys.argv) > 1:
        path = sys.argv[1]
        with open(path, "rb") as f:
            b = f.read()
        proc = PlantPhotoPreprocessor()
        spath, meta = proc.run_full_pipeline(b, os.path.basename(path), "test_farm")
        print(f"Saved to: {spath}")
        print(f"Metadata: {meta}")
