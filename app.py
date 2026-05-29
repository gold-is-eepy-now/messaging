import argparse
import asyncio
import base64
import dataclasses
import hashlib
import hmac
import json
import os
import secrets
import ssl
import time
from collections import defaultdict
from typing import Dict, List, Optional, Set, Tuple

import websockets
from websockets.server import WebSocketServerProtocol


def now_ts() -> int:
    return int(time.time())


def b64e(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode()


def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s.encode())


@dataclasses.dataclass
class ServerMessage:
    src_server: str
    dst_server: str
    payload: dict
    timestamp: int
    nonce: str
    sig: str


class SecureFederationProtocol:
    """Custom secure envelope: canonical JSON payload + HMAC-SHA256 signature."""

    def __init__(self, shared_keys: Dict[str, str], local_server_id: str):
        self.shared_keys = shared_keys
        self.local_server_id = local_server_id

    @staticmethod
    def canonical(obj: dict) -> bytes:
        return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()

    def sign(self, dst_server: str, payload: dict, timestamp: Optional[int] = None, nonce: Optional[str] = None) -> ServerMessage:
        if dst_server not in self.shared_keys:
            raise ValueError(f"No shared key with server {dst_server}")
        timestamp = timestamp or now_ts()
        nonce = nonce or secrets.token_hex(12)
        core = {
            "src_server": self.local_server_id,
            "dst_server": dst_server,
            "payload": payload,
            "timestamp": timestamp,
            "nonce": nonce,
        }
        secret = self.shared_keys[dst_server].encode()
        sig = hmac.new(secret, self.canonical(core), hashlib.sha256).digest()
        return ServerMessage(sig=b64e(sig), **core)

    def verify(self, data: dict) -> ServerMessage:
        required = ["src_server", "dst_server", "payload", "timestamp", "nonce", "sig"]
        for key in required:
            if key not in data:
                raise ValueError(f"missing {key}")
        src = data["src_server"]
        if src not in self.shared_keys:
            raise ValueError(f"unknown peer server {src}")
        core = {
            "src_server": data["src_server"],
            "dst_server": data["dst_server"],
            "payload": data["payload"],
            "timestamp": data["timestamp"],
            "nonce": data["nonce"],
        }
        secret = self.shared_keys[src].encode()
        expected = hmac.new(secret, self.canonical(core), hashlib.sha256).digest()
        got = b64d(data["sig"])
        if not hmac.compare_digest(expected, got):
            raise ValueError("bad signature")
        if abs(now_ts() - int(data["timestamp"])) > 60:
            raise ValueError("stale packet")
        return ServerMessage(**data)


class MessagingServer:
    def __init__(self, server_id: str, host: str, port: int, federation_port: int, shared_keys: Dict[str, str]):
        self.server_id = server_id
        self.host = host
        self.port = port
        self.federation_port = federation_port
        self.proto = SecureFederationProtocol(shared_keys, server_id)

        self.users: Dict[str, WebSocketServerProtocol] = {}
        self.user_server: Dict[str, str] = {}
        self.groups: Dict[str, Set[str]] = defaultdict(set)

    async def client_handler(self, ws: WebSocketServerProtocol):
        username = None
        try:
            async for raw in ws:
                msg = json.loads(raw)
                t = msg.get("type")
                if t == "register":
                    username = msg["username"]
                    self.users[username] = ws
                    self.user_server[username] = self.server_id
                    await ws.send(json.dumps({"type": "ok", "message": f"registered {username}@{self.server_id}"}))
                elif t == "dm":
                    await self.handle_dm(msg)
                elif t == "group_create":
                    self.groups[msg["group"]].add(msg["creator"])
                elif t == "group_join":
                    self.groups[msg["group"]].add(msg["username"])
                elif t == "group_msg":
                    await self.handle_group(msg)
                elif t == "call_offer" or t == "call_answer" or t == "ice_candidate":
                    await self.route_signal(msg)
                else:
                    await ws.send(json.dumps({"type": "error", "message": "unknown type"}))
        finally:
            if username and self.users.get(username) is ws:
                del self.users[username]

    async def route_signal(self, msg: dict):
        target = msg["to"]
        if "@" in target and target.split("@", 1)[1] != self.server_id:
            await self.forward_remote(target, msg)
        elif target in self.users:
            await self.users[target].send(json.dumps(msg))

    async def handle_dm(self, msg: dict):
        to = msg["to"]
        if "@" in to:
            _, srv = to.split("@", 1)
            if srv != self.server_id:
                await self.forward_remote(to, {"type": "dm_deliver", **msg})
                return
            to = to.split("@", 1)[0]
        if to in self.users:
            await self.users[to].send(json.dumps({"type": "dm", "from": msg["from"], "text": msg["text"]}))

    async def handle_group(self, msg: dict):
        group = msg["group"]
        for member in list(self.groups[group]):
            if member == msg["from"]:
                continue
            if "@" in member and member.split("@", 1)[1] != self.server_id:
                await self.forward_remote(member, {"type": "group_deliver", **msg, "to": member})
            elif member in self.users:
                await self.users[member].send(json.dumps({"type": "group_msg", "group": group, "from": msg["from"], "text": msg["text"]}))

    async def forward_remote(self, recipient: str, payload: dict):
        _, dst_server = recipient.split("@", 1)
        signed = self.proto.sign(dst_server, {"recipient": recipient, "inner": payload})
        uri = f"ws://{dst_server}/federation"
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps(dataclasses.asdict(signed)))
        except Exception as e:
            print("federation send failed", e)

    async def federation_handler(self, ws: WebSocketServerProtocol):
        async for raw in ws:
            try:
                signed = self.proto.verify(json.loads(raw))
            except Exception as e:
                await ws.send(json.dumps({"type": "reject", "reason": str(e)}))
                continue
            inner = signed.payload["inner"]
            recipient = signed.payload["recipient"]
            username = recipient.split("@", 1)[0]
            if inner["type"] == "dm_deliver" and username in self.users:
                await self.users[username].send(json.dumps({"type": "dm", "from": inner["from"], "text": inner["text"]}))
            elif inner["type"] == "group_deliver" and username in self.users:
                await self.users[username].send(json.dumps({"type": "group_msg", "group": inner["group"], "from": inner["from"], "text": inner["text"]}))
            elif inner["type"] in {"call_offer", "call_answer", "ice_candidate"} and username in self.users:
                await self.users[username].send(json.dumps(inner))

    async def run(self):
        client_srv = await websockets.serve(self.client_handler, self.host, self.port)
        fed_srv = await websockets.serve(self.federation_handler, self.host, self.federation_port, process_request=self._fed_route)
        print(f"Client ws://{self.host}:{self.port} | Federation ws://{self.host}:{self.federation_port}/federation")
        await asyncio.gather(client_srv.wait_closed(), fed_srv.wait_closed())

    async def _fed_route(self, path, request_headers):
        if path != "/federation":
            return (404, [], b"not found")
        return None


