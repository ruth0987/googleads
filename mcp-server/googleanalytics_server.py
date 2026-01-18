# mcp_ga4_tools_optimized.py
import os
import pickle
from typing import List, Dict, Any
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import DateRange, Dimension, Metric, RunReportRequest
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

mcp = FastMCP(name="ga4-mcp")

# GA4 Configuration from .env
DEFAULT_PROPERTY_ID = os.getenv("GA4_PROPERTY_ID", "")

# Constants
VALID_DIMENSIONS = {
    "date", "country", "city", "deviceCategory", "browser", "pageTitle",
    "pagePath", "sessionSource", "sessionMedium", "eventName", "language",
    "region", "operatingSystem", "screenResolution", "landingPage"
}

VALID_METRICS = {
    "sessions", "totalUsers", "screenPageViews", "engagedSessions",
    "eventCount", "averageSessionDuration", "bounceRate", "conversions",
    "engagementRate", "newUsers", "activeUsers"
}

# Report Templates - Easily extendable
REPORT_TEMPLATES = {
    "traffic_sources": {
        "name": "Traffic Source Analysis",
        "description": "Analyze traffic by source, medium, and campaign",
        "dimensions": ["sessionSource", "sessionMedium", "country"],
        "metrics": ["sessions", "totalUsers", "conversions", "bounceRate"],
        "default_date_range": "30daysAgo"
    },
    "content_performance": {
        "name": "Content Performance",
        "description": "Top performing pages and content",
        "dimensions": ["pageTitle", "pagePath", "date"],
        "metrics": ["screenPageViews", "averageSessionDuration", "bounceRate"],
        "default_date_range": "7daysAgo"
    },
    "device_analytics": {
        "name": "Device & Browser Analytics",
        "description": "Performance by device, browser, and OS",
        "dimensions": ["deviceCategory", "browser", "operatingSystem"],
        "metrics": ["sessions", "engagementRate", "averageSessionDuration"],
        "default_date_range": "30daysAgo"
    },
    "geographic_insights": {
        "name": "Geographic Insights",
        "description": "User behavior by location",
        "dimensions": ["country", "city", "language"],
        "metrics": ["totalUsers", "sessions", "conversions"],
        "default_date_range": "30daysAgo"
    },
    "engagement_metrics": {
        "name": "User Engagement Metrics",
        "description": "Deep dive into user engagement",
        "dimensions": ["date", "deviceCategory"],
        "metrics": ["engagedSessions", "engagementRate", "averageSessionDuration", "bounceRate"],
        "default_date_range": "14daysAgo"
    },
    "landing_pages": {
        "name": "Landing Page Performance",
        "description": "Entry point analysis",
        "dimensions": ["landingPage", "sessionSource"],
        "metrics": ["sessions", "bounceRate", "conversions"],
        "default_date_range": "30daysAgo"
    },
    "event_tracking": {
        "name": "Event Tracking Report",
        "description": "Custom event performance",
        "dimensions": ["eventName", "date"],
        "metrics": ["eventCount", "totalUsers"],
        "default_date_range": "7daysAgo"
    },
    "conversion_funnel": {
        "name": "Conversion Funnel Analysis",
        "description": "Conversion paths and sources",
        "dimensions": ["sessionSource", "sessionMedium", "deviceCategory"],
        "metrics": ["sessions", "conversions", "engagedSessions"],
        "default_date_range": "30daysAgo"
    }
}


