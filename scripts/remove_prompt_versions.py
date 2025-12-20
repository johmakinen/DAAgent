"""Remove all prompt versions except the latest one for all registered MLflow prompts."""

import sys
from pathlib import Path
import mlflow
from mlflow.tracking import MlflowClient

# Add parent directory to sys.path to allow importing app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.prompt_registry import PromptRegistry

def main():
    print("=" * 60)
    print("MLflow Prompt Version Cleanup")
    print("=" * 60)
    registry = PromptRegistry()
    client = registry._client
    if client is None:
        print("MLflow client is not available. Exiting.")
        sys.exit(1)

    prompts = registry.FALLBACK_PROMPTS
    if not prompts:
        print("No prompts found in registry.")
        return
    
    print("\nChecking registered prompts:")
    for name in prompts.keys():
        print(f"  - {name}")
    print()

    for name in prompts.keys():
        try:
            prompt_obj = mlflow.genai.load_prompt(f"prompts:/{name}@latest")
            latest_version = prompt_obj.version
            print(f"\nPrompt: {name}")
            print(f"  Latest version: {latest_version}")

            deleted_versions = []
            # Remove all versions except latest
            for version in range(1, latest_version):
                try:
                    client.delete_prompt_version(name, version=version)
                    deleted_versions.append(version)
                except Exception as e:
                    print(f"    [!] Failed to delete version {version} of '{name}': {e}")
            if deleted_versions:
                print(f"  Deleted versions: {', '.join(map(str, deleted_versions))}")
            else:
                print(f"  No old versions to delete.")

        except Exception as e:
            print(f"[ERROR] Failed to process prompt '{name}': {e}")

    print("\nCleanup complete.\n")

if __name__ == "__main__":
    main()