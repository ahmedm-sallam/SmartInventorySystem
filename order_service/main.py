import os
import logging
import httpx
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

import models, schemas, database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Order Service",
    description="Manages customer orders for SmartInventory system",
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
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8002")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8004")

# Dependency to get database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_product_info(product_id: int):
    """Get product information from product service"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Error getting product {product_id}: Status {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"Error communicating with product service: {e}")
        return None

async def check_inventory(product_id: int, quantity: float):
    """Check if there's enough inventory for a product"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{INVENTORY_SERVICE_URL}/inventory/{product_id}")
            if response.status_code == 200:
                inventory = response.json()
                return inventory["quantity"] >= quantity
            else:
                logger.error(f"Error checking inventory for product {product_id}: Status {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Error communicating with inventory service: {e}")
        return False

async def update_inventory(product_id: int, quantity: float):
    """Update inventory after an order is placed"""
    try:
        async with httpx.AsyncClient() as client:
            adjustment = {
                "amount": -quantity,  # Negative amount to reduce inventory
                "allow_negative": False
            }
            response = await client.post(
                f"{INVENTORY_SERVICE_URL}/inventory/{product_id}/adjust", 
                json=adjustment
            )
            if response.status_code == 200:
                return True
            else:
                logger.error(f"Error updating inventory for product {product_id}: Status {response.status_code}")
                return False
    except Exception as e:
        logger.error(f"Error communicating with inventory service: {e}")
        return False

async def notify_order_status(order_id: int, status: str, customer_email: str):
    """Send notification about order status"""
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "type": "order_status",
                "order_id": order_id,
                "status": status,
                "recipient": customer_email
            }
            await client.post(f"{NOTIFICATION_SERVICE_URL}/notifications/", json=payload)
    except Exception as e:
        logger.error(f"Failed to send order notification: {e}")

async def process_order(order_id: int, db: Session):
    """Process an order in the background"""
    logger.info(f"Processing order {order_id}")
    
    # Get the order
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if not order:
        logger.error(f"Order {order_id} not found")
        return
    
    # Get order items
    order_items = db.query(models.OrderItem).filter(models.OrderItem.order_id == order_id).all()
    
    # Check inventory for all items
    inventory_available = True
    for item in order_items:
        if not await check_inventory(item.product_id, item.quantity):
            inventory_available = False
            break
    
    if not inventory_available:
        # Update order status to failed
        order.status = "failed"
        order.updated_at = datetime.now()
        db.commit()
        
        # Notify customer
        await notify_order_status(order.id, "failed", order.customer_email)
        logger.warning(f"Order {order_id} failed due to insufficient inventory")
        return
    
    # Update inventory for all items
    for item in order_items:
        await update_inventory(item.product_id, item.quantity)
    
    # Update order status to processed
    order.status = "processed"
    order.updated_at = datetime.now()
    db.commit()
    
    # Notify customer
    await notify_order_status(order.id, "processed", order.customer_email)
    logger.info(f"Order {order_id} processed successfully")

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint for health checks"""
    return {"status": "ok", "service": "order-service"}

@app.post("/orders/", response_model=schemas.Order, status_code=status.HTTP_201_CREATED, tags=["Orders"])
async def create_order(
    order: schemas.OrderCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new order"""
    logger.info(f"Creating order for customer: {order.customer_name}")
    
    # Create new order
    db_order = models.Order(
        customer_name=order.customer_name,
        customer_email=order.customer_email,
        status="pending"
    )
    db.add(db_order)
    db.commit()
    db.refresh(db_order)
    
    # Add order items
    for item in order.items:
        # Verify product exists
        product = await get_product_info(item.product_id)
        if not product:
            db.delete(db_order)
            db.commit()
            raise HTTPException(status_code=404, detail=f"Product {item.product_id} not found")
        
        # Create order item
        db_item = models.OrderItem(
            order_id=db_order.id,
            product_id=item.product_id,
            quantity=item.quantity,
            unit_price=product["price"]
        )
        db.add(db_item)
    
    db.commit()
    
    # Process order in background
    background_tasks.add_task(process_order, db_order.id, db)
    
    # Refresh order with items
    db.refresh(db_order)
    
    return db_order

@app.get("/orders/", response_model=List[schemas.Order], tags=["Orders"])
def read_orders(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all orders with pagination"""
    logger.info(f"Fetching orders with skip={skip}, limit={limit}")
    orders = db.query(models.Order).offset(skip).limit(limit).all()
    return orders

@app.get("/orders/{order_id}", response_model=schemas.Order, tags=["Orders"])
def read_order(order_id: int, db: Session = Depends(get_db)):
    """Get order by ID"""
    logger.info(f"Fetching order with ID: {order_id}")
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if order is None:
        logger.warning(f"Order with ID {order_id} not found")
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.put("/orders/{order_id}/status", response_model=schemas.Order, tags=["Orders"])
async def update_order_status(
    order_id: int, 
    status_update: schemas.OrderStatusUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Update order status"""
    logger.info(f"Updating status for order ID: {order_id} to {status_update.status}")
    
    order = db.query(models.Order).filter(models.Order.id == order_id).first()
    if order is None:
        logger.warning(f"Order with ID {order_id} not found")
        raise HTTPException(status_code=404, detail="Order not found")
    
    order.status = status_update.status
    order.updated_at = datetime.now()
    db.commit()
    db.refresh(order)
    
    # Notify customer about status change
    background_tasks.add_task(notify_order_status, order.id, order.status, order.customer_email)
    
    return order

@app.get("/orders/customer/{email}", response_model=List[schemas.Order], tags=["Orders"])
def read_customer_orders(email: str, db: Session = Depends(get_db)):
    """Get all orders for a customer"""
    logger.info(f"Fetching orders for customer: {email}")
    orders = db.query(models.Order).filter(models.Order.customer_email == email).all()
    return orders

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
