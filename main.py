from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# CORS (optional)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global set of connected clients
clients = set()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.add(websocket)

    try:
        while True:
            data = await websocket.receive()
            
            # Handle text messages
            if "text" in data:
                message = data["text"]
                if message.startswith("#file"):
                    _, file_name, file_size = message.split("|")
                    file_size = int(file_size)
                    file_data = b""

                    while len(file_data) < file_size:
                        chunk = await websocket.receive_bytes()
                        file_data += chunk

                    os.makedirs("received_files", exist_ok=True)
                    with open(f"received_files/{file_name}", "wb") as f:
                        f.write(file_data)

                    # Notify others
                    await broadcast(f"Received file: {file_name}", exclude=websocket)
                else:
                    await broadcast(message, exclude=websocket)

    except WebSocketDisconnect:
        print("Client disconnected")
    finally:
        clients.discard(websocket)

async def broadcast(message: str, exclude: WebSocket = None):
    to_remove = []
    for client in clients:
        if client != exclude:
            try:
                await client.send_text(message)
            except:
                to_remove.append(client)
    for client in to_remove:
        clients.discard(client)
