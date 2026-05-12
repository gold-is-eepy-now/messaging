package com.example.fedchat

import kotlinx.coroutines.flow.MutableSharedFlow
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import org.json.JSONObject

/**
 * Lightweight Android websocket client for app.py server protocol.
 */
class FedChatClient(
    private val serverUrl: String,
    private val username: String,
    private val client: OkHttpClient = OkHttpClient()
) {
    val events = MutableSharedFlow<String>(extraBufferCapacity = 100)
    private var socket: WebSocket? = null

    fun connect() {
        val req = Request.Builder().url(serverUrl).build()
        socket = client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                webSocket.send(JSONObject(mapOf("type" to "register", "username" to username)).toString())
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                events.tryEmit(text)
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                events.tryEmit("{\"type\":\"error\",\"message\":\"${t.message}\"}")
            }
        })
    }

    fun sendDm(to: String, text: String) {
        socket?.send(
            JSONObject(
                mapOf(
                    "type" to "dm",
                    "from" to username,
                    "to" to to,
                    "text" to text
                )
            ).toString()
        )
    }

    fun createGroup(group: String) {
        socket?.send(JSONObject(mapOf("type" to "group_create", "group" to group, "creator" to username)).toString())
    }

    fun joinGroup(group: String) {
        socket?.send(JSONObject(mapOf("type" to "group_join", "group" to group, "username" to username)).toString())
    }

    fun sendGroupMessage(group: String, text: String) {
        socket?.send(
            JSONObject(
                mapOf(
                    "type" to "group_msg",
                    "group" to group,
                    "from" to username,
                    "text" to text
                )
            ).toString()
        )
    }

    fun sendCallOffer(to: String, sdp: String) {
        socket?.send(JSONObject(mapOf("type" to "call_offer", "from" to username, "to" to to, "sdp" to sdp)).toString())
    }

    fun sendCallAnswer(to: String, sdp: String) {
        socket?.send(JSONObject(mapOf("type" to "call_answer", "from" to username, "to" to to, "sdp" to sdp)).toString())
    }

    fun sendIceCandidate(to: String, candidate: String) {
        socket?.send(JSONObject(mapOf("type" to "ice_candidate", "from" to username, "to" to to, "candidate" to candidate)).toString())
    }

    fun close() {
        socket?.close(1000, "bye")
    }
}
