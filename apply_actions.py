import os
import json
import logging
from typing import List, Dict, Any
from ads_updater import ActionOrchestrator
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = os.getenv("DATA_DIR", "google_ads_data_llm")
CUSTOMER_ID = os.getenv("GOOGLE_ADS_CUSTOMER_ID", "1411274245")
DRY_RUN = False # Set to False for live execution

def load_generated_actions() -> List[Dict[str, Any]]:
    """Finds and loads all actions_*.json files from the data directory."""
    all_actions = []
    
    if not os.path.exists(DATA_DIR):
        logger.error(f"Data directory {DATA_DIR} not found.")
        return []

    # Iterate through all campaign folders
    for camp_dir in os.listdir(DATA_DIR):
        full_path = os.path.join(DATA_DIR, camp_dir)
        if not os.path.isdir(full_path):
            continue
            
        # Find action files
        for filename in os.listdir(full_path):
            if filename.startswith("actions_") and filename.endswith(".json"):
                file_path = os.path.join(full_path, filename)
                try:
                    with open(file_path, "r") as f:
                        data = json.load(f)
                        # We expect a dict with an 'actions' list
                        if "actions" in data and isinstance(data["actions"], list):
                            all_actions.extend(data["actions"])
                            logger.info(f"Loaded {len(data['actions'])} actions from {filename}")
                except Exception as e:
                    logger.error(f"Failed to load {file_path}: {e}")
                    
    return all_actions

def execute_batch():
    """Executes all loaded actions using the ActionOrchestrator."""
    actions = load_generated_actions()
    
    if not actions:
        logger.warning("No actions found to execute.")
        return

    logger.info(f"🚀 Initializing Orchestrator (Dry Run: {DRY_RUN})")
    orchestrator = ActionOrchestrator(customer_id=CUSTOMER_ID, dry_run=DRY_RUN)
    
    results = {
        "success": 0,
        "failed": 0,
        "skipped": 0
    }

    print("\n" + "="*80)
    print(f"BATCH EXECUTION SUMMARY (Total Actions: {len(actions)})")
    print("="*80)

    for i, action in enumerate(actions, 1):
        resource_type = action.get("resource_type")
        action_type = action.get("action_type")
        resource_name = action.get("resource_name")
        
        # Skip error fallbacks or manual review markers
        if resource_type == "Manual Review" or action_type == "ERROR_FALLBACK":
            logger.warning(f"Skipping manual review item: {action.get('rationale')}")
            results["skipped"] += 1
            continue

        if resource_name == "MISSING_IN_DATA":
            logger.error(f"Cannot execute action {action_type} - resource name is missing.")
            results["failed"] += 1
            continue

        print(f"\n[{i:02d}] Targeting: {resource_name}")
        print(f"     Action: {action_type} on {resource_type}")
        print(f"     Rationale: {action.get('rationale')}")
        
        try:
            result_str = orchestrator.execute_action(action)
            print(f"     Result: {result_str}")
            
            if "❌" in result_str:
                results["failed"] += 1
            elif "⚠️" in result_str:
                results["skipped"] += 1
            else:
                results["success"] += 1
                
        except Exception as e:
            logger.error(f"Orchestrator error on action {i}: {e}")
            results["failed"] += 1

    print("\n" + "="*80)
    print(f"EXECUTION COMPLETE")
    print(f"Success: {results['success']}")
    print(f"Failed:  {results['failed']}")
    print(f"Skipped: {results['skipped']}")
    print("="*80)

if __name__ == "__main__":
    execute_batch()
