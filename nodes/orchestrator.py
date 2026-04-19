from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional

from langgraph.graph import StateGraph, END
from state import AgriState
from nodes.historical_db_node import historical_db_node
from nodes.forecaster_node import forecaster_node
from nodes.vision_node import vision_node
from nodes.recommendation_node import recommendation_node

log = logging.getLogger(__name__)

def create_agrisense_graph():
    """
    Creates and compiles the AgriSense LangGraph workflow.
    
    Workflow:
    1. historical_db_node: Fetch historical yield and pest data.
    2. forecaster_node: Generate irrigation and yield forecasts.
    3. vision_node: Analyze satellite imagery and detect pests.
    4. recommendation_node: Synthesize final advisory.
    """
    # Initialize StateGraph with AgriState dataclass
    workflow = StateGraph(AgriState)

    # Add nodes
    workflow.add_node("fetch_history", historical_db_node)
    workflow.add_node("forecast", forecaster_node)
    workflow.add_node("vision_analysis", vision_node)
    workflow.add_node("recommendation", recommendation_node)

    # Define edges
    workflow.set_entry_point("fetch_history")
    
    workflow.add_edge("fetch_history", "forecast")
    workflow.add_edge("forecast", "vision_analysis")
    workflow.add_edge("vision_analysis", "recommendation")
    workflow.add_edge("recommendation", END)

    return workflow.compile()

class AgriSensePipeline:
    """
    High-level interface for running the AgriSense LangGraph pipeline.
    """
    def __init__(self):
        self.graph = create_agrisense_graph()
        log.info("AgriSense LangGraph pipeline initialized.")

    async def run(
        self,
        farm_id: str,
        satellite_data: Optional[Any] = None,
        aligned_df: Optional[Any] = None,
        feature_vector: Optional[Any] = None,
    ) -> AgriState:
        """
        Executes the full pipeline for a given farm.

        Returns the final AgriState (or dict if LangGraph returns dict).
        """
        initial_state = AgriState(
            farm_id=farm_id,
            satellite=satellite_data,
            aligned_df=aligned_df,
            feature_vector=feature_vector,
        )
        
        log.info("Running pipeline for farm_id=%s", farm_id)
        final_state = await self.graph.ainvoke(initial_state)
        return final_state


if __name__ == "__main__":
    import asyncio
    
    async def main():
        pipeline = AgriSensePipeline()
        # Test with dummy data (no satellite image — vision_node will degrade gracefully)
        result = await pipeline.run("test-farm-001")
        errors = result.errors if hasattr(result, "errors") else result.get("errors", [])
        advisory = result.full_advisory if hasattr(result, "full_advisory") else result.get("full_advisory")
        print(f"Pipeline finished with {len(errors)} errors.")
        if advisory:
            print("Advisory generated successfully.")
        else:
            print("No advisory produced (likely missing GEMINI_API_KEY or satellite data).")
            
    asyncio.run(main())
