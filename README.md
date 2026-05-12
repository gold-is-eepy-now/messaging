# Federated Secure Messaging App (Server + Client)

This project provides a **single Python app** that can run as:
- a messaging **server**
- a command-line **client**

It includes:
- username registration
- direct messages
- group chats
- call/video-call signaling (WebRTC signaling messages; media transport is client-side)
- server-to-server federation with a **custom secure protocol** (signed envelopes)

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Run two federated servers

Terminal 1:
```bash
python app.py server \
  --server-id localhost:9102 \
  --port 9101 \
  --federation-port 9102 \
  --shared-key localhost:9202=demo-secret
```

Terminal 2:
```bash
python app.py server \
  --server-id localhost:9202 \
  --port 9201 \
  --federation-port 9202 \
  --shared-key localhost:9102=demo-secret
```

## Run clients

```bash
python app.py client --server ws://localhost:9101 --username alice
python app.py client --server ws://localhost:9201 --username bob
```

Examples:
- DM: `/dm bob@localhost:9202 hello`
- Group create: `/gcreate engineering`
- Group join: `/gjoin engineering`
- Group message: `/gmsg engineering standup at 10`
- Call signaling: `/call bob@localhost:9202`

## Custom secure protocol

Federated payloads are wrapped as:
- `src_server`
- `dst_server`
- `payload`
- `timestamp`
- `nonce`
- `sig`

`sig` is HMAC-SHA256 over canonical JSON with a per-peer shared secret. The receiver verifies:
- signature
- server identity
- timestamp freshness (anti-replay window)

This gives integrity + origin authenticity for inter-server transfers.

## Android support

An Android client scaffold is included in `android-client/` with a Kotlin `FedChatClient` class that can register users, send DMs, manage groups, and exchange call signaling messages over WebSocket. See `android-client/README.md` for setup in Android Studio.


## Desktop GUI

Run a desktop graphical client:

```bash
python desktop_gui.py
```

The GUI supports connect/register, DM, group actions, and call-offer signaling.
