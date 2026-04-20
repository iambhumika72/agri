// src/types/api.ts

export interface IrrigationDay {
  date: string;
  predicted_soil_moisture: number;
  irrigation_needed: boolean;
  recommended_volume_liters: number;
  confidence: number;
}

export interface IrrigationSchedule {
  farm_id: string;
  schedule: IrrigationDay[];
  total_water_needed_liters: number;
  next_critical_date: string | null;
  confidence: number;
  model_used: string;
  generated_at: string;
}

export interface YieldForecast {
  farm_id: string;
  crop_type: string;
  predicted_yield: number;
  yield_lower: number;
  yield_upper: number;
  forecast_date: string;
  confidence_interval: number;
  trend_component: number;
  seasonal_component: number;
  key_drivers: string[];
  model_used: string;
}

export interface VisionAnalysis {
  farm_id: string;
  image_path: string;
  health_score: number;
  crop_health_status: string;
  pest_detected: boolean;
  pest_type: string;
  pest_confidence: number;
  affected_area_pct: number;
  growth_stage_visual: string;
  stress_pattern: string;
  urgency_level: string;
  visual_evidence: string;
  recommended_action: string;
  analysis_timestamp: string;
  gemini_latency_ms: number;
  token_count: number;
}

export interface PestCase {
  pest_name: string;
  symptoms: string;
  affected_crops: string[];
  organic_treatment: string;
  chemical_treatment: string;
  severity_level: string;
  treatment_window_days: number;
  source: string;
}

export interface TreatmentPlan {
  priority_score: number;
  act_within_hours: number;
  organic_first: boolean;
  treatment_steps: string[];
  estimated_cost_inr: string;
}

export interface PlantPestResult {
  farm_id: string | null;
  image_filename: string;
  preprocessing_metadata: Record<string, any>;
  vision_analysis: VisionAnalysis;
  similar_cases: PestCase[];
  treatment_plan: TreatmentPlan;
  confidence_label: string;
  final_confidence_adjusted: number;
  error: string | null;
  analysis_timestamp: string;
}

export interface YieldRecord {
  record_id: string;
  farm_id: string;
  crop_id: string;
  crop_name: string | null;
  season: string;
  year: number;
  yield_kg_per_hectare: number;
  harvest_date: string;
  notes: string | null;
}

export interface SoilRecord {
  soil_id: string;
  farm_id: string;
  recorded_date: string;
  ph_level: number | null;
  nitrogen_ppm: number | null;
  phosphorus_ppm: number | null;
  potassium_ppm: number | null;
  organic_matter_pct: number | null;
  moisture_pct: number | null;
}

export interface PestRecord {
  pest_id: string;
  farm_id: string;
  crop_id: string;
  pest_name: string;
  severity: number;
  affected_area_pct: number;
  detected_date: string;
  resolved_date: string | null;
  treatment_applied: string | null;
}

export interface FarmSummary {
  farm_id: string;
  [key: string]: any;
}

export interface HealthStatus {
  status: string;
  timestamp: string;
  components: Record<string, string>;
  uptime_seconds: number;
  version: string;
  environment: string;
}

export interface RecommendationResponse {
  farm_id: string;
  crop_type: string;
  full_advisory: string;
  irrigation_advice: string;
  yield_advice: string;
  pest_advice: string;
  sms_message: string;
  model_used: string;
  confidence: number;
  generated_at: string;
}

export interface AlertSummary {
  farm_id: string;
  active_critical: number;
  total_alerts: number;
  recent_alerts: any[];
}
