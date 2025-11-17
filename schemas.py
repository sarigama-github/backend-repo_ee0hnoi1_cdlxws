"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# SaaS: Research paper analysis schema
class Researchpaper(BaseModel):
    """
    Research papers uploaded by users and their analysis
    Collection name: "researchpaper"
    """
    title: str = Field(..., description="Paper title (fallback to filename if missing)")
    filename: str = Field(..., description="Original file name")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    word_count: int = Field(..., ge=0, description="Total words detected in text")
    sentence_count: int = Field(..., ge=0, description="Total sentences detected")
    avg_sentence_length: float = Field(..., ge=0, description="Average words per sentence")
    sections: List[str] = Field(default_factory=list, description="Detected section headings")
    readability: Optional[float] = Field(None, description="Approximate readability score (lower ~ simpler)")
    recommendations: List[str] = Field(default_factory=list, description="Actionable suggestions to improve the paper")
    status: str = Field("analyzed", description="Processing status")

# Example schemas kept for reference (not used by app):
class User(BaseModel):
    name: str
    email: str
    address: str
    age: Optional[int] = None
    is_active: bool = True

class Product(BaseModel):
    title: str
    description: Optional[str] = None
    price: float
    category: str
    in_stock: bool = True
