import os
import json
import re
from typing import Dict, Any, List, Optional

# ==============================================================================
# CONFIGURATION
# ==============================================================================

INPUT_DIR = os.getenv("DATA_DIR", "google_ads_data_llm")

# ==============================================================================
# UTILS
# ==============================================================================

def get_deep(d: Dict, path: str, default: Any = None) -> Any:
    """Gets a value from a dict regardless of whether it is flat (dot-notated) or nested."""
    if path in d: return d[path]
    parts = path.split('.')
    curr = d
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            return default
    return curr

def safe_float(val: Any) -> float:
    if val is None: return 0.0
    try:
        if isinstance(val, str): val = val.replace(',', '')
        return float(val)
    except (ValueError, TypeError):
        return 0.0

def micros_to_curr(micros: Any) -> float:
    return round(safe_float(micros) / 1_000_000, 2)

def clean_md(val: Any) -> str:
    """Escapes pipes for Markdown tables."""
    if val is None: return "N/A"
    return str(val).replace("|", "\\|").replace("\n", " ").strip()

def infer_campaign_type(payload: Dict) -> str:
    """
    Robustly infers campaign type based on explicit API field first,
    then data 'fingerprints', and naming conventions last.
    """
    # 0. EXPLICIT API FIELD (Best Source)
    explicit_type = payload.get("advertising_channel_type")
    if explicit_type:
        if explicit_type == "PERFORMANCE_MAX": return "PERFORMANCE_MAX"
        if explicit_type == "SHOPPING": return "SHOPPING"
        if explicit_type == "VIDEO": return "VIDEO"
        if explicit_type == "DISPLAY": return "DISPLAY"
        if explicit_type == "SEARCH": return "SEARCH"

    name = payload.get("campaign_name", "").lower()
    raw_data = payload.get("segment_data_raw", {})
    signals = payload.get("signals", {})

    # 1. PERFORMANCE MAX (PMAX)
    if (raw_data.get("asset_group_performance") or 
        raw_data.get("listing_group_filters") or 
        signals.get("pmax_asset_groups")):
        return "PERFORMANCE_MAX"

    # 2. SHOPPING
    if (raw_data.get("product_performance") or 
        raw_data.get("shopping_performance_view")):
        return "SHOPPING"

    # 3. VIDEO
    if (raw_data.get("video_performance") or "video" in name or "youtube" in name):
        return "VIDEO"

    # 4. SEARCH (Specific signals)
    if (raw_data.get("keyword_performance") or 
        raw_data.get("search_terms")):
        # Only return SEARCH if it's not already identified as something else
        return "SEARCH"

    # 5. DISPLAY
    if (raw_data.get("placement_performance_detailed") or 
        raw_data.get("topic_performance_view")):
        return "DISPLAY"

    # NAMING FALLBACKS
    if re.search(r'\bpmax\b|\bperformance\s?max\b', name): return "PERFORMANCE_MAX"
    if re.search(r'\bshopping\b|\bshop\b|\bfeed\b', name): return "SHOPPING"
    if re.search(r'\bdisplay\b|\bgdn\b|\bimage\b', name): return "DISPLAY"
    if re.search(r'\bvideo\b|\byoutube\b|\byt\b', name): return "VIDEO"
    if re.search(r'\bsearch\b|\bsem\b|\bbrand\b|\bgeneric\b', name): return "SEARCH"

    return "SEARCH"

# ==============================================================================
# THE METADATA-FIRST PREPARATION ENGINE
# ==============================================================================

