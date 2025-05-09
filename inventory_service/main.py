import os
import logging
import httpx
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware

import models, schemas, database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Inventory Service",
    description="Manages inventory and stock levels for SmartInventory system",
    version="0.1.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

# Environment variables
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8004")
STOCK_THRESHOLD = int(os.getenv("STOCK_THRESHOLD", "10"))

# Dependency to get database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def verify_product_exists(product_id: int) -> bool:
    """Verify that a product exists in the product service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
            if response.status_code == 200:
                return True
            return False
    except Exception as e:
        logger.error(f"Error communicating with product service: {e}")
        return False

async def notify_low_stock(inventory_item: models.InventoryItem):
    """Notify about low stock levels"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "type": "low_stock",
                "product_id": inventory_item.product_id,
                "current_quantity": inventory_item.quantity,
                "threshold": STOCK_THRESHOLD
            }
            await client.post(f"{NOTIFICATION_SERVICE_URL}/notifications/", json=payload)
    except Exception as e:
        logger.error(f"Failed to send low stock notification: {e}")

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint for health checks"""
    return {"status": "ok", "service": "inventory-service"}

@app.post("/inventory/", response_model=schemas.InventoryItem, status_code=status.HTTP_201_CREATED, tags=["Inventory"])
async def create_inventory_item(
    item: schemas.InventoryItemCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new inventory item or update if already exists"""
    logger.info(f"Creating/updating inventory for product ID: {item.product_id}")
    
    # Verify product exists
    product_exists = await verify_product_exists(item.product_id)
    if not product_exists:
        logger.warning(f"Product with ID {item.product_id} not found in product service")
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Check if inventory item already exists
    db_item = db.query(models.InventoryItem).filter(
        models.InventoryItem.product_id == item.product_id
    ).first()
    
    if db_item:
        # Update existing item
        db_item.quantity = item.quantity
        db_item.location = item.location
    else:
        # Create new item
        db_item = models.InventoryItem(
            product_id=item.product_id,
            quantity=item.quantity,
            location=item.location
        )
        db.add(db_item)
    
    db.commit()
    db.refresh(db_item)
    
    # Check for low stock
    if db_item.quantity <= STOCK_THRESHOLD:
        background_tasks.add_task(notify_low_stock, db_item)
    
    return db_item

@app.get("/inventory/", response_model=List[schemas.InventoryItem], tags=["Inventory"])
def read_inventory_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all inventory items with pagination"""
    logger.info(f"Fetching inventory items with skip={skip}, limit={limit}")
    items = db.query(models.InventoryItem).offset(skip).limit(limit).all()
    return items

@app.get("/inventory/{product_id}", response_model=schemas.InventoryItem, tags=["Inventory"])
def read_inventory_item(product_id: int, db: Session = Depends(get_db)):
    """Get inventory item by product ID"""
    logger.info(f"Fetching inventory for product ID: {product_id}")
    item = db.query(models.InventoryItem).filter(
        models.InventoryItem.product_id == product_id
    ).first()
    if item is None:
        logger.warning(f"Inventory for product ID {product_id} not found")
        raise HTTPException(status_code=404, detail="Inventory item not found")
    return item

@app.put("/inventory/{product_id}", response_model=schemas.InventoryItem, tags=["Inventory"])
async def update_inventory_item(
    product_id: int, 
    item: schemas.InventoryItemUpdate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Update an inventory item"""
    logger.info(f"Updating inventory for product ID: {product_id}")
    
    # Verify product exists
    product_exists = await verify_product_exists(product_id)
    if not product_exists:
        logger.warning(f"Product with ID {product_id} not found in product service")
        raise HTTPException(status_code=404, detail="Product not found")
    
    db_item = db.query(models.InventoryItem).filter(
        models.InventoryItem.product_id == product_id
    ).first()
    
    if db_item is None:
        logger.warning(f"Inventory for product ID {product_id} not found")
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Update inventory attributes
    for key, value in item.dict(exclude_unset=True).items():
        setattr(db_item, key, value)
    
    db.commit()
    db.refresh(db_item)
    
    # Check for low stock
    if db_item.quantity <= STOCK_THRESHOLD:
        background_tasks.add_task(notify_low_stock, db_item)
    
    return db_item

@app.post("/inventory/{product_id}/adjust", response_model=schemas.InventoryItem, tags=["Inventory"])
async def adjust_inventory(
    product_id: int, 
    adjustment: schemas.InventoryAdjustment, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Adjust inventory quantity (add or subtract)"""
    logger.info(f"Adjusting inventory for product ID: {product_id}, amount: {adjustment.amount}")
    
    db_item = db.query(models.InventoryItem).filter(
        models.InventoryItem.product_id == product_id
    ).first()
    
    if db_item is None:
        logger.warning(f"Inventory for product ID {product_id} not found")
        raise HTTPException(status_code=404, detail="Inventory item not found")
    
    # Prevent negative inventory unless allowed
    new_quantity = db_item.quantity + adjustment.amount
    if new_quantity < 0 and not adjustment.allow_negative:
        logger.warning(f"Adjustment would cause negative inventory for product ID {product_id}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adjustment would cause negative inventory"
        )
    
    db_item.quantity = new_quantity
    db.commit()
    db.refresh(db_item)
    
    # Check for low stock
    if db_item.quantity <= STOCK_THRESHOLD:
        background_tasks.add_task(notify_low_stock, db_item)
    
    return db_item

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
