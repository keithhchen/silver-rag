from sqlalchemy import Column, Integer, String, DateTime, Text
from pydantic import BaseModel
from datetime import datetime
from app.models.base import Base

class DocumentDB(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    gcs_document_id = Column(String(255), nullable=False)
    html_content = Column(String().with_variant(Text(length=16777215), 'mysql'), nullable=False)  # MEDIUMTEXT
    markdown_content = Column(String().with_variant(Text(length=16777215), 'mysql'), nullable=False)  # MEDIUMTEXT
    dify_document_id = Column(String(255), nullable=False)
    dify_upload_file_id = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)

class DocumentCreate(BaseModel):
    filename: str
    gcs_document_id: str
    html_content: str
    markdown_content: str
    dify_document_id: str
    dify_upload_file_id: str

class Document(DocumentCreate):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True