import os
import logging
from typing import List, Optional
from fastapi import FastAPI, Depends, HTTPException, status
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
    title="Product Service",
    description="Manages product information for SmartInventory system",
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

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint for health checks"""
    return {"status": "ok", "service": "product-service"}

@app.post("/products/", response_model=schemas.Product, status_code=status.HTTP_201_CREATED, tags=["Products"])
def create_product(product: schemas.ProductCreate, db: Session = Depends(get_db)):
    """Create a new product"""
    logger.info(f"Creating product: {product.name}")
    db_product = models.Product(
        name=product.name,
        description=product.description,
        price=product.price,
        sku=product.sku
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.get("/products/", response_model=List[schemas.Product], tags=["Products"])
def read_products(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Get all products with pagination"""
    logger.info(f"Fetching products with skip={skip}, limit={limit}")
    products = db.query(models.Product).offset(skip).limit(limit).all()
    return products

@app.get("/products/{product_id}", response_model=schemas.Product, tags=["Products"])
def read_product(product_id: int, db: Session = Depends(get_db)):
    """Get product by ID"""
    logger.info(f"Fetching product with ID: {product_id}")
    product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if product is None:
        logger.warning(f"Product with ID {product_id} not found")
        raise HTTPException(status_code=404, detail="Product not found")
    return product

@app.put("/products/{product_id}", response_model=schemas.Product, tags=["Products"])
def update_product(product_id: int, product: schemas.ProductUpdate, db: Session = Depends(get_db)):
    """Update a product"""
    logger.info(f"Updating product with ID: {product_id}")
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if db_product is None:
        logger.warning(f"Product with ID {product_id} not found")
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Update product attributes
    for key, value in product.dict(exclude_unset=True).items():
        setattr(db_product, key, value)
    
    db.commit()
    db.refresh(db_product)
    return db_product

@app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Products"])
def delete_product(product_id: int, db: Session = Depends(get_db)):
    """Delete a product"""
    logger.info(f"Deleting product with ID: {product_id}")
    db_product = db.query(models.Product).filter(models.Product.id == product_id).first()
    if db_product is None:
        logger.warning(f"Product with ID {product_id} not found")
        raise HTTPException(status_code=404, detail="Product not found")
    
    db.delete(db_product)
    db.commit()
    return None

@app.get("/products/sku/{sku}", response_model=schemas.Product, tags=["Products"])
def read_product_by_sku(sku: str, db: Session = Depends(get_db)):
    """Get product by SKU"""
    logger.info(f"Fetching product with SKU: {sku}")
    product = db.query(models.Product).filter(models.Product.sku == sku).first()
    if product is None:
        logger.warning(f"Product with SKU {sku} not found")
        raise HTTPException(status_code=404, detail="Product not found")
    return product

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
