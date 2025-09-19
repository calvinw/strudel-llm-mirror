"""
Strudel MCP Server with static build serving
FastAPI server handling MCP, WebSocket, and serving the built Strudel app
"""

import os
import sys
import json
import logging
import random
import string
from pathlib import Path
from typing import List, Dict
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse, RedirectResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# WebSocket Connection Manager
class ConnectionManager:
    """WebSocket connection manager with session support"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.session_connections: Dict[str, WebSocket] = {}  # session_id -> websocket

    async def connect(self, websocket: WebSocket, session_id: str = None):
        """Accept a WebSocket connection and optionally associate it with a session"""
        await websocket.accept()
        self.active_connections.append(websocket)
        if session_id:
            self.session_connections[session_id] = websocket
            logger.info(f"New WebSocket connection with session {session_id}. Total: {len(self.active_connections)}")
        else:
            logger.info(f"New WebSocket connection. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection and clean up session associations"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

        # Remove from session connections
        session_to_remove = None
        for session_id, ws in self.session_connections.items():
            if ws == websocket:
                session_to_remove = session_id
                break

        if session_to_remove:
            del self.session_connections[session_to_remove]
            logger.info(f"WebSocket disconnected (session {session_to_remove}). Total: {len(self.active_connections)}")
        else:
            logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def send_to_session(self, session_id: str, message: str) -> bool:
        """Send message to specific session. Returns True if successful."""
        if session_id in self.session_connections:
            try:
                await self.session_connections[session_id].send_text(message)
                return True
            except Exception as e:
                logger.error(f"Error sending to session {session_id}: {e}")
                self.disconnect(self.session_connections[session_id])
                return False
        else:
            return False

    def get_connection_count(self) -> int:
        """Get the number of active connections"""
        return len(self.active_connections)

    def generate_session_id(self) -> str:
        """Generate a memorable 4-character session ID (3 letters + 1 digit)"""
        while True:
            letters = ''.join(random.choices(string.ascii_lowercase, k=3))
            digit = random.choice(string.digits)
            session_id = letters + digit
            # Ensure it's not already in use
            if session_id not in self.session_connections:
                return session_id

    def get_session_ids(self) -> List[str]:
        """Get list of active session IDs"""
        return list(self.session_connections.keys())

# Create WebSocket manager
manager = ConnectionManager()

# Import MCP server and connect it to our WebSocket manager
from strudel_mcp_tools import mcp, set_websocket_manager, handle_code_response
set_websocket_manager(manager)

# Create the ASGI app for MCP
mcp_app = mcp.http_app(transport="sse")

# Create main FastAPI app
app = FastAPI(title="Strudel MCP Server with Static Build")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "x-api-key", "Upgrade", "Connection", "Sec-WebSocket-Key", "Sec-WebSocket-Version", "Sec-WebSocket-Protocol"],
    expose_headers=["Content-Type", "Authorization", "x-api-key"],
    max_age=86400
)

# Define static build directory
STATIC_BUILD_DIR = Path(__file__).parent / "website" / "dist"

async def oauth_metadata(request: Request):
    base_url = str(request.base_url).rstrip("/")
    return JSONResponse({
        "issuer": base_url
    })

# Status endpoint (must be before static file serving)
@app.get("/strudel/status")
async def get_status():
    """Get status of WebSocket connections"""
    return {
        "total_connections": manager.get_connection_count(),
        "active_sessions": manager.get_session_ids(),
        "static_build": str(STATIC_BUILD_DIR)
    }

# WebSocket endpoint for Strudel interface
@app.websocket("/strudel/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time communication with the Strudel player"""
    session_id = websocket.query_params.get('session_id')
    logger.info(f"Strudel WebSocket connection attempt with session_id='{session_id}'")

    await manager.connect(websocket, session_id)

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
                if message.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                elif message.get("type") == "current-code-response":
                    request_id = message.get("request_id", "")
                    current_code = message.get("code", "")
                    if request_id:
                        handle_code_response(request_id, current_code)
                elif message.get("type") == "evaluation-error":
                    error_msg = message.get("error", "Unknown error")
                    code_snippet = message.get("code", "Unknown code")
                    logger.error(f"Strudel evaluation error: {error_msg} | Code: {code_snippet}")
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Strudel WebSocket error: {e}")
        manager.disconnect(websocket)

# Serve the main Strudel REPL at /strudel/ specifically
@app.get("/strudel/")
async def serve_strudel_repl():
    """Serve the main Strudel REPL from static build"""
    index_file = STATIC_BUILD_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    else:
        return HTMLResponse(
            content="<h1>Error: Strudel build not found</h1><p>Run 'npm run build' to build the static files</p>",
            status_code=503
        )

