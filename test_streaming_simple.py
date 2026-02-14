#!/usr/bin/env python3
"""
Simple streaming test endpoint to verify SSE works.
"""
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import json
import asyncio

app = FastAPI()

@app.post("/test-stream")
async def test_stream():
    """Simple streaming endpoint for testing."""
    
    async def generate():
        for i in range(5):
            yield f"data: {json.dumps({'type': 'chunk', 'content': f'Message {i}', 'num': i})}\n\n"
            await asyncio.sleep(0.1)
        yield f"data: {json.dumps({'type': 'done'})}\n\n"
    
    return StreamingResponse(generate(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
