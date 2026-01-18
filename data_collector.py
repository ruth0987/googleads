import os
import re
import json
import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ====================================================================
# CONFIGURATION
# ====================================================================

MCC_ID = os.getenv("GOOGLE_ADS_MCC_ID", "8265069948")
DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
if not DEVELOPER_TOKEN:
    raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN environment variable is required")

# Resolve paths intelligently (Absolute or relative to root)
def resolve_path(p: str) -> str:
    if not p: return p
    if os.path.isabs(p): return p
    return os.path.abspath(os.path.join(os.path.dirname(__file__), p))

CLIENT_SECRET_PATH = resolve_path(os.getenv("GOOGLE_ADS_CLIENT_SECRET_PATH"))
if not CLIENT_SECRET_PATH:
    raise ValueError("GOOGLE_ADS_CLIENT_SECRET_PATH environment variable is required")

REFRESH_TOKEN_PATH = resolve_path(os.getenv("GOOGLE_ADS_REFRESH_TOKEN_PATH", "refresh_token_1.txt"))
TEST_CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "7137669444")
OUTPUT_DIR = os.getenv("DATA_DIR", "google_ads_data_llm")
LAZY_FETCH = os.getenv("LAZY_FETCH", "False").lower() == "true"
PRINT_PROGRESS = os.getenv("PRINT_PROGRESS", "True").lower() == "true"
IDEMPOTENCY_STORE = os.path.join(OUTPUT_DIR, "recommendations_store.json")

DEFAULT_PRODUCT_CONTEXT = {
    "avg_order_value_low": None,
    "avg_order_value_high": None,
    "conversion_value_is_revenue": True
}

DEFAULT_TARGET_ROAS = None
DEFAULT_TARGET_CPA = None
DEFAULT_TARGET_CTR_PCT = None

# ====================================================================
# API CLIENT SETUP
# ====================================================================

try:
    from google.ads.googleads.client import GoogleAdsClient
    from google.ads.googleads.errors import GoogleAdsException
    from google.protobuf.json_format import MessageToDict
except Exception:
    GoogleAdsClient = None
    GoogleAdsException = Exception
    MessageToDict = None

# ====================================================================
# UTILITIES
# ====================================================================

def safe_float(v: Any) -> Optional[float]:
    if v is None: return None
    try: return float(v)
    except: pass
    try: return float(str(v).replace(",", "").strip())
    except: return None

def micros_to_usd(micros: Any) -> Optional[float]:
    m = safe_float(micros)
    if m is None: return None
    return round(m / 1_000_000.0, 6)

def sanitize_filename(name: str) -> str:
    return re.sub(r"[^\w\-_\.]", "_", name)[:120]

def save_json(obj: Any, filename: str, output_dir: str = OUTPUT_DIR) -> str:
    os.makedirs(output_dir, exist_ok=True)
    fname = sanitize_filename(filename)
    path = os.path.join(output_dir, fname)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    return path