# Redirect /strudel to /strudel/
@app.get("/strudel")
async def redirect_to_strudel():
    return RedirectResponse(url="/strudel/", status_code=307)

# Mount static files for all other paths under /strudel/
@app.get("/strudel/{path:path}")
async def serve_strudel_assets(path: str):
    """Serve static assets from the build directory"""
    file_path = STATIC_BUILD_DIR / path

    # Check if file exists
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    # If it's a directory, try to serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")

    # Return 404 if file doesn't exist
    return HTMLResponse(
        content=f"<h1>404: Not Found</h1><p>File not found: {path}</p>",
        status_code=404
    )

# Serve manifest and other root-level assets (before mounts)
@app.get("/manifest.webmanifest")
async def serve_manifest():
    manifest_file = STATIC_BUILD_DIR / "manifest.webmanifest"
    if manifest_file.exists():
        return FileResponse(manifest_file, media_type="application/manifest+json")
    return HTMLResponse(status_code=404)

@app.get("/favicon.ico")
async def serve_favicon():
    favicon_file = STATIC_BUILD_DIR / "favicon.ico"
    if favicon_file.exists():
        return FileResponse(favicon_file, media_type="image/x-icon")
    return HTMLResponse(status_code=404)

# Serve root-level JSON files that Strudel needs
@app.get("/{filename}.json")
async def serve_json_files(filename: str):
    json_file = STATIC_BUILD_DIR / f"{filename}.json"
    if json_file.exists():
        return FileResponse(json_file, media_type="application/json")
    return HTMLResponse(status_code=404)

# Serve icons directory
@app.get("/icons/{filename}")
async def serve_icons(filename: str):
    icon_file = STATIC_BUILD_DIR / "icons" / filename
    if icon_file.exists():
        return FileResponse(icon_file)
    return HTMLResponse(status_code=404)

# Serve service worker
@app.get("/sw.js")
async def serve_service_worker():
    sw_file = STATIC_BUILD_DIR / "sw.js"
    if sw_file.exists():
        return FileResponse(sw_file, media_type="application/javascript")
    return HTMLResponse(status_code=404)

# Serve root-level JavaScript files (like workbox, registerSW, etc.)
@app.get("/{filename}.js")
async def serve_root_js_files(filename: str):
    js_file = STATIC_BUILD_DIR / f"{filename}.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    return HTMLResponse(status_code=404)

# Serve documentation routes under /strudel/ namespace
@app.get("/strudel/learn/")
async def serve_learn_root():
    """Serve learn root documentation"""
    index_file = STATIC_BUILD_DIR / "learn" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/strudel/learn/{path:path}")
async def serve_learn(path: str):
    """Serve learn documentation"""
    file_path = STATIC_BUILD_DIR / "learn" / path

    # If it's a directory, try to serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")

    # If it's a file, serve it directly
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    return HTMLResponse(status_code=404)

@app.get("/strudel/workshop/")
async def serve_workshop_root():
    """Serve workshop root documentation"""
    index_file = STATIC_BUILD_DIR / "workshop" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/strudel/workshop/{path:path}")
async def serve_workshop(path: str):
    """Serve workshop documentation"""
    file_path = STATIC_BUILD_DIR / "workshop" / path

    # If it's a directory, try to serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")

    # If it's a file, serve it directly
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    return HTMLResponse(status_code=404)

@app.get("/strudel/tutorial/")
async def serve_tutorial_root():
    """Serve tutorial root documentation"""
    index_file = STATIC_BUILD_DIR / "tutorial" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/strudel/tutorial/{path:path}")
async def serve_tutorial(path: str):
    """Serve tutorial documentation"""
    file_path = STATIC_BUILD_DIR / "tutorial" / path

    # If it's a directory, try to serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")

    # If it's a file, serve it directly
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    return HTMLResponse(status_code=404)

@app.get("/strudel/technical-manual/")
async def serve_technical_manual_root():
    """Serve technical manual root documentation"""
    index_file = STATIC_BUILD_DIR / "technical-manual" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/strudel/technical-manual/{path:path}")
async def serve_technical_manual(path: str):
    """Serve technical manual documentation"""
    file_path = STATIC_BUILD_DIR / "technical-manual" / path

    # If it's a directory, try to serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")

    # If it's a file, serve it directly
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    return HTMLResponse(status_code=404)

@app.get("/strudel/understand/")
async def serve_understand_root():
    """Serve understand root documentation"""
    index_file = STATIC_BUILD_DIR / "understand" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/strudel/understand/{path:path}")
