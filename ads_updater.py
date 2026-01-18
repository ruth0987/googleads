import os
import json
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from dotenv import load_dotenv
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.field_mask_pb2 import FieldMask

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# === CONFIGURATION ===
DEVELOPER_TOKEN = os.getenv("GOOGLE_ADS_DEVELOPER_TOKEN")
if not DEVELOPER_TOKEN:
    raise ValueError("GOOGLE_ADS_DEVELOPER_TOKEN environment variable is required")

MCC_ID = os.getenv("GOOGLE_ADS_MCC_ID", "8265069948")
CLIENT_SECRET_PATH = os.getenv("GOOGLE_ADS_CLIENT_SECRET_PATH")
if not CLIENT_SECRET_PATH:
    raise ValueError("GOOGLE_ADS_CLIENT_SECRET_PATH environment variable is required")

REFRESH_TOKEN_PATH = os.getenv("GOOGLE_ADS_REFRESH_TOKEN_PATH", str(Path(__file__).parent / "refresh_token_1.txt"))


class GoogleAdsClientWrapper:
    """Wrapper for Google Ads Client initialization."""
    
    @staticmethod
    def get_client() -> GoogleAdsClient:
        """Initialize and return the Google Ads API client."""
        try:
            with open(CLIENT_SECRET_PATH, "r") as f:
                secrets = json.load(f)
            
            with open(REFRESH_TOKEN_PATH, "r") as f:
                refresh_token = f.read().strip()
            
            config = {
                "developer_token": DEVELOPER_TOKEN,
                "client_id": secrets["installed"]["client_id"],
                "client_secret": secrets["installed"]["client_secret"],
                "refresh_token": refresh_token,
                "login_customer_id": MCC_ID,
                "use_proto_plus": True
            }
            
            return GoogleAdsClient.load_from_dict(config)
        except Exception as e:
            logger.error(f"Failed to initialize Google Ads Client: {e}")
            raise


class BaseUpdater:
    """Base class for all resource updaters containing shared logic."""
    
    SERVICE_CONFIG = {
        'CampaignService': 'mutate_campaigns',
        'CampaignBudgetService': 'mutate_campaign_budgets',
        'AdGroupService': 'mutate_ad_groups',
        'AdGroupCriterionService': 'mutate_ad_group_criteria',
        'CampaignCriterionService': 'mutate_campaign_criteria',
        'AdGroupAdService': 'mutate_ad_group_ads',
        'AssetGroupService': 'mutate_asset_groups',
        'AssetGroupListingGroupFilterService': 'mutate_asset_group_listing_group_filters',
        'CampaignSharedSetService': 'mutate_campaign_shared_sets',
    }
    
    def __init__(self, client: GoogleAdsClient, customer_id: str, dry_run: bool = False):
        self.client = client
        self.customer_id = customer_id.replace("-", "")
        self.dry_run = dry_run

    def _validate_fields(self, **fields) -> None:
        """Validate required fields are present and valid."""
        for name, value in fields.items():
            if value is None or value == "":
                raise ValueError(f"Required field '{name}' is missing or empty")
            
            # Type-specific validation
            if 'micros' in name and (isinstance(value, int) and value < 0):
                raise ValueError(f"{name} must be a positive integer, got: {value}")
            
            if 'resource_name' in name and not isinstance(value, str):
                raise ValueError(f"{name} must be a string")

    def _create_operation(self, service_key: str, op_type: str = "update"):
        """Create a service operation object."""
        op_class_name = f"{service_key}Operation"
        operation = self.client.get_type(op_class_name)
        
        if op_type == "update":
            return operation, operation.update
        elif op_type == "create":
            return operation, operation.create
        elif op_type == "remove":
            return operation, operation.remove
        return operation, None

    def _execute_with_mask(self, service_name: str, operation: Any, paths: List[str]) -> str:
        """Execute operation with FieldMask."""
        if self.dry_run:
            resource_name = getattr(operation.update, "resource_name", "NEW_RESOURCE")
            return f"[DRY RUN] Would execute {service_name} on {resource_name}. Changes: {paths}"

        try:
            if paths:
                self.client.copy_from(
                    operation.update_mask,
                    FieldMask(paths=paths)
                )

            service = self.client.get_service(service_name)
            method_name = self.SERVICE_CONFIG.get(service_name)
            mutate_method = getattr(service, method_name)
            
            response = mutate_method(
                customer_id=self.customer_id, 
                operations=[operation]
            )
            return f"✅ Success: {response.results[0].resource_name}"

        except GoogleAdsException as ex:
            error_msg = ex.failure.errors[0].message
            if "operation is not allowed for the given context" in error_msg:
                return f"⚠️ Skipped (Context Limit): {error_msg}"
            if "Mutates are not allowed" in error_msg:
                return f"⚠️ Skipped (Immutable): {error_msg}"
            return f"❌ API Error: {error_msg}"
        except Exception as ex:
            return f"❌ Exception: {str(ex)}"

    def _execute_create(self, service_name: str, operation: Any, description: str = "") -> str:
        """Standardized create operation execution."""
        if self.dry_run:
            return f"[DRY RUN] {description or f'Create on {service_name}'}"
        
        try:
            service = self.client.get_service(service_name)
            method_name = self.SERVICE_CONFIG.get(service_name)
            mutate_method = getattr(service, method_name)
            
            response = mutate_method(
                customer_id=self.customer_id, 
                operations=[operation]
            )
            return f"✅ Created: {response.results[0].resource_name}"
            
        except GoogleAdsException as ex:
            error_msg = ex.failure.errors[0].message
            if "operation is not allowed for the given context" in error_msg:
                return f"⚠️ Skipped (Context Limit): {error_msg}"
            if "Mutates are not allowed" in error_msg:
                return f"⚠️ Skipped (Immutable): {error_msg}"
            return f"❌ API Error: {error_msg}"
        except Exception as ex:
            return f"❌ Exception: {str(ex)}"


