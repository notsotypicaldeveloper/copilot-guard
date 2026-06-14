"""
Model client configuration — single place to swap GitHub Models ↔ Azure AI Foundry.
All agents and the Copilot answerer import get_openai_client() from here.
"""
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

PROVIDER = os.getenv("MODEL_PROVIDER", "github").lower()

if PROVIDER == "azure":
    BASE_URL = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/") + "/openai"
    API_KEY = os.getenv("AZURE_OPENAI_KEY", "")
    MODEL_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")
    API_VERSION = "2024-02-01"
else:
    # GitHub Models — OpenAI-compatible, free with a GitHub PAT
    BASE_URL = "https://models.inference.ai.azure.com"
    API_KEY = os.getenv("GITHUB_TOKEN", "")
    MODEL_NAME = "gpt-4o"
    API_VERSION = None


def get_openai_client() -> OpenAI:
    kwargs = {"api_key": API_KEY, "base_url": BASE_URL}
    if API_VERSION:
        kwargs["default_query"] = {"api-version": API_VERSION}
    return OpenAI(**kwargs)


def get_autogen_llm_config() -> dict:
    """LLM config dict for pyautogen agents."""
    config = {
        "model": MODEL_NAME,
        "api_key": API_KEY,
        "base_url": BASE_URL,
    }
    if API_VERSION:
        config["api_version"] = API_VERSION
        config["api_type"] = "azure"
    return {"config_list": [config], "temperature": 0.2}