async def serve_understand(path: str):
    """Serve understand documentation"""
    file_path = STATIC_BUILD_DIR / "understand" / path

    # If it's a directory, try to serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")

    # If it's a file, serve it directly
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    return HTMLResponse(status_code=404)

@app.get("/strudel/de/")
async def serve_de_root():
    """Serve German documentation root"""
    index_file = STATIC_BUILD_DIR / "de" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/strudel/de/{path:path}")
async def serve_de(path: str):
    """Serve German documentation"""
    file_path = STATIC_BUILD_DIR / "de" / path

    # If it's a directory, try to serve index.html
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")

    # If it's a file, serve it directly
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)

    return HTMLResponse(status_code=404)

# Root-level documentation routes (for navigation links in docs)
@app.get("/workshop/")
async def serve_workshop_root_direct():
    """Serve workshop root documentation at root level"""
    index_file = STATIC_BUILD_DIR / "workshop" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/workshop/{path:path}")
async def serve_workshop_direct(path: str):
    """Serve workshop documentation at root level"""
    file_path = STATIC_BUILD_DIR / "workshop" / path
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return HTMLResponse(status_code=404)

@app.get("/learn/")
async def serve_learn_root_direct():
    """Serve learn root documentation at root level"""
    index_file = STATIC_BUILD_DIR / "learn" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/learn/{path:path}")
async def serve_learn_direct(path: str):
    """Serve learn documentation at root level"""
    file_path = STATIC_BUILD_DIR / "learn" / path
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return HTMLResponse(status_code=404)

@app.get("/tutorial/")
async def serve_tutorial_root_direct():
    """Serve tutorial root documentation at root level"""
    index_file = STATIC_BUILD_DIR / "tutorial" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/tutorial/{path:path}")
async def serve_tutorial_direct(path: str):
    """Serve tutorial documentation at root level"""
    file_path = STATIC_BUILD_DIR / "tutorial" / path
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return HTMLResponse(status_code=404)

@app.get("/technical-manual/")
async def serve_technical_manual_root_direct():
    """Serve technical manual root documentation at root level"""
    index_file = STATIC_BUILD_DIR / "technical-manual" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/technical-manual/{path:path}")
async def serve_technical_manual_direct(path: str):
    """Serve technical manual documentation at root level"""
    file_path = STATIC_BUILD_DIR / "technical-manual" / path
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return HTMLResponse(status_code=404)

@app.get("/understand/")
async def serve_understand_root_direct():
    """Serve understand root documentation at root level"""
    index_file = STATIC_BUILD_DIR / "understand" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/understand/{path:path}")
async def serve_understand_direct(path: str):
    """Serve understand documentation at root level"""
    file_path = STATIC_BUILD_DIR / "understand" / path
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return HTMLResponse(status_code=404)

@app.get("/de/")
async def serve_de_root_direct():
    """Serve German documentation root at root level"""
    index_file = STATIC_BUILD_DIR / "de" / "index.html"
    if index_file.exists():
        return FileResponse(index_file, media_type="text/html")
    return HTMLResponse(status_code=404)

@app.get("/de/{path:path}")
async def serve_de_direct(path: str):
    """Serve German documentation at root level"""
    file_path = STATIC_BUILD_DIR / "de" / path
    if file_path.is_dir():
        index_file = file_path / "index.html"
        if index_file.exists():
            return FileResponse(index_file, media_type="text/html")
    if file_path.exists() and file_path.is_file():
        return FileResponse(file_path)
    return HTMLResponse(status_code=404)

# Mount static assets at root level for assets referenced by the HTML
app.mount("/_astro", StaticFiles(directory=str(STATIC_BUILD_DIR / "_astro")), name="astro_assets")
app.mount("/static", StaticFiles(directory=str(STATIC_BUILD_DIR)), name="static_assets")

# Add the OAuth metadata route before mounting
app.add_api_route("/.well-known/oauth-authorization-server", oauth_metadata, methods=["GET"])

# Mount MCP server at root (must be last)
app.mount("/", mcp_app)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"""
🎵 Strudel MCP Server Starting on port {port}!

🌐 Web Interface: http://localhost:{port}/strudel/
🤖 MCP Endpoint: http://localhost:{port}/sse
⚡ WebSocket: http://localhost:{port}/strudel/ws
📊 Status: http://localhost:{port}/strudel/status

📁 Serving static build from: {STATIC_BUILD_DIR}

Ready for both web browsers and Claude integration! 🎯
    """)
    uvicorn.run(app, host="0.0.0.0", port=port)