class CampaignUpdater(BaseUpdater):
    """Handles Campaign updates."""
    
    def update_status(self, resource_name: str, status: str) -> str:
        self._validate_fields(resource_name=resource_name, status=status)
        op, campaign = self._create_operation("Campaign")
        campaign.resource_name = resource_name
        campaign.status = self.client.enums.CampaignStatusEnum[status].value
        return self._execute_with_mask("CampaignService", op, ["status"])

    def set_target_cpa(self, resource_name: str, micros: int) -> str:
        self._validate_fields(resource_name=resource_name, target_cpa_micros=micros)
        op, campaign = self._create_operation("Campaign")
        campaign.resource_name = resource_name
        campaign.target_cpa.target_cpa_micros = micros
        return self._execute_with_mask("CampaignService", op, ["target_cpa.target_cpa_micros"])

    def set_target_roas(self, resource_name: str, value: float) -> str:
        self._validate_fields(resource_name=resource_name, target_roas=value)
        op, campaign = self._create_operation("Campaign")
        campaign.resource_name = resource_name
        campaign.target_roas.target_roas = value
        return self._execute_with_mask("CampaignService", op, ["target_roas.target_roas"])

    def set_bidding_strategy(self, resource_name: str, strategy_type: str) -> str:
        self._validate_fields(resource_name=resource_name, strategy_type=strategy_type)
        op, campaign = self._create_operation("Campaign")
        campaign.resource_name = resource_name
        strategy_enum = self.client.enums.BiddingStrategyTypeEnum[strategy_type].value
        campaign.bidding_strategy_type = strategy_enum
        return self._execute_with_mask("CampaignService", op, ["bidding_strategy_type"])

    def set_network_settings(self, resource_name: str, search: bool = True, partner: bool = False, content: bool = False) -> str:
        self._validate_fields(resource_name=resource_name)
        op, campaign = self._create_operation("Campaign")
        campaign.resource_name = resource_name
        campaign.network_settings.target_google_search = search
        campaign.network_settings.target_search_network = partner
        campaign.network_settings.target_content_network = content
        return self._execute_with_mask("CampaignService", op, [
            "network_settings.target_google_search",
            "network_settings.target_search_network",
            "network_settings.target_content_network"
        ])


class BudgetUpdater(BaseUpdater):
    """Handles Campaign Budget updates."""
    
    def set_amount(self, resource_name: str, micros: int) -> str:
        self._validate_fields(resource_name=resource_name, amount_micros=micros)
        op, budget = self._create_operation("CampaignBudget")
        budget.resource_name = resource_name
        budget.amount_micros = micros
        return self._execute_with_mask("CampaignBudgetService", op, ["amount_micros"])

    def set_delivery_method(self, resource_name: str, method: str) -> str:
        self._validate_fields(resource_name=resource_name, method=method)
        op, budget = self._create_operation("CampaignBudget")
        budget.resource_name = resource_name
        budget.delivery_method = self.client.enums.BudgetDeliveryMethodEnum[method].value
        return self._execute_with_mask("CampaignBudgetService", op, ["delivery_method"])


class AdGroupUpdater(BaseUpdater):
    """Handles Ad Group updates."""
    
    def update_status(self, resource_name: str, status: str) -> str:
        self._validate_fields(resource_name=resource_name, status=status)
        op, ag = self._create_operation("AdGroup")
        ag.resource_name = resource_name
        ag.status = self.client.enums.AdGroupStatusEnum[status].value
        return self._execute_with_mask("AdGroupService", op, ["status"])

    def set_cpc_bid(self, resource_name: str, micros: int) -> str:
        self._validate_fields(resource_name=resource_name, cpc_bid_micros=micros)
        op, ag = self._create_operation("AdGroup")
        ag.resource_name = resource_name
        ag.cpc_bid_micros = micros
        return self._execute_with_mask("AdGroupService", op, ["cpc_bid_micros"])
    
    def set_target_cpa(self, resource_name: str, micros: int) -> str:
        self._validate_fields(resource_name=resource_name, target_cpa_micros=micros)
        op, ag = self._create_operation("AdGroup")
        ag.resource_name = resource_name
        ag.target_cpa_micros = micros
        return self._execute_with_mask("AdGroupService", op, ["target_cpa_micros"])

    def set_cpv_bid(self, resource_name: str, micros: int) -> str:
        self._validate_fields(resource_name=resource_name, cpv_bid_micros=micros)
        op, ag = self._create_operation("AdGroup")
        ag.resource_name = resource_name
        ag.cpv_bid_micros = micros
        return self._execute_with_mask("AdGroupService", op, ["cpv_bid_micros"])
    
    def set_ad_rotation_mode(self, resource_name: str, mode: str) -> str:
        """mode: OPTIMIZE or ROTATE_FOREVER"""
        self._validate_fields(resource_name=resource_name, mode=mode)
        op, ag = self._create_operation("AdGroup")
        ag.resource_name = resource_name
        
        # Robust Enum lookup
        try:
            enum_val = self.client.enums.AdRotationModeEnum[mode].value
        except (AttributeError, KeyError):
            # Fallback to standard integers if Enum is inaccessible
            mode_map = {'OPTIMIZE': 2, 'ROTATE_FOREVER': 3}
            enum_val = mode_map.get(mode, 2)
            
        ag.ad_rotation_mode = enum_val
        return self._execute_with_mask("AdGroupService", op, ["ad_rotation_mode"])

