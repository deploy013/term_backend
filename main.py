import os
import asyncio
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

# Enable CORS for potential HTTP routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global list of connected WebSocket clients
connected_clients: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            data = await websocket.receive()
            # Handle text frame
            if data.get("type") == "websocket.receive" and isinstance(data.get("text"), str):
                message = data["text"]
                if message.startswith("#file|"):
                    await handle_file_transfer(websocket, message)
                else:
                    await broadcast(message, sender=websocket)
            # Ignore binary frames here; file handler will read them explicitly
    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def broadcast(message: str, sender: WebSocket = None):
    """Send a text message to all connected clients except the sender."""
    to_remove = []
    for client in connected_clients:
        if client != sender:
            try:
                await client.send_text(message)
            except Exception:
                to_remove.append(client)
    for client in to_remove:
        connected_clients.remove(client)

async def handle_file_transfer(websocket: WebSocket, header: str):
    _, file_name, file_size = header.split("|")
    total_size = int(file_size)
    received = 0
    chunks = []

    # 1) Read incoming file data
    while received < total_size:
        frame = await websocket.receive_bytes()
        chunks.append(frame)
        received += len(frame)
    file_data = b"".join(chunks)

    # 2) Save locally on the server
    os.makedirs("received_files", exist_ok=True)
    path = os.path.join("received_files", file_name)
    with open(path, "wb") as f:
        f.write(file_data)
    print(f"Saved file {file_name} ({received} bytes)")

    # 3) Forward to every other client
    for client in connected_clients:
        if client is websocket:
            continue

        # send the same header
        await client.send_text(header)
        # then send the binary data in the same chunk sizes
        for chunk in chunks:
            await client.send_bytes(chunk)
if __name__ == "__main__":
    port = int(os.getenv("PORT", 5032))
    uvicorn.run(app, host="0.0.0.0", port=port)
