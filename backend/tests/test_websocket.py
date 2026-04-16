"""
United Agents - WebSocket Feed Tests
Tests the WebSocket endpoint for real-time feed updates.
"""

import pytest
import asyncio
import websockets
import json
import os

# WebSocket URL - use the public URL with ws:// protocol
BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://e5920ce5-77da-44f3-a144-d0555c942f9c.preview.emergentagent.com')
WS_URL = BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://') + '/api/v1/ws/feed'


class TestWebSocketFeed:
    """WebSocket feed endpoint tests"""
    
    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection can be established"""
        try:
            async with websockets.connect(WS_URL, close_timeout=5) as ws:
                print(f"✓ WebSocket connected to {WS_URL}")
                # Connection is established if we reach this point
                assert ws is not None
                print("✓ WebSocket connection verified")
        except Exception as e:
            pytest.fail(f"WebSocket connection failed: {e}")
    
    @pytest.mark.asyncio
    async def test_websocket_ping_pong(self):
        """Test WebSocket responds to ping with pong"""
        try:
            async with websockets.connect(WS_URL, close_timeout=5) as ws:
                # Send ping
                await ws.send("ping")
                print("✓ Sent ping")
                
                # Wait for pong response
                response = await asyncio.wait_for(ws.recv(), timeout=5)
                assert response == "pong", f"Expected 'pong', got '{response}'"
                print("✓ Received pong response")
        except asyncio.TimeoutError:
            pytest.fail("WebSocket ping/pong timed out")
        except Exception as e:
            pytest.fail(f"WebSocket ping/pong failed: {e}")
    
    @pytest.mark.asyncio
    async def test_websocket_multiple_pings(self):
        """Test WebSocket handles multiple ping/pong cycles"""
        try:
            async with websockets.connect(WS_URL, close_timeout=5) as ws:
                for i in range(3):
                    await ws.send("ping")
                    response = await asyncio.wait_for(ws.recv(), timeout=5)
                    assert response == "pong"
                    print(f"✓ Ping/pong cycle {i+1} successful")
        except Exception as e:
            pytest.fail(f"Multiple ping/pong failed: {e}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
