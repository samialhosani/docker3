# config.py
import json
import os
import urllib.parse
from typing import Literal
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class LocalConfig(BaseModel):
    provider: str = Field(..., description="e.g., ollama, llama.cpp, huggingface")
    model_name: str
    api_base: str = Field(default="http://localhost:11434")
    temperature: float = Field(default=0.1, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024)
    context_window: int = Field(default=4096)

class RemoteConfig(BaseModel):
    provider: str = Field(..., description="e.g., openai, anthropic, azure")
    model_name: str
    api_base: str
    temperature: float = Field(default=0.3, ge=0.0, le=2.0)
    max_tokens: int = Field(default=2048)
    env_api_key_name: str = Field(..., description="Name of the env var holding the API key")

    @property
    def api_key(self) -> str:
        key = os.getenv(self.env_api_key_name)
        if not key:
            raise ValueError(f"Environment variable '{self.env_api_key_name}' is not set!")
        return key

class AppConfig(BaseModel):
    mode: Literal["local", "remote"]
    local_config: LocalConfig
    remote_config: RemoteConfig
    
    # --- AI Specific Storage ---
    vector_db_path: str = Field(default="education_vectors.db")
    materials_dir: str = Field(default="./materials")

    @property
    def mysql_db_url(self) -> str:
        """Dynamically constructs the MySQL connection string from .env variables."""
        host = os.getenv("DB_HOST", "127.0.0.1")
        port = os.getenv("DB_PORT", "3306")
        db_name = os.getenv("DB_DATABASE", "eduverse")
        user = os.getenv("DB_USERNAME", "root")
        raw_password = os.getenv("DB_PASSWORD", "")
        
        # Safely encode the password in case it contains special characters
        password = urllib.parse.quote_plus(raw_password) if raw_password else ""
        
        auth = f"{user}:{password}" if password else f"{user}"
        return f"mysql+pymysql://{auth}@{host}:{port}/{db_name}"

    @property
    def active_llm_config(self) -> LocalConfig | RemoteConfig:
        if self.mode == "local":
            return self.local_config
        return self.remote_config

def load_config(file_path: str = "config.json") -> AppConfig:
    try:
        with open(file_path, "r") as file:
            data = json.load(file)
        return AppConfig(**data)
    except FileNotFoundError:
        print(f"⚠️ Config not found at {file_path}. Using default settings.")
        return AppConfig(
            mode="local",
            local_config=LocalConfig(provider="ollama", model_name="llama3"),
            remote_config=RemoteConfig(provider="openai", model_name="gpt-4o", api_base="", env_api_key_name="OPENAI_API_KEY")
        )