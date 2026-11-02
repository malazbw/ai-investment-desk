"""
Chat schemas for request/response
"""
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime


class ChatMessage(BaseModel):
    """Chat message from user"""
    message: str
    conversation_id: Optional[str] = None
    include_agents: Optional[List[str]] = None  # Override which agents to run


class ChatResponse(BaseModel):
    """Chat response with analysis"""
    response: str
    conversation_id: str
    analysis: Dict[str, Any]  # Agent outputs
    timestamp: datetime
    agents_used: List[str]
