package com.example.fedchat

import android.os.Bundle
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch

class MainActivity : AppCompatActivity() {
    private lateinit var client: FedChatClient

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            setPadding(24, 24, 24, 24)
        }

        val server = EditText(this).apply { hint = "ws://10.0.2.2:9101"; setText("ws://10.0.2.2:9101") }
        val username = EditText(this).apply { hint = "username"; setText("alice") }
        val to = EditText(this).apply { hint = "recipient (bob@localhost:9202)" }
        val message = EditText(this).apply { hint = "message" }
        val log = TextView(this).apply { text = "Disconnected" }

        val connect = Button(this).apply {
            text = "Connect"
            setOnClickListener {
                client = FedChatClient(server.text.toString(), username.text.toString())
                client.connect()
                lifecycleScope.launch {
                    client.events.collect { event ->
                        log.text = event
                    }
                }
            }
        }

        val sendDm = Button(this).apply {
            text = "Send DM"
            setOnClickListener {
                client.sendDm(to.text.toString(), message.text.toString())
            }
        }

        val call = Button(this).apply {
            text = "Send Call Offer"
            setOnClickListener {
                client.sendCallOffer(to.text.toString(), "android-offer-sdp")
            }
        }

        listOf(server, username, to, message, connect, sendDm, call, log).forEach { root.addView(it) }
        setContentView(root)
    }
}
