"""
models/profit_calculator.py
===========================
Financial engine for ROI, cost breakdown, and net profit projections.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict

log = logging.getLogger(__name__)

# Estimated average costs per hectare for common crops in India (INR)
# Includes components like seeds, fertilizers, pesticides, labor, and irrigation.
REGIONAL_AVERAGE_COSTS = {
    "wheat": 38000,
    "rice": 48000,
    "maize": 32000,
    "cotton": 58000,
    "mustard": 26000,
    "default": 40000
}


@dataclass
class ProfitAnalysis:
    """Consolidated financial analysis for a single crop."""
    crop: str
    total_cost: float
    gross_revenue: float
    net_profit: float
    roi_pct: float
    break_even_price: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "crop": self.crop,
            "total_cost": self.total_cost,
            "gross_revenue": self.gross_revenue,
            "net_profit": self.net_profit,
            "roi_pct": round(self.roi_pct, 2),
            "break_even_price": round(self.break_even_price, 2)
        }


class ProfitCalculator:
    """Calculates ROI and profit breakdowns using yield and price forecasts."""

    def calculate_profit(
        self,
        crop: str,
        predicted_yield_kg_ha: float,
        predicted_price_inr_quintal: float,
        user_cost_per_ha: float = None
    ) -> ProfitAnalysis:
        """
        Computes financial projections.
        
        Args:
            crop: Name of the crop.
            predicted_yield_kg_ha: Forecasted yield in kg per hectare.
            predicted_price_inr_quintal: Forecasted market price in INR per quintal (100kg).
            user_cost_per_ha: Optional custom cost provided by the farmer.
            
        Returns:
            A ProfitAnalysis dataclass containing the calculated metrics.
        """
        log.info("Calculating profit metrics for crop=%s", crop)

        # 1. Determine Cost per Hectare
        cost_per_ha = user_cost_per_ha if user_cost_per_ha else REGIONAL_AVERAGE_COSTS.get(crop.lower(), REGIONAL_AVERAGE_COSTS["default"])
        
        # 2. Compute Revenue
        # Formula: Gross Revenue = (Yield in kg / 100) * Price per quintal
        gross_revenue = (predicted_yield_kg_ha / 100.0) * predicted_price_inr_quintal
        
        # 3. Compute Net Profit
        net_profit = gross_revenue - cost_per_ha
        
        # 4. Compute ROI (Return on Investment)
        roi_pct = (net_profit / cost_per_ha) * 100.0 if cost_per_ha > 0 else 0.0
        
        # 5. Compute Break-even Price (INR per quintal)
        # Price at which Net Profit = 0
        # (Yield / 100) * Price = Cost => Price = (Cost * 100) / Yield
        break_even_price = (cost_per_ha * 100.0) / max(predicted_yield_kg_ha, 1.0)

        log.debug(
            "Profit Summary for %s: Revenue=%.2f, Cost=%.2f, ROI=%.2f%%", 
            crop, gross_revenue, cost_per_ha, roi_pct
        )

        return ProfitAnalysis(
            crop=crop,
            total_cost=float(cost_per_ha),
            gross_revenue=float(gross_revenue),
            net_profit=float(net_profit),
            roi_pct=float(roi_pct),
            break_even_price=float(break_even_price)
        )
