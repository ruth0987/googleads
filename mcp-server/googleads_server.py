import json
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from mcp.server.fastmcp import FastMCP

# --------------------------------------------------------------------------
# HARDCODED CONFIG
# --------------------------------------------------------------------------
MCC_ID = "8265069948"
DEVELOPER_TOKEN = "AXYmsdVBkpQyeWdhf0NsQA"
CLIENT_SECRET_PATH = "/Users/ruthwikreddy/Documents/langchain/client_secret_2_284506040555-81h9foakpnq3nl8ridpt4ea6m6f12dfo.apps.googleusercontent.com (1).json"
REFRESH_TOKEN_PATH = "refresh_token_1.txt"
TEST_CUSTOMER_ID = "1411274245"

# --------------------------------------------------------------------------
# HELPERS
# --------------------------------------------------------------------------

def get_date_range_for_period(period: str) -> tuple[str, str]:
    """Returns (start_date, end_date) in YYYY-MM-DD format."""
    today = datetime.now()
    if period == "last_7_days":
        end = today - timedelta(days=1)
        start = end - timedelta(days=6)
    elif period == "last_30_days":
        end = today - timedelta(days=1)
        start = end - timedelta(days=29)
    elif period == "previous_7_days":
        end = today - timedelta(days=8)
        start = end - timedelta(days=6)
    elif period == "previous_30_days":
        end = today - timedelta(days=31)
        start = end - timedelta(days=29)
    else:
        # Default to last 30
        end = today - timedelta(days=1)
        start = end - timedelta(days=29)
    
    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")

def get_previous_period_dates(start_date: str, end_date: str) -> tuple[str, str]:
    """Calculates the previous period of the same length."""
    s = datetime.strptime(start_date, "%Y-%m-%d")
    e = datetime.strptime(end_date, "%Y-%m-%d")
    delta = (e - s).days + 1
    prev_e = s - timedelta(days=1)
    prev_s = prev_e - timedelta(days=delta - 1)
    return prev_s.strftime("%Y-%m-%d"), prev_e.strftime("%Y-%m-%d")


# --------------------------------------------------------------------------
# QUERY TEMPLATES
# --------------------------------------------------------------------------
QUERY_TEMPLATES = {
    "campaign_overview": """
        SELECT 
            campaign.id,
            campaign.name,
            campaign.status,
            campaign.advertising_channel_type,
            campaign_budget.amount_micros,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """,
    
    "keyword_performance": """
        SELECT 
            campaign.name,
            ad_group.name,
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.quality_score
        FROM keyword_view
        WHERE segments.date DURING {date_range}
            AND metrics.impressions > 0
        ORDER BY metrics.clicks DESC
    """,
    
    "ad_performance": """
        SELECT 
            campaign.name,
            ad_group.name,
            ad_group_ad.ad.id,
            ad_group_ad.ad.type,
            ad_group_ad.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr
        FROM ad_group_ad
        WHERE segments.date DURING {date_range}
            AND ad_group_ad.status = 'ENABLED'
        ORDER BY metrics.impressions DESC
    """,
    
    "search_terms": """
        SELECT 
            campaign.name,
            ad_group.name,
            search_term_view.search_term,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr
        FROM search_term_view
        WHERE segments.date DURING {date_range}
        ORDER BY metrics.clicks DESC
    """,
    
    "geographic_performance": """
        SELECT 
            geographic_view.country_criterion_id,
            geographic_view.location_type,
            campaign.name,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr
        FROM geographic_view
        WHERE segments.date DURING {date_range}
        ORDER BY metrics.conversions DESC
    """,
    
    "device_performance": """
        SELECT 
            campaign.name,
            segments.device,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr,
            metrics.average_cpc
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
        ORDER BY metrics.cost_micros DESC
    """,
    
    "hourly_performance": """
        SELECT 
            campaign.name,
            segments.hour,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.ctr
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
        ORDER BY segments.hour
    """,
    
    "budget_analysis": """
        SELECT 
            campaign.id,
            campaign.name,
            campaign_budget.amount_micros,
            campaign_budget.delivery_method,
            campaign_budget.explicitly_shared,
            metrics.cost_micros,
            metrics.impressions,
            metrics.clicks
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
        ORDER BY campaign_budget.amount_micros DESC
    """,
    
    "conversion_analysis": """
        SELECT 
            campaign.name,
            segments.conversion_action_name,
            metrics.conversions,
            metrics.conversions_value,
            metrics.cost_per_conversion,
            metrics.conversions_from_interactions_rate
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
            AND metrics.conversions > 0
        ORDER BY metrics.conversions_value DESC
    """
}

