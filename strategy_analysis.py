import os
import json
import time
from typing import Dict, Any, List
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage

# Load environment variables
load_dotenv()

# === CONFIGURATION ===
INPUT_DIR = os.getenv("DATA_DIR", "google_ads_data_llm")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is required")

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data: Any, path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# === CAMPAIGN TYPE INFERENCE ===
def infer_campaign_type(payload: Dict) -> str:
    """
    Infers the campaign type without relying on raw_data.json.
    Prioritizes explicit API field if present.
    """
    # 0. EXPLICIT API FIELD
    explicit_type = payload.get("advertising_channel_type")
    if explicit_type:
        if explicit_type == "PERFORMANCE_MAX": return "PERFORMANCE_MAX"
        if explicit_type == "SHOPPING": return "SHOPPING"
        if explicit_type == "VIDEO": return "VIDEO"
        if explicit_type == "DISPLAY": return "DISPLAY"
        if explicit_type == "SEARCH": return "SEARCH"

    name = payload.get("campaign_name", "").lower()
    raw_data = payload.get("segment_data_raw", {})
    
    # 1. Check for PMax specific signals
    if raw_data.get("asset_group_performance") or "pmax" in name or "performance max" in name:
        return "PERFORMANCE_MAX"
        
    # 2. Check for Video specific signals
    if raw_data.get("video_performance") or "video" in name or "youtube" in name:
        return "VIDEO"

    # 3. Check for Search specific signals
    if raw_data.get("keyword_performance") or "search" in name or "brand" in name:
        return "SEARCH"
    
    if raw_data.get("product_performance") and not raw_data.get("asset_group_performance"):
        return "SHOPPING"
    if raw_data.get("keyword_performance"):
        return "SEARCH"
    if raw_data.get("placement_performance_detailed") and not raw_data.get("keyword_performance"):
        return "DISPLAY"
    
    if "shopping" in name:
        return "SHOPPING"
    if "display" in name:
        return "DISPLAY"
        
    return "SEARCH"


# === LLM STRATEGY LOGIC ===
def select_strategy_with_llm(
    campaign_data: Dict, 
    campaign_type: str,
    markdown_context: str,
    llm: ChatGroq
) -> Dict[str, Any]:
    """
    Select optimization strategies using LLM.
    
    Args:
        campaign_data: The enriched campaign payload (metadata only)
        campaign_type: PERFORMANCE_MAX, SEARCH, SHOPPING, or DISPLAY
        markdown_context: The MD file content with detailed performance tables
        llm: The LLM instance
    """
    # Build campaign type specific guidance
    # Build campaign type specific guidance
    type_guidance = {
        "PERFORMANCE_MAX": (
            "Focus: Asset Groups, Products, and Budget. PMax is a 'black box'. "
            "FORBIDDEN: Keyword actions, Device/Geo modifiers, Ad Scheduling (mostly invalid). "
            "PRIORITIZE: Pausing/Enabling Asset Groups, Product Exclusions, and Budget changes."
        ),
        "SEARCH": (
            "Focus: Quality Score, Device/Geo/Audience precision, and Search Term waste. "
            "VALID: All Standard Actions (Keywords, Negatives, Bids, Modifiers)."
        ),
        "SHOPPING": (
            "Focus: Product-level performance, Feed health, and ROAS scaling. "
            "VALID: Product Bids/Exclusions, Negatives. "
            "FORBIDDEN: Keywords (unless Query sculpting)."
        ),
        "DISPLAY": (
            "Focus: Placement waste, Creative engagement (CTR), and Audience efficiency. "
            "VALID: Placement/Topic Exclusions, Audience Bids/Exclusions."
        ),
        "VIDEO": (
            "Focus: CPV efficiency, View rate, and Budget scaling. "
            "FORBIDDEN: SET_CPC_BID (Use SET_CPV_BID), Campaign Keywords on non-Action subtypes. "
            "VALID: Placement Exclusions, Device Modifiers (some subtypes), Audiences."
        )
    }.get(campaign_type, "Standard optimization approach.")

    system_prompt = (
        "You are a Senior Google Ads Growth Architect. Your goal is to analyze the provided campaign data "
        "holistically and recommend the most effective optimization strategy. "
        "Use your expert judgment to weigh conflicting signals (e.g., high spend vs low ROAS) "
        "and prioritize actions that drive the biggest impact for the specific campaign type."
    )

    user_prompt = f"""
### CAMPAIGN ARCHITECTURE
- **Campaign Type**: {campaign_type}
- **Type-Specific Focus**: {type_guidance}

### AVAILABLE STRATEGY OPTIONS (Select the best fit)
1. **Maximize Impressions**: Best for stalled or brand new campaigns needing initial traffic.
2. **Maximize Clicks**: Best when traffic volume is the bottleneck and IS Loss is high.
3. **Maximize Conversions**: Best for stable campaigns needing more volume at similar efficiency.
4. **Maximize ROAS**: Best for high-performers exceeding targets that should be scaled aggressively.
5. **Improve CTR**: Best when ads are showing but not driving engagement (Low CTR).
6. **Improve Quality Score**: (Search Only) Best when high CPCs or Rank Loss are hindering performance.
7. **Improve Conversion Rate**: Best when traffic is good but not converting (wasteful spend).
8. **Budget Optimization**: Best when the campaign is profitable but limited by budget.
9. **Reduce Waste**: Best when there is significant spend on non-converting segments (terms, placements, devices).
10. **Feed Optimization (PMax)**: Best when product availability or diversity is the issue.

### ANALYTICAL THOUGHT PROCESS
- **Holistic Review**: Don't just look at one metric. Consider the interplay between Spend, ROAS, Impression Share, and Conversions.
- **Identify the Bottleneck**: Is it Traffic (Impressions/Clicks)? Efficiency (CTR/CVR)? or Scalability (Budget)?
- **Campaign Maturity**: Treat a brand new campaign differently (needs traffic) than a mature one (needs efficiency).
- **Profitability vs. Growth**: If ROAS is high, lean towards Scaling (Budget/Max ROAS). If ROAS is low, lean towards Efficiency (Reduce Waste/Improve CVR).
- **Signal Strength**: Look for strong deviations in the segment data (Device, Geo, Day of Week) to justify your choice.

### OUTPUT FORMAT (JSON only, no explanation outside JSON)
{{
  "primary_strategy": "X. Strategy Name",
  "secondary_strategy": "Y. Strategy Name" or null,
  "tertiary_strategy": "Z. Strategy Name" or null,
  "confidence": "LOW | MEDIUM | HIGH",
  "optimization_mode": "AGGRESSIVE_SCALING | CONSERVATIVE_CLEANUP | BALANCED_OPTIMIZATION | DATA_COLLECTION",
  "rationale_summary": "Explain based on SPECIFIC signals (e.g. 'Mobile CPA is 3x higher than desktop' or '56% IS lost to budget').",
  "risk_level": "LOW | MEDIUM | HIGH",
  "expected_impact_30_days": {{
    "primary_metric_target": "ROAS | Conversions | CTR | CPA | Spend",
    "primary_metric_value": 0.0,
    "secondary_metric_target": "metric" or null,
    "secondary_metric_value": 0.0,
    "secondary_metric_unit": "USD | % | x" or null
  }}
}}

### CAMPAIGN AUDIT DATA (Analyze the tables carefully)
{markdown_context}
"""
    
    try:
        messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_prompt)]
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # Robust JSON extraction
        try:
            start_index = content.find('{')
            end_index = content.rfind('}')
            if start_index != -1 and end_index != -1:
                json_str = content[start_index:end_index+1]
                strategy = json.loads(json_str)
                
                # --- Post-process to prevent PMax/Search strategy hallucinations ---
                if campaign_type == "PERFORMANCE_MAX":
                    strategy_keys = ["primary_strategy", "secondary_strategy", "tertiary_strategy"]
                    for k in strategy_keys:
                        val = strategy.get(k)
                        if val and "Quality Score" in val:
                            strategy[k] = "10. Feed Optimization (PMax)"
                            if k == "primary_strategy":
                                strategy["rationale_summary"] += " [Note: Strategy adjusted from Quality Score to Feed Optimization for PMax compatibility]"

                return strategy
            else:
                raise ValueError("No JSON object found in response")
        except json.JSONDecodeError:
             # Fallback: try to clean markdown if simple extraction failed
             clean_content = content.replace("```json", "").replace("```", "")
             strategy = json.loads(clean_content)
             
             if campaign_type == "PERFORMANCE_MAX":
                strategy_keys = ["primary_strategy", "secondary_strategy", "tertiary_strategy"]
                for k in strategy_keys:
                    val = strategy.get(k)
                    if val and "Quality Score" in val:
                        strategy[k] = "10. Feed Optimization (PMax)"
             return strategy
    except Exception as e:
        return { "primary_strategy": "Manual Review", "optimization_mode": "ERROR", "rationale_summary": str(e) }

