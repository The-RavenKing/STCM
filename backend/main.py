from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from typing import List
import uvicorn
from pathlib import Path

from config import config
from database import db
from init_db import init_database

# Import routes
from api.routes import router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("🚀 Starting SillyTavern Campaign Manager...")
    
    # Initialize database
    init_database(config.db_path)
    print(f"✓ Database initialized at {config.db_path}")
    
    # Test Ollama connection
    from services.ollama_client import ollama_client
    success, message = await ollama_client.test_connection()
    print(message)
    
    yield
    
    # Shutdown
    print("👋 Shutting down STCM...")

# Create FastAPI app
app = FastAPI(
    title="SillyTavern Campaign Manager",
    description="Automated lorebook management for D&D campaigns",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Serve frontend static files
frontend_path = Path("frontend")
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory="frontend"), name="static")

# Root endpoint - serve index.html
@app.get("/")
async def read_root():
    """Serve the main dashboard"""
    index_path = frontend_path / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"message": "STCM API is running. Frontend not found."}

# Health check
@app.get("/health")
async def health_check():
    """API health check"""
    return {
        "status": "healthy",
        "database": "connected",
        "ollama": await check_ollama_status()
    }

async def check_ollama_status():
    """Check if Ollama is accessible"""
    from services.ollama_client import ollama_client
    success, _ = await ollama_client.test_connection()
    return "connected" if success else "disconnected"

# WebSocket for real-time updates
active_connections: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_connections:
            active_connections.remove(websocket)

async def broadcast_update(message: dict):
    """Broadcast update to all connected WebSocket clients"""
    disconnected = []
    
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            disconnected.append(connection)
    
    # Remove disconnected clients
    for conn in disconnected:
        active_connections.remove(conn)

# Make broadcast available to other modules
app.state.broadcast = broadcast_update

if __name__ == "__main__":
    # Get server config
    host = config.get('server.host', '0.0.0.0')
    port = config.get('server.port', 8000)
    
    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   SillyTavern Campaign Manager                            ║
║                                                           ║
║   Dashboard: http://localhost:{port}                          ║
║   API Docs:  http://localhost:{port}/docs                     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