class DataPreparer:
    def __init__(self):
        self.resource_map = {} 
        self.id_counter = 0
        self.qs_lookup = {}
        self.mod_lookup = {} # Key: "DEVICE:MOBILE", "LOC:2840", "SCHED:MONDAY:10"
        self.shared_set_keywords = {} # Mapping SharedSet RN -> List of keywords
        self.asset_lookup = {} # Mapping Asset RN -> Content/Metadata

    def _register_rn(self, rn: str) -> str:
        """Converts Long Resource Names -> Short ID_X for LLM brevity."""
        if not rn or not isinstance(rn, str):
            return "N/A"
        
        # Allow real resource names OR our virtual composite IDs
        if "customers/" not in rn and "COMPOSITE:" not in rn:
            return "N/A"
        for sid, name in self.resource_map.items():
            if name == rn: return sid
        
        sid = f"ID_{self.id_counter}"
        self.resource_map[sid] = rn
        self.id_counter += 1
        return sid

    def _extract_metrics(self, item: Dict) -> Dict:
        """Standard metrics extractor. Handles both nested 'metrics' block and flat keys."""
        cost = safe_float(get_deep(item, "metrics.cost_micros")) / 1e6
        conv = safe_float(get_deep(item, "metrics.conversions"))
        val = safe_float(get_deep(item, "metrics.conversions_value"))
        clicks = safe_float(get_deep(item, "metrics.clicks"))
        impr = safe_float(get_deep(item, "metrics.impressions"))
        
        cpa = round(cost / conv, 2) if conv > 0 else 0.0
        roas = round(val / cost, 2) if cost > 0 else 0.0
        
        return {
            "cost": cost, "conv": conv, "value": val, 
            "impr": impr, "clicks": clicks, "cpa": cpa, "roas": roas,
            "is_dead_weight": (cost == 0 and impr == 0)
        }

    # --------------------------------------------------------------------------
    # SPECIALIZED SEGMENT PROCESSORS
    # --------------------------------------------------------------------------

    def process_keywords(self, key: str, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            m = self._extract_metrics(item)
            if m['is_dead_weight']: continue 
            
            rn = get_deep(item, "ad_group_criterion.resource_name")
            ag_rn = get_deep(item, "ad_group.resource_name")
            txt = clean_md(get_deep(item, "ad_group_criterion.keyword.text"))
            match = clean_md(get_deep(item, "ad_group_criterion.keyword.match_type"))
            bid = micros_to_curr(get_deep(item, "ad_group_criterion.cpc_bid_micros"))
            status = get_deep(item, "ad_group_criterion.status")
            
            # Enriched QS from lookup
            qs_info = self.qs_lookup.get(rn, {})
            qs = qs_info.get("score", "N/A")
            qs_details = f"{qs} (CR:{qs_info.get('creative','?')}/LP:{qs_info.get('landing','?')}/CTR:{qs_info.get('ctr','?')})" if qs != "N/A" else "N/A"

            # Impression Share
            is_val = get_deep(item, "metrics.search_impression_share", "N/A")
            if isinstance(is_val, float): is_val = f"{is_val*100:.1f}%"

            # Estimates for better bidding decisions
            first_pg = micros_to_curr(get_deep(item, "ad_group_criterion.position_estimates.first_page_cpc_micros", 0))

            sid = self._register_rn(rn)
            aid = self._register_rn(ag_rn)
            rows.append(f"| {sid} | {aid} | {txt} | {match} | ${bid} | ${first_pg} | {status} | {qs_details} | {is_val} | ${m['cost']:.2f} | {m['conv']} |")

        if not rows: return ""
        header = "#### KEYWORDS (ResourceType: AD_GROUP_CRITERION)\n"
        header += "| Keyword_ID | AdGroup_ID | Keyword_Text | Match_Type | Curr_Bid | 1stPg_Est | Status | Quality_Score | Impression_Share | Cost | Conv |\n"
        header += "|---|---|---|---|---|---|---|---|---|---|---|\n"
        return header + "\n".join(rows[:50]) + "\n\n"

    def process_search_terms(self, key: str, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            m = self._extract_metrics(item)
            if m['is_dead_weight']: continue
            
            term = clean_md(get_deep(item, "search_term_view.search_term"))
            status = clean_md(get_deep(item, "search_term_view.status"))
            kw_txt = clean_md(get_deep(item, "segments.keyword.info.text", "N/A"))
            
            # Link to the actual keyword ID
            kw_rn = get_deep(item, "segments.keyword.ad_group_criterion")
            kw_id = self._register_rn(kw_rn) if kw_rn else "N/A"
            
            ag_rn = get_deep(item, "ad_group.resource_name")
            c_rn = get_deep(item, "campaign.resource_name")
            
            aid = self._register_rn(ag_rn)
            cid = self._register_rn(c_rn)
            rows.append(f"| {term} | {aid} | {kw_id} | {status} | {kw_txt} | ${m['cost']:.2f} | {m['conv']} |")

        if not rows: return ""
        header = "#### SEARCH TERMS (ResourceType: SEARCH_TERM_VIEW)\n"
        header += "| Search_Term | AdGroup_ID | Triggering_Keyword_ID | Match_Status | Keyword_Text | Cost | Conv |\n"
        header += "|---|---|---|---|---|---|---|\n"
        return header + "\n".join(rows[:40]) + "\n\n"

    def process_listing_group_filters(self, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            # STRUCTURAL: KEEP ALL
            rn = get_deep(item, "asset_group_listing_group_filter.resource_name")
            ag_rn = get_deep(item, "asset_group.resource_name")
            type_ = get_deep(item, "asset_group_listing_group_filter.type_")
            
            # Extract tree identity
            case_val = "All/Root"
            props = ["product_type.value", "product_brand.value", "product_item_id.value", "product_condition.condition"]
            for p in props:
                val = get_deep(item, f"asset_group_listing_group_filter.case_value.{p}")
                if val:
                    case_val = f"{p.split('.')[1]}: {val}"
                    break
            
            sid = self._register_rn(rn)
            aid = self._register_rn(ag_rn)
            rows.append(f"| {sid} | {aid} | {case_val} | {type_} |")
            
        header = "#### PMAX LISTING FILTERS\n"
        header += "| ListingFilter_ID | AssetGroup_ID | Target_Value | Filter_Type |\n"
        header += "|---|---|---|---|\n"
        return header + "\n".join(rows) + "\n\n"

    def process_negatives(self, items: List[Dict], title: str) -> str:
        if not items: return ""
        rows = []
        for item in items:
            # Choose correct keys based on whether it's campaign or ad group level
            rn = get_deep(item, "campaign_criterion.resource_name") or get_deep(item, "ad_group_criterion.resource_name")
            txt = clean_md(get_deep(item, "campaign_criterion.keyword.text") or get_deep(item, "ad_group_criterion.keyword.text"))
            mtch = clean_md(get_deep(item, "campaign_criterion.keyword.match_type") or get_deep(item, "ad_group_criterion.keyword.match_type"))
            
            sid = self._register_rn(rn)
            rows.append(f"| {sid} | {txt} | {mtch} |")
            
        header = f"#### EXISTING {title.upper()}\n| Criterion_ID | Text | Match |\n|---|---|---|\n"
        return header + "\n".join(rows[:50]) + "\n\n"

    def process_demographics(self, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            m = self._extract_metrics(item)
            # Demographics structural even if small spend
            rn = get_deep(item, "ad_group_criterion.resource_name")
            ag_rn = get_deep(item, "ad_group.resource_name")
            
            lbl = "Unknown"
            prefixes = ["age_range", "gender", "income_range"]
            for p in prefixes:
                val = get_deep(item, f"ad_group_criterion.{p}.type_")
                if val:
                    lbl = val
                    break
            
            sid = self._register_rn(rn)
            aid = self._register_rn(ag_rn)
            rows.append(f"| {sid} | {aid} | {lbl} | ${m['cost']:.1f} | {m['conv']} | {int(m['impr'])} |")
            
        header = "#### DEMOGRAPHICS (AGE/GENDER/INCOME)\n| Demographic_ID | AdGroup_ID | Segment | Cost | Conv | Impr |\n|---|---|---|---|---|---|\n"
        return header + "\n".join(rows) + "\n\n"

    def process_products(self, key: str, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            m = self._extract_metrics(item)
            if m['is_dead_weight']: continue
            
            pid = clean_md(get_deep(item, "segments.product_item_id"))
            title = clean_md(get_deep(item, "segments.product_title", "Product"))
            brand = clean_md(get_deep(item, "segments.product_brand", "N/A"))
            type_l1 = clean_md(get_deep(item, "segments.product_type_l1", "N/A"))
            
            ag_rn = get_deep(item, "ad_group.resource_name")
            aid = self._register_rn(ag_rn)
            
            rows.append(f"| {pid} | {aid} | {title} | {brand} | {type_l1} | ${m['cost']:.1f} | {m['conv']} | {m['roas']} |")

        if not rows: return ""
        header = "#### PRODUCT PERFORMANCE\n"
        header += "| Product_ID | AdGroup_ID | Title | Brand | TypeL1 | Cost | Conv | ROAS |\n"
        header += "|---|---|---|---|---|---|---|---|\n"
        return header + "\n".join(rows[:50]) + "\n\n"

    def process_generic_perf(self, key: str, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            m = self._extract_metrics(item)
            if m['is_dead_weight'] and "daily" not in key: continue
            
            # Label & Action Metadata
            lbl = "Item"
            mod_key = None
            details = "N/A"
            
            if "device" in key: 
                dev = clean_md(get_deep(item, "segments.device"))
                lbl = dev
                mod_key = f"DEVICE:{dev}"
                details = f"Device:{dev}"
            elif "geo" in key: 
                loc = get_deep(item, "geographic_view.country_criterion_id")
                typ = get_deep(item, "geographic_view.location_type")
                lbl = f"Loc:{loc} ({typ})"
                mod_key = f"LOC:{loc}"
                details = f"ID:{loc} | Type:{typ}"
            elif "schedule" in key: 
                day = get_deep(item, "segments.day_of_week")
                hr = get_deep(item, "segments.hour")
                lbl = f"{day}@{hr}"
                mod_key = f"SCHED:{day}:{hr}"
                details = f"Day:{day} | Hr:{hr}"
            elif "placement" in key: 
                lbl = get_deep(item, "group_placement_view.placement")
                details = f"Type:{get_deep(item, 'group_placement_view.placement_type')}"
            elif "daily" in key: lbl = get_deep(item, "segments.date")
            elif "ad_group" in key: lbl = get_deep(item, "ad_group.name")
            elif "asset_group" in key: lbl = get_deep(item, "asset_group.name")
            elif "ad_performance" in key: 
                type_ = get_deep(item, 'ad_group_ad.ad.type')
                ad_id = get_deep(item, 'ad_group_ad.ad.id')
                lbl = f"{type_} ({ad_id})"
                details = f"Ad_ID:{ad_id}"
                # For Ads, we might want to see the text
                headlines = get_deep(item, "ad_group_ad.ad.responsive_search_ad.headlines", [])
                if headlines:
                    h_txt = " | ".join([h.get('text', '') for h in headlines[:3]])
                    details += f" | Text:{h_txt}..."

            # ID Resolution (The "Target" for an Action)
            rn = "N/A"
            # 1. Match with an existing modifier (Highest Priority for SET)
            if mod_key and mod_key in self.mod_lookup:
                rn = self.mod_lookup[mod_key]
            
            # 2. Heuristic fallback (Composite ID for segments, or Criterion -> AdGroup -> Campaign)
            if rn == "N/A":
                # If it's a segment row (Device, Loc, Sched) that we can target, create a unique virtual ID
                if mod_key:
                    c_rn = get_deep(item, "campaign.resource_name")
                    if c_rn:
                        rn = f"COMPOSITE:{c_rn}:{mod_key}"
                
                # General fallback
                if rn == "N/A":
                    for candidate in ["ad_group_criterion", "campaign_criterion", "ad_group", "ad_group_ad", "asset_group", "campaign"]:
                        val = get_deep(item, f"{candidate}.resource_name")
                        if val:
                            rn = val
                            break
            
            sid = self._register_rn(rn)
            cpc = round(m['cost'] / m['clicks'], 2) if m['clicks'] > 0 else 0.0
            rows.append(f"| {sid} | {lbl} | {details} | ${m['cost']:.2f} | {int(m['clicks'])} | {int(m['impr'])} | ${cpc} | {m['conv']} | {m['roas']} |")

        if not rows: return ""
        t = key.replace("_", " ").upper().replace("PERFORMANCE", "").strip()
        header = f"#### {t} PERFORMANCE\n"
        # Use more descriptive ID header based on what we resolved
        id_header = "Target_ID"
        if "device" in key or "geo" in key or "schedule" in key: id_header = "Target_Criterion_ID"
        elif "ad_group" in key: id_header = "AdGroup_ID"
        elif "asset_group" in key: id_header = "AssetGroup_ID"
        elif "ad_performance" in key: id_header = "Ad_ID"
        
        header += f"| {id_header} | Segment_Label | Metadata | Cost | Clicks | Impr | CPC | Conv | ROAS |\n"
        header += "|---|---|---|---|---|---|---|---|---|\n"
        return header + "\n".join(rows[:60]) + "\n\n"

    def process_bid_modifiers(self, items: List[Dict]) -> str:
        """Handles Category 2 Actions."""
        if not items: return ""
        rows = []
        for item in items:
            # STRUCTURAL
            rn = get_deep(item, "campaign_criterion.resource_name")
            mod = get_deep(item, "campaign_criterion.bid_modifier", 1.0)
            status = get_deep(item, "campaign_criterion.status")
            
            lbl = get_deep(item, "campaign_criterion.type")
            if "DEVICE" in str(lbl): lbl = f"Device:{get_deep(item, 'campaign_criterion.device.type_')}"
            elif "LOCATION" in str(lbl): lbl = f"Loc:{get_deep(item, 'campaign_criterion.location.geo_target_constant')}"
            elif "AD_SCHEDULE" in str(lbl): lbl = f"Sched:{get_deep(item, 'campaign_criterion.ad_schedule.day_of_week')}"
            
            sid = self._register_rn(rn)
            rows.append(f"| {sid} | {lbl} | {mod} | {status} |")
        
        header = "#### EXISTING BID MODIFIERS\n"
        header += "| Criterion_ID | Type/Target | Modifier | Status |\n"
        header += "|---|---|---|---|\n"
        return header + "\n".join(rows) + "\n\n"

    def process_audiences(self, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            m = self._extract_metrics(item)
            rn = get_deep(item, "ad_group_criterion.resource_name")
            ag_rn = get_deep(item, "ad_group.resource_name")
            status = get_deep(item, "ad_group_criterion.status")
            
            # Identify Audience Type
            user_list = get_deep(item, "ad_group_criterion.user_list.user_list")
            interest = get_deep(item, "ad_group_criterion.user_interest.user_interest_category")
            
            name = "Unknown"
            if user_list: name = f"UserList:{user_list}"
            elif interest: name = f"Interest:{interest}"
            
            # Use Ad Group Criterion ID mapping
            sid = self._register_rn(rn)
            aid = self._register_rn(ag_rn)
            
            rows.append(f"| {sid} | {aid} | {name} | {status} | ${m['cost']:.1f} | {m['conv']} | {m['roas']} |")
            
        header = "#### AUDIENCE PERFORMANCE (AD GROUP CRITERIA)\n"
        header += "| Criterion_ID | AdGroup_ID | Audience_Name | Status | Cost | Conv | ROAS |\n"
        header += "|---|---|---|---|---|---|---|\n"
        return header + "\n".join(rows[:50]) + "\n\n"

    def process_placements(self, key: str, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            m = self._extract_metrics(item)
            if m['is_dead_weight']: continue
            
            url = get_deep(item, "group_placement_view.placement")
            name = clean_md(get_deep(item, "group_placement_view.display_name", url))
            type_ = get_deep(item, "group_placement_view.placement_type")
            
            # Actionable ID (Campaign ID for exclusion)
            cid = self._register_rn(get_deep(item, "campaign.resource_name"))
            
            cpc = round(m['cost'] / m['clicks'], 2) if m['clicks'] > 0 else 0.0
            rows.append(f"| {cid} | {name} | {type_} | ${m['cost']:.1f} | {int(m['clicks'])} | ${cpc} | {m['conv']} | {m['roas']} |")
            
        if not rows: return ""
        header = "#### PLACEMENT PERFORMANCE (DISPLAY/PMAX)\n"
        header += "| Campaign_ID | Placement | Type | Cost | Clicks | CPC | Conv | ROAS |\n"
        header += "|---|---|---|---|---|---|---|---|\n"
        return header + "\n".join(rows[:40]) + "\n\n"

    def process_shared_negatives(self, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            name = clean_md(get_deep(item, "shared_set.name"))
            type_ = get_deep(item, "shared_set.type")
            status = get_deep(item, "shared_set.status")
            rn = get_deep(item, "shared_set.resource_name")
            
            # Enrich with keywords from lookup
            keywords = self.shared_set_keywords.get(rn, [])
            kw_preview = ", ".join(keywords[:10]) + ("..." if len(keywords) > 10 else "")
            if not kw_preview: kw_preview = "(Empty)"

            sid = self._register_rn(rn)
            rows.append(f"| {sid} | {name} | {kw_preview} | {status} |")
            
        header = "#### SHARED NEGATIVE KEYWORD LISTS\n"
        header += "| SharedSet_ID | List_Name | Keywords_Preview | Status |\n"
        header += "|---|---|---|---|\n"
        return header + "\n".join(rows) + "\n\n"

    def process_asset_group_assets(self, items: List[Dict]) -> str:
        if not items: return ""
        rows = []
        for item in items:
            ag_rn = get_deep(item, "asset_group.resource_name")
            # Now available thanks to data_collection update
            rn = get_deep(item, "asset_group_asset.resource_name") 
            asset_rn = get_deep(item, "asset_group_asset.asset")
            field_type = get_deep(item, "asset_group_asset.field_type")
            status = get_deep(item, "asset_group_asset.status")
            perf = get_deep(item, "asset_group_asset.performance_label", "N/A")

            # Lookup asset content
            asset_data = self.asset_lookup.get(asset_rn, {})
            content = "N/A"
            if "TEXT" in field_type:
                content = asset_data.get("text", "N/A")
            elif "IMAGE" in field_type:
                content = asset_data.get("url", "Image")
            elif "YOUTUBE" in field_type:
                content = f"YT:{asset_data.get('youtube_id', 'Video')}"

            # Fallback if RN missing (should not happen now)
            if not rn and ag_rn and asset_rn:
                rn = f"COMPOSITE:AGA:{ag_rn}:{asset_rn}"

            aga_id = self._register_rn(rn)
            aid = self._register_rn(ag_rn)
            rows.append(f"| {aga_id} | {aid} | {field_type} | {clean_md(content)} | {perf} | {status} |")

        if not rows: return ""
        header = "#### ASSET GROUP ASSETS (CREATIVES)\n"
        header += "| AssetGroupAsset_ID | AssetGroup_ID | Field_Type | Content | Perf_Label | Status |\n"
        header += "|---|---|---|---|---|---|\n"
        return header + "\n".join(rows[:50]) + "\n\n"

    def process_budget_bidding(self, data: Any) -> str:
        # Handles both List and Dict
        b = data[0] if isinstance(data, list) and data else data
        if not b or not isinstance(b, dict): return ""
        
        c_rn = get_deep(b, "campaign.resource_name")
        b_rn = get_deep(b, "campaign_budget.resource_name")
        sid = self._register_rn(c_rn)
        bid = self._register_rn(b_rn)
        
        amt = micros_to_curr(get_deep(b, "campaign_budget.amount_micros"))
        strat = get_deep(b, "campaign.bidding_strategy_type")
        roas = get_deep(b, "campaign.maximize_conversion_value.target_roas") or get_deep(b, "campaign.target_roas.target_roas", "N/A")
        cpa = micros_to_curr(get_deep(b, "campaign.maximize_conversions.target_cpa_micros") or get_deep(b, "campaign.target_cpa.target_cpa_micros", 0))
        delivery = get_deep(b, "campaign_budget.delivery_method", "N/A")
        
        out = "#### CAMPAIGN SETTINGS & BUDGET BINDING\n"
        out += f"- **Campaign_ID**: {sid} (Campaign)\n"
        out += f"- **Budget_ID**: {bid} (CampaignBudget)\n"
        out += f"- **Daily_Micro_Amount**: ${amt}\n"
        out += f"- **Budget_Delivery**: {delivery}\n"
        out += f"- **Bidding_Strategy**: {strat}\n"
        out += f"- **Target_ROAS**: {roas}\n"
        out += f"- **Target_CPA**: ${cpa}\n"
        
        # Networks
        out += "\n#### NETWORK SETTINGS\n"
        nets = {
            "Google Search": "target_google_search",
            "Search Network": "target_search_network",
            "Content Network": "target_content_network",
            "Partner Search": "target_partner_search_network"
        }
        for lbl, key in nets.items():
            val = get_deep(b, f"campaign.network_settings.{key}")
            out += f"- **{lbl}**: {val}\n"
        
        return out + "\n"

    # --------------------------------------------------------------------------
    # MAIN ENGINE
    # --------------------------------------------------------------------------

    def prepare_campaign(self, campaign_folder: str):
        files = os.listdir(campaign_folder)
        enriched_file = next((f for f in files if f.endswith("_enriched.json")), None)
        if not enriched_file: return

        with open(os.path.join(campaign_folder, enriched_file), 'r') as f:
            full_data = json.load(f)
            data = full_data.get("payload", {})
            account = full_data.get("account_level", {})
        
        raw = data.get("segment_data_raw", {})
        self.resource_map = {}
        self.id_counter = 0

        # Build Lookups
        self.qs_lookup = {}
        for item in raw.get("quality_score", []):
            rn = get_deep(item, "ad_group_criterion.resource_name")
            if rn:
                self.qs_lookup[rn] = {
                    "score": get_deep(item, "ad_group_criterion.quality_info.quality_score"),
                    "creative": get_deep(item, "ad_group_criterion.quality_info.creative_quality_score"),
                    "landing": get_deep(item, "ad_group_criterion.quality_info.post_click_quality_score"),
                    "ctr": get_deep(item, "ad_group_criterion.quality_info.search_predicted_ctr")
                }
        
        self.mod_lookup = {}
        for item in raw.get("bid_modifiers", []):
            rn = get_deep(item, "campaign_criterion.resource_name")
            typ = get_deep(item, "campaign_criterion.type")
            if "DEVICE" in str(typ):
                dev = get_deep(item, "campaign_criterion.device.type_")
                self.mod_lookup[f"DEVICE:{dev}"] = rn
            elif "LOCATION" in str(typ):
                loc = get_deep(item, "campaign_criterion.location.geo_target_constant")
                self.mod_lookup[f"LOC:{loc}"] = rn
            elif "AD_SCHEDULE" in str(typ):
                day = get_deep(item, "campaign_criterion.ad_schedule.day_of_week")
                hr = get_deep(item, "campaign_criterion.ad_schedule.start_hour")
                self.mod_lookup[f"SCHED:{day}:{hr}"] = rn

        self.shared_set_keywords = {}
        for kw_item in account.get("shared_set_keywords", []):
            ss_rn = get_deep(kw_item, "shared_set.resource_name")
            txt = get_deep(kw_item, "shared_criterion.keyword.text")
            if ss_rn and txt:
                if ss_rn not in self.shared_set_keywords:
                    self.shared_set_keywords[ss_rn] = []
                self.shared_set_keywords[ss_rn].append(txt)

        self.asset_lookup = {}
        for asset_item in account.get("assets", []):
            rn = get_deep(asset_item, "asset.resource_name")
            if rn:
                self.asset_lookup[rn] = {
                    "text": get_deep(asset_item, "asset.text_asset.text"),
                    "url": get_deep(asset_item, "asset.image_asset.full_size.url"),
                    "youtube_id": get_deep(asset_item, "asset.youtube_video_asset.youtube_video_id")
                }
        
        camp_type = infer_campaign_type(data)
        
        # Start with High-Level Diagnostics Overview
        md_out = self.process_campaign_summary(data)
        
        # 1. Budget & Bidding
        md_out += self.process_budget_bidding(raw.get("budget_bidding", {}))

        # 2. Key Performance (The Winners/Losers)
        perf_map = {
            "ad_group_performance": self.process_generic_perf,
            "keyword_performance": self.process_keywords,
            "search_terms": self.process_search_terms,
            "product_performance": self.process_products,
            "asset_group_performance": self.process_generic_perf,
            "device_performance": self.process_generic_perf,
            "geo_performance": self.process_generic_perf,
            "ad_schedule_performance": self.process_generic_perf,
            "placement_performance_detailed": self.process_placements,
            "ad_performance": self.process_generic_perf,
            "daily_performance": self.process_generic_perf,
            "audience_performance": self.process_audiences,  # Added
        }
        for k, proc in perf_map.items():
            if k in raw: md_out += proc(k, raw[k])

        # 3. Structural Context (The Setup)
        md_out += self.process_listing_group_filters(raw.get("listing_group_filters", []))
        md_out += self.process_asset_group_assets(raw.get("asset_group_asset", []))
        md_out += self.process_shared_negatives(raw.get("shared_negative_keywords", []))
        md_out += self.process_bid_modifiers(raw.get("bid_modifiers", []))
        md_out += self.process_demographics(raw.get("demographics_performance", []))
        # process_audiences is handled in perf_map now for better grouping, or we can explicit call it here.
        # User requested it. Let's keep it in perf_map as it has metrics.
        md_out += self.process_negatives(raw.get("existing_negative_keywords", []), "Campaign_Negatives")
        md_out += self.process_negatives(raw.get("ad_group_negative_keywords", []), "AdGroup_Negatives")
        
        # Save MD with Unique Filename
        clean_name = re.sub(r'[^\w\-]', '_', data.get('campaign_name', 'Unknown'))
        filename = f"llm_context_{clean_name}.md"
        with open(os.path.join(campaign_folder, filename), "w", encoding="utf-8") as f:
            f.write(md_out)
        
        # Also keep a symlink/copy as 'llm_context.md' for standard scripts if needed
        with open(os.path.join(campaign_folder, "llm_context.md"), "w", encoding="utf-8") as f:
            f.write(md_out)
        
        # Save Resource Map for the 'Apply' step
        with open(os.path.join(campaign_folder, "resource_map.json"), "w", encoding="utf-8") as f:
            json.dump(self.resource_map, f, indent=2)

        print(f"✓ Metadata-Enriched Prep: {data.get('campaign_name')} | {len(self.resource_map)} IDs Mapped.")

    def run(self):
        for root, dirs, files in os.walk(INPUT_DIR):
            if any(f.endswith("_enriched.json") for f in files):
                self.prepare_campaign(root)

        
    def process_payload_extras(self, payload: Dict) -> str:
        """Includes all other metadata from the payload except segments and thresholds."""
        exclude = {"segment_data_raw", "thresholds"}
        
        # Groupings
        basic_keys = ["campaign_id", "advertising_channel_type", "advertising_channel_sub_type", 
                      "campaign_days_running", "analysis_date", "generated_at_local"]
        complex_keys = ["goals", "budget", "product_context", "bidding_strategy", "derived_metrics", "signals"]
        
        out = "\n### 1.2 EXTENDED CAMPAIGN METADATA\n"
        
        # Basic fields
        out += "#### Core Metadata\n"
        for k in basic_keys:
            if k in payload:
                out += f"- **{k.replace('_', ' ').title()}**: {payload[k]}\n"
        
        # Complex fields
        for k in complex_keys:
            if k in payload:
                out += f"\n#### {k.replace('_', ' ').upper()}\n"
                v = payload[k]
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        if isinstance(sv, (dict, list)):
                            out += f"- **{sk}**: {json.dumps(sv)}\n"
                        else:
                            out += f"- **{sk}**: {sv}\n"
                else:
                    out += f"- {v}\n"
                    
        # Catch-all
        already_covered = set(basic_keys) | set(complex_keys) | exclude | {"campaign_name"}
        remaining = [k for k in payload.keys() if k not in already_covered]
        if remaining:
            out += "\n#### OTHER SIGNALS\n"
            for k in remaining:
                v = payload[k]
                if isinstance(v, (dict, list)):
                    out += f"- **{k}**: {json.dumps(v)}\n"
                else:
                    out += f"- **{k}**: {v}\n"
                
        return out + "\n"

    def process_campaign_summary(self, payload: Dict) -> str:
        name = clean_md(payload.get("campaign_name", "Unknown"))
        c_type = infer_campaign_type(payload)
        strat = payload.get("bidding_strategy", {})
        m = payload.get("derived_metrics", {})
        
        # FIX: Use safe_float() to handle None values coming from the API
        spend_val = safe_float(m.get('total_spend_usd'))
        roas_val = safe_float(m.get('roas'))
        cpa_val = safe_float(m.get('cpa_usd'))
        conv_val = safe_float(m.get('conversions'))
        
        # Format safely
        spend = f"${spend_val:.2f}"
        roas = f"{roas_val:.2f}"
        cpa = f"${cpa_val:.2f}"
        conv = f"{conv_val:.2f}"
        
        # Metrics
        cpc_val = safe_float(m.get('cpc_usd'))
        ctr_val = safe_float(m.get('ctr_pct'))
        share = m.get('search_impression_share_pct', 'N/A')
        lost = m.get('search_budget_lost_impression_share_pct', 'N/A')
        
        # Formatting
        cpc = f"${cpc_val:.2f}"
        ctr = f"{ctr_val:.2f}%"
        
        # Anomalies/Signals preview
        signals = payload.get("signals", {})
        anomalies = signals.get("anomalies", [])
        anomaly_text = f"\n* **⚠️ ANOMALIES DETECTED:** {', '.join(anomalies)}" if anomalies else ""

        summary_md = f"""# CAMPAIGN AUDIT: {name}
            
### 1. HIGH-LEVEL DIAGNOSTICS
* **Campaign Type:** {c_type}
* **Strategy:** {strat.get('type', 'Unknown')} (Target ROAS: {strat.get('target_roas', 'N/A')})
* **30-Day Spend:** {spend} | **Conversions:** {conv}
* **30-Day ROAS:** {roas} | **30-Day CPA:** {cpa}
* **Avg CPC:** {cpc} | **CTR:** {ctr}
* **Impression Share:** {share}% (Lost to Budget: {lost}%){anomaly_text}
"""
        # Append the extra payload data
        summary_md += self.process_payload_extras(payload)
        
        summary_md += "\n### 2. DETAILED PERFORMANCE TABLES\n"
        return summary_md

if __name__ == "__main__":
    DataPreparer().run()