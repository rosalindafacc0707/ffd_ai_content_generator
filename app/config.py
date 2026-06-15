from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    adobe_firefly_api_key: str = ""
    adobe_firefly_client_id: str = ""
    adobe_ims_token: str = ""
    workfront_base_url: str = ""
    workfront_api_key: str = ""
    dam_local_path: Path = Path("./dam")
    dam_images_json: Path = Path("./dam/images_seed.json")
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    app_mode: str = "demo"
    log_level: str = "INFO"
    webhook_secret: str = "changeme"
    sd_api_url: str = "http://localhost:7860"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()