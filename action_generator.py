import os
import json
import time
import re
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables
load_dotenv()

# ==============================================================================
# CONFIGURATION
# ==============================================================================

INPUT_DIR = os.getenv("DATA_DIR", "google_ads_data_llm")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")

# ==============================================================================
# UTILS
# ==============================================================================

def load_json(path: str) -> Any:
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def sanitize_filename(name: str) -> str:
    """Safely sanitize a string for use as a filename."""
    return re.sub(r"[^\w\-_\.]", "_", name)[:120]

def clean_strategy_name(strategy_str: str) -> str:
    """Removes leading numbering (e.g., '1. ') from the strategy name."""
    if not strategy_str: return ""
    parts = strategy_str.split(". ", 1)
    return parts[1] if len(parts) > 1 else strategy_str

def resolve_resource_ids(actions: List[Dict], resource_map: Dict[str, str]) -> List[Dict]:
    """
    Post-processing step to convert Short IDs (ID_X) from the LLM 
    back into actual Google Ads Resource Names (customers/123/...)
    """
    resolved_actions = []
    for action in actions:
        # 1. Resolve Primary Resource Name
        raw_rn = action.get("resource_name", "N/A")
        if raw_rn in resource_map:
            action["resource_name"] = resource_map[raw_rn]
        
        # 2. Resolve Secondary Fields (Campaign, AdGroup, AssetGroup pointers)
        for field in ["campaign", "ad_group", "asset_group"]:
            val = action.get(field)
            if val and val in resource_map:
                action[field] = resource_map[val]
                
        resolved_actions.append(action)
    return resolved_actions

# ==============================================================================
# LLM ACTION GENERATION (TIER 3 CORE)
# ==============================================================================

def get_allowed_actions_for_type(campaign_type: str) -> str:
    """Returns valid actions and strict prohibitions for the campaign type."""
    
    common_exclusions = (
        "   - `ADD_PLACEMENT_EXCLUSION`: REQUIRES 'campaign' (Use Campaign ID), 'url' (str)\n"
        "   - `ADD_TOPIC_EXCLUSION`: REQUIRES 'campaign' (Use Campaign ID), 'topic_constant_id' (str)"
    )

    if campaign_type == "PERFORMANCE_MAX":
        return f"""
### ALLOWED ACTIONS (STRICTLY FOR PERFORMANCE_MAX)
1. **ASSET_GROUP**
   - `UPDATE_STATUS`: "ENABLED" | "PAUSED"

2. **ASSET_GROUP_ASSET** (Creative)
   - `PAUSE_ASSET`: REQUIRES "resource_name". Only if performance_label="LOW".
   - `ENABLE_ASSET`: REQUIRES "resource_name".

3. **ASSET_GROUP_LISTING_GROUP_FILTER** (Retail/Feed)
   - `EXCLUDE_PRODUCT_BY_ID`: REQUIRES "asset_group", "product_item_id"
   - `EXCLUDE_PRODUCT_BY_BRAND`: REQUIRES "asset_group", "brand"

4. **CAMPAIGN**
   - `UPDATE_STATUS`: "PAUSED" (Do NOT enable unless explicitly requested)
   - `SET_TARGET_ROAS`: [float]
   - `SET_TARGET_CPA`: [int micros]

5. **CAMPAIGN_BUDGET**
   - `SET_AMOUNT_MICROS`: [int micros]

### PROHIBITED ACTIONS (DO NOT GENERATE)
- NO Keywords (AdGroupCriterion).
- NO Device/Location Modifiers (CampaignCriterion).
- NO AdGroup changes (Do not exist).
"""

    elif campaign_type == "VIDEO":
        return f"""
### ALLOWED ACTIONS (STRICTLY FOR VIDEO)
1. **AD_GROUP**
   - `SET_CPV_BID`: [int micros] (Use this for bidding)
   - `UPDATE_STATUS`: "ENABLED" | "PAUSED"

2. **CAMPAIGN**
   - `UPDATE_STATUS`: "PAUSED"
   - `SET_TARGET_CPA`: [int micros] (Only if tCPA strategy)

3. **CAMPAIGN_CRITERION**
   {common_exclusions}
   - `ADD_NEGATIVE_KEYWORD`: "campaign", "keyword_text" (Valid for Video)
   - `SET_DEVICE_BID_MODIFIER`: "campaign", "device_type", "new_suggested_value" (Check if allowed for subtype)

4. **CAMPAIGN_BUDGET**
   - `SET_AMOUNT_MICROS`: [int micros]

### PROHIBITED ACTIONS
- NO `SET_CPC_BID` (Video uses CPV or tCPA).
- NO `SET_TARGET_ROAS` on Campaign (Usually invalid for standard Video Action).
"""

    elif campaign_type == "DISPLAY":
        return f"""
### ALLOWED ACTIONS (STRICTLY FOR DISPLAY)
1. **AD_GROUP**
   - `SET_CPC_BID`: [int micros]
   - `UPDATE_STATUS`: "ENABLED" | "PAUSED"

2. **CAMPAIGN_CRITERION**
   {common_exclusions}
   - `SET_DEVICE_BID_MODIFIER`
   - `SET_LOCATION_BID_MODIFIER`
   - `SET_AD_SCHEDULE`

3. **CAMPAIGN**
   - `SET_TARGET_ROAS`: [float]
   - `SET_TARGET_CPA`: [int micros]
   
4. **CAMPAIGN_BUDGET**
   - `SET_AMOUNT_MICROS`: [int micros]

### PROHIBITED ACTIONS
- Avoid Search-centric Keyword actions unless explicitly targeting "Content Keywords".
"""

    else: # SEARCH (Default)
        return f"""
### ALLOWED ACTIONS (STRICTLY FOR SEARCH)
1. **AD_GROUP_CRITERION (Keywords)**
   - `UPDATE_STATUS`: "ENABLED" | "PAUSED"
   - `SET_CPC_BID`: [int micros]
   - `ADD_NEGATIVE`: "ad_group", "keyword_text", "match_type"

2. **CAMPAIGN_CRITERION (Targeting)**
   - `SET_DEVICE_BID_MODIFIER`
   - `SET_LOCATION_BID_MODIFIER`
   - `ADD_NEGATIVE_KEYWORD`
   - `SET_AD_SCHEDULE`
   {common_exclusions}

3. **AD_GROUP**
   - `SET_CPC_BID`
   - `SET_TARGET_CPA`
   - `UPDATE_STATUS`

4. **CAMPAIGN**
   - `SET_TARGET_ROAS`
   - `SET_TARGET_CPA`
   - `UPDATE_STATUS`

5. **CAMPAIGN_BUDGET**
   - `SET_AMOUNT_MICROS`
"""