def load_json(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def _flatten_message_dict(message_pb_dict: Dict, parent_key: str = "") -> Dict[str, Any]:
    out = {}
    for k, v in message_pb_dict.items():
        nk = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            out.update(_flatten_message_dict(v, nk))
        elif isinstance(v, list):
            out[nk] = v
        else:
            out[nk] = v
    return out

def compute_input_hash(obj: Dict) -> str:
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

# ====================================================================
# GAQL QUERIES
# ====================================================================

QUERY_DEFINITIONS = {
    # ==================== ACCOUNT LEVEL (ADDED) ====================
    "conversion_actions": {
        "name": "Conversion Actions",
        "query": """
            SELECT
                conversion_action.resource_name,
                conversion_action.id,
                conversion_action.name,
                conversion_action.status,
                conversion_action.type,
                conversion_action.category,
                conversion_action.primary_for_goal
            FROM conversion_action
            WHERE conversion_action.status = 'ENABLED'
        """,
        "store_as": "conversion_actions",
        "id_field": "conversion_action.id",
        "is_array": True
    },
   
    # ==================== CAMPAIGN CORE ====================
    "campaign_core": {
        "name": "Campaign Core",
        "query": """
            SELECT
                campaign.resource_name,
                campaign.id,
                campaign.name,
                campaign.status,
                campaign.advertising_channel_type,
                campaign.advertising_channel_sub_type,
                campaign.start_date,
                campaign.end_date,
                campaign.serving_status,
                campaign.ad_serving_optimization_status
            FROM campaign
            WHERE campaign.status = 'ENABLED' AND campaign.serving_status = 'SERVING'
        """,
        "store_as": "core",
        "id_field": "campaign.id"
    },
   
    # ==================== BUDGET & BIDDING ====================
    "campaign_budget_bidding": {
        "name": "Campaign Budget & Bidding",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                campaign_budget.resource_name,
                campaign_budget.amount_micros,
                campaign_budget.delivery_method,
                campaign.bidding_strategy_type,
                campaign.target_cpa.target_cpa_micros,
                campaign.target_roas.target_roas,
                campaign.maximize_conversions.target_cpa_micros,
                campaign.maximize_conversion_value.target_roas,
                campaign.manual_cpc.enhanced_cpc_enabled,
                campaign.network_settings.target_google_search,
                campaign.network_settings.target_search_network,
                campaign.network_settings.target_content_network,
                campaign.network_settings.target_partner_search_network
            FROM campaign
            WHERE campaign.status = 'ENABLED'
        """,
        "store_as": "budget_bidding",
        "id_field": "campaign.id"
    },
   
    # ==================== PERFORMANCE ====================
    "campaign_performance": {
        "name": "Campaign Performance 30d",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                campaign.name,
                metrics.impressions,
                metrics.clicks,
                metrics.ctr,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "performance_30d",
        "id_field": "campaign.id"
    },
   
    "impression_share": {
        "name": "Impression Share",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                metrics.search_impression_share,
                metrics.search_budget_lost_impression_share,
                metrics.search_rank_lost_impression_share,
                metrics.search_top_impression_share,
                metrics.search_absolute_top_impression_share
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "impression_share",
        "id_field": "campaign.id"
    },
   
    # ==================== KEYWORDS ====================
    "keyword_performance": {
        "name": "Keyword Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                ad_group.id,
                ad_group.resource_name,
                ad_group.name,
                ad_group_criterion.resource_name,
                ad_group_criterion.criterion_id,
                ad_group_criterion.status,
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                ad_group_criterion.cpc_bid_micros,
                ad_group_criterion.final_urls,
                metrics.impressions,
                metrics.clicks,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value,
                metrics.search_impression_share,
                ad_group_criterion.position_estimates.first_page_cpc_micros,
                ad_group_criterion.position_estimates.top_of_page_cpc_micros
            FROM keyword_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
            AND ad_group_criterion.status != 'REMOVED'
        """,
        "store_as": "keyword_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== QUALITY SCORE (CRITICAL!) ====================
    "quality_score": {
        "name": "Quality Score",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                ad_group.id,
                ad_group.resource_name,
                ad_group_criterion.resource_name,
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.quality_info.quality_score,
                ad_group_criterion.quality_info.creative_quality_score,
                ad_group_criterion.quality_info.post_click_quality_score,
                ad_group_criterion.quality_info.search_predicted_ctr,
                metrics.impressions
            FROM keyword_view
            WHERE campaign.status = 'ENABLED'
            AND ad_group_criterion.status = 'ENABLED'
            AND segments.date DURING LAST_30_DAYS
        """,
        "store_as": "quality_score",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== SEARCH TERMS ====================
    "search_terms": {
        "name": "Search Terms",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                ad_group.id,
                ad_group.resource_name,
                search_term_view.search_term,
                search_term_view.status,
                segments.keyword.info.text,
                segments.keyword.info.match_type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM search_term_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "search_terms",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== EXISTING NEGATIVE KEYWORDS ====================
    "existing_negative_keywords": {
        "name": "Existing Negative Keywords",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                campaign_criterion.resource_name,
                campaign_criterion.criterion_id,
                campaign_criterion.keyword.text,
                campaign_criterion.keyword.match_type,
                campaign_criterion.type
            FROM campaign_criterion
            WHERE campaign_criterion.type = 'KEYWORD'
            AND campaign_criterion.negative = TRUE
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "existing_negative_keywords",
        "id_field": "campaign.id",
        "is_array": True
    },

    # ==================== AD GROUP NEGATIVE KEYWORDS ====================
    "ad_group_negative_keywords": {
        "name": "Ad Group Negative Keywords",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                ad_group.id,
                ad_group.resource_name,
                ad_group_criterion.resource_name,
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                ad_group_criterion.negative
            FROM ad_group_criterion
            WHERE ad_group_criterion.type = 'KEYWORD'
            AND ad_group_criterion.negative = TRUE
            AND campaign.status = 'ENABLED'
            AND ad_group_criterion.status != 'REMOVED'
        """,
        "store_as": "ad_group_negative_keywords",
        "id_field": "campaign.id",
        "is_array": True
    },

    # ==================== DEMOGRAPHICS PERFORMANCE ====================
    "age_performance": {
        "name": "Age Performance",
        "query": """
            SELECT
                campaign.id,
                ad_group.id,
                ad_group_criterion.age_range.type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM age_range_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "demographics_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
    "gender_performance": {
        "name": "Gender Performance",
        "query": """
            SELECT
                campaign.id,
                ad_group.id,
                ad_group_criterion.gender.type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM gender_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "demographics_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
    "income_performance": {
        "name": "Income Performance",
        "query": """
            SELECT
                campaign.id,
                ad_group.id,
                ad_group_criterion.income_range.type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM income_range_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "demographics_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
    "shared_negative_keywords": {
        "name": "Shared Negative Keyword Lists",
        "query": """
            SELECT
                campaign.id,
                shared_set.name,
                shared_set.type,
                shared_set.status,
                shared_set.resource_name
            FROM campaign_shared_set
            WHERE shared_set.type = 'NEGATIVE_KEYWORDS'
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "shared_negative_keywords",
        "id_field": "campaign.id",
        "is_array": True
    },
    "shared_set_keywords": {
        "name": "Keywords within Shared Sets",
        "is_account_level": True,
        "query": """
            SELECT
                shared_set.resource_name,
                shared_criterion.keyword.text,
                shared_criterion.keyword.match_type,
                shared_criterion.type
            FROM shared_criterion
        """,
        "store_as": "shared_set_keywords"
    },
   
    # ==================== BID MODIFIERS (CRITICAL!) ====================
    "bid_modifiers": {
        "name": "Current Bid Modifiers",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                campaign_criterion.resource_name,
                campaign_criterion.criterion_id,
                campaign_criterion.type,
                campaign_criterion.status,
                campaign_criterion.bid_modifier,
                campaign_criterion.negative,
                campaign_criterion.device.type,
                campaign_criterion.location.geo_target_constant,
                campaign_criterion.ad_schedule.day_of_week,
                campaign_criterion.ad_schedule.start_hour,
                campaign_criterion.ad_schedule.end_hour,
                campaign_criterion.ad_schedule.start_minute,
                campaign_criterion.ad_schedule.end_minute
            FROM campaign_criterion
            WHERE campaign.status = 'ENABLED'
            AND campaign_criterion.status != 'REMOVED'
        """,
        "store_as": "bid_modifiers",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== DEVICE PERFORMANCE ====================
    "device_performance": {
        "name": "Device Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                segments.device,
                metrics.impressions,
                metrics.clicks,
                metrics.average_cpc,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "device_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== GEO PERFORMANCE ====================
    "geo_performance": {
        "name": "Geo Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                campaign.status,
                geographic_view.country_criterion_id,
                geographic_view.location_type,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM geographic_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "geo_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== AD SCHEDULE PERFORMANCE (CRITICAL!) ====================
    "ad_schedule_performance": {
        "name": "Ad Schedule Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                segments.day_of_week,
                segments.hour,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "ad_schedule_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== AD PERFORMANCE ====================
    "ad_performance": {
        "name": "Ad Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                ad_group.id,
                ad_group.resource_name,
                ad_group_ad.resource_name,
                ad_group_ad.ad.id,
                ad_group_ad.status,
                ad_group_ad.policy_summary.approval_status,
                ad_group_ad.ad.type,
                ad_group_ad.ad.final_urls,
                ad_group_ad.ad.responsive_search_ad.headlines,
                ad_group_ad.ad.responsive_search_ad.descriptions,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM ad_group_ad
            WHERE segments.date DURING LAST_30_DAYS
            AND ad_group_ad.status != 'REMOVED'
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "ad_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== AD GROUP PERFORMANCE ====================
    "ad_group_performance": {
        "name": "Ad Group Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                ad_group.id,
                ad_group.resource_name,
                ad_group.name,
                ad_group.status,
                ad_group.cpc_bid_micros,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM ad_group
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "ad_group_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== PLACEMENT PERFORMANCE (for exclusions) ====================
    "placement_performance_detailed": {
        "name": "Placement Performance Detailed",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                group_placement_view.placement,
                group_placement_view.placement_type,
                group_placement_view.display_name,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM group_placement_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "placement_performance_detailed",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== AUDIENCE PERFORMANCE (CRITICAL!) ====================
    "audience_performance": {
        "name": "Audience Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                ad_group.id,
                ad_group.resource_name,
                ad_group_criterion.resource_name,
                ad_group_criterion.criterion_id,
                ad_group_criterion.status,
                ad_group_criterion.user_list.user_list,
                ad_group_criterion.user_interest.user_interest_category,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM ad_group_audience_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "audience_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== DAILY PERFORMANCE (for trends) ====================
    "daily_performance": {
        "name": "Daily Performance",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                segments.date,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM campaign
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
            ORDER BY segments.date DESC
        """,
        "store_as": "daily_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
   
    # ==================== RECOMMENDATIONS (Google's suggestions) ====================
    "recommendations": {
        "name": "Recommendations",
        "query": """
            SELECT
                recommendation.resource_name,
                recommendation.campaign,
                recommendation.type,
                recommendation.impact,
                recommendation.dismissed,
                campaign.status
            FROM recommendation
            WHERE recommendation.dismissed = FALSE
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "recommendations",
        "id_field": "recommendation.campaign",
        "is_array": True,
        "extract_id_from_resource": True
    },
    # ==================== PRODUCT PERFORMANCE (CRITICAL for Shopping/PMax) ====================
    "product_performance": {
        "name": "Product Performance (Shopping/PMax)",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                campaign.status,
                ad_group.id,
                ad_group.resource_name,
                segments.product_item_id,
                segments.product_title,
                segments.product_brand,
                segments.product_type_l1,
                segments.product_type_l2,
                segments.product_type_l3,
                metrics.impressions,
                metrics.clicks,
                metrics.cost_micros,
                metrics.conversions,
                metrics.conversions_value
            FROM shopping_performance_view
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "product_performance",
        "id_field": "campaign.id",
        "is_array": True
    },

    # ==================== PMAX: ASSET GROUP PERFORMANCE ====================
    "asset_group_performance": {
        "name": "Asset Group Performance (PMax)",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                asset_group.id,
                asset_group.resource_name,
                asset_group.name,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                metrics.conversions_value
            FROM asset_group
            WHERE segments.date DURING LAST_30_DAYS
            AND campaign.status = 'ENABLED'
        """,
        "store_as": "asset_group_performance",
        "id_field": "campaign.id",
        "is_array": True
    },
    # ==================== PMAX: ASSET GROUP ASSETS ====================
    "asset_group_asset": {
        "name": "Asset Group Assets (PMax)",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                asset_group.id,
                asset_group.resource_name,
                asset_group_asset.resource_name,
                asset_group_asset.asset,
                asset_group_asset.field_type,
                asset_group_asset.status
            FROM asset_group_asset
            WHERE campaign.status = 'ENABLED'
        """,
        "store_as": "asset_group_asset",
        "id_field": "campaign.id",
        "is_array": True
    },

    # ==================== PMAX: ASSET GROUP LISTING GROUP FILTERS (CRITICAL for Actions) ====================
    "asset_group_listing_group_filters": {
        "name": "Asset Group Listing Group Filters (PMax)",
        "query": """
            SELECT
                campaign.id,
                campaign.resource_name,
                asset_group.id,
                asset_group.resource_name,
                asset_group_listing_group_filter.resource_name,
                asset_group_listing_group_filter.type,
                asset_group_listing_group_filter.case_value.product_type.level,
                asset_group_listing_group_filter.case_value.product_type.value,
                asset_group_listing_group_filter.case_value.product_brand.value,
                asset_group_listing_group_filter.case_value.product_channel.channel,
                asset_group_listing_group_filter.case_value.product_condition.condition,
                asset_group_listing_group_filter.case_value.product_custom_attribute.index,
                asset_group_listing_group_filter.case_value.product_custom_attribute.value
            FROM asset_group_listing_group_filter
            WHERE campaign.status = 'ENABLED'
        """,
        "store_as": "listing_group_filters",
        "id_field": "campaign.id",
        "is_array": True
    },
    "assets": {
        "name": "All Assets",
        "is_account_level": True,
        "query": """
            SELECT
                asset.resource_name,
                asset.id,
                asset.name,
                asset.type,
                asset.text_asset.text,
                asset.image_asset.full_size.url,
                asset.youtube_video_asset.youtube_video_id
            FROM asset
        """,
        "store_as": "assets"
    }
}

# ====================================================================
# API CLIENT
# ====================================================================

class GoogleAdsAPIClient:
    def __init__(self, developer_token: str, mcc_id: str, client_secret_path: str, refresh_token_path: str):
        self.developer_token = developer_token
        self.mcc_id = mcc_id
        self.client_secret_path = client_secret_path
        self.refresh_token_path = refresh_token_path
        self.client = None

    def _ensure_client(self):
        if self.client: return
        if GoogleAdsClient is None:
            raise RuntimeError("google-ads library not found.")
        with open(self.refresh_token_path) as f:
            refresh_token = f.read().strip()
        with open(self.client_secret_path) as f:
            data = json.load(f)
        key = "installed" if "installed" in data else "web"
        config = {
            "developer_token": self.developer_token,
            "client_id": data[key]["client_id"],
            "client_secret": data[key]["client_secret"],
            "refresh_token": refresh_token,
            "login_customer_id": self.mcc_id,
            "use_proto_plus": True
        }
        self.client = GoogleAdsClient.load_from_dict(config)

    def execute_query(self, customer_id: str, query: str) -> Dict[str, Any]:
        self._ensure_client()
        ga_service = self.client.get_service("GoogleAdsService")
        try:
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            rows = []
            for batch in stream:
                for row in batch.results:
                    pb = row._pb if hasattr(row, "_pb") else row
                    pd = MessageToDict(pb, preserving_proto_field_name=True)
                    rows.append(_flatten_message_dict(pd))
            return {"success": True, "data": rows, "row_count": len(rows)}
        except GoogleAdsException as ex:
            return {"success": False, "error": str(ex), "data": [], "row_count": 0}
        except Exception as e:
            return {"success": False, "error": str(e), "data": [], "row_count": 0}

# ====================================================================
# DATA PROCESSING LOGIC
# ====================================================================

def organize_results_by_campaign(all_results: Dict[str, Dict]) -> Tuple[Dict[str, Dict], Dict[str, Any]]:
    campaigns = {}
    account_level = {}
    for key, defn in QUERY_DEFINITIONS.items():
        res = all_results.get(key, {})
        if not res.get("success"): continue
        rows = res.get("data", [])
        store_as = defn["store_as"]
        is_array = defn.get("is_array", False)
        is_account_level = defn.get("is_account_level", False)
        
        if is_account_level:
            account_level[store_as] = rows
            continue

        id_field = defn.get("id_field")
        for r in rows:
            cid = None
            if id_field and r.get(id_field):
                cid = r.get(id_field)
            else:
                for k in ("campaign.id", "campaign", "campaign.resource_name"):
                    if r.get(k):
                        cid = r.get(k); break
            if isinstance(cid, str) and "campaigns/" in cid:
                cid = cid.split("/")[-1]
            if not cid: continue
            
            if cid not in campaigns:
                campaigns[cid] = {
                    "campaign_id": cid,
                    "name": r.get("campaign.name") or r.get("campaign_name") or f"campaign_{cid}",
                    "data": {}
                }
            
            if is_array:
                campaigns[cid]["data"].setdefault(store_as, []).append(r)
            else:
                existing = campaigns[cid]["data"].get(store_as, {})
                campaigns[cid]["data"][store_as] = {**existing, **r}
    return campaigns, account_level

def calculate_simple_derived_metrics(perf_row: Dict, imp_row: Dict) -> Dict:
    clicks = safe_float(perf_row.get("metrics.clicks")) or 0.0
    impressions = safe_float(perf_row.get("metrics.impressions")) or 0.0
    cost_usd = micros_to_usd(perf_row.get("metrics.cost_micros")) or 0.0
    conversions = safe_float(perf_row.get("metrics.conversions")) or 0.0
    conv_value = safe_float(perf_row.get("metrics.conversions_value")) or 0.0

    ctr = round((clicks / impressions * 100), 2) if impressions > 0 else None
    avg_cpc = round(cost_usd / clicks, 2) if clicks > 0 else None
    roas = round(conv_value / cost_usd, 2) if cost_usd > 0 else None
    cvr = round((conversions / clicks * 100), 2) if clicks > 0 else None
    cpa = round(cost_usd / conversions, 2) if conversions > 0 else None

    return {
        "total_spend_usd": round(cost_usd, 2),
        "total_clicks": int(clicks),
        "total_impressions": int(impressions),
        "ctr_pct": ctr,
        "avg_cpc_usd": avg_cpc,
        "conversions": conversions,
        "conversion_value_usd": round(conv_value, 2),
        "roas": roas,
        "conversion_rate_pct": cvr,
        "cpa_usd": cpa,
        "search_impression_share_pct": round(safe_float(imp_row.get("metrics.search_impression_share") or 0) * 100, 2),
        "search_budget_lost_impression_share_pct": round(safe_float(imp_row.get("metrics.search_budget_lost_impression_share") or 0) * 100, 2),
        "search_rank_lost_impression_share_pct": round(safe_float(imp_row.get("metrics.search_rank_lost_impression_share") or 0) * 100, 2),
    }

# --- AOV & THRESHOLDS ---

def _determine_aov_tier(aov_usd: float) -> str:
    if aov_usd >= 500: return "tier_1_very_high"
    elif aov_usd >= 200: return "tier_2_high"
    elif aov_usd >= 50: return "tier_3_medium"
    else: return "tier_4_low"

def resolve_aov(product_context_input: Dict, derived_metrics: Dict) -> Tuple[Dict, List[str]]:
    missing = []
    pc = {"avg_order_value_low": None, "avg_order_value_high": None, "aov_usd": None, "aov_tier": "tier_4_low", "conversion_value_is_revenue": None}
    
    low = product_context_input.get("avg_order_value_low")
    high = product_context_input.get("avg_order_value_high")
    low_f, high_f = safe_float(low), safe_float(high)
    
    if low_f is not None and high_f is not None:
        aov = (low_f + high_f) / 2.0
        pc.update({"avg_order_value_low": low_f, "avg_order_value_high": high_f, "aov_usd": round(aov, 2),
                   "aov_tier": _determine_aov_tier(aov), "conversion_value_is_revenue": True})
        return pc, missing

    conv_value = safe_float(derived_metrics.get("conversion_value_usd"))
    conv_cnt = safe_float(derived_metrics.get("conversions"))
    if conv_value and conv_cnt and conv_cnt > 0 and product_context_input.get("conversion_value_is_revenue", False):
        aov = conv_value / conv_cnt
        pc.update({"aov_usd": round(aov, 2), "avg_order_value_low": round(aov * 0.9, 2), "avg_order_value_high": round(aov * 1.1, 2),
                   "aov_tier": _determine_aov_tier(aov), "conversion_value_is_revenue": True})
        return pc, missing

    missing.extend(["avg_order_value_low", "avg_order_value_high"])
    return pc, missing

def build_thresholds(aov_tier: str) -> Dict:
    base = {
        "min_impressions_to_evaluate": 3000, "min_clicks_to_evaluate": 300,
        "min_conversions_for_confident_decision": 20, "min_conversions_for_smart_bidding_like_logic": 30,
        "min_days_before_optimize_decision": 14, "min_days_before_stop_decision": 7,
        "min_days_since_last_major_change": 7, "min_stable_days_for_trend": 7,
        "min_significant_change_in_ctr_pct_points": 0.5, "min_significant_change_in_cvr_pct_points": 0.5,
        "min_segments_required_for_segment_optimization": 2, "min_conversions_per_segment_for_action": 5,
        "max_cpa_vs_target_multiplier_for_stop": 2.0, "min_roas_vs_target_multiplier_for_stop": 0.5,
        "neutral_band_roas_vs_target_low": 0.8, "neutral_band_roas_vs_target_high": 1.2
    }
    if aov_tier == "tier_3_medium":
        base.update({"min_impressions_to_evaluate": 2500, "min_clicks_to_evaluate": 250,
                     "min_conversions_for_confident_decision": 15, "min_conversions_for_smart_bidding_like_logic": 20})
    elif aov_tier == "tier_2_high":
        base.update({"min_impressions_to_evaluate": 2000, "min_clicks_to_evaluate": 200,
                     "min_conversions_for_confident_decision": 10, "min_conversions_for_smart_bidding_like_logic": 15})
    elif aov_tier == "tier_1_very_high":
        base.update({"min_impressions_to_evaluate": 1500, "min_clicks_to_evaluate": 150,
                     "min_conversions_for_confident_decision": 5, "min_conversions_for_smart_bidding_like_logic": 10})
    return base

# ---------------------------------------------------------------------
# SIGNALS & ANOMALIES (Consolidated)
# ---------------------------------------------------------------------
def generate_signals_and_anomalies(segment_data: Dict, derived_metrics: Dict) -> Dict[str, Any]:
    """Generates signals, filtering out segments with zero spend and impressions."""
    signals = {}

    # --- 1. Quality Score ---
    qs_rows = segment_data.get("quality_score", [])
    if qs_rows:
        total_imps = sum(safe_float(r.get("metrics.impressions", 0)) or 0 for r in qs_rows)
        weighted_sum = sum(
            (safe_float(r.get("ad_group_criterion.quality_info.quality_score", 0)) or 0) *
            (safe_float(r.get("metrics.impressions", 0)) or 0)
            for r in qs_rows
        )
        avg_qs = round(weighted_sum / total_imps, 2) if total_imps > 0 else None
        if avg_qs is not None:
            signals["quality_score"] = {
                "avg_weighted": avg_qs,
                "count": len(qs_rows)
            }

    # --- 2. Devices ---
    devices = {}
    for d in segment_data.get("device_performance", []):
        dev = d.get("segments.device")
        cost = micros_to_usd(d.get("metrics.cost_micros", 0)) or 0
        conv = safe_float(d.get("metrics.conversions", 0)) or 0
        impr = safe_float(d.get("metrics.impressions", 0)) or 0
        
        # FILTER: Only keep if there is spend or impressions
        if cost > 0 or impr > 0:
            devices[dev] = {
                "cost": round(cost, 2), 
                "conversions": conv, 
                "impressions": int(impr),
                "cpa": round(cost/conv, 2) if conv > 0 else None
            }
    if devices:
        signals["devices"] = devices

    # --- 3. Demographics ---
    demo_perf = segment_data.get("demographics_performance", [])
    if demo_perf:
        demo_summary = {"AGE_RANGE": {}, "GENDER": {}, "INCOME_RANGE": {}}
        for d in demo_perf:
            d_type = d.get("ad_group_criterion.type") or d.get("ad_group_criterion.type_")
            cost = micros_to_usd(d.get("metrics.cost_micros", 0)) or 0
            conv = safe_float(d.get("metrics.conversions", 0)) or 0
            impr = safe_float(d.get("metrics.impressions", 0)) or 0
            
            if cost == 0 and impr == 0:
                continue

            label = d.get("ad_group_criterion.age_range.type") or d.get("ad_group_criterion.gender.type") or d.get("ad_group_criterion.income_range.type") or "Unknown"
            
            if d_type in demo_summary:
                if label not in demo_summary[d_type]:
                    demo_summary[d_type][label] = {"cost": 0, "conv": 0, "impr": 0}
                demo_summary[d_type][label]["cost"] += cost
                demo_summary[d_type][label]["conv"] += conv
                demo_summary[d_type][label]["impr"] += impr
        
        # Clean up empty categories
        signals["demographics"] = {k: v for k, v in demo_summary.items() if v}

    # --- 4. Products ---
    products = segment_data.get("product_performance", [])
    if products:
        top_products = sorted(products, key=lambda x: safe_float(x.get("metrics.conversions_value", 0)), reverse=True)[:5]
        signals["products"] = {
            "top_5_by_revenue": [{
                "title": p.get("segments.product_title"),
                "revenue": micros_to_usd(p.get("metrics.conversions_value", 0)),
                "cost": micros_to_usd(p.get("metrics.cost_micros", 0))
            } for p in top_products if (micros_to_usd(p.get("metrics.cost_micros", 0)) or 0) > 0]
        }

    # --- 5. Asset Groups ---
    assets = segment_data.get("asset_group_performance", [])
    if assets:
        signals["pmax_asset_groups"] = [{
            "name": a.get("asset_group_name") or a.get("asset_group.resource_name"),
            "cost": micros_to_usd(a.get("metrics.cost_micros", 0)),
            "conversions": safe_float(a.get("metrics.conversions", 0))
        } for a in assets if (micros_to_usd(a.get("metrics.cost_micros", 0)) or 0) > 0]

    # --- 6. Search Terms & Placements Waste ---
    st_rows = segment_data.get("search_terms", [])
    if st_rows:
        wasted_st = sum(micros_to_usd(s.get("metrics.cost_micros", 0)) or 0 for s in st_rows if safe_float(s.get("metrics.conversions", 0)) == 0)
        if wasted_st > 0:
            signals["search_terms_waste"] = round(wasted_st, 2)

    placement_rows = segment_data.get("placement_performance_detailed", [])
    if placement_rows:
        wasted_pl = sum(micros_to_usd(p.get("metrics.cost_micros", 0)) or 0 for p in placement_rows if safe_float(p.get("metrics.conversions", 0)) == 0)
        if wasted_pl > 0:
            signals["placement_waste"] = round(wasted_pl, 2)

    return {"signals": signals}

# ---------------------------------------------------------------------
# BUILD PAYLOAD
# ---------------------------------------------------------------------
def build_canonical_payload(campaign: Dict, account_level: Dict, product_context_input: Dict = None) -> Dict:
    raw = campaign.get("data", {})
    perf_row = raw.get("performance_30d", {}) or {}
    imp_row = raw.get("impression_share", {}) or {}

    # 1. Derived Metrics
    derived = calculate_simple_derived_metrics(perf_row, imp_row)

    # 2. Product Context & AOV
    if product_context_input is None:
        product_context_input = DEFAULT_PRODUCT_CONTEXT.copy()
    product_context, _ = resolve_aov(product_context_input, derived)

    # 3. Thresholds
    thresholds = build_thresholds(product_context.get("aov_tier", "tier_4_low"))

    # 4. Prepare Segment Data
    segment_data_raw = {
        "keyword_performance": raw.get("keyword_performance", []),
        "quality_score": raw.get("quality_score", []),
        "search_terms": raw.get("search_terms", []),
        "device_performance": raw.get("device_performance", []),
        "geo_performance": raw.get("geo_performance", []),
        "ad_schedule_performance": raw.get("ad_schedule_performance", []),
        "placement_performance_detailed": raw.get("placement_performance_detailed", []),
        "asset_group_performance": raw.get("asset_group_performance", []),
        "daily_performance": raw.get("daily_performance", []),
        "budget_bidding": raw.get("budget_bidding", []),  # CRITICAL: Store budget data
        "product_performance": raw.get("product_performance", []),  # CRITICAL: Store product performance data
        "listing_group_filters": raw.get("listing_group_filters", []),  # CRITICAL: Store listing group filter resource names
        "ad_group_negative_keywords": [
            item for item in raw.get("ad_group_negative_keywords", []) 
            if item.get("ad_group_criterion.negative") is True
        ],
        "shared_negative_keywords": raw.get("shared_negative_keywords", []),
        "demographics_performance": raw.get("demographics_performance", [])
    }

    # 5. Generate Signals & Anomalies (Consolidated Call)
    summary = generate_signals_and_anomalies(segment_data_raw, derived)

    # 6. Budget Stats
    daily_spend_micros = [safe_float(d.get("metrics.cost_micros", 0)) or 0 for d in segment_data_raw.get("daily_performance", [])[:14]]
    avg_daily_spend = (sum(daily_spend_micros) / len(daily_spend_micros)) / 1e6 if daily_spend_micros else 0
    
    raw_bidding = raw.get("budget_bidding", {}) or {}
    daily_budget_usd = micros_to_usd(raw_bidding.get("campaign_budget.amount_micros")) or 0.0
    spend_ratio = avg_daily_spend / daily_budget_usd if daily_budget_usd > 0 else 0

    # 7. Bidding Info
    target_roas = (raw_bidding.get("campaign.target_roas.target_roas") or
                   raw_bidding.get("campaign.maximize_conversion_value.target_roas"))
    target_cpa = micros_to_usd(raw_bidding.get("campaign.target_cpa.target_cpa_micros") or
                               raw_bidding.get("campaign.maximize_conversions.target_cpa_micros"))

    bidding_strategy = {
        "type": raw_bidding.get("campaign.bidding_strategy_type", "ManualCPC"),
        "target_roas": float(target_roas) if target_roas else None,
        "target_cpa_usd": target_cpa
    }

    core_data = raw.get("core", {}) or {}
    launch_date = core_data.get("campaign.start_date")
    advertising_channel_type = core_data.get("campaign.advertising_channel_type", "SEARCH")
    advertising_channel_sub_type = core_data.get("campaign.advertising_channel_sub_type")
    
    days_running = None
    if launch_date:
        try:
            days_running = (datetime.now() - datetime.strptime(launch_date, "%Y-%m-%d")).days
        except: pass

    # 8. Final Payload
    payload = {
        "campaign_id": campaign["campaign_id"],
        "campaign_name": campaign["name"],
        "advertising_channel_type": advertising_channel_type,
        "advertising_channel_sub_type": advertising_channel_sub_type,
        "campaign_days_running": days_running,
        "bidding_strategy": bidding_strategy,
        "goals": {"target_roas": float(target_roas) if target_roas else None, "target_cpa_usd": target_cpa},
        "derived_metrics": derived,
        "budget": {
            "daily_budget_usd": daily_budget_usd,
            "avg_daily_spend_last_14d": round(avg_daily_spend, 2),
            "spend_vs_budget_ratio": round(spend_ratio, 2),
            "is_limited_by_budget": (derived.get("search_budget_lost_impression_share_pct") or 0) > 10.0
        },
        "product_context": product_context,
        "thresholds": thresholds,
        "analysis_date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "generated_at_local": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "signals": summary["signals"],
        "segment_data_raw": segment_data_raw
    }

    return payload

# ---------------------------------------------------------------------
# ENRICHMENT & MAIN
# ---------------------------------------------------------------------
def enrich_all_campaigns(all_results: Dict[str, Dict], product_contexts: Dict[str, Dict] = None) -> Dict[str, Any]:
    campaigns, account_level = organize_results_by_campaign(all_results)
    
    core_rows = all_results.get("campaign_core", {}).get("data", [])
    valid_ids = {str(r.get("campaign.id")) for r in core_rows}
    campaigns = {cid: c for cid, c in campaigns.items() if cid in valid_ids}

    if product_contexts is None:
        product_contexts = {}

    enriched = {}
    saved = []

    for cid, cinfo in campaigns.items():
        try:
            pc_input = product_contexts.get(cid, DEFAULT_PRODUCT_CONTEXT.copy())
            payload = build_canonical_payload(cinfo, account_level, pc_input)
            enriched[cid] = {"payload": payload}

            name = cinfo.get("name") or f"campaign_{cid}"
            safe_name = sanitize_filename(name)
            dir_path = os.path.join(OUTPUT_DIR, safe_name)
            os.makedirs(dir_path, exist_ok=True)
            path = save_json({"payload": payload}, f"{safe_name}_enriched.json", dir_path)
            saved.append(path)

            if PRINT_PROGRESS:
                print(f"Campaign {cid} ({name}): Ready -> {safe_name}_enriched.json")
        except Exception as e:
            print(f"Error enriching {cid}: {e}")
            import traceback; traceback.print_exc()
            enriched[cid] = {"error": str(e)}

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "customer_id": TEST_CUSTOMER_ID,
        "campaign_count": len(campaigns),
        "saved_paths": saved,
        "enriched_campaigns": enriched
    }

def main():
    print("=" * 80)
    print("Google Ads -> LLM-Ready Pipeline")
    print("=" * 80)

    # Example: Inject specific contexts if known
    product_contexts = {
        # "123456789": {"avg_order_value_low": 250, "avg_order_value_high": 350, "conversion_value_is_revenue": True}
    }

    all_results = {}
    if LAZY_FETCH and os.path.exists(os.path.join(OUTPUT_DIR, "raw_data.json")):
        all_results = load_json(os.path.join(OUTPUT_DIR, "raw_data.json"))
        print("Loaded raw data from disk.")
    else:
        print("Fetching from Google Ads API...")
        client = GoogleAdsAPIClient(DEVELOPER_TOKEN, MCC_ID, CLIENT_SECRET_PATH, REFRESH_TOKEN_PATH)
        for key, defn in QUERY_DEFINITIONS.items():
            if PRINT_PROGRESS:
                print(f"  Querying: {defn['name']} ...", end=" ")
            res = client.execute_query(TEST_CUSTOMER_ID, defn["query"])
            all_results[key] = res
            if PRINT_PROGRESS:
                print("Done" if res.get("success") else f"Failed: {res.get('error')}")
        
        if not LAZY_FETCH:
            save_json(all_results, "raw_data.json")

    print("\nEnriching...")
    result = enrich_all_campaigns(all_results, product_contexts)

    print("\n" + "=" * 80)
    print(f"DONE. Processed {result['campaign_count']} campaigns.")
    print(f"Output: {OUTPUT_DIR}/[campaign_name]/")
    print("=" * 80)

if __name__ == "__main__":
    main()