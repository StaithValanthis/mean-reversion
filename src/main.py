"""Main entry point and configuration loading."""
import os
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

load_dotenv()


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config YAML file

    Returns:
        Configuration dictionary
    """
    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    # Override testnet from env if specified
    if "BYBIT_TESTNET" in os.environ:
        testnet_env = os.environ["BYBIT_TESTNET"].lower() in ("true", "1", "yes")
        config["exchange"]["testnet"] = testnet_env

    return config