def generate_actions_with_llm(markdown_context: str, strategy_recommendation: Dict, llm: ChatGroq, campaign_type: str = "SEARCH") -> List[Dict]:
    """
    Asks the LLM to analyze the markdown performance context and strategy 
    to generate a list of structured Google Ads API actions using SHORT IDs.
    """
    
    system_prompt = (
        "You are a Google Ads API specialist. Analyze performance data and strategies to "
        "generate precise, structured actions. Use IDs (ID_X) from the tables."
    )

    strategy_json = json.dumps(strategy_recommendation, indent=2)
    allowed_actions_block = get_allowed_actions_for_type(campaign_type)

    user_prompt = f"""
### RECOMMENDED STRATEGY
{strategy_json}

### GOALS:
1. Identify high-impact elements (e.g., low-ROAS keywords, budget-limited campaigns, poor-CTR ads).
2. Correlate data across segments (e.g., if Mobile spend is high but ROAS is low, adjust device modifiers).
3. Generate an actionable list of changes. Prioritize the top highest-spend/highest-waste items.

### RESOURCE IDENTIFICATION RULES (CRITICAL):
The Markdown tables contain a column for IDs (e.g., `ID_1`, `ID_50`).
**YOU MUST USE THIS SHORT ID (e.g. "ID_50") EXACTLY AS IT APPEARS in the resource_name field.**
Do NOT try to guess the real resource name. Just return the `ID_X` string.
- If you are updating a Keyword, `resource_name` = "ID_of_Keyword"
- If you are adding a Negative to a Campaign, `resource_name` = "ID_of_Campaign"

{allowed_actions_block}

### MARKDOWN PERFORMANCE CONTEXT:
{markdown_context}

### INSTRUCTIONS & GUARDRAILS (CRITICAL):
1. **Resource Consistency**: Ensure the `resource_type` matches the `resource_name` (ID_X) you are targeting. 
   - If ID_X refers to an Ad Group (ID_119 in your table), use `resource_type`: "AD_GROUP".
   - Do NOT use `AD_GROUP_CRITERION` to pause an `AD_GROUP`.

2. **Placement Exclusions**: When using `ADD_PLACEMENT_EXCLUSION`, you MUST use the key `"url"` (str) for the placement URL. Do NOT put the URL in `new_suggested_value`.

3. **Video Campaign Rules**:
   - **Bidding Strategy**: Check the `Bidding_Strategy` in the table. 
     - If it is `TARGET_CPV`, you **CANNOT** use `SET_TARGET_ROAS`.
     - Suggest `SET_CPV_BID` on the Ad Group instead.
   - **Targeting Limitations**: Many Video campaigns do NOT allow campaign-level targeting mutates (e.g., `SET_DEVICE_BID_MODIFIER`). If a Video campaign is failing to convert, prioritize pausing the `AD_GROUP` or adjusting the `BUDGET` rather than device modifiers.

4. **Bidding Logic**:
   - Only suggest `SET_TARGET_ROAS` if the campaign is ALREADY using a `tROAS` strategy (Maximize Conversion Value with a target).
   - Only suggest `SET_TARGET_CPA` if the campaign is using a `tCPA` strategy.

### JSON OBJECT FORMAT
{{
  "resource_type": "... (e.g. CAMPAIGN | AD_GROUP | AD_GROUP_CRITERION)",
  "resource_name": "ID_X",
  "action_type": "... (e.g. SET_TARGET_ROAS | UPDATE_STATUS)",
  "new_suggested_value": 0.0,
  "rationale": "...",
  "prediction_30d": "...",
  "campaign": "ID_X", (ID of the parent campaign if required)
  "ad_group": "ID_Y", (ID of the parent ad_group if required)
  "url": "...", (REQUIRED for ADD_PLACEMENT_EXCLUSION)
  "keyword_text": "...", (REQUIRED for ADD_NEGATIVE)
  "match_type": "..." (REQUIRED for ADD_NEGATIVE)
}}

RETURN ONLY A JSON LIST OF OBJECTS:
"""
    
    try:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = llm.invoke(messages)
        content = response.content.strip()
        
        if "[" in content and "]" in content:
            content = content[content.find("["):content.rfind("]")+1]
        elif "```json" in content:
            content = content.split("```json")[-1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[-1].split("```")[0].strip()
            
        actions = json.loads(content)
        if not isinstance(actions, list):
            raise ValueError("LLM did not return a list.")

        return actions
        
    except Exception as e:
        print(f"  Error invoking LLM: {e}")
        return []

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

def main():
    print("=" * 60)
    print("ACTION GENERATION ENGINE")
    print("=" * 60)
    
    if not GROQ_API_KEY:
        print("ERROR: GROQ_API_KEY environment variable is not set.")
        return

    os.environ["GROQ_API_KEY"] = GROQ_API_KEY
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.1)
    
    if not os.path.exists(INPUT_DIR):
        print(f"Error: Input directory '{INPUT_DIR}' not found.")
        return

    campaign_dirs = [d for d in os.listdir(INPUT_DIR) if os.path.isdir(os.path.join(INPUT_DIR, d))]
    
    for camp_dir in campaign_dirs:
        full_dir_path = os.path.join(INPUT_DIR, camp_dir)
        
        enriched_file = None
        strategy_file = None
        markdown_file = None
        resource_map_file = None
        
        for f in os.listdir(full_dir_path):
            if f.endswith("_enriched.json"):
                enriched_file = os.path.join(full_dir_path, f)
            elif f.startswith("strategy_") and f.endswith(".json"):
                strategy_file = os.path.join(full_dir_path, f)
            elif f.startswith("llm_context_") and f.endswith(".md"):
                markdown_file = os.path.join(full_dir_path, f)
            elif f == "resource_map.json":
                resource_map_file = os.path.join(full_dir_path, f)
                
        if not enriched_file or not strategy_file or not markdown_file or not resource_map_file:
            print(f"Skipping {camp_dir}: Missing required files.")
            continue
            
        print(f"\nProcessing Campaign: {camp_dir}")
        
        try:
            # 1. Load Data
            enriched_data = load_json(enriched_file)
            strategy_data = load_json(strategy_file)
            resource_map = load_json(resource_map_file)
            with open(markdown_file, "r") as f:
                markdown_context = f.read()
            
            payload = enriched_data.get("payload", {})
            campaign_name = payload.get("campaign_name", camp_dir)
            campaign_id = payload.get("campaign_id", "Unknown")
            
            # Robust extraction of Campaign Type from Markdown header (Source of Truth)
            # Format: * **Campaign Type:** PERFORMANCE_MAX
            match = re.search(r"\* \*\*Campaign Type:\*\* (\w+)", markdown_context)
            if match:
                campaign_type = match.group(1)
            else:
                # Fallback to payload
                campaign_type = payload.get("advertising_channel_type", "SEARCH")
                if "PERFORMANCE_MAX" in campaign_type: campaign_type = "PERFORMANCE_MAX"
                elif "VIDEO" in campaign_type: campaign_type = "VIDEO"
                elif "DISPLAY" in campaign_type: campaign_type = "DISPLAY"
                elif "SHOPPING" in campaign_type: campaign_type = "SHOPPING"
                
            print(f"  Campaign Type: {campaign_type}")

            # 3. LLM Action Generation
            raw_actions = generate_actions_with_llm(markdown_context, strategy_data, llm, campaign_type)
            
            # 4. Resolve IDs back to real Resource Names
            final_actions = resolve_resource_ids(raw_actions, resource_map)
            
            print(f"  Generated {len(final_actions)} structured actions.")
            
            # 5. Save Final Output
            final_output = {
                "campaign_id": campaign_id,
                "campaign_name": campaign_name,
                "campaign_type": campaign_type,
                "strategy": strategy_data,
                "actions": final_actions,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            
            output_filename = f"actions_{sanitize_filename(campaign_name)}.json"
            output_path = os.path.join(full_dir_path, output_filename)
            save_json(final_output, output_path)
            print(f"  Saved Actions: {output_filename}")
            
            time.sleep(1)
            
        except Exception as e:
            print(f"  Error processing {camp_dir}: {e}")

if __name__ == "__main__":
    main()
