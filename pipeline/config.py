"""
Configuration for the Legal Case Pipeline
"""

import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env file
load_dotenv()


@dataclass
class PipelineConfig:
    """Configuration settings for the pipeline."""
    
    # Database
    database_url: str = ""
    
    # LlamaParse (PDF extraction)
    llama_cloud_api_key: Optional[str] = None
    
    # Ollama (LLM extraction)
    ollama_base_url: str = "https://ollama.legaldb.ai"
    ollama_model: str = "qwen:32b"
    
    # Processing settings
    max_text_chars: int = 30000      # Max chars to send to LLM
    llm_timeout: int = 120           # LLM request timeout in seconds
    
    @classmethod
    def from_env(cls) -> 'PipelineConfig':
        """Load configuration from environment variables."""
        return cls(
            database_url=os.getenv(
                "DATABASE_URL", 
                "postgresql://postgres:postgres@localhost:5432/cases_llama3_3"
            ),
            llama_cloud_api_key=os.getenv("LLAMA_CLOUD_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
            max_text_chars=int(os.getenv("MAX_TEXT_CHARS", "30000")),
            llm_timeout=int(os.getenv("LLM_TIMEOUT", "120")),
        )
    
    def validate(self) -> bool:
        """Validate that required settings are present."""
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        return True
