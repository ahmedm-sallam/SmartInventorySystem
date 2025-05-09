from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re

class ProductBase(BaseModel):
    """Base schema for Product"""
    name: str = Field(..., min_length=1, max_length=100, example="Laptop")
    description: Optional[str] = Field(None, max_length=1000, example="A powerful laptop with 16GB RAM")
    price: float = Field(..., gt=0, example=999.99)
    sku: str = Field(..., min_length=3, max_length=50, example="LAP-001")

    @validator('sku')
    def sku_must_be_valid(cls, v):
        if not re.match(r'^[A-Za-z0-9\-]+$', v):
            raise ValueError('SKU must contain only alphanumeric characters and hyphens')
        return v
    
    @validator('price')
    def price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError('Price must be greater than zero')
        return v

class ProductCreate(ProductBase):
    """Schema for creating a product"""
    pass

class ProductUpdate(BaseModel):
    """Schema for updating a product"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    sku: Optional[str] = Field(None, min_length=3, max_length=50)

    @validator('sku')
    def sku_must_be_valid(cls, v):
        if v and not re.match(r'^[A-Za-z0-9\-]+$', v):
            raise ValueError('SKU must contain only alphanumeric characters and hyphens')
        return v
    
    @validator('price')
    def price_must_be_positive(cls, v):
        if v and v <= 0:
            raise ValueError('Price must be greater than zero')
        return v

class Product(ProductBase):
    """Schema for reading a product"""
    id: int
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
