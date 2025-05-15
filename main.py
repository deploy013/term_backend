import os
import asyncio
import websockets
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import uvicorn

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connected_clients: List[WebSocket] = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            message = await websocket.receive_text()
            if message.startswith("#file"):
                await handle_file_transfer(websocket, message)
            else:
                await broadcast(message, sender=websocket)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception as e:
        print(f"Error: {e}")
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def broadcast(message: str, sender: WebSocket = None):
    for client in connected_clients:
        if client != sender:
            try:
                await client.send_text(message)
            except Exception as e:
                print(f"Broadcast error: {e}")

async def handle_file_transfer(websocket: WebSocket, header: str):
    try:
        _, file_name, file_size = header.split("|")
        file_size = int(file_size)
        file_data = await websocket.receive_bytes()

        os.makedirs("received_files", exist_ok=True)
        file_path = os.path.join("received_files", file_name)
        with open(file_path, "wb") as f:
            f.write(file_data)

        print(f"Received file: {file_name} ({file_size} bytes)")
        await broadcast(f"{file_name} has been received.", sender=websocket)
    except Exception as e:
        print(f"File transfer error: {e}")
        await broadcast("Error receiving file.", sender=websocket)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5032))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
