from pydantic import BaseModel
from typing import Optional



class PushRequest(BaseModel):
    do_reset : Optional[int] =0

class SearchRequest(BaseModel):
    # Backward compatible with existing clients using `text`
    question: Optional[str] = None
    text: Optional[str] = None
    limit: Optional[int] = 3

    
    