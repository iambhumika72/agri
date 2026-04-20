from __future__ import annotations

"""
generative/prompt_templates.py
================================
Structured prompt templates for AgriSense LLM recommendation synthesis.
All templates follow a Role → Context → Task → Format pattern.
"""

from string import Template
from typing import Optional

# ---------------------------------------------------------------------------
# Irrigation Recommendation Prompt
# ---------------------------------------------------------------------------

IRRIGATION_SYSTEM = (
    "You are AgriSense, an AI agronomist advisor for small-scale Indian farmers. "
    "You speak clearly, practically, and in simple language a farmer can act on today. "
    "Always give specific, actionable advice. Never give generic platitudes."
)

IRRIGATION_TEMPLATE = Template(
    "## Farm Report\n"
    "$farm_context\n\n"
    "## Irrigation Forecast\n"
    "Next critical irrigation date: $next_critical_date\n"
    "Total water needed (7 days): $total_water_liters liters\n"
    "Soil moisture forecast (day-by-day): $moisture_forecast\n"
    "Irrigation model confidence: $confidence%\n\n"
    "## Your Task\n"
    "Based on the farm data above, provide an irrigation recommendation with:\n"
    "1. **Immediate Action** (what to do today or tomorrow)\n"
    "2. **7-Day Schedule** (which days to irrigate and how much, in simple terms)\n"
    "3. **Water Conservation Tip** (one practical tip for this season)\n"
    "4. **Warning** (if any critical risk is detected)\n\n"
    "Keep your response under 200 words. Use bullet points. "
    "Address the farmer directly as 'you'."
)

# ---------------------------------------------------------------------------
# Yield Forecast Prompt
# ---------------------------------------------------------------------------

YIELD_SYSTEM = (
    "You are AgriSense, an AI crop advisor. "
    "You help farmers understand their yield forecast and take action to improve it. "
    "Be encouraging but honest. Base advice strictly on the data provided."
)

YIELD_TEMPLATE = Template(
    "## Farm Report\n"
    "$farm_context\n\n"
    "## Yield Forecast\n"
    "Predicted yield: $predicted_yield kg/hectare\n"
    "Confidence range: $yield_lower – $yield_upper kg/hectare\n"
    "Key drivers: $key_drivers\n"
    "Yield trend vs last season: $yield_trend\n\n"
    "## Your Task\n"
    "Explain this yield forecast to the farmer:\n"
    "1. **What the forecast means** (in simple terms)\n"
    "2. **Top factor affecting yield** (and what to do about it)\n"
    "3. **One action to improve yield** before harvest\n\n"
    "Keep response under 150 words. No jargon."
)

# ---------------------------------------------------------------------------
# Pest Alert Prompt
# ---------------------------------------------------------------------------

PEST_SYSTEM = (
    "You are AgriSense, an AI plant disease and pest specialist. "
    "You identify crop threats early and tell farmers exactly what to do. "
    "Prioritize low-cost, locally available solutions first."
)

PEST_TEMPLATE = Template(
    "## Farm Report\n"
    "$farm_context\n\n"
    "## Pest & Disease Risk\n"
    "Pest risk score: $pest_risk_score / 1.0\n"
    "Satellite-detected likely cause: $likely_cause\n"
    "Stressed zone: $stressed_zone_pct% of field\n"
    "Crop growth stage: $growth_stage\n\n"
    "## Your Task\n"
    "Provide a pest/disease alert if risk > 0.3, or a reassurance if risk is low:\n"
    "1. **Risk Level** (low / medium / high)\n"
    "2. **Most Likely Threat** (based on season and satellite data)\n"
    "3. **Immediate Action** (inspect, spray, or monitor — be specific)\n"
    "4. **Prevention** (for the next 2 weeks)\n\n"
    "Keep response under 150 words."
)

# ---------------------------------------------------------------------------
# General Advisory Prompt (combines all signals)
# ---------------------------------------------------------------------------

FULL_ADVISORY_SYSTEM = (
    "You are AgriSense, a trusted AI farming advisor for small-scale farmers in India. "
    "You have access to satellite imagery analysis, soil sensors, weather forecasts, "
    "and historical farm data. Your job is to synthesize all signals into one clear, "
    "priority-ordered action plan that the farmer can execute today. "
    "Be concise, warm, and empowering. Write as if you're talking to a farmer face-to-face."
)

