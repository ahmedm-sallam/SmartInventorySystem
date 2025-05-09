import os
import logging
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
    title="Notification Service",
    description="Manages notifications for SmartInventory system",
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

# Dependency to get database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def send_email_notification(recipient: str, subject: str, message: str):
    """Send email notification (mock implementation)"""
    logger.info(f"[EMAIL] To: {recipient}, Subject: {subject}, Message: {message}")
    # In a real implementation, this would connect to an email service
    # like SendGrid, Mailgun, SES, etc.
    return True

async def send_sms_notification(phone_number: str, message: str):
    """Send SMS notification (mock implementation)"""
    logger.info(f"[SMS] To: {phone_number}, Message: {message}")
    # In a real implementation, this would connect to an SMS service
    # like Twilio, Nexmo, etc.
    return True

async def process_notification(notification_id: int, db: Session):
    """Process a notification in the background"""
    logger.info(f"Processing notification {notification_id}")
    
    # Get the notification
    notification = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if not notification:
        logger.error(f"Notification {notification_id} not found")
        return
    
    try:
        # Handle different notification types
        if notification.type == "low_stock":
            # Send low stock alert
            subject = "Low Stock Alert"
            message = f"Product ID {notification.data.get('product_id')} is running low. " \
                      f"Current quantity: {notification.data.get('current_quantity')}, " \
                      f"Threshold: {notification.data.get('threshold')}"
            
            await send_email_notification(
                recipient="inventory_manager@example.com",  # This would be configurable
                subject=subject,
                message=message
            )
            
        elif notification.type == "order_status":
            # Send order status update
            order_id = notification.data.get('order_id')
            status = notification.data.get('status')
            recipient = notification.data.get('recipient')
            
            subject = f"Order #{order_id} Status Update"
            message = f"Your order #{order_id} has been {status}."
            
            if recipient:
                await send_email_notification(
                    recipient=recipient,
                    subject=subject,
                    message=message
                )
        
        # Mark notification as sent
        notification.status = "sent"
        notification.sent_at = datetime.now()
        db.commit()
        logger.info(f"Notification {notification_id} processed successfully")
        
    except Exception as e:
        # Mark notification as failed
        notification.status = "failed"
        notification.error_message = str(e)
        db.commit()
        logger.error(f"Failed to process notification {notification_id}: {e}")

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint for health checks"""
    return {"status": "ok", "service": "notification-service"}

@app.post("/notifications/", response_model=schemas.Notification, status_code=status.HTTP_201_CREATED, tags=["Notifications"])
async def create_notification(
    notification: schemas.NotificationCreate, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create a new notification"""
    logger.info(f"Creating notification of type: {notification.type}")
    
    # Create new notification
    db_notification = models.Notification(
        type=notification.type,
        data=notification.data,
        status="pending"
    )
    db.add(db_notification)
    db.commit()
    db.refresh(db_notification)
    
    # Process notification in background
    background_tasks.add_task(process_notification, db_notification.id, db)
    
    return db_notification

@app.get("/notifications/", response_model=List[schemas.Notification], tags=["Notifications"])
def read_notifications(
    skip: int = 0, 
    limit: int = 100, 
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all notifications with optional filtering by status"""
    logger.info(f"Fetching notifications with status={status}")
    
    query = db.query(models.Notification)
    
    if status:
        query = query.filter(models.Notification.status == status)
    
    notifications = query.offset(skip).limit(limit).all()
    return notifications

@app.get("/notifications/{notification_id}", response_model=schemas.Notification, tags=["Notifications"])
def read_notification(notification_id: int, db: Session = Depends(get_db)):
    """Get notification by ID"""
    logger.info(f"Fetching notification with ID: {notification_id}")
    notification = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if notification is None:
        logger.warning(f"Notification with ID {notification_id} not found")
        raise HTTPException(status_code=404, detail="Notification not found")
    return notification

@app.post("/notifications/{notification_id}/resend", response_model=schemas.Notification, tags=["Notifications"])
async def resend_notification(
    notification_id: int, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Resend a failed notification"""
    logger.info(f"Resending notification with ID: {notification_id}")
    
    notification = db.query(models.Notification).filter(models.Notification.id == notification_id).first()
    if notification is None:
        logger.warning(f"Notification with ID {notification_id} not found")
        raise HTTPException(status_code=404, detail="Notification not found")
    
    # Update status to pending
    notification.status = "pending"
    notification.error_message = None
    notification.sent_at = None
    db.commit()
    db.refresh(notification)
    
    # Process notification in background
    background_tasks.add_task(process_notification, notification.id, db)
    
    return notification

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
