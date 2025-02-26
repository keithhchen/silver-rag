from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Database settings
    database_url: str = Field(..., env='DATABASE_URL')
    
    # Google Cloud Storage settings
    google_cloud_credentials: str = Field(..., env='GOOGLE_CLOUD_CREDENTIALS')
    
    # Upstage API settings
    upstage_api_key: str = Field(..., env='UPSTAGE_API_KEY')
    upstage_api_url: str = Field('https://api.upstage.ai/v1/document-ai/document-parse')
    
    # Dify API settings, as RAG solution
    dify_dataset_api_key: str = Field(..., env='DIFY_DATASET_API_KEY')
    dify_dataset_id: str = Field(..., env='DIFY_DATASET_ID')
    # dify_dataset_api_url: str = Field('http://119.3.235.4/v1/datasets/{dataset_id}')
    # dify_api_url: str = Field('http://119.3.235.4/v1')
    dify_dataset_api_url: str = Field('https://api.dify.ai/v1/datasets/{dataset_id}')
    dify_api_url: str = Field('https://api.dify.ai/v1')
    dify_api_key: str = Field(..., env='DIFY_API_KEY')
    
    class Config:
        env_file = '.env'