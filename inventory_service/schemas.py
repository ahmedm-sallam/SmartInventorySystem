from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field

class InventoryItemBase(BaseModel):
    """Base schema for inventory items"""
    product_id: int = Field(..., gt=0, example=1)
    quantity: float = Field(..., ge=0, example=100)
    location: Optional[str] = Field(None, max_length=100, example="Warehouse A")

class InventoryItemCreate(InventoryItemBase):
    """Schema for creating an inventory item"""
    pass

class InventoryItemUpdate(BaseModel):
    """Schema for updating an inventory item"""
    quantity: Optional[float] = Field(None, ge=0)
    location: Optional[str] = Field(None, max_length=100)

class InventoryAdjustment(BaseModel):
    """Schema for adjusting inventory quantity"""
    amount: float = Field(..., example=10)
    allow_negative: bool = Field(False, example=False)
    
    class Config:
        json_schema_extra = {
            "example": {
                "amount": 10,
                "allow_negative": False
            }
        }

class InventoryItem(InventoryItemBase):
    """Schema for reading an inventory item"""
    id: int
    last_updated: datetime
    created_at: datetime

    class Config:
        from_attributes = True