async def run_client(server: str, username: str):
    async with websockets.connect(server) as ws:
        await ws.send(json.dumps({"type": "register", "username": username}))
        print(await ws.recv())

        async def reader():
            async for m in ws:
                print("<", m)

        async def writer():
            while True:
                line = await asyncio.to_thread(input, "> ")
                if line.startswith("/dm "):
                    to, text = line[4:].split(" ", 1)
                    await ws.send(json.dumps({"type": "dm", "from": username, "to": to, "text": text}))
                elif line.startswith("/gcreate "):
                    group = line.split(" ", 1)[1]
                    await ws.send(json.dumps({"type": "group_create", "group": group, "creator": username}))
                elif line.startswith("/gjoin "):
                    group = line.split(" ", 1)[1]
                    await ws.send(json.dumps({"type": "group_join", "group": group, "username": username}))
                elif line.startswith("/gmsg "):
                    rem = line[6:]
                    group, text = rem.split(" ", 1)
                    await ws.send(json.dumps({"type": "group_msg", "group": group, "from": username, "text": text}))
                elif line.startswith("/call "):
                    to = line.split(" ", 1)[1]
                    await ws.send(json.dumps({"type": "call_offer", "from": username, "to": to, "sdp": "fake-offer-sdp"}))
                elif line == "/quit":
                    break
                else:
                    print("commands: /dm /gcreate /gjoin /gmsg /call /quit")

        await asyncio.gather(reader(), writer())


def parse_shared_keys(items: List[str]) -> Dict[str, str]:
    result = {}
    for item in items:
        host, key = item.split("=", 1)
        result[host] = key
    return result


def main():
    parser = argparse.ArgumentParser(description="Federated secure messaging app (server+client)")
    sub = parser.add_subparsers(dest="mode", required=True)

    s = sub.add_parser("server")
    s.add_argument("--server-id", required=True, help="server address key, e.g. localhost:9002")
    s.add_argument("--host", default="0.0.0.0")
    s.add_argument("--port", type=int, default=9001)
    s.add_argument("--federation-port", type=int, default=9002)
    s.add_argument("--shared-key", action="append", default=[], help="peer_host:port=sharedsecret")

    c = sub.add_parser("client")
    c.add_argument("--server", required=True, help="ws://host:port")
    c.add_argument("--username", required=True)

    args = parser.parse_args()
    if args.mode == "server":
        shared_keys = parse_shared_keys(args.shared_key)
        server = MessagingServer(args.server_id, args.host, args.port, args.federation_port, shared_keys)
        asyncio.run(server.run())
    else:
        asyncio.run(run_client(args.server, args.username))


if __name__ == "__main__":
    main()