FULL_ADVISORY_TEMPLATE = Template(
    "## Complete Farm Analysis — $farm_id\n"
    "Crop: $crop_type | Season: $season | Growth Stage: $growth_stage\n\n"
    "### Field Conditions\n"
    "$farm_context\n\n"
    "### Irrigation (7-Day Outlook)\n"
    "- Next irrigation needed: $next_critical_date\n"
    "- Water required: $total_water_liters liters\n"
    "- Irrigation score: $irrigation_score/10\n\n"
    "### Yield Outlook\n"
    "- Predicted: $predicted_yield kg/ha (range: $yield_lower–$yield_upper)\n"
    "- Trend: $yield_trend\n\n"
    "### Pest & Disease\n"
    "- Risk score: $pest_risk_score/1.0\n"
    "- Satellite finding: $likely_cause ($stressed_zone_pct% stressed)\n\n"
    "## Your Task\n"
    "Write a complete farm advisory with these sections:\n"
    "1. **Today's Priority Actions** (top 3, numbered)\n"
    "2. **This Week's Plan** (irrigation + monitoring schedule)\n"
    "3. **Warnings** (any critical issues)\n"
    "4. **Good News** (what's going well)\n\n"
    "Max 250 words. Direct, practical, no jargon."
)

# ---------------------------------------------------------------------------
# SMS/Short message prompt (for Twilio delivery)
# ---------------------------------------------------------------------------

SMS_TEMPLATE = Template(
    "Farm $farm_id Alert:\n"
    "- Irrigation: $irrigation_action\n"
    "- Yield: $yield_summary\n"
    "- Pest risk: $pest_level\n"
    "Reply HELP for full report."
)

# ---------------------------------------------------------------------------
# Profit Boost Advisor Prompt
# ---------------------------------------------------------------------------

PROFIT_BOOST_SYSTEM = (
    "You are a Senior Agricultural Economist and Farm Business Advisor. "
    "Your goal is to help Indian farmers maximize their ROI and net profit. "
    "You analyze field capability, yield forecasts, and market trends to provide "
    "strategic advice on crop selection and profit optimization."
)

PROFIT_BOOST_TEMPLATE = Template(
    "## Field Capability Profile\n"
    "Overall Score: $capability_score / 1.0\n"
    "Soil health (pH: $ph, OM: $om%)\n"
    "Climate suitability: $climate_suitability / 1.0\n"
    "Pest pressure history: $pest_pressure / 1.0\n\n"
    "## Financial Projections for Preferred Crop ($crop)\n"
    "Predicted Modal Price: ₹$predicted_price / quintal\n"
    "Predicted Yield: $predicted_yield kg/ha\n"
    "Estimated Cost: ₹$total_cost\n"
    "Net Profit: ₹$net_profit\n"
    "ROI: $roi%\n\n"
    "## Your Task\n"
    "Based on the data above, provide a 'Profit Boost' strategy:\n"
    "1. **Crop Suitability Analysis**: Briefly explain why $crop is a good (or risky) choice for this field.\n"
    "2. **Specific ROI Boosters**: Suggest 3 concrete actions to increase profit (e.g., precise nutrient management, intercropping, or timing harvest).\n"
    "3. **Market Strategy**: Suggest the best time or market to sell based on the price trend.\n"
    "4. **Alternative recommendation**: If another crop would be more profitable for this field capability, suggest it.\n\n"
    "Keep response under 250 words. Be practical and clear."
)


