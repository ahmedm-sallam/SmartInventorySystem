# SmartInventorySystem

SmartInventorySystem is a microservices-based inventory management system designed to handle products, inventory, orders, and notifications efficiently. It is built using FastAPI and Docker for scalability and modularity.

## Features

- **Product Service**: Manages product information such as name, description, price, and SKU.
- **Inventory Service**: Tracks stock levels and locations of products.
- **Order Service**: Handles customer orders and updates inventory accordingly.
- **Notification Service**: Sends notifications for events like low stock or order status updates.
- **API Gateway**: Acts as a single entry point for all microservices.

## Architecture

The system follows a microservices architecture with the following components:

1. **Product Service**: Manages product-related data.
2. **Inventory Service**: Manages inventory and stock levels.
3. **Order Service**: Handles customer orders and inventory updates.
4. **Notification Service**: Sends notifications via email or SMS.
5. **API Gateway**: Routes requests to the appropriate microservice.

Each service is containerized using Docker and communicates via HTTP.

## Prerequisites

- Docker and Docker Compose
- Python 3.8+

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/your-repo/SmartInventorySystem.git
   cd SmartInventorySystem
   ```

2. Build and start the services using Docker Compose:
   ```bash
   docker-compose up --build
   ```

3. Access the API Gateway at `http://localhost:5000`.

## Environment Variables

Each service uses environment variables for configuration. Below are the key variables:

- **Product Service**:
  - `DATABASE_URL`: Database connection string
- **Inventory Service**:
  - `PRODUCT_SERVICE_URL`: URL of the Product Service
  - `STOCK_THRESHOLD`: Threshold for low stock notifications
- **Order Service**:
  - `INVENTORY_SERVICE_URL`: URL of the Inventory Service
- **Notification Service**:
  - `DATABASE_URL`: Database connection string

## API Endpoints

### API Gateway

- `GET /`: Root endpoint
- `GET /health`: Health check
- `/{service}/{path}`: Proxy to specific service

### Product Service

- `POST /products/`: Create a new product
- `GET /products/`: List all products
- `GET /products/{product_id}`: Get product details
- `PUT /products/{product_id}`: Update product details
- `DELETE /products/{product_id}`: Delete a product

### Inventory Service

- `POST /inventory/`: Add inventory item
- `GET /inventory/`: List inventory items

### Order Service

- `POST /orders/`: Create a new order
- `GET /orders/`: List all orders

### Notification Service

- `POST /notifications/`: Create a new notification
- `GET /notifications/`: List all notifications

## Project Structure

```
SmartInventorySystem/
├── api_gateway/
│   ├── Dockerfile
│   ├── main.py
│   └── requirements.txt
├── inventory_service/
│   ├── database.py
│   ├── Dockerfile
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   └── schemas.py
├── notification_service/
│   ├── database.py
│   ├── Dockerfile
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   └── schemas.py
├── order_service/
│   ├── database.py
│   ├── Dockerfile
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   └── schemas.py
├── product_service/
│   ├── database.py
│   ├── Dockerfile
│   ├── main.py
│   ├── models.py
│   ├── requirements.txt
│   └── schemas.py
├── docker-compose.yaml
└── README.md
```

## Contributing

Contributions are welcome! Please fork the repository and submit a pull request.

## License

This project is licensed under the MIT License. See the LICENSE file for details.

## Contact

For questions or support, please contact [AhmedM.SallamIbrahim@Gmail.com].
