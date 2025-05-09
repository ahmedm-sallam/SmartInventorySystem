import os
import logging
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="API Gateway",
    description="API Gateway for SmartInventory Microservices",
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

# Environment variables for service URLs
PRODUCT_SERVICE_URL = os.getenv("PRODUCT_SERVICE_URL", "http://localhost:8001")
INVENTORY_SERVICE_URL = os.getenv("INVENTORY_SERVICE_URL", "http://localhost:8002")
ORDER_SERVICE_URL = os.getenv("ORDER_SERVICE_URL", "http://localhost:8003")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8004")

# Service registry
SERVICE_REGISTRY = {
    "products": PRODUCT_SERVICE_URL,
    "inventory": INVENTORY_SERVICE_URL,
    "orders": ORDER_SERVICE_URL,
    "notifications": NOTIFICATION_SERVICE_URL,
}

@app.get("/", tags=["Root"])
def read_root():
    """Root endpoint for health checks and service discovery"""
    return {
        "status": "ok", 
        "service": "api-gateway",
        "available_services": list(SERVICE_REGISTRY.keys())
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint that pings all services"""
    results = {}
    
    async with httpx.AsyncClient() as client:
        for service_name, service_url in SERVICE_REGISTRY.items():
            try:
                response = await client.get(f"{service_url}/", timeout=2.0)
                results[service_name] = {
                    "status": "up" if response.status_code == 200 else "down",
                    "status_code": response.status_code
                }
            except Exception as e:
                results[service_name] = {
                    "status": "down",
                    "error": str(e)
                }
    
    all_up = all(result["status"] == "up" for result in results.values())
    
    return {
        "status": "healthy" if all_up else "degraded",
        "services": results
    }

@app.api_route("/{service}/{path:path}", methods=["GET", "POST", "PUT", "DELETE"], include_in_schema=True)
async def proxy_request(service: str, path: str, request: Request):
    """Proxy requests to the appropriate microservice"""
    # We don't need to skip routes here, as FastAPI's router will handle the special aggregation endpoints
    # The proxy will only be called for routes that don't match specific endpoints
        
    if service not in SERVICE_REGISTRY:
        raise HTTPException(status_code=404, detail=f"Service '{service}' not found")
    
    service_url = SERVICE_REGISTRY[service]
    
    # Map service name to actual service endpoints
    service_paths = {
        "products": "products",
        "inventory": "inventory",
        "orders": "orders",
        "notifications": "notifications"
    }
    
    # Determine the correct path to forward
    service_path = service_paths.get(service, '')
    
    # Construct the target URL carefully to avoid protocol issues
    if service_url.endswith('/'):
        service_url = service_url[:-1]
        
    if service_path:
        target_url = f"{service_url}/{service_path}/{path}"
    else:
        target_url = f"{service_url}/{path}"
    
    # Get request body
    body = None
    if request.method in ["POST", "PUT"]:
        body = await request.json()
    
    # Get request headers and query params
    headers = dict(request.headers)
    headers.pop("host", None)
    
    params = dict(request.query_params)
    
    # Forward the request to the appropriate service
    try:
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method=request.method,
                url=target_url,
                json=body,
                headers=headers,
                params=params,
                timeout=30.0
            )
            
            return JSONResponse(
                content=response.json(),
                status_code=response.status_code
            )
    except httpx.RequestError as e:
        logger.error(f"Error forwarding request to {target_url}: {e}")
        raise HTTPException(status_code=503, detail=f"Service unavailable: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/products/{product_id}/with-inventory", tags=["Aggregation"])
async def get_product_with_inventory(product_id: int):
    """Aggregate product and inventory information"""
    product = None
    inventory = None
    
    async with httpx.AsyncClient() as client:
        # Get product information
        try:
            product_response = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
            if product_response.status_code == 200:
                product = product_response.json()
        except Exception as e:
            logger.error(f"Error fetching product data: {e}")
        
        # Get inventory information
        try:
            inventory_response = await client.get(f"{INVENTORY_SERVICE_URL}/inventory/{product_id}")
            if inventory_response.status_code == 200:
                inventory = inventory_response.json()
        except Exception as e:
            logger.error(f"Error fetching inventory data: {e}")
    
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Combine product and inventory information
    result = {
        **product,
        "inventory": inventory if inventory else {"quantity": 0, "location": None}
    }
    
    return result

@app.get("/orders/{order_id}/with-products", tags=["Aggregation"])
async def get_order_with_products(order_id: int):
    """Aggregate order information with product details"""
    async with httpx.AsyncClient() as client:
        # Get order information
        order_response = await client.get(f"{ORDER_SERVICE_URL}/orders/{order_id}")
        if order_response.status_code != 200:
            raise HTTPException(
                status_code=order_response.status_code, 
                detail="Order not found"
            )
        
        order = order_response.json()
        
        # Get product information for each order item
        enriched_items = []
        for item in order.get("items", []):
            product_id = item.get("product_id")
            try:
                product_response = await client.get(f"{PRODUCT_SERVICE_URL}/products/{product_id}")
                if product_response.status_code == 200:
                    product = product_response.json()
                    enriched_items.append({
                        **item,
                        "product": {
                            "name": product.get("name"),
                            "sku": product.get("sku"),
                            "description": product.get("description")
                        }
                    })
                else:
                    enriched_items.append({
                        **item,
                        "product": {"error": "Product not found"}
                    })
            except Exception as e:
                logger.error(f"Error fetching product data: {e}")
                enriched_items.append({
                    **item,
                    "product": {"error": str(e)}
                })
        
        # Return the enriched order
        return {
            **order,
            "items": enriched_items
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
