from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API Configuration
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Server Configuration
    SERVER_NAME: str = "Law Helper API"
    SERVER_HOST: str = "localhost"
    SERVER_PORT: int = 8000
    DEBUG: bool = True

    # Database Configuration - Auto-detect Docker vs local environment
    @property
    def database_host(self) -> str:
        """Auto-detect if running inside Docker or locally"""
        import socket
        try:
            # Try to resolve the Docker container name
            socket.gethostbyname("legal_ai_postgres")
            return "legal_ai_postgres"  # Inside Docker network
        except socket.gaierror:
            return "localhost"  # Outside Docker, use localhost
    
    @property  
    def default_database_url(self) -> str:
        """Generate DATABASE_URL based on environment"""
        host = self.database_host
        return f"postgresql://{self.DATABASE_USER}:{self.DATABASE_PASSWORD}@{host}:{self.DATABASE_PORT}/{self.DATABASE_NAME}"
    
    DATABASE_URL: Optional[str] = None  # Will use default_database_url if None
    DATABASE_HOST: str = "localhost" 
    DATABASE_PORT: int = 5433
    DATABASE_NAME: str = "cases_llama3.3"
    DATABASE_USER: str = "legal_user"
    DATABASE_PASSWORD: str = "legal_pass"
    
    # AI/LLM Configuration
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    PINECONE_API_KEY: Optional[str] = None
    LANGCHAIN_API_KEY: Optional[str] = None
    
    # Database connection details (legacy PostgreSQL env vars)
    PGHOST: str = "localhost"  # Use "localhost" for direct connection, "legal_ai_postgres" for Docker internal
    PGPORT: str = "5433"
    PGDATABASE: str = "cases_llama3.3"
    PGUSER: str = "legal_user"
    PGPASSWORD: str = "legal_pass"
    
    # Ollama Configuration
    OLLAMA_MODEL: str = "qwen:32b"
    OLLAMA_EMBED_MODEL: str = "mxbai-embed-large"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    USE_OLLAMA: bool = True

    # CORS Configuration
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000", "http://localhost:8080"]

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Allow extra environment variables


settings = Settings()