class GA4Client:
    """Google Analytics 4 client with lazy authentication."""
    
    def __init__(self, credentials_file: str, token_file: str = 'token.pickle'):
        self.credentials_file = credentials_file
        self.token_file = token_file
        self.scopes = ['https://www.googleapis.com/auth/analytics.readonly']
        self.credentials = None
        self.client = None

    def _ensure_client(self):
        """Lazy initialization - authenticate only when needed."""
        if self.client is not None:
            return
        
        try:
            # Load existing token
            if os.path.exists(self.token_file):
                with open(self.token_file, 'rb') as token:
                    self.credentials = pickle.load(token)

            # Refresh or create new credentials
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file(
                        self.credentials_file, 
                        self.scopes
                    )
                    self.credentials = flow.run_local_server(port=0)

                # Save token
                os.makedirs(os.path.dirname(self.token_file) or '.', exist_ok=True)
                with open(self.token_file, 'wb') as token:
                    pickle.dump(self.credentials, token)

            self.client = BetaAnalyticsDataClient(credentials=self.credentials)
            
        except FileNotFoundError:
            raise Exception(f"Credentials file not found: {self.credentials_file}")
        except Exception as e:
            raise Exception(f"Authentication failed: {str(e)}")

    def run_report(
        self, 
        property_id: str, 
        dimensions: List[str], 
        metrics: List[str], 
        start_date: str, 
        end_date: str, 
        limit: int,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Execute GA4 report request with auto-authentication."""
        try:
            self._ensure_client()
            
            request = RunReportRequest(
                property=property_id,
                dimensions=[Dimension(name=d) for d in dimensions],
                metrics=[Metric(name=m) for m in metrics],
                date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
                limit=limit,
                offset=offset
            )
            
            response = self.client.run_report(request=request)
            
            return {
                "success": True,
                "data": self._parse_response(response),
                "row_count": len(response.rows),
                "metadata": {
                    "date_range": f"{start_date} to {end_date}",
                    "dimensions": dimensions,
                    "metrics": metrics
                }
            }
            
        except Exception as e:
            error_msg = str(e)
            hint = "Check property ID and date formats"
            
            if "PERMISSION_DENIED" in error_msg:
                hint = "Property not accessible. Verify property ID and OAuth permissions."
            elif "INVALID_ARGUMENT" in error_msg:
                hint = "Invalid dimension/metric combination or date format."
            elif "RESOURCE_EXHAUSTED" in error_msg:
                hint = "API quota exceeded. Try reducing limit or date range."
            
            return {
                "success": False,
                "error": f"API request failed: {error_msg}",
                "hint": hint,
                "request_details": {
                    "property_id": property_id,
                    "date_range": f"{start_date} to {end_date}",
                    "dimensions": dimensions,
                    "metrics": metrics
                }
            }

    def _parse_response(self, response) -> List[Dict[str, str]]:
        """Parse GA4 API response into list of dictionaries."""
        data = []
        for row in response.rows:
            row_data = {}
            
            for i, dimension_value in enumerate(row.dimension_values):
                row_data[response.dimension_headers[i].name] = dimension_value.value
            
            for i, metric_value in enumerate(row.metric_values):
                row_data[response.metric_headers[i].name] = metric_value.value
            
            data.append(row_data)
        
        return data


# Initialize client
credentials_path = os.getenv('GA4_CREDENTIALS_PATH', 'credentials.json')
token_path = os.getenv('GA4_TOKEN_PATH', './tokens/token.pickle')

ga4_client = GA4Client(
    credentials_file=credentials_path,
    token_file=token_path
)


# ---------------- MCP TOOLS ---------------- #

@mcp.tool()
def fetch_basic_report(
    property_id: str = DEFAULT_PROPERTY_ID, 
    start_date: str = '30daysAgo', 
    end_date: str = 'today', 
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetch basic GA4 report with date, country, sessions, users, and pageviews.
    
    Args:
        property_id: GA4 property ID (e.g., "123456789" or "properties/123456789")
        start_date: Start date ("7daysAgo", "yesterday", "2024-01-01") [default: "30daysAgo"]
        end_date: End date (same formats) [default: "today"]
        limit: Max rows (1-500) [default: 100]
    
    Returns:
        Dict with report data or error details
    """
    # Inline validation
    errors = []
    
    # Normalize property ID
    pid = property_id.strip().replace("properties/", "")
    if not pid.isdigit():
        errors.append(f"Invalid property ID: '{property_id}'. Must be numeric.")
    normalized_prop_id = f"properties/{pid}"
    
    # Validate limit
    if not (1 <= limit <= 500):
        errors.append(f"Limit must be 1-500, got {limit}")
    
    if errors:
        return {
            "success": False,
            "errors": errors,
            "hint": "Use format '123456789' or 'properties/123456789'"
        }
    
    # Execute report
    return ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=["date", "country"],
        metrics=["sessions", "totalUsers", "screenPageViews"],
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


@mcp.tool()
def fetch_custom_report(
    dimensions: List[str],
    metrics: List[str],
    property_id: str = DEFAULT_PROPERTY_ID,
    start_date: str = '30daysAgo',
    end_date: str = 'today',
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetch custom GA4 report with specified dimensions and metrics.
    
    Args:
        property_id: GA4 property ID (e.g., "123456789")
        dimensions: Dimension names (e.g., ["date", "country", "deviceCategory"])
        metrics: Metric names (e.g., ["sessions", "totalUsers"])
        start_date: Start date ("7daysAgo", "2024-01-01") [default: "30daysAgo"]
        end_date: End date [default: "today"]
        limit: Max rows (1-500) [default: 100]
    
    Valid Dimensions: date, country, city, region, deviceCategory, browser, 
                      operatingSystem, pageTitle, pagePath, sessionSource, 
                      sessionMedium, eventName, language, screenResolution, landingPage
    
    Valid Metrics: sessions, totalUsers, newUsers, activeUsers, screenPageViews, 
                   engagedSessions, conversions, eventCount, averageSessionDuration, 
                   bounceRate, engagementRate
    
    Returns:
        Dict with report data or error details
    """
    # Inline validation
    errors = []
    
    # Property ID
    pid = property_id.strip().replace("properties/", "")
    if not pid.isdigit():
        errors.append(f"Invalid property ID: '{property_id}'")
    normalized_prop_id = f"properties/{pid}"
    
    # Dimensions
    invalid_dims = set(dimensions) - VALID_DIMENSIONS
    if invalid_dims:
        errors.append(f"Invalid dimensions: {sorted(invalid_dims)}")
        errors.append(f"Valid: {sorted(VALID_DIMENSIONS)}")
    if not dimensions:
        errors.append("At least one dimension required")
    
    # Metrics
    invalid_metrics = set(metrics) - VALID_METRICS
    if invalid_metrics:
        errors.append(f"Invalid metrics: {sorted(invalid_metrics)}")
        errors.append(f"Valid: {sorted(VALID_METRICS)}")
    if not metrics:
        errors.append("At least one metric required")
    
    # Limit
    if not (1 <= limit <= 500):
        errors.append(f"Limit must be 1-500, got {limit}")
    
    if errors:
        return {"success": False, "errors": errors}
    
    # Execute report
    return ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=dimensions,
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )


@mcp.tool()
def fetch_template_report(
    template_name: str,
    property_id: str = DEFAULT_PROPERTY_ID,
    start_date: str = None,
    end_date: str = 'today',
    limit: int = 100
) -> Dict[str, Any]:
    """
    Fetch a pre-configured report template.
    
    Templates provide common report configurations for quick analysis.
    Use list_report_templates() to see all available templates.
    
    Args:
        property_id: GA4 property ID (e.g., "123456789")
        template_name: Template name (e.g., "traffic_sources", "content_performance")
        start_date: Start date [default: template's default]
        end_date: End date [default: "today"]
        limit: Max rows (1-500) [default: 100]
    
    Returns:
        Dict with report data or error details
    """
    if template_name not in REPORT_TEMPLATES:
        return {
            "success": False,
            "error": f"Unknown template: '{template_name}'",
            "available_templates": list(REPORT_TEMPLATES.keys())
        }
    
    template = REPORT_TEMPLATES[template_name]
    if start_date is None:
        start_date = template["default_date_range"]
        
    pid = property_id.strip().replace("properties/", "")
    normalized_prop_id = f"properties/{pid}"
    
    res = ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=template["dimensions"],
        metrics=template["metrics"],
        start_date=start_date,
        end_date=end_date,
        limit=min(limit, 500)
    )
    if res.get("success"):
        res["template"] = {"name": template["name"], "description": template["description"]}
    return res

@mcp.tool()
def detect_anomalies(
    property_id: str = DEFAULT_PROPERTY_ID,
    lookback_days: int = 14
) -> Dict[str, Any]:
    """
    Detect performance anomalies in GA4 metrics (Users, Sessions, Bounce Rate).
    Compares yesterday's performance against the historical average.
    """
    pid = property_id.strip().replace("properties/", "")
    normalized_prop_id = f"properties/{pid}"
    
    # Yesterday is data[-1], History is data[:-1]
    res = ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=["date"],
        metrics=["sessions", "totalUsers", "bounceRate", "engagementRate"],
        start_date=f"{lookback_days+1}daysAgo",
        end_date="yesterday",
        limit=lookback_days + 1
    )
    
    if not res.get("success") or len(res.get("data", [])) < 3:
        return {"success": False, "error": "Insufficient data"}
        
    data = res["data"]
    # Sort by date to be sure
    data.sort(key=lambda x: x["date"])
    
    yesterday_metrics = data[-1]
    history = data[:-1]
    
    anomalies = []
    metrics_to_check = ["sessions", "totalUsers", "bounceRate", "engagementRate"]
    
    for m_name in metrics_to_check:
        history_vals = [float(day[m_name]) for day in history]
        avg = sum(history_vals) / len(history_vals)
        curr = float(yesterday_metrics[m_name])
        
        if avg > 0:
            diff_pct = (curr - avg) / avg
            # Thresholds: 40% for absolute metrics, 20% for rates
            threshold = 0.4 if m_name in ["sessions", "totalUsers"] else 0.2
            
            if abs(diff_pct) > threshold:
                direction = "up" if diff_pct > 0 else "down"
                anomalies.append({
                    "metric": m_name,
                    "avg": round(avg, 2),
                    "current": round(curr, 2),
                    "change_pct": round(diff_pct * 100, 2),
                    "severity": "high" if abs(diff_pct) > threshold * 2 else "medium"
                })
                
    return {
        "success": True,
        "date": yesterday_metrics["date"],
        "anomalies_found": len(anomalies) > 0,
        "anomalies": anomalies,
        "summary": "No major anomalies detected" if not anomalies else f"Found {len(anomalies)} anomalies"
    }

@mcp.tool()
def fetch_report_page(
    dimensions: List[str],
    metrics: List[str],
    property_id: str = DEFAULT_PROPERTY_ID,
    start_date: str = '30daysAgo',
    end_date: str = 'today',
    limit: int = 100,
    offset: int = 0
) -> Dict[str, Any]:
    """
    Fetch a specific page of a GA4 report using limit and offset.
    
    Args:
        property_id: GA4 property ID
        dimensions: List of dimensions
        metrics: List of metrics
        start_date: Start date
        end_date: End date
        limit: Number of rows per page
        offset: Number of rows to skip
    """
    pid = property_id.strip().replace("properties/", "")
    normalized_prop_id = f"properties/{pid}"
    
    return ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=dimensions,
        metrics=metrics,
        start_date=start_date,
        end_date=end_date,
        limit=limit,
        offset=offset
    )

@mcp.tool()
def get_account_overview(
    property_id: str = DEFAULT_PROPERTY_ID,
    start_date: str = '30daysAgo',
    end_date: str = 'today'
) -> Dict[str, Any]:
    """
    Get a high-level summary of account performance.
    Returns aggregated Users, Sessions, Views, Conversions, and Bounce Rate.
    """
    pid = property_id.strip().replace("properties/", "")
    normalized_prop_id = f"properties/{pid}"
    
    # Run report with no dimensions to get account-wide totals
    res = ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=[], 
        metrics=["totalUsers", "sessions", "screenPageViews", "conversions", "bounceRate", "engagementRate"],
        start_date=start_date,
        end_date=end_date,
        limit=1
    )
    
    if not res.get("success") or not res.get("data"):
        return res
        
    return {
        "success": True,
        "summary": res["data"][0],
        "metadata": res["metadata"]
    }

@mcp.tool()
def summarize_traffic_sources(
    property_id: str = DEFAULT_PROPERTY_ID,
    start_date: str = '30daysAgo',
    end_date: str = 'today',
    top_n: int = 10
) -> Dict[str, Any]:
    """
    Returns an aggregated summary of traffic sources.
    Groups smaller sources into 'Other' to keep context small.
    """
    pid = property_id.strip().replace("properties/", "")
    normalized_prop_id = f"properties/{pid}"
    
    res = ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=["sessionSource", "sessionMedium"],
        metrics=["sessions", "conversions", "engagementRate"],
        start_date=start_date,
        end_date=end_date,
        limit=100
    )
    
    if not res.get("success"):
        return res
        
    data = res["data"]
    # Sort by sessions
    data.sort(key=lambda x: int(x.get("sessions", 0)), reverse=True)
    
    top_sources = data[:top_n]
    other_sources = data[top_n:]
    
    if other_sources:
        other_sessions = sum(int(x.get("sessions", 0)) for x in other_sources)
        other_conversions = sum(int(x.get("conversions", 0)) for x in other_sources)
        top_sources.append({
            "sessionSource": "Other",
            "sessionMedium": "(mixed)",
            "sessions": str(other_sessions),
            "conversions": str(other_conversions),
            "engagementRate": "n/a"
        })
        
    return {
        "success": True,
        "top_sources": top_sources,
        "total_rows_original": len(data),
        "metadata": res["metadata"]
    }

@mcp.tool()
def summarize_page_performance(
    property_id: str = DEFAULT_PROPERTY_ID,
    start_date: str = '30daysAgo',
    end_date: str = 'today',
    top_n: int = 10
) -> Dict[str, Any]:
    """
    Returns an aggregated summary of page performance.
    Groups smaller pages into 'Other' to keep context small.
    """
    pid = property_id.strip().replace("properties/", "")
    normalized_prop_id = f"properties/{pid}"
    
    res = ga4_client.run_report(
        property_id=normalized_prop_id,
        dimensions=["pagePath"],
        metrics=["screenPageViews", "averageSessionDuration", "bounceRate"],
        start_date=start_date,
        end_date=end_date,
        limit=100
    )
    
    if not res.get("success"):
        return res
        
    data = res["data"]
    data.sort(key=lambda x: int(x.get("screenPageViews", 0)), reverse=True)
    
    top_pages = data[:top_n]
    other_pages = data[top_n:]
    
    if other_pages:
        other_views = sum(int(x.get("screenPageViews", 0)) for x in other_pages)
        top_pages.append({
            "pagePath": "Other",
            "screenPageViews": str(other_views),
            "averageSessionDuration": "n/a",
            "bounceRate": "n/a"
        })
        
    return {
        "success": True,
        "top_pages": top_pages,
        "total_rows_original": len(data),
        "metadata": res["metadata"]
    }


@mcp.tool()
def list_report_templates() -> Dict[str, Any]:
    """
    Get all available pre-configured report templates.
    
    Templates provide common report configurations that can be used
    with fetch_template_report() for quick analysis.
    
    Returns:
        Dict with list of templates and their configurations
    """
    templates = {}
    for key, config in REPORT_TEMPLATES.items():
        templates[key] = {
            "name": config["name"],
            "description": config["description"],
            "dimensions": config["dimensions"],
            "metrics": config["metrics"],
            "default_date_range": config["default_date_range"]
        }
    
    return {
        "success": True,
        "templates": templates,
        "count": len(templates)
    }


@mcp.tool()
def list_valid_dimensions() -> Dict[str, Any]:
    """Get all valid GA4 dimensions for custom reports."""
    return {
        "success": True,
        "dimensions": sorted(VALID_DIMENSIONS),
        "count": len(VALID_DIMENSIONS)
    }


@mcp.tool()
def list_valid_metrics() -> Dict[str, Any]:
    """Get all valid GA4 metrics for custom reports."""
    return {
        "success": True,
        "metrics": sorted(VALID_METRICS),
        "count": len(VALID_METRICS)
    }


# ---------------- MCP RESOURCES ---------------- #

@mcp.resource("ga4://reference")
def ga4_reference() -> str:
    """Complete reference guide for GA4 MCP tools."""
    return f"""
# GA4 MCP Tools - Quick Reference

## 🔧 Available Tools

1. **fetch_basic_report()** - Quick report: date, country, sessions, users, pageviews
2. **fetch_custom_report()** - Custom dimensions/metrics
3. **fetch_template_report()** - Pre-configured report templates
4. **list_report_templates()** - See all available templates
5. **list_valid_dimensions()** - Get all dimensions
6. **list_valid_metrics()** - Get all metrics

**Note**: Authentication is automatic - no manual auth needed!

---

## 📊 Dimensions ({len(VALID_DIMENSIONS)})
{', '.join(sorted(VALID_DIMENSIONS))}

## 📈 Metrics ({len(VALID_METRICS)})
{', '.join(sorted(VALID_METRICS))}

---

## 🆔 Property ID Format
- `"123456789"` (auto-converted to properties/123456789)
- `"properties/123456789"` (full format)

## 📅 Date Formats
**Relative**: "today", "yesterday", "7daysAgo", "30daysAgo"
**Absolute**: "2024-01-01" (YYYY-MM-DD)

---

## 🚀 Examples

### Using Templates (Recommended)
```python
# Quick traffic analysis
fetch_template_report(
    property_id="123456789",
    template_name="traffic_sources",
    start_date="7daysAgo"
)

# Content performance
fetch_template_report(
    property_id="123456789",
    template_name="content_performance"
)
```

### Custom Reports
```python
fetch_custom_report(
    property_id="123456789",
    dimensions=["sessionSource", "sessionMedium"],
    metrics=["sessions", "totalUsers"],
    start_date="7daysAgo"
)
```

---

⚠️ **Max 10,000 rows per request** | **Case-sensitive field names**
"""


@mcp.resource("ga4://templates")
def ga4_templates() -> str:
    """Detailed documentation of all report templates."""
    docs = "# GA4 Report Templates\n\n"
    docs += "Pre-configured reports for common analytics use cases.\n\n"
    docs += "---\n\n"
    
    for key, config in REPORT_TEMPLATES.items():
        docs += f"## {config['name']}\n"
        docs += f"**Template ID**: `{key}`\n\n"
        docs += f"**Description**: {config['description']}\n\n"
        docs += f"**Dimensions**: {', '.join(config['dimensions'])}\n\n"
        docs += f"**Metrics**: {', '.join(config['metrics'])}\n\n"
        docs += f"**Default Date Range**: {config['default_date_range']}\n\n"
        docs += "**Usage**:\n```python\n"
        docs += f"fetch_template_report(\n"
        docs += f"    property_id='123456789',\n"
        docs += f"    template_name='{key}'\n"
        docs += ")\n```\n\n"
        docs += "---\n\n"
    
    return docs


# ---------------- MCP PROMPTS ---------------- #

@mcp.prompt()
def traffic_analysis_prompt(property_id: str = DEFAULT_PROPERTY_ID, time_period: str = "last_week") -> str:
    """
    Generate a comprehensive traffic source analysis report.
    
    Args:
        property_id: GA4 property ID
        time_period: "last_week", "last_month", "last_quarter"
    """
    date_map = {
        "last_week": ("7daysAgo", "today"),
        "last_month": ("30daysAgo", "today"),
        "last_quarter": ("90daysAgo", "today")
    }
    
    start_date, end_date = date_map.get(time_period, ("7daysAgo", "today"))
    
    return f"""
Please generate a comprehensive traffic analysis report for property {property_id}.

1. First, call summarize_traffic_sources():
   - Time period: {start_date} to {end_date}

2. Analyze the results and provide:
   - Top traffic sources by sessions
   - Conversion efficiency by source
   - Key insights and recommendations

3. If more detail is needed for a specific source, use fetch_report_page() with appropriate filters.

4. Format the response as:
   - Executive summary (2-3 sentences)
   - Data table with key metrics
   - Insights and trends
   - Recommendations for optimization
"""


@mcp.prompt()
def content_audit_prompt(property_id: str = DEFAULT_PROPERTY_ID) -> str:
    """
    Generate a content performance audit.
    
    Args:
        property_id: GA4 property ID
    """
    return f"""
Please conduct a content performance audit for property {property_id}.

1. Call summarize_page_performance() for the last 30 days.

2. Analyze and identify:
   - Top pages by pageviews
   - Pages with highest bounce rate
   - Pages with best engagement
   - Underperforming pages that need optimization

3. If more detail is needed for specific page paths, use fetch_report_page().

4. Provide recommendations:
   - Which pages to optimize first
   - Content gaps to fill
   - SEO opportunities

Format as a prioritized action plan with specific page URLs.
"""


@mcp.prompt()
def mobile_optimization_prompt(property_id: str = DEFAULT_PROPERTY_ID) -> str:
    """
    Analyze mobile vs desktop performance.
    
    Args:
        property_id: GA4 property ID
    """
    return f"""
Please analyze mobile performance for property {property_id}.

1. Fetch the device_analytics template report (last 30 days)

2. Compare metrics across:
   - Desktop vs Mobile vs Tablet
   - Different browsers and operating systems
   - Engagement rate differences
   - Bounce rate comparison

3. Identify:
   - Mobile-specific issues (high bounce rate, low engagement)
   - Browser compatibility problems
   - Optimization opportunities

4. Provide actionable mobile optimization recommendations.
"""


@mcp.prompt()
def conversion_optimization_prompt(property_id: str = DEFAULT_PROPERTY_ID) -> str:
    """
    Generate conversion funnel analysis and optimization plan.
    
    Args:
        property_id: GA4 property ID
    """
    return f"""
Please analyze conversion performance for property {property_id}.

1. Fetch the conversion_funnel template report (last 30 days)

2. Analyze:
   - Conversion rate by traffic source
   - Device category impact on conversions
   - Best performing source/medium combinations
   - Drop-off points in the funnel

3. Calculate:
   - Overall conversion rate
   - Conversion rate by segment
   - ROI indicators per channel

4. Provide:
   - Quick wins for improving conversion rate
   - Long-term optimization strategy
   - Budget allocation recommendations
"""


@mcp.prompt()
def geographic_expansion_prompt(property_id: str = DEFAULT_PROPERTY_ID) -> str:
    """
    Analyze geographic opportunities for expansion.
    
    Args:
        property_id: GA4 property ID
    """
    return f"""
Please analyze geographic opportunities for property {property_id}.

1. Fetch the geographic_insights template report (last 90 days)

2. Identify:
   - Top performing countries/cities
   - Emerging markets (growing traffic)
   - Underserved regions with potential
   - Language preferences by region

3. Analyze:
   - User behavior differences by location
   - Conversion rates by country
   - Engagement patterns

4. Recommend:
   - Which markets to prioritize for expansion
   - Localization opportunities
   - Regional marketing strategies
"""


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("GA4 MCP Tools Server (with Templates & Prompts)")
    print("=" * 60)
    print(f"Credentials: {credentials_path}")
    print(f"Token: {token_path}")
    print(f"Dimensions: {len(VALID_DIMENSIONS)} | Metrics: {len(VALID_METRICS)}")
    print(f"Templates: {len(REPORT_TEMPLATES)}")
    print("=" * 60)
    print("Server starting... (authentication is automatic)")
    print("=" * 60)
    
    try:
        mcp.run(transport="stdio")
    except KeyboardInterrupt:
        print("\n\nServer stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\nFATAL ERROR: {e}")
        sys.exit(1)