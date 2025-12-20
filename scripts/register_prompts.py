#!/usr/bin/env python3
"""
Manual script to register prompts to MLflow.

This script registers all prompts from the PromptRegistry FALLBACK_PROMPTS
to MLflow. It can be run manually when you want to update prompts in MLflow.

Usage:
    python scripts/register_prompts.py              # Register only if prompts don't exist
    python scripts/register_prompts.py --force     # Force update existing prompts (creates new versions)
"""
import argparse
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.prompt_registry import PromptRegistry
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """Main function to register prompts."""
    parser = argparse.ArgumentParser(
        description='Register prompts to MLflow registry',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force update existing prompts (creates new versions)'
    )
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("MLflow Prompt Registration Script")
    print("=" * 60)
    print()
    
    # Initialize prompt registry
    try:
        registry = PromptRegistry()
        if registry._client is None:
            print("ERROR: MLflow client is not available.")
            print("Please ensure MLflow is properly configured and running.")
            sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to initialize PromptRegistry: {e}")
        sys.exit(1)
    
    # Get list of prompts to register
    prompts = registry.FALLBACK_PROMPTS
    print(f"Found {len(prompts)} prompts to register:")
    for name in prompts.keys():
        print(f"  - {name}")
    print()
    
    if args.force:
        print("Mode: FORCE UPDATE (will create new versions for existing prompts)")
    else:
        print("Mode: REGISTER IF MISSING (will skip existing prompts)")
    print()
    
    # Register prompts
    print("Registering prompts...")
    print("-" * 60)
    
    registered_count = 0
    skipped_count = 0
    error_count = 0
    
    for name, template in prompts.items():
        try:
            # Check if prompt exists (only if not forcing)
            if not args.force and registry._prompt_exists(name):
                print(f"SKIP:  {name} (already exists)")
                skipped_count += 1
                continue
            
            # Register the prompt
            registry.register_prompt_if_missing(
                name=name,
                template=template,
                commit_message="Initial version from codebase" if not args.force else "Updated version from codebase",
                tags={"source": "codebase", "agent": name},
                force_update=args.force
            )
            
            if args.force:
                print(f"UPDATE: {name}")
            else:
                print(f"REGISTER: {name}")
            registered_count += 1
            
        except Exception as e:
            print(f"ERROR:  {name} - {e}")
            error_count += 1
    
    print("-" * 60)
    print()
    print("Summary:")
    print(f"  Registered/Updated: {registered_count}")
    print(f"  Skipped:            {skipped_count}")
    print(f"  Errors:             {error_count}")
    print()
    
    if error_count > 0:
        print("WARNING: Some prompts failed to register. Check the errors above.")
        sys.exit(1)
    else:
        print("SUCCESS: All prompts processed successfully!")
        print()
        print("You can now view and manage these prompts in the MLflow UI.")


if __name__ == "__main__":
    main()

