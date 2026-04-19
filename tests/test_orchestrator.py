import pytest
import asyncio
from nodes.orchestrator import AgriSensePipeline
from state import AgriState

@pytest.mark.asyncio
async def test_pipeline_run():
    pipeline = AgriSensePipeline()
    # Using a fake farm_id
    farm_id = "test-farm-orchestrator"
    
    # We don't provide real satellite data or aligned_df, so nodes should fallback
    # to degraded modes gracefully.
    final_state = await pipeline.run(farm_id)
    
    # LangGraph may return state as a dict if not using a specific class-based schema
    # Or it might be the object. Let's be flexible.
    if isinstance(final_state, dict):
        assert final_state["farm_id"] == farm_id
        assert "full_advisory" in final_state
    else:
        assert final_state.farm_id == farm_id
        assert final_state.full_advisory is not None
    
    print("Pipeline run successful.")
    
if __name__ == "__main__":
    asyncio.run(test_pipeline_run())