# --------------------------------------------------------------------------
# GOOGLE ADS CLIENT
# --------------------------------------------------------------------------
class GoogleAdsAPIClient:
    def __init__(self, developer_token, mcc_id, client_secret_path, refresh_token_path):
        self.developer_token = developer_token
        self.mcc_id = mcc_id
        self.client_secret_path = client_secret_path
        self.refresh_token_path = refresh_token_path
        self.client = None

    def _ensure_client(self):
        """Initialize the Google Ads client if not already initialized."""
        if self.client:
            return
        try:
            with open(self.refresh_token_path, "r") as f:
                refresh_token = f.read().strip()
            with open(self.client_secret_path, "r") as f:
                data = json.load(f)
                key = "installed" if "installed" in data else "web"
            
            config = {
                "developer_token": self.developer_token,
                "client_id": data[key]["client_id"],
                "client_secret": data[key]["client_secret"],
                "refresh_token": refresh_token,
                "login_customer_id": self.mcc_id,
                "use_proto_plus": True,
            }
            self.client = GoogleAdsClient.load_from_dict(config)
        except Exception as e:
            raise Exception(f"Failed to initialize Google Ads client: {str(e)}")

    def execute_query(self, customer_id: str, query: str,   limit: int = 200) -> Dict[str, Any]:
        """Execute a GAQL query and return structured results."""
        try:
            self._ensure_client()
            ga_service = self.client.get_service("GoogleAdsService")
            
            # Add LIMIT if not present
            if "LIMIT" not in query.upper():
                query += f" LIMIT {limit}"
            
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            data = []
            for batch in stream:
                for row in batch.results:
                    data.append(self._parse_message(row))
            
            return {
                "success": True, 
                "data": data, 
                "row_count": len(data),
                "query": query,
                "customer_id": customer_id
            }
        except GoogleAdsException as ex:
            error_details = {
                "error_code": ex.error.code().name if hasattr(ex.error, 'code') else "UNKNOWN",
                "message": ex.failure.errors[0].message if ex.failure.errors else str(ex),
                "trigger": ex.failure.errors[0].trigger.string_value if ex.failure.errors and hasattr(ex.failure.errors[0], 'trigger') else None
            }
            return {
                "success": False, 
                "error": str(ex),
                "error_details": error_details,
                "query": query
            }
        except Exception as e:
            return {
                "success": False, 
                "error": str(e),
                "query": query
            }

    def _parse_message(self, message):
        """Recursively parse protobuf message to dict."""
        result = {}
        for field in message._pb.ListFields():
            name = field[0].name
            value = field[1]
            if hasattr(value, "_pb"):
                result[name] = self._parse_message(value)
            else:
                result[name] = str(value)
        return result

    def get_accessible_customers(self) -> Dict[str, Any]:
        """Get list of all accessible customer accounts."""
        try:
            self._ensure_client()
            customer_service = self.client.get_service("CustomerService")
            accessible_customers = customer_service.list_accessible_customers()
            return {
                "success": True,
                "customer_ids": list(accessible_customers.resource_names)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}


# Initialize the Google Ads client
ads_client = GoogleAdsAPIClient(
    developer_token=DEVELOPER_TOKEN,
    mcc_id=MCC_ID,
    client_secret_path=CLIENT_SECRET_PATH,
    refresh_token_path=REFRESH_TOKEN_PATH
)

# --------------------------------------------------------------------------
# FASTMCP SERVER
# --------------------------------------------------------------------------
mcp = FastMCP("Google Ads MCP")

# --------------------------------------------------------------------------
# CORE TOOLS
# --------------------------------------------------------------------------

@mcp.tool()
def list_accessible_accounts() -> Dict[str, Any]:
    """
    List all Google Ads accounts accessible under the configured MCC account.
    
    Returns:
        List of accessible customer IDs
    """
    return ads_client.get_accessible_customers()


@mcp.tool()
def get_account_info(customer_id: str = TEST_CUSTOMER_ID) -> Dict[str, Any]:
    """
    Get detailed information about a specific Google Ads account.
    
    Args:
        customer_id: Google Ads customer ID (without dashes)
    
    Returns:
        Account details (name, currency, timezone, descriptive name)
    """
    query = """
        SELECT 
            customer.id,
            customer.descriptive_name,
            customer.currency_code,
            customer.time_zone,
            customer.tracking_url_template,
            customer.auto_tagging_enabled,
            customer.optimization_score
        FROM customer
    """
    return ads_client.execute_query(customer_id, query, limit=1)


@mcp.tool()
def run_template_query(
    template_name: str,
    customer_id: str = TEST_CUSTOMER_ID,
    date_range: str = "LAST_30_DAYS",
    limit: int = 200
) -> Dict[str, Any]:
    """
    Execute a pre-defined query template with dynamic parameters.
    
    Available templates:
    - campaign_overview: Campaign metrics and performance
    - keyword_performance: Keyword-level metrics and quality scores
    - ad_performance: Ad-level performance data
    - search_terms: Search query performance
    - geographic_performance: Performance by location
    - device_performance: Performance by device type
    - hourly_performance: Performance by hour of day
    - budget_analysis: Budget allocation and spending
    - conversion_analysis: Conversion metrics and values
    
    Args:
        template_name: Name of the query template to execute
        customer_id: Google Ads customer ID (without dashes)
        date_range: Date range (e.g., LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH)
        limit: Maximum number of results
    
    Returns:
        Query results
    """
    if template_name not in QUERY_TEMPLATES:
        available = ", ".join(QUERY_TEMPLATES.keys())
        return {
            "success": False,
            "error": f"Unknown template: {template_name}",
            "available_templates": list(QUERY_TEMPLATES.keys())
        }
    
    query = QUERY_TEMPLATES[template_name].format(date_range=date_range)
    result = ads_client.execute_query(customer_id, query, limit)
    
    # Add metadata
    result["template_name"] = template_name
    result["date_range"] = date_range
    
    return result


@mcp.tool()
def execute_custom_query(
    query: str,
    customer_id: str = TEST_CUSTOMER_ID,
    limit: int = 200,
    validate: bool = True
) -> Dict[str, Any]:
    """
    Execute a custom GAQL query with validation and safety checks.
    
    Args:
        query: GAQL query string
        customer_id: Google Ads customer ID (without dashes)
        limit: Maximum number of results
        validate: Whether to validate the query before execution
    
    Returns:
        Query results
    """
    if validate:
        # Basic validation checks
        query_upper = query.upper()
        if "DELETE" in query_upper or "UPDATE" in query_upper or "INSERT" in query_upper:
            return {
                "success": False,
                "error": "Modification queries (DELETE, UPDATE, INSERT) are not allowed"
            }
        
        if "SELECT" not in query_upper:
            return {
                "success": False,
                "error": "Query must contain SELECT statement"
            }
        
        if "FROM" not in query_upper:
            return {
                "success": False,
                "error": "Query must contain FROM clause"
            }
    
    return ads_client.execute_query(customer_id, query, limit)


