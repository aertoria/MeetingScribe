#!/usr/bin/env python3
"""Test script to verify WebSocket diarization endpoint"""

import asyncio
import websockets
import json

async def test_websocket():
    uri = "ws://localhost:5000/ws/transcribe"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to WebSocket endpoint")
            
            # Wait for ready message
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Received: {data}")
            
            # Send a test command
            await websocket.send(json.dumps({"command": "get_summary"}))
            
            # Wait for response
            response = await websocket.recv()
            data = json.loads(response)
            print(f"Summary response: {data}")
            
            # Send stop command
            await websocket.send(json.dumps({"command": "stop"}))
            print("Test completed successfully!")
            
    except Exception as e:
        print(f"Test failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())