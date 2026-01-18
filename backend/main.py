import os
import json
import sys
import glob
import asyncio
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add root directory to path to import local modules
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

# Import real business logic
from ads_updater import ActionOrchestrator
from chatbot_client import get_chatbot_response, cleanup as chatbot_cleanup

app = FastAPI(title="Growth-OS Backend")

# CORS for Next.js - Allow all origins for dev/staging deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, you should restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = os.path.join(ROOT_DIR, "google_ads_data_llm")
CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "1411274245").replace("-", "")

# --- Pydantic Models ---

class ActionPayload(BaseModel):
    resource_type: str
    action_type: str
    resource_name: str
    new_suggested_value: Any
    old_value: Optional[Any] = None
    rationale: Optional[str] = None
    campaign_id: str
    # Add any other fields that ActionOrchestrator might need
    ad_group: Optional[str] = None
    keyword_text: Optional[str] = None
    match_type: Optional[str] = None
    location_id: Optional[str] = None
    device_type: Optional[str] = None
    asset_group: Optional[str] = None

class ChatMessage(BaseModel):
    message: str
    agent_type: str = "ads" # 'ads' or 'analytics'
    history: Optional[List[Dict[str, str]]] = None

# --- Helper Functions ---

def clean_json_string(s: str) -> str:
    """Helper to clean corrupted JSON tails like }box or ``` marks"""
    if not s: return "{}"
    s = s.strip()
    if s.startswith("```json"): s = s[7:]
    if s.startswith("```"): s = s[3:]
    if s.endswith("```"): s = s[:-3]
    
    # Find last valid closing brace
    last_brace = s.rfind("}")
    if last_brace != -1:
        s = s[:last_brace+1]
    return s

# --- Routes ---

@app.on_event("shutdown")
async def shutdown_event():
    await chatbot_cleanup()

@app.get("/")
def health_check():
    return {"status": "Growth-OS Backend Active", "version": "1.1.0"}

