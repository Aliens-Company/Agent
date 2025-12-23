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

_DEFAULT_FLOW_CONTROL = {
    "prompt1": 1,
    "prompt2": 1,
    "download1": 1,
    "prompt3": 1,
    "download2": 1,
}


def _normalize_flag(value, default: int = 1) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, (int, float)):
        return 1 if int(value) else 0
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"1", "true", "yes", "run", "enable"}:
            return 1
        if lowered in {"0", "false", "no", "skip", "disable"}:
            return 0
    return default


def _load_flow_control():
    external = getattr(_ALIEN_CONFIG, "FLOW_CONTROL", None)
    user_map = external if isinstance(external, dict) else {}
    merged = {}
    for step, default in _DEFAULT_FLOW_CONTROL.items():
        merged[step] = _normalize_flag(user_map.get(step, default), default)
    return merged


FLOW_CONTROL = _load_flow_control()


__all__ = [
    "AZURE_ENDPOINT",
    "AZURE_API_KEY",
    "AZURE_API_VERSION",
    "LLM_DEPLOYMENT",
    "DEBUGE_MODE",
    "CHAT_SESSION_URL",
    "FLOW_CONTROL",
]
