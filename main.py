import os
import asyncio
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

app = FastAPI()

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
    print(f"Client connected: {websocket.client}")
    try:
        while True:
            data = await websocket.receive()
            if data.get("type") == "websocket.receive" and isinstance(data.get("text"), str):
                message = data["text"]
                if message.startswith("#file|"):
                    print(f"Received file header from {websocket.client}: {message}")
                    await handle_file_transfer(websocket, message)
                else:
                    print(f"Received message from {websocket.client}: {message}")
                    await broadcast(message, sender=websocket)
    except WebSocketDisconnect:
        print(f"Client disconnected: {websocket.client}")
    except Exception as e:
        print(f"WebSocket error from {websocket.client}: {e}")
    finally:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

async def broadcast(message: str, sender: WebSocket = None):
    to_remove = []
    for client in connected_clients:
        if client != sender:
            try:
                await client.send_text(message)
                print(f"Broadcasted message to {client.client}: {message}")
            except Exception:
                to_remove.append(client)
    for client in to_remove:
        connected_clients.remove(client)

async def handle_file_transfer(websocket: WebSocket, header: str):
    _, file_name, file_size = header.split("|")
    total_size = int(file_size)
    received = 0
    chunks = []

    # 1) Read the file bytes in chunks
    while received < total_size:
        frame = await websocket.receive_bytes()
        chunks.append(frame)
        received += len(frame)

    print(f"Received complete file '{file_name}' ({received} bytes) from {websocket.client}")

    # 2) Immediately broadcast to all other clients (no disk save)
    for client in connected_clients:
        if client is websocket:
            continue

        try:
            # Send header
            await client.send_text(header)
            print(f"Sent file header to {client.client}: {header}")
            # Send all chunks
            for chunk in chunks:
                await client.send_bytes(chunk)
            print(f"Sent complete file '{file_name}' ({received} bytes) to {client.client}")
        except Exception as e:
            print(f"Error sending file to {client.client}: {e}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5032))
    uvicorn.run(app, host="0.0.0.0", port=port)
