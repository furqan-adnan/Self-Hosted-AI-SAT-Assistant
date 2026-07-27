from typing import List, Dict, Optional
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str
    history: Optional[List[Dict[str, str]]] = []
