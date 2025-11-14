"""Node for parsing asset URI."""
import time

from storage.schemas import AgentState, AssetURI


def parse_asset_node(state: AgentState) -> AgentState:
    """
    Parse the asset URI into components.

    Args:
        state: Current agent state

    Returns:
        Updated state with parsed asset
    """
    start = time.time()

    try:
        asset = AssetURI.from_uri(state.asset_uri)
        state.asset = asset

        # Track telemetry
        state.telemetry_data["parse_asset"] = {
            "asset_uri": state.asset_uri,
            "asset_type": asset.asset_type,
            "asset_descriptor": asset.asset_descriptor,
            "asset_domain": asset.asset_domain,
            "time_ms": (time.time() - start) * 1000
        }

    except ValueError as e:
        state.errors.append(f"Asset parsing error: {str(e)}")
        state.telemetry_data["parse_asset"] = {
            "error": str(e),
            "time_ms": (time.time() - start) * 1000
        }

    return state