class KeywordUpdater(BaseUpdater):
    """Handles Ad Group Criterion (Keyword) updates."""
    
    def update_status(self, resource_name: str, status: str) -> str:
        self._validate_fields(resource_name=resource_name, status=status)
        op, crit = self._create_operation("AdGroupCriterion")
        crit.resource_name = resource_name
        crit.status = self.client.enums.AdGroupCriterionStatusEnum[status].value
        return self._execute_with_mask("AdGroupCriterionService", op, ["status"])

    def set_cpc_bid(self, resource_name: str, micros: int) -> str:
        self._validate_fields(resource_name=resource_name, cpc_bid_micros=micros)
        op, crit = self._create_operation("AdGroupCriterion")
        crit.resource_name = resource_name
        crit.cpc_bid_micros = micros
        return self._execute_with_mask("AdGroupCriterionService", op, ["cpc_bid_micros"])

    def set_bid_modifier(self, resource_name: str, modifier: float) -> str:
        self._validate_fields(resource_name=resource_name, modifier=modifier)
        op, crit = self._create_operation("AdGroupCriterion")
        crit.resource_name = resource_name
        crit.bid_modifier = modifier
        return self._execute_with_mask("AdGroupCriterionService", op, ["bid_modifier"])

    def update_final_url(self, resource_name: str, url: str) -> str:
        self._validate_fields(resource_name=resource_name, url=url)
        op, crit = self._create_operation("AdGroupCriterion")
        crit.resource_name = resource_name
        crit.final_urls.append(url)
        return self._execute_with_mask("AdGroupCriterionService", op, ["final_urls"])

    def add_negative(self, ad_group_resource: str, text: str, match_type: str = "BROAD") -> str:
        self._validate_fields(ad_group_resource=ad_group_resource, text=text)
        op_obj, _ = self._create_operation("AdGroupCriterion", op_type="create")
        criterion = op_obj.create
        criterion.ad_group = ad_group_resource
        criterion.negative = True
        criterion.keyword.text = text
        criterion.keyword.match_type = self.client.enums.KeywordMatchTypeEnum[match_type].value
        return self._execute_create("AdGroupCriterionService", op_obj, f"Add negative '{text}' to {ad_group_resource}")


