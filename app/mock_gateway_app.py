from fastapi import FastAPI

from app.mock_gateway.router import router as mock_gateway_router

app = FastAPI(title="Mock Payment Gateway")
app.include_router(mock_gateway_router)
