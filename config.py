from pathlib import Path
import importlib.util


def _load_external_agent_config():
    """Load sensitive config values from the shared .Alien directory."""
    base_dir = Path(__file__).resolve().parents[1]
    config_path = base_dir / ".Alien" / "Config" / "Agent.py"

    if not config_path.exists():
        raise FileNotFoundError(
            "Agent configuration missing. Create .Alien/Config/Agent.py with the required keys."
        )

    spec = importlib.util.spec_from_file_location("alien_agent_config", config_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None, "Config loader could not be initialized"
    spec.loader.exec_module(module)
    return module


_ALIEN_CONFIG = _load_external_agent_config()

AZURE_ENDPOINT = getattr(_ALIEN_CONFIG, "AZURE_ENDPOINT", "")
AZURE_API_KEY = getattr(_ALIEN_CONFIG, "AZURE_API_KEY", "")
AZURE_API_VERSION = getattr(_ALIEN_CONFIG, "AZURE_API_VERSION", "")
LLM_DEPLOYMENT = getattr(_ALIEN_CONFIG, "LLM_DEPLOYMENT", "")
DEBUGE_MODE = getattr(_ALIEN_CONFIG, "DEBUGE_MODE", False)
CHAT_SESSION_URL = getattr(_ALIEN_CONFIG, "CHAT_SESSION_URL", "")


__all__ = [
    "AZURE_ENDPOINT",
    "AZURE_API_KEY",
    "AZURE_API_VERSION",
    "LLM_DEPLOYMENT",
    "DEBUGE_MODE",
    "CHAT_SESSION_URL",
]