class CampaignTargetingUpdater(BaseUpdater):
    """Handles Campaign Criterion updates."""
    
    def _find_campaign_criterion(self, campaign_resource: str, device_type: str = None, location_id: str = None) -> Optional[str]:
        """Find existing campaign criterion resource name by device type or location ID."""
        try:
            service = self.client.get_service("CampaignCriterionService")
            ga_service = self.client.get_service("GoogleAdsService")
            
            # Extract campaign ID from resource name
            # Handle potential composite IDs (COMPOSITE:customers/123/campaigns/456:DEVICE:MOBILE)
            clean_rn = campaign_resource
            if clean_rn.startswith("COMPOSITE:"):
                clean_rn = clean_rn.split(":")[1]
            campaign_id = clean_rn.split("/")[-1]
            
            # Ensure campaign_id is numeric before querying GAQL
            if not campaign_id.isdigit():
                logger.debug(f"Skipping criterion search: {campaign_id} is not a valid numeric ID.")
                return None

            query = f"""
                SELECT
                    campaign_criterion.resource_name,
                    campaign_criterion.type,
                    campaign_criterion.device.type,
                    campaign_criterion.location.geo_target_constant
                FROM campaign_criterion
                WHERE campaign.id = {campaign_id}
                AND campaign_criterion.status != 'REMOVED'
            """
            
            if device_type:
                query += f" AND campaign_criterion.type = 'DEVICE'"
            elif location_id:
                query += f" AND campaign_criterion.type = 'LOCATION'"
            
            response = ga_service.search(customer_id=self.customer_id, query=query)
            
            for row in response:
                criterion = row.campaign_criterion
                if device_type:
                    if criterion.type_ == self.client.enums.CriterionTypeEnum.DEVICE:
                        device_enum = criterion.device.type_
                        # Handle both enum and string comparison
                        device_name = device_enum.name if hasattr(device_enum, 'name') else str(device_enum)
                        if device_name == device_type or str(device_enum) == device_type:
                            return criterion.resource_name
                elif location_id:
                    if criterion.type_ == self.client.enums.CriterionTypeEnum.LOCATION:
                        loc_const = criterion.location.geo_target_constant
                        if loc_const:
                            # Extract location ID from geoTargetConstants/{id} format
                            if "/" in str(loc_const):
                                loc_id = str(loc_const).split("/")[-1]
                            else:
                                loc_id = str(loc_const)
                            if loc_id == str(location_id):
                                return criterion.resource_name
            
            return None
        except Exception as e:
            logger.warning(f"Error finding campaign criterion: {e}")
            return None
    
    def _create_device_modifier(self, campaign_resource: str, device_type: str, modifier: float) -> str:
        """Create a new device bid modifier criterion."""
        op_obj, _ = self._create_operation("CampaignCriterion", op_type="create")
        criterion = op_obj.create
        criterion.campaign = campaign_resource
        criterion.device.type = self.client.enums.DeviceEnum[device_type].value
        criterion.bid_modifier = modifier
        return self._execute_create("CampaignCriterionService", op_obj, f"Create device modifier {device_type} = {modifier}")
    
    def _create_location_modifier(self, campaign_resource: str, location_id: str, modifier: float) -> str:
        """Create a new location bid modifier criterion."""
        op_obj, _ = self._create_operation("CampaignCriterion", op_type="create")
        criterion = op_obj.create
        criterion.campaign = campaign_resource
        criterion.location.geo_target_constant = f"geoTargetConstants/{location_id}"
        criterion.bid_modifier = modifier
        return self._execute_create("CampaignCriterionService", op_obj, f"Create location modifier {location_id} = {modifier}")
    
    def set_bid_modifier(self, resource_name: str, modifier: float) -> str:
        """Set bid modifier for an existing campaign criterion."""
        self._validate_fields(resource_name=resource_name, modifier=modifier)
        op, crit = self._create_operation("CampaignCriterion")
        crit.resource_name = resource_name
        crit.bid_modifier = modifier
        return self._execute_with_mask("CampaignCriterionService", op, ["bid_modifier"])
    
    def set_device_bid_modifier(self, campaign_resource: str, device_type: str, modifier: float) -> str:
        """Set device bid modifier - finds existing or creates new."""
        self._validate_fields(campaign_resource=campaign_resource, device_type=device_type, modifier=modifier)
        
        # Try to find existing device criterion
        existing_rn = self._find_campaign_criterion(campaign_resource, device_type=device_type)
        
        if existing_rn:
            # Update existing
            return self.set_bid_modifier(existing_rn, modifier)
        else:
            # Create new
            return self._create_device_modifier(campaign_resource, device_type, modifier)
    
    def set_location_bid_modifier(self, campaign_resource: str, location_id: str, modifier: float) -> str:
        """Set location bid modifier - finds existing or creates new."""
        self._validate_fields(campaign_resource=campaign_resource, location_id=location_id, modifier=modifier)
        
        # Try to find existing location criterion
        existing_rn = self._find_campaign_criterion(campaign_resource, location_id=location_id)
        
        if existing_rn:
            # Update existing
            return self.set_bid_modifier(existing_rn, modifier)
        else:
            # Create new
            return self._create_location_modifier(campaign_resource, location_id, modifier)

    def add_location_exclusion(self, campaign_resource: str, location_id: str) -> str:
        self._validate_fields(campaign_resource=campaign_resource, location_id=location_id)
        op_obj, _ = self._create_operation("CampaignCriterion", op_type="create")
        criterion = op_obj.create
        criterion.campaign = campaign_resource
        criterion.negative = True
        criterion.location.geo_target_constant = f"geoTargetConstants/{location_id}"
        return self._execute_create("CampaignCriterionService", op_obj, f"Exclude location {location_id}")

    def set_ad_schedule(self, campaign_resource: str, day: str, start_hour: int, end_hour: int, start_min: str = "ZERO", end_min: str = "ZERO") -> str:
        self._validate_fields(campaign_resource=campaign_resource, day=day)
        op_obj, _ = self._create_operation("CampaignCriterion", op_type="create")
        criterion = op_obj.create
        criterion.campaign = campaign_resource
        
        # Robust integer conversion
        try:
            criterion.ad_schedule.day_of_week = self.client.enums.DayOfWeekEnum[day].value
            criterion.ad_schedule.start_hour = int(start_hour if start_hour is not None else 0)
            criterion.ad_schedule.end_hour = int(end_hour if end_hour is not None else 24)
            criterion.ad_schedule.start_minute = self.client.enums.MinuteOfHourEnum[start_min or "ZERO"].value
            criterion.ad_schedule.end_minute = self.client.enums.MinuteOfHourEnum[end_min or "ZERO"].value
        except (ValueError, TypeError, KeyError) as e:
            return f"❌ Validation Error: Invalid schedule parameters ({e})"
            
        return self._execute_create("CampaignCriterionService", op_obj, f"Set Schedule {day} {start_hour}-{end_hour}")

    def add_negative_keyword(self, campaign_resource: str, text: str, match_type: str = "BROAD") -> str:
        self._validate_fields(campaign_resource=campaign_resource, text=text)
        op_obj, _ = self._create_operation("CampaignCriterion", op_type="create")
        criterion = op_obj.create
        criterion.campaign = campaign_resource
        criterion.negative = True
        criterion.keyword.text = text
        criterion.keyword.match_type = self.client.enums.KeywordMatchTypeEnum[match_type].value
        return self._execute_create("CampaignCriterionService", op_obj, f"Add negative '{text}'")

    def add_placement_exclusion(self, campaign_resource: str, url: str) -> str:
        self._validate_fields(campaign_resource=campaign_resource, url=url)
        op_obj, _ = self._create_operation("CampaignCriterion", op_type="create")
        criterion = op_obj.create
        criterion.campaign = campaign_resource
        criterion.negative = True
        criterion.placement.url = url
        return self._execute_create("CampaignCriterionService", op_obj, f"Exclude placement '{url}'")

    def add_id_exclusion(self, campaign_resource: str, exclusion_id: str, id_type: str = "TOPIC") -> str:
        # Generic for Topic, etc.
        self._validate_fields(campaign_resource=campaign_resource, exclusion_id=exclusion_id)
        op_obj, _ = self._create_operation("CampaignCriterion", op_type="create")
        criterion = op_obj.create
        criterion.campaign = campaign_resource
        criterion.negative = True
        if id_type == "TOPIC":
            criterion.topic.topic_constant = f"topicConstants/{exclusion_id}"
        return self._execute_create("CampaignCriterionService", op_obj, f"Exclude {id_type} '{exclusion_id}'")