@mcp.tool()
def build_query(
    resource: str,
    fields: List[str],
    date_range: Optional[str] = "LAST_30_DAYS",
    filters: Optional[List[str]] = None,
    order_by: Optional[str] = None,
    limit: int = 200,
    customer_id: str = TEST_CUSTOMER_ID
) -> Dict[str, Any]:
    """
    Build and execute a GAQL query dynamically from components.
    
    Args:
        resource: Resource name (e.g., 'campaign', 'ad_group', 'keyword_view')
        fields: List of fields to select (e.g., ['campaign.name', 'metrics.clicks'])
        date_range: Date range filter (e.g., 'LAST_7_DAYS', 'THIS_MONTH')
        filters: Additional WHERE conditions (e.g., ['campaign.status = ENABLED'])
        order_by: Field to order by with direction (e.g., 'metrics.clicks DESC')
        limit: Maximum number of results
        customer_id: Google Ads customer ID
    
    Returns:
        Query results and the generated query
    """
    # Build SELECT clause
    select_clause = "SELECT " + ", ".join(fields)
    
    # Build FROM clause
    from_clause = f"FROM {resource}"
    
    # Build WHERE clause
    where_conditions = []
    if date_range:
        where_conditions.append(f"segments.date DURING {date_range}")
    if filters:
        where_conditions.extend(filters)
    
    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    
    # Build ORDER BY clause
    order_clause = f"ORDER BY {order_by}" if order_by else ""
    
    # Combine all parts
    query_parts = [select_clause, from_clause, where_clause, order_clause]
    query = " ".join(part for part in query_parts if part)
    
    result = ads_client.execute_query(customer_id, query, limit)
    result["generated_query"] = query
    
    return result


@mcp.tool()
def analyze_performance(
    customer_id: str = TEST_CUSTOMER_ID,
    date_range: str = "LAST_30_DAYS",
    min_impressions: int = 0
) -> Dict[str, Any]:
    """
    Get comprehensive performance analysis with calculated metrics.
    
    Args:
        customer_id: Google Ads customer ID
        date_range: Date range for analysis
        min_impressions: Minimum impressions threshold for filtering
    
    Returns:
        Analyzed performance data including ROI, ROAS, and recommendations
    """
    query = f"""
        SELECT 
            campaign.id,
            campaign.name,
            campaign.status,
            metrics.impressions,
            metrics.clicks,
            metrics.cost_micros,
            metrics.conversions,
            metrics.conversions_value,
            metrics.ctr,
            metrics.average_cpc,
            metrics.cost_per_conversion
        FROM campaign
        WHERE segments.date DURING {date_range}
            AND campaign.status != 'REMOVED'
            AND metrics.impressions >= {min_impressions}
        ORDER BY metrics.cost_micros DESC
    """
    
    result = ads_client.execute_query(customer_id, query)
    
    if not result.get("success"):
        return result
    
    # Calculate additional metrics
    analyzed_data = []
    for row in result["data"]:
        campaign_data = row.get("campaign", {})
        metrics = row.get("metrics", {})
        
        cost = float(metrics.get("cost_micros", 0)) / 1_000_000
        conversions_value = float(metrics.get("conversions_value", 0))
        conversions = float(metrics.get("conversions", 0))
        
        # Calculate ROI and ROAS
        roi = ((conversions_value - cost) / cost * 100) if cost > 0 else 0
        roas = (conversions_value / cost) if cost > 0 else 0
        
        analyzed_data.append({
            "campaign_id": campaign_data.get("id"),
            "campaign_name": campaign_data.get("name"),
            "status": campaign_data.get("status"),
            "impressions": int(metrics.get("impressions", 0)),
            "clicks": int(metrics.get("clicks", 0)),
            "cost": round(cost, 2),
            "conversions": round(conversions, 2),
            "conversions_value": round(conversions_value, 2),
            "ctr": round(float(metrics.get("ctr", 0)) * 100, 2),
            "avg_cpc": round(float(metrics.get("average_cpc", 0)), 2),
            "cost_per_conversion": round(float(metrics.get("cost_per_conversion", 0)), 2),
            "roi_percent": round(roi, 2),
            "roas": round(roas, 2)
        })
    
    return {
        "success": True,
        "date_range": date_range,
        "campaigns": analyzed_data,
        "count": len(analyzed_data)
    }


