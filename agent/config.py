import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT.parent.parent.parent / "_tools" / "ms-playwright"))

# USD per 1M tokens (input, output); used for the per-run cost guardrail.
PRICES = {
    "openai/gpt-4.1-mini": (0.40, 1.60),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "openai/gpt-4.1": (2.00, 8.00),
}


@dataclass(frozen=True)
class Settings:
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://openrouter.ai/api/v1")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_model: str = os.getenv("LLM_MODEL", "openai/gpt-4.1-mini")
    e2b_api_key: str = os.getenv("E2B_API_KEY", "")
    tavily_api_key: str = os.getenv("TAVILY_API_KEY", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    pgdata: Path = ROOT / ".pgdata"
    otlp_endpoint: str = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    traces_dir: Path = ROOT / "traces"
    workspace: Path = ROOT / "workspace"
    quixbugs: Path = Path(os.getenv("QUIXBUGS_DIR", str(ROOT.parent.parent.parent / "_tools" / "QuixBugs")))
    max_steps: int = int(os.getenv("MAX_STEPS", "25"))
    max_cost_usd: float = float(os.getenv("MAX_COST_USD", "0.10"))
    max_tokens: int = int(os.getenv("MAX_TOKENS", "200000"))
    sandbox_timeout_s: int = int(os.getenv("SANDBOX_TIMEOUT_S", "60"))
    max_fix_attempts: int = int(os.getenv("MAX_FIX_ATTEMPTS", "3"))
    loop_repeat_limit: int = 3

    def price(self) -> tuple[float, float]:
        return PRICES.get(self.llm_model, (1.0, 4.0))


settings = Settings()
