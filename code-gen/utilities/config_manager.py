"""Configuration management for the RAG system."""

import yaml
import sys
from pathlib import Path
from typing import Dict, Any


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from specified YAML file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        print(f"❌ Config file not found: {config_path}")
        print(f"Expected location: {config_file.absolute()}")
        
        # Offer to create a default config
        create_default = input("Would you like to create a default config file? (y/N): ").lower().strip()
        if create_default == 'y':
            create_default_config(config_file)
        else:
            sys.exit(1)
    
    try:
        with open(config_file, "r") as f:
            config = yaml.safe_load(f)
        print(f"✅ Loaded config from: {config_file.absolute()}")
        return config
    except yaml.YAMLError as e:
        print(f"❌ Error parsing YAML config: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        sys.exit(1)


def create_default_config(config_path: Path) -> None:
    """Create a default configuration file."""
    default_config = {
        "llm": {
            "provider": "anthropic",
            "model": "claude-3-7-sonnet-20250219",
            "temperature": 0.2,
            "max_tokens": 4096,
            "api_key": "your-claude-api-key-here"
        },
        "qdrant": {
            "host": "localhost",
            "port": 6333,
            "collection_name": "kotlin-code"
        },
        "retriever": {
            "top_k": 10
        },
        "agents": {
            "planner": {
                "minDecomposedQuestions": 1,
                "maxDecomposedQuestions": 10
            }
        },
        "embedding": {
            "model": "BAAI/bge-small-en-v1.5"
        }
    }
    
    try:
        with open(config_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False, indent=2)
        print(f"✅ Created default config at: {config_path.absolute()}")
        print("⚠️  Please edit the config file and add your Claude API key before running again.")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error creating default config: {e}")
        sys.exit(1)