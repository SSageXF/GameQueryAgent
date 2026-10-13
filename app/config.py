import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    mode: str = "live"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout: float = 45
    max_tokens: int = 700
    planner_max_tokens: int = 2000
    planner_timeout: float = 20
    retrieval_backend: str = 'vector'

    def __post_init__(self):
        if self.mode not in {"live", "mock"}:
            raise ValueError("AGENT_MODE must be live or mock")
        if self.retrieval_backend not in {'vector','lexical'}:
            raise ValueError('RETRIEVAL_BACKEND must be vector or lexical')
        if not 1 <= self.timeout <= 180:
            raise ValueError("REQUEST_TIMEOUT_SECONDS must be between 1 and 180")
        if not 100 <= self.max_tokens <= 4000:
            raise ValueError("LLM_MAX_TOKENS must be between 100 and 4000")
        if not 100 <= self.planner_max_tokens <= 4000 or not 1 <= self.planner_timeout <= 60:
            raise ValueError('Invalid query planner budget')

    @property
    def ready(self) -> bool:
        return self.mode == "mock" or bool(self.base_url and self.api_key and self.model)


def load_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    return Settings(
        mode=os.getenv("AGENT_MODE", "live"),
        base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
        api_key=os.getenv("LLM_API_KEY", ""),
        model=os.getenv("LLM_MODEL", ""),
        timeout=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "45")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "700")),
        planner_max_tokens=int(os.getenv('LLM_PLANNER_MAX_TOKENS','2000')),
        planner_timeout=float(os.getenv('LLM_PLANNER_TIMEOUT_SECONDS','20')),
        retrieval_backend=os.getenv('RETRIEVAL_BACKEND','vector'),
    )
