
from pydantic import BaseModel
from typing import List, Optional

class CreateChatRequest(BaseModel):
    member_ids: List[int]
    name: Optional[str] = None