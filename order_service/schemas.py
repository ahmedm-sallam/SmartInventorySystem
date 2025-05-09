from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, EmailStr

class OrderItemBase(BaseModel):
    """Base schema for order items"""
    product_id: int = Field(..., gt=0)
    quantity: float = Field(..., gt=0)

class OrderItemCreate(OrderItemBase):
    """Schema for creating an order item"""
    pass

class OrderItemRead(OrderItemBase):
    """Schema for reading an order item"""
    id: int
    unit_price: float

    class Config:
        orm_mode = True

class OrderBase(BaseModel):
    """Base schema for orders"""
    customer_name: str = Field(..., min_length=1, max_length=100)
    customer_email: EmailStr

class OrderCreate(OrderBase):
    """Schema for creating an order"""
    items: List[OrderItemCreate] = Field(..., min_items=1)

class OrderStatusUpdate(BaseModel):
    """Schema for updating order status"""
    status: str = Field(..., regex="^(pending|processing|processed|failed|delivered)$")

class Order(OrderBase):
    """Schema for reading an order"""
    id: int
    status: str
    created_at: datetime
    updated_at: Optional[datetime]
    items: List[OrderItemRead]

    class Config:
        orm_mode = True
