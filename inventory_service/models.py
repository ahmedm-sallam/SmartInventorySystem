from sqlalchemy import Column, Integer, String, DateTime, Float, CheckConstraint
from sqlalchemy.sql import func
from database import Base

class InventoryItem(Base):
    """Inventory item database model"""
    __tablename__ = "inventory_items"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, unique=True, index=True, nullable=False)
    quantity = Column(Float, nullable=False, default=0)
    location = Column(String, nullable=True)
    last_updated = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