# === MAIN EXECUTION ===
def main():
    print("=" * 60)
    print("STRATEGY ANALYSIS WITH CAMPAIGN TYPE AWARENESS")
    print("=" * 60)
    
    llm = ChatGroq(model="llama-3.3-70b-versatile", temperature=0.0, api_key=GROQ_API_KEY)
    
    campaign_files = []
    for root, _, files in os.walk(INPUT_DIR):
        for file in files:
            if file.endswith("_enriched.json"):
                campaign_files.append(os.path.join(root, file))
    
    if not campaign_files:
        print("No campaigns found.")
        return

    # Process Each Campaign
    for file_path in campaign_files:
        try:
            data = load_json(file_path)
            payload = data.get("payload", {})
            name = payload.get("campaign_name", "Unknown")
            campaign_dir = os.path.dirname(file_path)
            
            # Infer campaign type from payload
            campaign_type = infer_campaign_type(payload)
            
            # Load Markdown Context
            clean_name = name.replace(" ", "_").replace("/", "_").replace("|", "_")
            # Try specific named file first, then generic fallback
            md_path = os.path.join(campaign_dir, f"llm_context_{clean_name}.md")
            if not os.path.exists(md_path):
                md_path = os.path.join(campaign_dir, "llm_context.md")
            
            markdown_context = ""
            if os.path.exists(md_path):
                with open(md_path, "r", encoding="utf-8") as f:
                    markdown_context = f.read()
            else:
                print(f"  Warning: No markdown context found at {md_path}")
            
            print(f"\nProcessing: {name}")
            print(f"  Type: {campaign_type}")

            strategy = select_strategy_with_llm(payload, campaign_type, markdown_context, llm)
            print(f"  Result: {strategy.get('primary_strategy')}")
            
            # Save results
            payload["strategy_recommendation"] = strategy
            save_json({"payload": payload}, file_path)
            
            safe_name = name.replace(" ", "_").replace("/", "_").replace("|", "_")
            save_json(strategy, os.path.join(os.path.dirname(file_path), f"strategy_{safe_name}.json"))
            
            time.sleep(1) # Rate limit
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    main()