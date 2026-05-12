# Android Support (FedChat)

This module adds Android client support for the Python messaging server (`app.py`).

## What it provides

- Gradle Android project skeleton (`android-client/`)
- `FedChatClient` Kotlin class using OkHttp WebSocket
- Compatibility with server message types:
  - register
  - dm
  - group_create / group_join / group_msg
  - call_offer / call_answer / ice_candidate

## Use

1. Open `android-client/` in Android Studio.
2. Sync Gradle.
3. Use `FedChatClient("ws://10.0.2.2:9101", "alice")` on emulator.
4. Observe incoming JSON events from `events` flow and map them to your UI.

## Notes

- Media for voice/video calls should be implemented via Android WebRTC; this client currently handles signaling only.
- For production, run messaging over TLS (`wss://`) and add certificate pinning.
