import re

INTENTS = {
    "irrigation_advice":   ["pani", "irrigation", "water", "moisture", 
                            "sinchai", "नमी", "पानी"],
    "pest_disease":        ["pest", "disease", "insect", "kida", "bimari",
                            "fungus", "कीड़ा", "बीमारी"],
    "fertilizer_advice":   ["fertilizer", "khad", "urea", "npk", "nutrient",
                            "खाद", "उर्वरक"],
    "yield_prediction":    ["yield", "production", "harvest", "paidavar",
                            "उपज", "पैदावार"],
    "weather_query":       ["weather", "rain", "temperature", "mausam",
                            "बारिश", "मौसम"],
    "market_price":        ["price", "mandi", "rate", "bhav", "sell",
                            "बेचना", "मंडी", "भाव"],
    "govt_scheme":         ["scheme", "yojana", "subsidy", "loan", "sarkar",
                            "योजना", "सब्सिडी"],
    "general_farming":     []  # default fallback
}

def detect_intent(message: str) -> str:
    msg_lower = message.lower()
    
    for intent, keywords in INTENTS.items():
        if any(kw in msg_lower for kw in keywords):
            return intent
            
    return "general_farming"

def get_intent_instruction(intent: str) -> str:
    instructions = {
        "irrigation_advice": "Focus on soil moisture levels and weather. Give specific advice in litres or hours of irrigation.",
        "pest_disease": "Describe symptoms to watch for and organic/chemical treatment options with dosage.",
        "fertilizer_advice": "Give NPK recommendations based on crop stage and soil pH. Mention local brand names if possible.",
        "yield_prediction": "Use historical data and current conditions to give realistic yield estimate with reasoning.",
        "market_price": "Advise on best time to sell based on crop readiness and general price trends.",
        "general_farming": "Answer helpfully as an experienced Indian agronomist.",
        "govt_scheme": "Discuss relevant government schemes, but advise checking with local Krishi Kendra."
    }
    return instructions.get(intent, instructions["general_farming"])

def detect_language(message: str) -> str:
    # Very simple check for Devanagari block
    if re.search(r'[\u0900-\u097F]', message):
        return "hi"
    return "en"