class AdUpdater(BaseUpdater):
    """Handles Ad Group Ad updates."""
    
    def update_status(self, resource_name: str, status: str) -> str:
        self._validate_fields(resource_name=resource_name, status=status)
        op, ad = self._create_operation("AdGroupAd")
        ad.resource_name = resource_name
        ad.status = self.client.enums.AdGroupAdStatusEnum[status].value
        return self._execute_with_mask("AdGroupAdService", op, ["status"])


class AssetGroupUpdater(BaseUpdater):
    """Handles Asset Group updates."""
    
    def update_status(self, resource_name: str, status: str) -> str:
        self._validate_fields(resource_name=resource_name, status=status)
        op, ag = self._create_operation("AssetGroup")
        ag.resource_name = resource_name
        ag.status = self.client.enums.AssetGroupStatusEnum[status].value
        return self._execute_with_mask("AssetGroupService", op, ["status"])


class AssetGroupAssetUpdater(BaseUpdater):
    """Handles Asset Group Asset updates (Linkage between Asset and AssetGroup)."""
    
    def update_status(self, resource_name: str, status: str) -> str:
        self._validate_fields(resource_name=resource_name, status=status)
        op, aga = self._create_operation("AssetGroupAsset")
        aga.resource_name = resource_name
        
        # Robust Enum lookup
        try:
            enum_val = self.client.enums.AssetGroupAssetStatusEnum[status].value
        except (AttributeError, KeyError):
            status_map = {'ENABLED': 2, 'PAUSED': 3, 'REMOVED': 4}
            enum_val = status_map.get(status, 2)
            
        aga.status = enum_val
        return self._execute_with_mask("AssetGroupAssetService", op, ["status"])


class SharedSetUpdater(BaseUpdater):
    """Handles Shared Set attachments to Campaigns."""
    
    def attach_shared_set(self, campaign_resource: str, shared_set_resource: str) -> str:
        self._validate_fields(campaign_resource=campaign_resource, shared_set_resource=shared_set_resource)
        op_obj, _ = self._create_operation("CampaignSharedSet", op_type="create")
        css = op_obj.create
        css.campaign = campaign_resource
        css.shared_set = shared_set_resource
        return self._execute_create("CampaignSharedSetService", op_obj, f"Attach {shared_set_resource} to {campaign_resource}")

    def detach_shared_set(self, campaign_resource: str, shared_set_resource: str) -> str:
        # To detach, we need the resource_name of the CampaignSharedSet entity, NOT just the Campaign and Shared Set.
        # This usually requires a lookup. However, if we assume the standard format:
        # customers/{customer_id}/campaignSharedSets/{campaign_id}~{shared_set_id}
        # We can try to construct it.
        c_id = campaign_resource.split("/")[-1]
        s_id = shared_set_resource.split("/")[-1]
        css_rn = f"customers/{self.customer_id}/campaignSharedSets/{c_id}~{s_id}"
        
        op_obj, _ = self._create_operation("CampaignSharedSet", op_type="remove")
        op_obj.remove = css_rn
        return self._execute_with_mask("CampaignSharedSetService", op_obj, []) # Removal doesn't need mask but helper requires args


class ProductFilterUpdater(BaseUpdater):
    """Handles Listing Group Filters for PMax."""
    
    def _create_exclusion(self, asset_group: str, dimension_setup_func):
        op_obj, _ = self._create_operation("AssetGroupListingGroupFilter", op_type="create")
        filter_obj = op_obj.create
        filter_obj.asset_group = asset_group
        filter_obj.type_ = self.client.enums.ListingGroupFilterTypeEnum.UNIT_EXCLUDED
        dimension_setup_func(filter_obj.case_value)
        return op_obj

    def _exec_filter(self, op_obj, desc):
        return self._execute_create("AssetGroupListingGroupFilterService", op_obj, desc)

    def exclude_product_by_id(self, asset_group: str, value: str) -> str:
        self._validate_fields(asset_group=asset_group, value=value)
        op = self._create_exclusion(asset_group, lambda cv: setattr(cv.product_item_id, 'value', value))
        return self._exec_filter(op, f"Exclude product ID {value}")

    def exclude_product_by_brand(self, asset_group: str, value: str) -> str:
        self._validate_fields(asset_group=asset_group, value=value)
        op = self._create_exclusion(asset_group, lambda cv: setattr(cv.product_brand, 'value', value))
        return self._exec_filter(op, f"Exclude brand {value}")

    def exclude_product_by_category(self, asset_group: str, id_value: str) -> str:
        self._validate_fields(asset_group=asset_group, id_value=id_value)
        op = self._create_exclusion(asset_group, lambda cv: setattr(cv.product_category, 'category_id', int(id_value)))
        return self._exec_filter(op, f"Exclude category {id_value}")
    
    def exclude_product_by_condition(self, asset_group: str, condition: str) -> str:
        self._validate_fields(asset_group=asset_group, condition=condition)
        cond_enum = self.client.enums.ProductConditionEnum[condition].value
        op = self._create_exclusion(asset_group, lambda cv: setattr(cv.product_condition, 'condition', cond_enum))
        return self._exec_filter(op, f"Exclude condition {condition}")

    def exclude_product_by_custom_label(self, asset_group: str, index: int, value: str) -> str:
        self._validate_fields(asset_group=asset_group, value=value)
        def setup(cv):
            cv.product_custom_attribute.index = self.client.enums.ProductCustomAttributeIndexEnum[f"INDEX{index}"].value
            cv.product_custom_attribute.value = value
        op = self._create_exclusion(asset_group, setup)
        return self._exec_filter(op, f"Exclude Label{index} = {value}")


