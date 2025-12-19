# manager.py
from fastapi import WebSocket
from typing import Dict, Set
from collections import defaultdict

class ConnectionManager:
    def __init__(self):
        # Ключ — user_id (int), а не email (str)
        self.active_connections: Dict[int, WebSocket] = {}
        self.group_memberships: Dict[int, Set[int]] = defaultdict(set)  # group_id → {user_id}

    async def connect(self, websocket: WebSocket, user_id: int):
        
        self.active_connections[user_id] = websocket

    def disconnect(self, user_id: int):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        for members in self.group_memberships.values():
            members.discard(user_id)

    def add_to_group(self, group_id: int, user_id: int):
        self.group_memberships[group_id].add(user_id)

    def remove_from_group(self, group_id: int, user_id: int):
        self.group_memberships[group_id].discard(user_id)

    async def send_personal_message(self, message: dict, user_id: int):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)

    async def send_group_message(self, message: dict, group_id: int):
        for user_id in self.group_memberships[group_id]:
            if user_id in self.active_connections:
                await self.active_connections[user_id].send_json(message)

manager = ConnectionManager()