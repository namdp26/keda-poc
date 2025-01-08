from fastapi import FastAPI, Response, HTTPException
from prometheus_client import generate_latest, Counter, Histogram, Gauge
from prometheus_client.core import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator
from typing import List, Optional
from pydantic import BaseModel
import time
import random
import uuid

# Models
class Book(BaseModel):
    id: str
    title: str
    author: str
    price: float

class Order(BaseModel):
    id: str
    items: List[str]  # List of book IDs
    total: float
    status: str

app = FastAPI(title="FastAPI Bookstore")

# Sample data
books_db = {
    "book1": Book(id="book1", title="The Great Gatsby", author="F. Scott Fitzgerald", price=9.99),
    "book2": Book(id="book2", title="1984", author="George Orwell", price=12.99),
    "book3": Book(id="book3", title="To Kill a Mockingbird", author="Harper Lee", price=14.99)
}

orders_db = {}

# Create a custom registry
registry = CollectorRegistry()

# Initialize Prometheus metrics
REQUEST_COUNT = Counter(
    'app_request_count_total',
    'Application Request Count',
    ['method', 'endpoint', 'http_status'],
    registry=registry
)

REQUEST_LATENCY = Histogram(
    'app_request_latency_seconds',
    'Application Request Latency',
    ['method', 'endpoint'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
    registry=registry
)

REQUESTS_PER_SECOND = Gauge(
    'app_requests_per_second',
    'Current Requests per Second',
    registry=registry
)

# Track request timestamps for RPS calculation
request_timestamps = []
RPS_WINDOW = 60

# Initialize Prometheus instrumentator
instrumentator = Instrumentator().instrument(app)

@app.on_event("startup")
async def startup():
    instrumentator.expose(app)

def calculate_current_rps():
    current_time = time.time()
    while request_timestamps and current_time - request_timestamps[0] > RPS_WINDOW:
        request_timestamps.pop(0)
    return len(request_timestamps) / RPS_WINDOW if request_timestamps else 0

# Health and Metrics endpoints
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/metrics")
async def metrics():
    current_rps = calculate_current_rps()
    return {
        "request_count": REQUEST_COUNT._value.sum(),
        "current_rps": current_rps,
        "average_latency": REQUEST_LATENCY._sum.sum() / REQUEST_LATENCY._count.sum() if REQUEST_LATENCY._count.sum() > 0 else 0
    }

@app.get("/prometheus")
async def prometheus_metrics():
    return Response(generate_latest(registry), media_type="text/plain")

# Books endpoints
@app.get("/books")
async def get_books():
    # Simulate random processing time
    time.sleep(random.uniform(0.1, 0.3))
    return list(books_db.values())

@app.get("/books/{book_id}")
async def get_book(book_id: str):
    # Simulate random processing time
    time.sleep(random.uniform(0.1, 0.2))
    if book_id not in books_db:
        raise HTTPException(status_code=404, detail="Book not found")
    return books_db[book_id]

@app.post("/books/search")
async def search_books(keyword: str):
    # Simulate random processing time
    time.sleep(random.uniform(0.2, 0.4))
    results = [
        book for book in books_db.values()
        if keyword.lower() in book.title.lower() or keyword.lower() in book.author.lower()
    ]
    return results

# Orders endpoints
@app.post("/orders")
async def create_order(book_ids: List[str]):
    # Simulate random processing time
    time.sleep(random.uniform(0.3, 0.5))
    
    # Validate books exist
    total = 0
    for book_id in book_ids:
        if book_id not in books_db:
            raise HTTPException(status_code=404, detail=f"Book {book_id} not found")
        total += books_db[book_id].price
    
    order_id = str(uuid.uuid4())
    order = Order(
        id=order_id,
        items=book_ids,
        total=total,
        status="pending"
    )
    orders_db[order_id] = order
    return order

@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    # Simulate random processing time
    time.sleep(random.uniform(0.1, 0.2))
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    return orders_db[order_id]

@app.put("/orders/{order_id}/status")
async def update_order_status(order_id: str, status: str):
    # Simulate random processing time
    time.sleep(random.uniform(0.2, 0.3))
    if order_id not in orders_db:
        raise HTTPException(status_code=404, detail="Order not found")
    orders_db[order_id].status = status
    return orders_db[order_id]

@app.middleware("http")
async def track_requests(request, call_next):
    # Record request timestamp for RPS calculation
    current_time = time.time()
    request_timestamps.append(current_time)
    
    # Update RPS metric
    REQUESTS_PER_SECOND.set(calculate_current_rps())
    
    # Track latency
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    # Update metrics
    REQUEST_COUNT.labels(
        method=request.method,
        endpoint=request.url.path,
        http_status=response.status_code
    ).inc()
    
    REQUEST_LATENCY.labels(
        method=request.method,
        endpoint=request.url.path
    ).observe(duration)
    
    return response

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)