@mcp.tool()
def get_account_overview(
    customer_id: str = TEST_CUSTOMER_ID,
    period: str = "last_30_days"
) -> Dict[str, Any]:
    """
    High-level snapshot of account performance.
    Returns: Spend, clicks, conversions, CPA, CTR, ROAS for specified period vs previous period.
    """
    start_date, end_date = get_date_range_for_period(period)
    prev_start, prev_end = get_previous_period_dates(start_date, end_date)
    
    query = f"""
        SELECT 
            metrics.cost_micros, 
            metrics.clicks, 
            metrics.conversions, 
            metrics.ctr, 
            metrics.average_cpc, 
            metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
    """
    curr_result = ads_client.execute_query(customer_id, query)
    
    prev_query = f"""
        SELECT 
            metrics.cost_micros, 
            metrics.clicks, 
            metrics.conversions, 
            metrics.ctr, 
            metrics.average_cpc, 
            metrics.conversions_value
        FROM campaign
        WHERE segments.date BETWEEN '{prev_start}' AND '{prev_end}'
    """
    prev_result = ads_client.execute_query(customer_id, prev_query)
    
    def extract_metrics(res):
        if not res.get("success") or not res.get("data"):
            return {
                "spend": 0.0, "clicks": 0, "conversions": 0.0, 
                "cpa": 0.0, "ctr": 0.0, "roas": 0.0, "cpc": 0.0
            }
        
        # Aggregate across all campaigns
        total_cost = 0.0
        total_clicks = 0
        total_conv = 0.0
        total_conv_val = 0.0
        total_impressions = 0 # Need for weighted CTR/CPC if we had it, but let's just sum/avg simple
        
        for row in res["data"]:
            m = row.get("metrics", {})
            total_cost += float(m.get("cost_micros", 0))
            total_clicks += int(m.get("clicks", 0))
            total_conv += float(m.get("conversions", 0))
            total_conv_val += float(m.get("conversions_value", 0))
            
        cost_units = total_cost / 1_000_000
        return {
            "spend": round(cost_units, 2),
            "clicks": total_clicks,
            "conversions": round(total_conv, 2),
            "cpa": round(cost_units / total_conv, 2) if total_conv > 0 else 0.0,
            "roas": round(total_conv_val / cost_units, 2) if cost_units > 0 else 0.0,
            # For simplicity, we'll return aggregate-based CTR/CPC
            "clicks_per_conv": round(total_clicks / total_conv, 2) if total_conv > 0 else 0.0
        }

    curr_m = extract_metrics(curr_result)
    prev_m = extract_metrics(prev_result)
    
    return {
        "current_period": {"start": start_date, "end": end_date, "metrics": curr_m},
        "previous_period": {"start": prev_start, "end": prev_end, "metrics": prev_m},
        "period_type": period
    }