@app.get("/api/campaigns")
def get_campaigns():
    """Aggregates all campaign JSONs into a Dashboard-friendly format."""
    campaigns = []
    
    if not os.path.exists(DATA_DIR):
        return []

    for campaign_folder in os.listdir(DATA_DIR):
        folder_path = os.path.join(DATA_DIR, campaign_folder)
        if not os.path.isdir(folder_path):
            continue
            
        actions_files = glob.glob(os.path.join(folder_path, "actions_*.json"))
        if not actions_files:
            continue
            
        action_file = actions_files[0]
        
        try:
            with open(action_file, "r") as f:
                data = json.loads(clean_json_string(f.read()))
                
            c_id = data.get("campaign_id", "Unknown")
            c_name = data.get("campaign_name", campaign_folder)
            c_type = data.get("campaign_type", "SEARCH")
            
            # Enrich with metrics from enriched.json
            metrics = {"spend": 0, "roas": 0, "conversions": 0, "ctr": 0, "trend": [], "trend_status": "WAITING_FOR_SIGNALS"}
            detailed_metrics = {}
            
            def safe_float(v, default=0.0):
                if v is None: return default
                try: return float(v)
                except: return default

            status = "HEALTHY"
            actions_preview = ""
            optimization_mode = "DATA_COLLECTION"
            expected_impact = None
            strategy_summary = ""
            strategy_details = {
                "confidence": "LOW",
                "risk_level": "LOW",
                "primary_strategy": None,
                "secondary_strategy": None,
                "tertiary_strategy": None
            }

            enriched_files = glob.glob(os.path.join(folder_path, "*_enriched.json"))
            if enriched_files:
                try:
                    with open(enriched_files[0], "r") as ef:
                        edata = json.loads(clean_json_string(ef.read()))
                        # Try to find recent metrics in the payload
                        payload = edata.get("payload", {})
                        derived = payload.get("derived_metrics", {})
                        if derived:
                            metrics["spend"] = safe_float(derived.get("total_spend_usd"))
                            metrics["roas"] = safe_float(derived.get("roas"))
                            metrics["conversions"] = safe_float(derived.get("conversions"))
                            metrics["ctr"] = safe_float(derived.get("ctr_pct"))
                            detailed_metrics = {k: safe_float(v) for k, v in derived.items()}
                        
                        # Optimization Mode & Impact
                        strat = payload.get("strategy_recommendation", {})
                        if not strat:
                            # Fallback to root level if not in payload
                            strat = edata.get("strategy_recommendation", {})
                        
                        if strat:
                            optimization_mode = strat.get("optimization_mode", "BALANCED_OPTIMIZATION")
                            expected_impact = strat.get("expected_impact_30_days")
                            if strat.get("rationale_summary"):
                                strategy_summary = strat.get("rationale_summary")
                            
                            strategy_details.update({
                                "confidence": strat.get("confidence", "LOW"),
                                "risk_level": strat.get("risk_level", "LOW"),
                                "primary_strategy": strat.get("primary_strategy"),
                                "secondary_strategy": strat.get("secondary_strategy"),
                                "tertiary_strategy": strat.get("tertiary_strategy"),
                            })

                        # Extract trend data
                        daily = payload.get("segment_data_raw", {}).get("daily_performance", [])
                        if daily:
                            metrics["trend"] = [
                                {
                                    "date": d.get("segments.date", ""),
                                    "spend": safe_float(d.get("metrics.cost_micros", 0)) / 1_000_000,
                                    "conversions": safe_float(d.get("metrics.conversions", 0))
                                }
                                for d in daily
                            ][-7:]
                            metrics["trend_status"] = "LIVE_FEED" if len(metrics["trend"]) >= 3 else "STABILIZING"
                        else:
                            metrics["trend_status"] = "COLLECTING_SIGNALS"
                            # Fake trend for UI if no daily data (but marked as collecting)
                            metrics["trend"] = [
                                {"date": f"Day {i}", "spend": metrics["spend"]/(i+1) if metrics["spend"] else 0, "conversions": metrics["conversions"]/(i+1) if metrics["conversions"] else 0}
                                for i in range(7)
                            ]
                                    
                except Exception as e:
                    print(f"Error reading enriched data for {campaign_folder}: {e}")

            # Enhance actions with predictions from actions_*.json if available
            raw_actions = data.get("actions", [])
            actions_files = glob.glob(os.path.join(folder_path, "actions_*.json"))
            if actions_files:
                try:
                    with open(actions_files[0], "r") as af:
                        adata = json.loads(clean_json_string(af.read()))
                        # Merge predictions back to actions
                        pred_map = { a.get("resource_name"): a.get("prediction_30d") for a in adata.get("actions", []) }
                        for ra in raw_actions:
                            ra["prediction_30d"] = pred_map.get(ra.get("resource_name"), "Optimizing node performance.")
                except:
                    pass

            if raw_actions:
                count = len(raw_actions)
                actions_preview = f"{count} recommendations pending"
                status = optimization_mode # Use optimization mode as status

            campaigns.append({
                "id": c_id,
                "name": c_name,
                "type": c_type,
                "metrics": metrics,
                "detailed_metrics": detailed_metrics,
                "status": status,
                "optimization_mode": optimization_mode,
                "expected_impact": expected_impact,
                "strategy_details": strategy_details,
                "budget_health": payload.get("budget", {}),
                "signal_breakdown": {
                    "devices": payload.get("signals", {}).get("devices", {}),
                    "top_products": payload.get("signals", {}).get("products", {}).get("top_5_by_revenue", []),
                    "asset_groups": payload.get("signals", {}).get("pmax_asset_groups", []),
                    "demographics": payload.get("signals", {}).get("demographics", {})
                },
                "actions_preview": actions_preview,
                "pending_actions_count": len(raw_actions),
                "strategy_summary": strategy_summary or data.get("strategy", {}).get("rationale_summary", ""),
                "actions": raw_actions
            })
            
        except Exception as e:
            print(f"Error processing {campaign_folder}: {e}")
            continue

    return campaigns

@app.get("/api/campaign/{campaign_id}")
def get_campaign_detail(campaign_id: str):
    all_campaigns = get_campaigns()
    for c in all_campaigns:
        if c["id"] == campaign_id:
            return c
    raise HTTPException(status_code=404, detail="Campaign not found")

@app.post("/api/actions/apply")
async def apply_action(action: ActionPayload):
    """
    RECEIVES an action from the frontend and EXECUTES it via ActionOrchestrator.
    """
    try:
        # Instantiate the REAL orchestrator (dry_run=False if you want real changes)
        # Note: MCC_ID and other creds are loaded via env in ads_updater.py
        orchestrator = ActionOrchestrator(CUSTOMER_ID, dry_run=False)
        
        # Convert pydantic model to dict for execute_action (Pydantic V2)
        action_dict = action.model_dump()
        
        # Ensure new_value is set (execute_action expects 'new_value' or 'new_suggested_value')
        if "new_suggested_value" in action_dict and "new_value" not in action_dict:
            action_dict["new_value"] = action_dict["new_suggested_value"]
            
        result = orchestrator.execute_action(action_dict)
        
        if "❌" in result:
            return {"status": "error", "message": result}
        
        return {
            "status": "success", 
            "message": result, 
            "new_value": action_dict["new_value"]
        }
    except Exception as e:
        print(f"Error applying action: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/chat")
async def chat_interaction(chat: ChatMessage):
    """
    Connects the frontend chat to the REAL MCP Chat Agents.
    """
    try:
        # Convert history to LangChain messages if needed
        # (For now, get_chatbot_response handles simple string, but we can expand)
        response_text = await get_chatbot_response(chat.message, chat.agent_type)
        return {"response": response_text}
    except Exception as e:
        print(f"Error in chat: {e}")
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    import uvicorn
    # Use the PORT environment variable if provided by the host (like Render)
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