def build_irrigation_prompt(farm_context: str, irrigation_data: dict) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for irrigation recommendation."""
    user = IRRIGATION_TEMPLATE.substitute(
        farm_context=farm_context,
        next_critical_date=irrigation_data.get("next_critical_date", "Not determined"),
        total_water_liters=irrigation_data.get("total_water_needed_liters", 0),
        moisture_forecast=irrigation_data.get("moisture_forecast", "N/A"),
        confidence=round(irrigation_data.get("confidence", 0) * 100, 1),
    )
    return IRRIGATION_SYSTEM, user


def build_yield_prompt(farm_context: str, yield_data: dict) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for yield advisory."""
    trend = "📈 improving" if yield_data.get("trend_component", 0) > 0 else "📉 declining"
    user = YIELD_TEMPLATE.substitute(
        farm_context=farm_context,
        predicted_yield=round(yield_data.get("predicted_yield", 0), 1),
        yield_lower=round(yield_data.get("yield_lower", 0), 1),
        yield_upper=round(yield_data.get("yield_upper", 0), 1),
        key_drivers=", ".join(yield_data.get("key_drivers", ["N/A"])),
        yield_trend=trend,
    )
    return YIELD_SYSTEM, user


def build_pest_prompt(farm_context: str, pest_data: dict) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for pest alert."""
    user = PEST_TEMPLATE.substitute(
        farm_context=farm_context,
        pest_risk_score=round(pest_data.get("pest_risk_score", 0), 2),
        likely_cause=pest_data.get("likely_cause", "unknown"),
        stressed_zone_pct=round(pest_data.get("stressed_zone_pct", 0), 1),
        growth_stage=pest_data.get("growth_stage", "unknown"),
    )
    return PEST_SYSTEM, user


def build_full_advisory_prompt(
    farm_context: str,
    farm_id: str,
    crop_type: str,
    season: str,
    growth_stage: str,
    irrigation_data: dict,
    yield_data: dict,
    pest_data: dict,
    vision_analysis: Optional[dict] = None,
) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for the complete farm advisory."""
    trend = "improving" if yield_data.get("trend_component", 0) > 0 else "declining"
    vision = vision_analysis or {}
    user = FULL_ADVISORY_TEMPLATE.substitute(
        farm_id=farm_id,
        crop_type=crop_type,
        season=season,
        growth_stage=growth_stage,
        farm_context=farm_context,
        next_critical_date=str(irrigation_data.get("next_critical_date", "N/A")),
        total_water_liters=round(irrigation_data.get("total_water_needed_liters", 0), 1),
        irrigation_score=round(irrigation_data.get("irrigation_need_score", 0), 1),
        predicted_yield=round(yield_data.get("predicted_yield", 0), 1),
        yield_lower=round(yield_data.get("yield_lower", 0), 1),
        yield_upper=round(yield_data.get("yield_upper", 0), 1),
        yield_trend=trend,
        pest_risk_score=round(pest_data.get("pest_risk_score", 0), 2),
        likely_cause=vision.get("likely_cause", pest_data.get("likely_cause", "unknown")),
        stressed_zone_pct=round(vision.get("stressed_zone_pct", 0), 1),
    )
    return FULL_ADVISORY_SYSTEM, user


def build_profit_boost_prompt(
    profile: dict, 
    analysis: dict
) -> tuple[str, str]:
    """Returns (system_prompt, user_prompt) for profit boost advisory."""
    user = PROFIT_BOOST_TEMPLATE.substitute(
        capability_score=round(profile.get("overall_capability_score", 0), 2),
        ph=profile.get("ph_level", 6.5),
        om=profile.get("organic_matter", 2.0),
        climate_suitability=round(profile.get("temp_suitability", 0.5), 2),
        pest_pressure=round(profile.get("historical_pest_pressure", 0), 2),
        crop=analysis.get("crop", "Unknown"),
        predicted_price=round(analysis.get("predicted_price", 0), 2),
        predicted_yield=round(analysis.get("predicted_yield", 0), 1),
        total_cost=round(analysis.get("total_cost", 0), 2),
        net_profit=round(analysis.get("net_profit", 0), 2),
        roi=round(analysis.get("roi_pct", 0), 2),
    )
    return PROFIT_BOOST_SYSTEM, user


if __name__ == "__main__":
    system, user = build_irrigation_prompt(
        farm_context="Farm F1 | Wheat | Kharif | 45 days since planting",
        irrigation_data={
            "next_critical_date": "2024-06-15",
            "total_water_needed_liters": 12000,
            "moisture_forecast": "22%, 21%, 20%, 19%, 18%, 18%, 17%",
            "confidence": 0.82,
        }
    )
    print("SYSTEM:", system[:80], "...")
    print("USER:", user)