class ActionOrchestrator:
    """Routes actions to the correct specialized updater."""
    
    def __init__(self, customer_id: str, dry_run: bool = False):
        self.client = GoogleAdsClientWrapper.get_client()
        self.customer_id = customer_id
        self.dry_run = dry_run
        
        # Initialize Updaters
        self.campaign = CampaignUpdater(self.client, customer_id, dry_run)
        self.budget = BudgetUpdater(self.client, customer_id, dry_run)
        self.ad_group = AdGroupUpdater(self.client, customer_id, dry_run)
        self.keyword = KeywordUpdater(self.client, customer_id, dry_run)
        self.targeting = CampaignTargetingUpdater(self.client, customer_id, dry_run)
        self.ad = AdUpdater(self.client, customer_id, dry_run)
        self.asset_group = AssetGroupUpdater(self.client, customer_id, dry_run)
        self.asset_group_asset = AssetGroupAssetUpdater(self.client, customer_id, dry_run)
        self.shared_set = SharedSetUpdater(self.client, customer_id, dry_run)
        self.product_filter = ProductFilterUpdater(self.client, customer_id, dry_run)

    def execute_action(self, action: Dict[str, Any]) -> str:
        """Dispatch action to appropriate updater."""
        try:
            resource_type = action.get("resource_type")
            action_type = action.get("action_type")
            resource_name = action.get("resource_name")
            new_value = action.get("new_value") or action.get("new_suggested_value")

            # === PRE-PROCESS COMPOSITE IDs ===
            # Format: COMPOSITE:customers/123/campaigns/456:DEVICE:MOBILE
            # Format: COMPOSITE:customers/123/campaigns/456:LOC:1234
            if resource_name and resource_name.startswith("COMPOSITE:"):
                parts = resource_name.split(":")
                # Update action with extracted info for easier routing
                resource_name = parts[1] # The real RN
                action["resource_name"] = resource_name 
                
                if parts[2] == "DEVICE":
                    action["device_type"] = parts[3]
                elif parts[2] == "LOC":
                    action["location_id"] = parts[3]
                elif parts[2] == "SCHED":
                    action["day"] = parts[3]
                    # Only set if not already provided by LLM (allow override)
                    if "start_hour" not in action:
                        action["start_hour"] = int(parts[4])
                    if "end_hour" not in action:
                        # Default to 1 hour block if only one hour is in the ID
                        action["end_hour"] = int(parts[4]) + 1

            # === CAMPAIGN ===
            if resource_type == "CAMPAIGN":
                if action_type == "UPDATE_STATUS":
                    if new_value not in ["PAUSED", "ENABLED"]:
                        return f"❌ Validation Error: CAMPAIGN UPDATE_STATUS allows 'PAUSED' or 'ENABLED', got '{new_value}'."
                    return self.campaign.update_status(resource_name, new_value)
                elif action_type == "SET_TARGET_CPA":
                    return self.campaign.set_target_cpa(resource_name, int(new_value))
                elif action_type == "SET_TARGET_ROAS":
                    return self.campaign.set_target_roas(resource_name, float(new_value))
                elif action_type == "SET_BIDDING_STRATEGY":
                    return self.campaign.set_bidding_strategy(resource_name, new_value)
                elif action_type == "SET_NETWORK_SETTINGS":
                    # Handle both flat and nested (in new_value) settings
                    settings = new_value if isinstance(new_value, dict) else action
                    return self.campaign.set_network_settings(
                        resource_name, 
                        search=settings.get("target_google_search", True),
                        partner=settings.get("target_search_network", False),
                        content=settings.get("target_content_network", False)
                    )
                elif action_type == "SET_TARGET_CPV":
                    # Heuristic: Campaigns don't have Target CPV at the core, it's usually on AdGroups.
                    # Try to find Ad Groups for this campaign? 
                    # For now, if LLM hallucinated this on campaign, and it has an Ad Group, let's route it.
                    ag_rn = action.get("ad_group")
                    if ag_rn:
                        return self.ad_group.set_cpv_bid(ag_rn, int(new_value))
                    return f"❌ Error: SET_TARGET_CPV is usually an AD_GROUP action. Please specify 'ad_group'."
            
            # === BUDGET ===
            elif resource_type == "CAMPAIGN_BUDGET":
                if action_type == "SET_AMOUNT_MICROS":
                    return self.budget.set_amount(resource_name, int(new_value))
                elif action_type == "SET_DELIVERY_METHOD":
                    return self.budget.set_delivery_method(resource_name, new_value)
            
            # === AD GROUP ===
            elif resource_type == "AD_GROUP":
                if action_type == "UPDATE_STATUS":
                    return self.ad_group.update_status(resource_name, new_value)
                elif action_type == "SET_CPC_BID":
                    return self.ad_group.set_cpc_bid(resource_name, int(new_value))
                elif action_type == "SET_CPV_BID":
                    return self.ad_group.set_cpv_bid(resource_name, int(new_value))
                elif action_type == "SET_TARGET_CPA":
                    return self.ad_group.set_target_cpa(resource_name, int(new_value))
                elif action_type == "SET_AD_ROTATION_MODE":
                    return self.ad_group.set_ad_rotation_mode(resource_name, new_value)

            # === KEYWORDS / LISTING GROUPS (AD GROUP CRITERION) ===
            elif resource_type == "AD_GROUP_CRITERION":
                # Robustness: Check if LLM accidentally passed an Ad Group RN for a criterion action
                if resource_name and "/adGroups/" in resource_name and "/adGroupCriteria/" not in resource_name:
                    if action_type == "SET_CPC_BID":
                        return self.ad_group.set_cpc_bid(resource_name, int(new_value))
                    elif action_type == "SET_CPV_BID":
                        return self.ad_group.set_cpv_bid(resource_name, int(new_value))
                    elif action_type == "UPDATE_STATUS":
                        return self.ad_group.update_status(resource_name, new_value)
                    elif action_type == "SET_TARGET_CPA":
                        return self.ad_group.set_target_cpa(resource_name, int(new_value))

                if action_type == "UPDATE_STATUS":
                    return self.keyword.update_status(resource_name, new_value)
                elif action_type == "SET_CPC_BID":
                    return self.keyword.set_cpc_bid(resource_name, int(new_value))
                elif action_type == "SET_BID_MODIFIER":
                    return self.keyword.set_bid_modifier(resource_name, float(new_value))
                elif action_type == "ADD_NEGATIVE":
                    return self.keyword.add_negative(
                        action.get("ad_group"), 
                        action.get("keyword_text"), 
                        action.get("match_type", "BROAD")
                    )

            # === CAMPAIGN TARGETING ===
            elif resource_type == "CAMPAIGN_CRITERION":
                if action_type == "SET_BID_MODIFIER":
                    # Direct update of existing criterion
                    return self.targeting.set_bid_modifier(resource_name, float(new_value))
                elif action_type == "SET_DEVICE_BID_MODIFIER":
                    # Check if resource_name is a campaign criterion resource name or campaign resource name
                    if resource_name and "/campaignCriteria/" in resource_name:
                        # It's already a criterion resource name
                        return self.targeting.set_bid_modifier(resource_name, float(new_value))
                    else:
                        # It's a campaign resource name, need device_type
                        # HEURISTIC: Try to find device_type in rationale if missing
                        device_type = action.get("device_type")
                        if not device_type and action.get("rationale"):
                            rat = action.get("rationale").upper()
                            if "MOBILE" in rat: device_type = "MOBILE"
                            elif "DESKTOP" in rat: device_type = "DESKTOP"
                            elif "TABLET" in rat: device_type = "TABLET"

                        if not device_type:
                            return f"❌ Error: SET_DEVICE_BID_MODIFIER requires 'device_type' field (MOBILE, DESKTOP, TABLET)"
                        campaign_resource = resource_name or action.get("campaign")
                        if not campaign_resource:
                            return f"❌ Error: SET_DEVICE_BID_MODIFIER requires 'campaign' or valid 'resource_name'"
                        return self.targeting.set_device_bid_modifier(campaign_resource, device_type, float(new_value))
                elif action_type == "SET_LOCATION_BID_MODIFIER":
                    # Check if resource_name is a campaign criterion resource name or campaign resource name
                    if resource_name and "/campaignCriteria/" in resource_name:
                        # It's already a criterion resource name
                        return self.targeting.set_bid_modifier(resource_name, float(new_value))
                    else:
                        # It's a campaign resource name, need location_id
                        location_id = action.get("location_id")
                        campaign_resource = resource_name or action.get("campaign")
                        if not campaign_resource:
                            return f"❌ Error: SET_LOCATION_BID_MODIFIER requires 'campaign' or valid 'resource_name'"
                        return self.targeting.set_location_bid_modifier(campaign_resource, str(location_id), float(new_value))
                elif action_type == "ADD_NEGATIVE_KEYWORD":
                    campaign_resource = action.get("campaign") or resource_name
                    # HEURISTIC: Try to get text from new_value if missing
                    text = action.get("keyword_text") or action.get("new_value") or action.get("new_suggested_value")
                    return self.targeting.add_negative_keyword(
                        campaign_resource, 
                        str(text), 
                        action.get("match_type", "BROAD")
                    )
                elif action_type == "ADD_LOCATION_EXCLUSION":
                    campaign_resource = action.get("campaign") or resource_name
                    location_id = action.get("location_id") or action.get("new_value") or action.get("new_suggested_value")
                    return self.targeting.add_location_exclusion(
                        campaign_resource,
                        str(location_id)
                    )
                elif action_type == "SET_AD_SCHEDULE":
                    campaign_resource = action.get("campaign") or resource_name
                    # Ensure end_hour is at least start_hour + 1
                    sh = action.get("start_hour")
                    eh = action.get("end_hour")
                    if sh is not None and (eh is None or int(eh) <= int(sh)):
                        eh = int(sh) + 1
                    
                    return self.targeting.set_ad_schedule(
                        campaign_resource,
                        action.get("day"),
                        sh,
                        eh
                     )
                elif action_type == "ADD_PLACEMENT_EXCLUSION":
                    c_rn = action.get("campaign") or resource_name
                    raw_url = action.get("url")
                    if "," in raw_url:
                        # Handle multiple URLs
                        urls = [u.strip() for u in raw_url.split(",") if u.strip()]
                        results = []
                        for u in urls:
                            results.append(self.targeting.add_placement_exclusion(c_rn, u))
                        return "\n".join(results)
                    return self.targeting.add_placement_exclusion(c_rn, raw_url.strip())
                elif action_type == "ADD_TOPIC_EXCLUSION":
                    c_rn = action.get("campaign") or resource_name
                    return self.targeting.add_id_exclusion(c_rn, action.get("topic_constant_id"), "TOPIC")

            # === AD GROUP AD ===
            elif resource_type == "AD_GROUP_AD":
                if action_type == "UPDATE_STATUS":
                    return self.ad.update_status(resource_name, new_value)

            # === ASSET GROUP (PMAX) ===
            elif resource_type == "ASSET_GROUP":
                if action_type == "UPDATE_STATUS":
                    return self.asset_group.update_status(resource_name, new_value)

            # === PRODUCT FILTER ===
            elif resource_type == "ASSET_GROUP_LISTING_GROUP_FILTER":
                # HEURISTIC: If asset_group is missing, assume resource_name is the Asset Group (often happened in previous runs)
                ag = action.get("asset_group") or resource_name
                if action_type == "EXCLUDE_PRODUCT_BY_ID":
                    val = action.get("product_item_id") or action.get("new_value") or action.get("new_suggested_value")
                    return self.product_filter.exclude_product_by_id(ag, str(val))
                elif action_type == "EXCLUDE_PRODUCT_BY_BRAND":
                    val = action.get("brand") or action.get("new_value") or action.get("new_suggested_value")
                    return self.product_filter.exclude_product_by_brand(ag, str(val))
                elif action_type == "EXCLUDE_PRODUCT_BY_CATEGORY":
                    val = action.get("category_id") or action.get("new_value") or action.get("new_suggested_value")
                    return self.product_filter.exclude_product_by_category(ag, str(val))
                elif action_type == "EXCLUDE_PRODUCT_BY_CONDITION":
                    # HEURISTIC: If condition is missing, it might be in new_value
                    cond = action.get("condition") or action.get("new_value") or action.get("new_suggested_value")
                    return self.product_filter.exclude_product_by_condition(ag, str(cond))
                elif action_type == "EXCLUDE_PRODUCT_BY_CUSTOM_LABEL":
                    return self.product_filter.exclude_product_by_custom_label(ag, action.get("label_index"), action.get("label_value"))

            # === ASSET GROUP ASSET ===
            elif resource_type == "ASSET_GROUP_ASSET":
                if action_type in ["UPDATE_STATUS", "PAUSE_ASSET", "ENABLE_ASSET"]:
                    # Map PAUSE_ASSET -> PAUSED, ENABLE_ASSET -> ENABLED
                    status = new_value 
                    if action_type == "PAUSE_ASSET": status = "PAUSED"
                    if action_type == "ENABLE_ASSET": status = "ENABLED"
                    return self.asset_group_asset.update_status(resource_name, status)

            # === CAMPAIGN SHARED SET ===
            elif resource_type == "CAMPAIGN_SHARED_SET":
                c_rn = action.get("campaign") or resource_name
                ss_rn = action.get("shared_set")
                if action_type == "ATTACH_SHARED_SET":
                    return self.shared_set.attach_shared_set(c_rn, ss_rn)
                elif action_type == "DETACH_SHARED_SET":
                    return self.shared_set.detach_shared_set(c_rn, ss_rn)

            return f"⚠️ Warning: Unhandled resource/action type: {resource_type} / {action_type}"

        except ValueError as ve:
             return f"❌ Validation Error: {str(ve)}"
        except Exception as e:
            return f"❌ Error executing action: {str(e)}"

