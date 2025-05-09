from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field

class NotificationBase(BaseModel):
    """Base schema for notifications"""
    type: str = Field(..., description="Notification type (e.g., low_stock, order_status)")
    data: Dict[str, Any] = Field(..., description="Notification data payload")

class NotificationCreate(NotificationBase):
    """Schema for creating a notification"""
    pass

class Notification(NotificationBase):
    """Schema for reading a notification"""
    id: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    sent_at: Optional[datetime] = None

    class Config:
        orm_mode = True