@mcp.tool()
def list_campaigns(
    customer_id: str = TEST_CUSTOMER_ID,
    status: Optional[str] = "ACTIVE",
    date_range: str = "LAST_30_DAYS"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Browse account structure and campaign performance.
    Args:
        status: ACTIVE, PAUSED, or None for all
        date_range: DURING date_range or BETWEEN dates
    """
    status_filter = ""
    if status == "ACTIVE":
        status_filter = "AND campaign.status = 'ENABLED'"
    elif status == "PAUSED":
        status_filter = "AND campaign.status = 'PAUSED'"
        
    query = f"""
        SELECT 
            campaign.id, 
            campaign.name, 
            campaign.status, 
            metrics.cost_micros, 
            metrics.conversions, 
            metrics.cost_per_conversion
        FROM campaign
        WHERE segments.date DURING {date_range}
        {status_filter}
        AND campaign.status != 'REMOVED'
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    formatted = []
    for row in result["data"]:
        c = row["campaign"]
        m = row["metrics"]
        formatted.append({
            "id": c["id"],
            "name": c["name"],
            "status": c["status"],
            "spend": round(float(m.get("cost_micros", 0)) / 1_000_000, 2),
            "conversions": round(float(m.get("conversions", 0)), 2),
            "cpa": round(float(m.get("cost_per_conversion", 0)), 2)
        })
    return formatted


@mcp.tool()
def get_campaign_metrics(
    campaign_id: str,
    customer_id: str = TEST_CUSTOMER_ID,
    date_range: str = "LAST_30_DAYS"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Deep dive on one campaign with daily metrics.
    """
    query = f"""
        SELECT 
            segments.date,
            metrics.cost_micros,
            metrics.conversions,
            metrics.average_cpc,
            metrics.ctr,
            metrics.search_impression_share
        FROM campaign
        WHERE campaign.id = {campaign_id}
        AND segments.date DURING {date_range}
        ORDER BY segments.date ASC
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    formatted = []
    for row in result["data"]:
        m = row["metrics"]
        formatted.append({
            "date": row["segments"]["date"],
            "spend": round(float(m.get("cost_micros", 0)) / 1_000_000, 2),
            "conversions": round(float(m.get("conversions", 0)), 2),
            "cpc": round(float(m.get("average_cpc", 0)), 2),
            "ctr": round(float(m.get("ctr", 0)) * 100, 2),
            "impression_share": m.get("search_impression_share")
        })
    return formatted


@mcp.tool()
def list_ad_groups(
    campaign_id: str,
    customer_id: str = TEST_CUSTOMER_ID,
    date_range: str = "LAST_30_DAYS"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns ad group performance metrics for a specific campaign.
    """
    query = f"""
        SELECT 
            ad_group.id,
            ad_group.name,
            ad_group.status,
            metrics.cost_micros,
            metrics.conversions,
            metrics.cost_per_conversion
        FROM ad_group
        WHERE campaign.id = {campaign_id}
        AND segments.date DURING {date_range}
        AND ad_group.status != 'REMOVED'
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    formatted = []
    for row in result["data"]:
        ag = row["ad_group"]
        m = row["metrics"]
        formatted.append({
            "id": ag["id"],
            "name": ag["name"],
            "status": ag["status"],
            "spend": round(float(m.get("cost_micros", 0)) / 1_000_000, 2),
            "conversions": round(float(m.get("conversions", 0)), 2),
            "cpa": round(float(m.get("cost_per_conversion", 0)), 2)
        })
    return formatted


@mcp.tool()
def list_keywords(
    campaign_id: Optional[str] = None,
    ad_group_id: Optional[str] = None,
    customer_id: str = TEST_CUSTOMER_ID,
    date_range: str = "LAST_30_DAYS"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns keyword performance metrics.
    """
    filters = []
    if campaign_id: filters.append(f"campaign.id = {campaign_id}")
    if ad_group_id: filters.append(f"ad_group.id = {ad_group_id}")
    filter_str = " AND ".join(filters) if filters else "metrics.impressions > 0"
    
    query = f"""
        SELECT 
            ad_group_criterion.keyword.text,
            ad_group_criterion.keyword.match_type,
            metrics.cost_micros,
            metrics.clicks,
            metrics.conversions,
            metrics.cost_per_conversion
        FROM keyword_view
        WHERE {filter_str}
        AND segments.date DURING {date_range}
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    formatted = []
    for row in result["data"]:
        kw = row["ad_group_criterion"]["keyword"]
        m = row["metrics"]
        formatted.append({
            "keyword": kw["text"],
            "match_type": kw["match_type"],
            "spend": round(float(m.get("cost_micros", 0)) / 1_000_000, 2),
            "clicks": int(m.get("clicks", 0)),
            "conversions": round(float(m.get("conversions", 0)), 2),
            "cpa": round(float(m.get("cost_per_conversion", 0)), 2)
        })
    return formatted


@mcp.tool()
def get_search_terms(
    campaign_id: str,
    customer_id: str = TEST_CUSTOMER_ID,
    date_range: str = "LAST_30_DAYS"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns actual search queries and their performance.
    """
    query = f"""
        SELECT 
            search_term_view.search_term,
            metrics.cost_micros,
            metrics.conversions,
            metrics.clicks
        FROM search_term_view
        WHERE campaign.id = {campaign_id}
        AND segments.date DURING {date_range}
        AND metrics.clicks > 0
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    formatted = []
    for row in result["data"]:
        st = row["search_term_view"]
        m = row["metrics"]
        formatted.append({
            "search_term": st["search_term"],
            "spend": round(float(m.get("cost_micros", 0)) / 1_000_000, 2),
            "clicks": int(m.get("clicks", 0)),
            "conversions": round(float(m.get("conversions", 0)), 2)
        })
    return formatted


@mcp.tool()
def get_budget_status(
    customer_id: str = TEST_CUSTOMER_ID
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns budget health: campaigns hitting budget, lost impression share, and projected spend.
    """
    query = f"""
        SELECT 
            campaign.id,
            campaign.name,
            campaign_budget.amount_micros,
            metrics.cost_micros,
            metrics.search_budget_lost_impression_share
        FROM campaign
        WHERE campaign.status = 'ENABLED'
        AND segments.date DURING LAST_30_DAYS
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    formatted = []
    for row in result["data"]:
        c = row["campaign"]
        b = row["campaign_budget"]
        m = row["metrics"]
        
        daily_budget = float(b.get("amount_micros", 0)) / 1_000_000
        avg_daily_spend = (float(m.get("cost_micros", 0)) / 1_000_000) / 30
        lost_share = float(m.get("search_budget_lost_impression_share", 0))
        
        formatted.append({
            "campaign_name": c["name"],
            "daily_budget": round(daily_budget, 2),
            "avg_daily_spend": round(avg_daily_spend, 2),
            "budget_utilization": round((avg_daily_spend / daily_budget * 100), 2) if daily_budget > 0 else 0,
            "lost_impression_share_budget": round(lost_share * 100, 2),
            "is_limited_by_budget": lost_share > 0.1
        })
    return formatted


@mcp.tool()
def get_auction_insights(
    customer_id: str = TEST_CUSTOMER_ID,
    campaign_id: Optional[str] = None,
    date_range: str = "LAST_30_DAYS"
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Returns auction insights: competitor overlap, impression share, top-of-page rate.
    Uses campaign_search_term_insight or similar. 
    Note: Auction insights require specific data availability.
    """
    # Using auction_insight_search_term_view which is widely available in newer API versions
    query = f"""
        SELECT 
            auction_insight_search_term_view.competitor_domain,
            metrics.auction_insight_search_impression_share,
            metrics.auction_insight_search_overlap_rate,
            metrics.auction_insight_search_top_of_page_share
        FROM auction_insight_search_term_view
        WHERE segments.date DURING {date_range}
    """
    if campaign_id:
        query += f" AND campaign.id = {campaign_id}"
        
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    formatted = []
    for row in result["data"]:
        insight = row["auction_insight_search_term_view"]
        m = row["metrics"]
        formatted.append({
            "competitor": insight.get("competitor_domain"),
            "impression_share": round(float(m.get("auction_insight_search_impression_share", 0)) * 100, 2),
            "overlap_rate": round(float(m.get("auction_insight_search_overlap_rate", 0)) * 100, 2),
            "top_of_page_rate": round(float(m.get("auction_insight_search_top_of_page_share", 0)) * 100, 2)
        })
    return formatted


@mcp.tool()
def compare_periods(
    customer_id: str = TEST_CUSTOMER_ID,
    period_a: str = "last_7_days",
    period_b: str = "previous_7_days"
) -> Dict[str, Any]:
    """
    Compare two periods and return delta metrics.
    """
    def get_metrics(per):
        start, end = get_date_range_for_period(per)
        q = f"""
            SELECT metrics.cost_micros, metrics.clicks, metrics.conversions, metrics.conversions_value
            FROM campaign WHERE segments.date BETWEEN '{start}' AND '{end}'
        """
        res = ads_client.execute_query(customer_id, q)
        if not res.get("success") or not res.get("data"):
            return {"spend": 0, "clicks": 0, "conv": 0, "val": 0}
        
        total_spend = sum(float(r["metrics"].get("cost_micros", 0)) for r in res["data"]) / 1_000_000
        total_clicks = sum(int(r["metrics"].get("clicks", 0)) for r in res["data"])
        total_conv = sum(float(r["metrics"].get("conversions", 0)) for r in res["data"])
        total_val = sum(float(r["metrics"].get("conversions_value", 0)) for r in res["data"])
        
        return {
            "spend": total_spend,
            "clicks": total_clicks,
            "conv": total_conv,
            "val": total_val
        }
    
    mA = get_metrics(period_a)
    mB = get_metrics(period_b)
    
    deltas = {}
    for key in mA:
        valA = mA[key]
        valB = mB[key]
        diff = valA - valB
        pct = (diff / valB * 100) if valB > 0 else 0
        deltas[key] = {
            "current": round(valA, 2),
            "previous": round(valB, 2),
            "delta": round(diff, 2),
            "delta_percent": round(pct, 2),
            "direction": "↑" if diff > 0 else "↓" if diff < 0 else "→"
        }
    
    return {
        "period_a": period_a,
        "period_b": period_b,
        "comparisons": deltas
    }


@mcp.tool()
def detect_anomalies(
    customer_id: str = TEST_CUSTOMER_ID,
    lookback_days: int = 14
) -> Dict[str, Any]:
    """
    Automated checks for spend spikes, conversion drops, CTR drops, unusual CPC changes.
    Compares yesterday's performance to the average of last N days.
    """
    end_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=lookback_days + 1)).strftime("%Y-%m-%d")
    
    query = f"""
        SELECT 
            segments.date,
            metrics.cost_micros,
            metrics.conversions,
            metrics.clicks,
            metrics.impressions
        FROM campaign
        WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'
        AND campaign.status != 'REMOVED'
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success") or not result.get("data"):
        return {"status": "insufficient_data", "details": result.get("error")}
    
    # Aggregate by date
    daily_stats = {}
    for row in result["data"]:
        d = row["segments"]["date"]
        if d not in daily_stats:
            daily_stats[d] = {"cost": 0.0, "conv": 0.0, "clicks": 0, "imps": 0}
        
        m = row["metrics"]
        daily_stats[d]["cost"] += float(m.get("cost_micros", 0))
        daily_stats[d]["conv"] += float(m.get("conversions", 0))
        daily_stats[d]["clicks"] += int(m.get("clicks", 0))
        daily_stats[d]["imps"] += int(m.get("impressions", 0))
    
    sorted_dates = sorted(daily_stats.keys())
    if len(sorted_dates) < 3:
        return {"status": "insufficient_data", "dates_found": len(sorted_dates)}
    
    yesterday_date = sorted_dates[-1]
    history_dates = sorted_dates[:-1]
    
    yesterday_metrics = daily_stats[yesterday_date]
    
    def get_history_avg(key):
        vals = [daily_stats[d][key] for d in history_dates]
        return sum(vals) / len(vals) if vals else 0

    avg_cost = get_history_avg("cost")
    avg_conv = get_history_avg("conv")
    
    # Calculate CTR and CPC averages differently (weighted average)
    total_history_clicks = sum(daily_stats[d]["clicks"] for d in history_dates)
    total_history_imps = sum(daily_stats[d]["imps"] for d in history_dates)
    total_history_cost = sum(daily_stats[d]["cost"] for d in history_dates)
    
    avg_ctr = total_history_clicks / total_history_imps if total_history_imps > 0 else 0
    avg_cpc = total_history_cost / total_history_clicks if total_history_clicks > 0 else 0
    
    curr_cost = yesterday_metrics["cost"]
    curr_conv = yesterday_metrics["conv"]
    curr_ctr = yesterday_metrics["clicks"] / yesterday_metrics["imps"] if yesterday_metrics["imps"] > 0 else 0
    curr_cpc = yesterday_metrics["cost"] / yesterday_metrics["clicks"] if yesterday_metrics["clicks"] > 0 else 0
    
    anomalies = []
    if avg_cost > 0:
        spike = (curr_cost - avg_cost) / avg_cost
        if spike > 0.4: anomalies.append(f"Spend spike: {round(spike*100, 2)}% above average")
    
    if avg_conv > 0:
        drop = (curr_conv - avg_conv) / avg_conv
        if drop < -0.4: anomalies.append(f"Conversion drop: {round(drop*100, 2)}% below average")
        
    if avg_ctr > 0:
        ctr_drop = (curr_ctr - avg_ctr) / avg_ctr
        if ctr_drop < -0.3: anomalies.append(f"CTR drop: {round(ctr_drop*100, 2)}% below average")
        
    if avg_cpc > 0:
        cpc_change = (curr_cpc - avg_cpc) / avg_cpc
        if abs(cpc_change) > 0.3: anomalies.append(f"Unusual CPC change: {round(cpc_change*100, 2)}% deviation")

    return {
        "date": yesterday_date,
        "anomalies_found": len(anomalies) > 0,
        "anomalies": anomalies,
        "metrics": {
            "spend": round(curr_cost / 1_000_000, 2),
            "conversions": round(curr_conv, 2),
            "ctr": round(curr_ctr * 100, 4),
            "cpc": round(curr_cpc / 1_000_000, 2)
        }
    }

@mcp.tool()
def get_top_wasting_keywords(
    customer_id: str = TEST_CUSTOMER_ID,
    date_range: str = "LAST_30_DAYS",
    min_spend: float = 50.0
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Identifies keywords with high spend but zero conversions.
    """
    query = f"""
        SELECT 
            campaign.name,
            ad_group.name,
            ad_group_criterion.keyword.text,
            metrics.cost_micros,
            metrics.clicks,
            metrics.conversions
        FROM keyword_view
        WHERE metrics.conversions = 0
        AND segments.date DURING {date_range}
        ORDER BY metrics.cost_micros DESC
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    wasting = []
    for row in result["data"]:
        m = row["metrics"]
        spend = float(m.get("cost_micros", 0)) / 1_000_000
        if spend >= min_spend:
            wasting.append({
                "campaign": row["campaign"]["name"],
                "ad_group": row["ad_group"]["name"],
                "keyword": row["ad_group_criterion"]["keyword"]["text"],
                "spend": round(spend, 2),
                "clicks": int(m.get("clicks", 0))
            })
    return wasting

@mcp.tool()
def get_budget_issues(
    customer_id: str = TEST_CUSTOMER_ID
) -> Union[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Identifies campaigns that are limited by budget or have high lost impression share due to budget.
    """
    query = f"""
        SELECT 
            campaign.id,
            campaign.name,
            campaign_budget.amount_micros,
            metrics.search_budget_lost_impression_share,
            metrics.cost_micros
        FROM campaign
        WHERE campaign.status = 'ENABLED'
        AND segments.date DURING LAST_7_DAYS
        AND metrics.search_budget_lost_impression_share > 0.1
    """
    result = ads_client.execute_query(customer_id, query)
    if not result.get("success"): return result
    
    issues = []
    for row in result["data"]:
        m = row["metrics"]
        lost_share = float(m.get("search_budget_lost_impression_share", 0))
        issues.append({
            "campaign_name": row["campaign"]["name"],
            "lost_impression_share_budget": round(lost_share * 100, 2),
            "daily_budget": round(float(row["campaign_budget"].get("amount_micros", 0)) / 1_000_000, 2),
            "avg_daily_spend_last_7_days": round((float(m.get("cost_micros", 0)) / 1_000_000) / 7, 2)
        })
    return issues


# --------------------------------------------------------------------------
# RESOURCES
# --------------------------------------------------------------------------

@mcp.resource("google-ads://quick-start")
def quick_start_guide() -> str:
    """Quick start guide for Google Ads MCP."""
    return f"""
# Google Ads MCP - Quick Start Guide

## 🚀 Getting Started

### Current Configuration
- **MCC Account**: {MCC_ID}
- **Test Customer**: {TEST_CUSTOMER_ID}
- **Authentication**: OAuth with refresh token

### Basic Workflow
1. **List accounts**: `list_accessible_accounts()`
2. **Get account info**: `get_account_info(customer_id="...")`
3. **Run analysis**: `analyze_performance(customer_id="...")`

## 📊 Common Use Cases

### 1. Campaign Overview
```python
run_template_query(
    template_name="campaign_overview",
    customer_id="{TEST_CUSTOMER_ID}",
    date_range="LAST_7_DAYS"
)
```

### 2. Keyword Performance
```python
run_template_query(
    template_name="keyword_performance",
    customer_id="{TEST_CUSTOMER_ID}",
    date_range="LAST_30_DAYS"
)
```

### 3. Custom Query
```python
execute_custom_query(
    query='''
        SELECT campaign.name, metrics.clicks, metrics.cost_micros
        FROM campaign
        WHERE segments.date DURING LAST_7_DAYS
        ORDER BY metrics.clicks DESC
    ''',
    customer_id="{TEST_CUSTOMER_ID}"
)
```

### 4. Dynamic Query Building
```python
build_query(
    resource="campaign",
    fields=["campaign.name", "metrics.clicks", "metrics.impressions"],
    date_range="LAST_30_DAYS",
    filters=["campaign.status = ENABLED", "metrics.clicks > 100"],
    order_by="metrics.clicks DESC",
    customer_id="{TEST_CUSTOMER_ID}"
)
```

### 5. Performance Analysis with ROI
```python
analyze_performance(
    customer_id="{TEST_CUSTOMER_ID}",
    date_range="LAST_30_DAYS",
    min_impressions=1000
)
```


###recommendations 
 ```sql 
    SELECT
      recommendation.type,
      recommendation.campaign,
      recommendation.dismissed,
      recommendation.campaign_budget,
      recommendation.resource_name
    FROM recommendation
```
  
## 🎯 Available Templates
- `campaign_overview` - Overall campaign metrics
- `keyword_performance` - Keyword-level data with quality scores
- `ad_performance` - Ad-level performance
- `search_terms` - Search query analysis
- `geographic_performance` - Location-based metrics
- `device_performance` - Device breakdown
- `hourly_performance` - Hour-of-day analysis
- `budget_analysis` - Budget utilization
- `conversion_analysis` - Conversion tracking

## 📅 Date Ranges
- `TODAY`, `YESTERDAY`
- `LAST_7_DAYS`, `LAST_30_DAYS`
- `THIS_WEEK`, `LAST_WEEK`
- `THIS_MONTH`, `LAST_MONTH`
- `THIS_QUARTER`, `LAST_QUARTER`
- `THIS_YEAR`, `LAST_YEAR`
- Custom: `BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'`

## 💡 Tips
- Always filter by date to improve query performance
- Use LIMIT to prevent overwhelming results
- Test with small date ranges first
- Cost values are in micros (÷ 1,000,000 for dollars)
- Check error_details in failed responses for debugging
"""


@mcp.resource("google-ads://resources")
def available_resources() -> str:
    """Complete list of available Google Ads resources."""
    return """
# Google Ads API Resources

## 🎯 Campaign Level
- `campaign` - Campaign data and settings
- `campaign_budget` - Budget information
- `campaign_criterion` - Campaign-level targeting

## 📁 Ad Group Level
- `ad_group` - Ad group data
- `ad_group_ad` - Individual ads
- `ad_group_criterion` - Keywords and targeting

## 🔑 Keyword & Search
- `keyword_view` - Keyword performance
- `search_term_view` - Search query performance
- `keyword_plan` - Keyword planning data

## 📊 Analytics & Reporting
- `campaign_performance` - Campaign metrics
- `ad_group_performance` - Ad group metrics
- `keyword_performance` - Keyword metrics

## 🎯 Targeting
- `geographic_view` - Location performance
- `age_range_view` - Age demographic data
- `gender_view` - Gender demographic data
- `user_location_view` - User location data

## 📱 Device & Platform
- `device_view` - Device performance (mobile, desktop, tablet)
- `platform_view` - Platform breakdown

## ⏰ Time-based
- `hour_of_day_view` - Hourly performance
- `day_of_week_view` - Daily performance

## 💰 Conversion & Attribution
- `conversion_action` - Conversion actions
- `click_view` - Click-level data
- `call_view` - Call conversion data

## 🎨 Creative
- `ad_group_ad_asset_view` - Asset performance
- `asset` - Creative assets

## 📈 Optimization
- `recommendation` - Account recommendations
- `customer_negative_criterion` - Account-level negatives

## Common Field Patterns

### Campaign Fields
- `campaign.id`, `campaign.name`, `campaign.status`
- `campaign.advertising_channel_type`
- `campaign.bidding_strategy_type`
- `campaign.start_date`, `campaign.end_date`

### Metrics Fields
- `metrics.impressions`, `metrics.clicks`
- `metrics.cost_micros`, `metrics.conversions`
- `metrics.ctr`, `metrics.average_cpc`
- `metrics.conversions_value`, `metrics.cost_per_conversion`

### Segments Fields
- `segments.date`, `segments.week`, `segments.month`
- `segments.device`, `segments.hour`
- `segments.conversion_action_name`

"""


@mcp.resource("google-ads://gaql-advanced")
def gaql_advanced_guide() -> str:
    """Advanced GAQL techniques and best practices."""
    return """
# Advanced GAQL Techniques

## 🎯 Complex Filtering

### Multiple Conditions
```sql
WHERE campaign.status IN (ENABLED, PAUSED)
  AND metrics.impressions > 1000
  AND metrics.ctr > 0.01
  AND campaign.name LIKE '%Brand%'
```

### Date Filtering
```sql
-- Predefined ranges
WHERE segments.date DURING LAST_30_DAYS

-- Custom ranges
WHERE segments.date BETWEEN '2024-01-01' AND '2024-12-31'

-- Exclude dates
WHERE segments.date DURING LAST_30_DAYS
  AND segments.date NOT IN ('2024-12-25', '2024-01-01')
```

## 📊 Aggregation Patterns

### Campaign-level Aggregation
```sql
SELECT 
    campaign.name,
    SUM(metrics.impressions) as total_impressions,
    SUM(metrics.clicks) as total_clicks
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
GROUP BY campaign.name
```


## 🔍 Advanced Queries

### Top Spending Campaigns with Poor ROI
```sql
SELECT 
    campaign.name,
    metrics.cost_micros,
    metrics.conversions,
    metrics.conversions_value
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.cost_micros > 1000000
  AND metrics.conversions_value < metrics.cost_micros
ORDER BY metrics.cost_micros DESC
LIMIT 20
```

### High-Impression, Low-Click Keywords
```sql
SELECT 
    campaign.name,
    ad_group.name,
    ad_group_criterion.keyword.text,
    metrics.impressions,
    metrics.clicks,
    metrics.ctr
FROM keyword_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.impressions > 1000
  AND metrics.ctr < 0.01
ORDER BY metrics.impressions DESC
```

### Device Performance Comparison
```sql
SELECT 
    campaign.name,
    segments.device,
    metrics.impressions,
    metrics.clicks,
    metrics.conversions,
    metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.status = ENABLED
ORDER BY campaign.name, segments.device
```


### Geographic High-Value Analysis
```sql
SELECT 
    campaign.name,
    geographic_view.country_criterion_id,
    metrics.conversions_value,
    metrics.cost_micros,
    metrics.conversions
FROM geographic_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.conversions_value > 1000
ORDER BY metrics.conversions_value DESC
```

### Search Term Opportunity Analysis
```sql
SELECT 
    campaign.name,
    ad_group.name,
    search_term_view.search_term,
    metrics.impressions,
    metrics.clicks,
    metrics.conversions,
    metrics.cost_micros
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND metrics.clicks > 5
  AND metrics.conversions > 0
  AND search_term_view.status = 'ADDED'
ORDER BY metrics.conversions DESC
```

## ⚡ Performance Optimization

### Best Practices
1. **Always use date filters** - Reduces data scanned
2. **Limit result sets** - Use LIMIT clause
3. **Index-friendly filters** - Filter on status, IDs first
4. **Avoid wildcards at start** - `LIKE '%term'` is slow
5. **Use specific fields** - Don't SELECT * equivalent

### Efficient Date Filtering
```sql
-- Good: Uses predefined range
WHERE segments.date DURING LAST_30_DAYS

-- Also good: Specific date range
WHERE segments.date BETWEEN '2024-01-01' AND '2024-01-31'

-- Avoid: No date filter (slow!)
-- WHERE campaign.status = ENABLED
```

### Field Compatibility
Not all fields can be queried together. Check compatibility:
- Metrics require a date segment or resource-level query
- Some views have restricted field combinations
- Use validation tools or check API documentation

## 🛠️ Debugging Queries

### Common Errors
1. **INVALID_FIELD_NAME** - Check field spelling and compatibility
2. **FIELD_NOT_SEGMENTABLE** - Cannot use field with segments
3. **INCOMPATIBLE_FIELDS** - Fields cannot be queried together
4. **INVALID_DATE_RANGE** - Date format or range invalid

### Testing Strategy
```sql
-- Start simple
SELECT campaign.id, campaign.name FROM campaign LIMIT 10

-- Add date filter
SELECT campaign.id, campaign.name 
FROM campaign 
WHERE segments.date DURING LAST_7_DAYS 
LIMIT 10

-- Add metrics
SELECT campaign.name, metrics.impressions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
LIMIT 10

-- Add filters
SELECT campaign.name, metrics.impressions
FROM campaign
WHERE segments.date DURING LAST_7_DAYS
  AND campaign.status = ENABLED
  AND metrics.impressions > 0
LIMIT 10
```
"""


if __name__ == "__main__":
    mcp.run(transport="stdio")