def micros_to_usd(micros: int) -> float:
    return micros / 1_000_000

def usd_to_micros(usd: float) -> int:
    return int(usd * 1_000_000)

class GoogleAdsUpdater:
    """Legacy wrapper for backward compatibility."""
    
    def __init__(self, customer_id: str, dry_run: bool = False):
        self.orchestrator = ActionOrchestrator(customer_id, dry_run)

    # Proxy methods delegating to specialized updaters
    def update_campaign_status(self, resource_name, status):
        return self.orchestrator.campaign.update_status(resource_name, status)
        
    def set_budget_amount(self, resource_name, amount_micros):
        return self.orchestrator.budget.set_amount(resource_name, amount_micros)

    def set_campaign_target_roas(self, resource_name, value):
        return self.orchestrator.campaign.set_target_roas(resource_name, value)

    def set_campaign_target_cpa(self, resource_name, micros):
        return self.orchestrator.campaign.set_target_cpa(resource_name, micros)

    def update_ad_group_status(self, resource_name, status):
        return self.orchestrator.ad_group.update_status(resource_name, status)

    def set_ad_group_cpc_bid(self, resource_name, micros):
        return self.orchestrator.ad_group.set_cpc_bid(resource_name, micros)

    def update_keyword_status(self, resource_name, status):
        return self.orchestrator.keyword.update_status(resource_name, status)

    def set_keyword_cpc_bid(self, resource_name, micros):
        return self.orchestrator.keyword.set_cpc_bid(resource_name, micros)

    def set_keyword_bid_modifier(self, resource_name, modifier):
        return self.orchestrator.keyword.set_bid_modifier(resource_name, modifier)

    def set_device_bid_modifier(self, campaign_resource, device_type, modifier):
        # Note: This is a simplification. Real implementation would need to find the criterion ID for the device.
        # For now, we'll assume resource_name is already the criterion resource name if provided.
        return self.orchestrator.targeting.set_bid_modifier(campaign_resource, modifier)

    def set_location_bid_modifier(self, resource_name, modifier):
        return self.orchestrator.targeting.set_bid_modifier(resource_name, modifier)

    def add_campaign_negative_keyword(self, campaign_resource, text, match_type="BROAD"):
        return self.orchestrator.targeting.add_negative_keyword(campaign_resource, text, match_type)

    def update_ad_status(self, resource_name, status):
        return self.orchestrator.ad.update_status(resource_name, status)

    def update_asset_group_status(self, resource_name, status):
        return self.orchestrator.asset_group.update_status(resource_name, status)

    def exclude_product_by_id(self, asset_group, product_id):
        return self.orchestrator.product_filter.exclude_product_by_id(asset_group, product_id)

    def exclude_product_by_brand(self, asset_group, brand):
        return self.orchestrator.product_filter.exclude_product_by_brand(asset_group, brand)

