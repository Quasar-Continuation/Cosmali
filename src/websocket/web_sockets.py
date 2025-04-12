import asyncio
import json
from quart import websocket

from util.blacklist.ip_blacklist import black_list_ip
from util.system.stats import get_system_stats


connected_websockets = set()


async def stats_broadcaster():
    """Task to broadcast system stats to all connected websockets"""
    while True:
        if connected_websockets:  # only get stats if someone is connected
            stats = get_system_stats()
            message = json.dumps({"type": "system_stats", "data": stats})

            websockets = connected_websockets.copy()
            for queue in websockets:
                await queue.put(message)

        await asyncio.sleep(1)


def register_websocket_routes(app):
    """Register the WebSocket routes with the Quart app"""

    @app.websocket("/ws")
    @black_list_ip()
    async def ws():
        """Websocket endpoint for real-time updates"""

        queue = asyncio.Queue()
        connected_websockets.add(queue)

        try:

            stats = get_system_stats()
            await websocket.send(json.dumps({"type": "system_stats", "data": stats}))

            async def receiver():
                while True:
                    data = await websocket.receive()

            async def sender():
                while True:
                    message = await queue.get()
                    await websocket.send(message)

            receiver_task = asyncio.create_task(receiver())
            sender_task = asyncio.create_task(sender())

            await asyncio.gather(receiver_task, sender_task)
        except asyncio.CancelledError:

            pass
        finally:

            connected_websockets.discard(queue)

    return app
