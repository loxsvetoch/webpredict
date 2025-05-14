from pydantic import BaseModel
from typing import Optional


class Group(BaseModel):
    id: int
    error: str
    t_a: str
    a: str
    b: str
    img: str
    
    class Config:
        orm_mode = True

