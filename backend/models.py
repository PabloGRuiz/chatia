from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Any, Dict
from datetime import datetime
from bson import ObjectId
import json

class PyObjectId(ObjectId):
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v, handler=None):
        if not ObjectId.is_valid(v):
            raise ValueError("Invalid ObjectId")
        return ObjectId(v)

    @classmethod
    def __get_pydantic_json_schema__(cls, field_schema):
        field_schema.update(type="string")

class UserDB(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    email: EmailStr
    password_hash: str
    role: str = "user" # "admin" or "user"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

class FolderDB(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    name: str
    description: Optional[str] = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

class ChatMessage(BaseModel):
    role: str # "user" or "assistant"
    content: str
    folder_name: Optional[str] = None
    filenames: Optional[List[str]] = None
    execution_time: Optional[float] = None
    source_documents: Optional[List[Dict[str, Any]]] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ChatSessionDB(BaseModel):
    id: Optional[PyObjectId] = Field(alias="_id", default=None)
    user_id: str
    folder_id: Optional[str] = None
    title: Optional[str] = None
    messages: List[ChatMessage] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True
        json_encoders = {ObjectId: str}

class ChatRequest(BaseModel):
    query: str
    folder_id: Optional[str] = None
    filenames: Optional[List[str]] = []
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    folder_name: Optional[str] = None
    filenames: Optional[List[str]] = None
    execution_time: Optional[float] = None
    source_documents: Optional[List[Dict[str, Any]]] = None

class TruncateRequest(BaseModel):
    index: int

class TitleUpdateRequest(BaseModel):
    title: str
