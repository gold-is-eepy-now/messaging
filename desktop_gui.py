import asyncio
import json
import queue
import threading
import tkinter as tk
from tkinter import ttk

import websockets


class DesktopChatGUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FedChat Desktop")
        self.root.geometry("820x560")

        self.server_var = tk.StringVar(value="ws://localhost:9101")
        self.username_var = tk.StringVar(value="alice")
        self.to_var = tk.StringVar()
        self.group_var = tk.StringVar(value="engineering")

        self.outgoing = queue.Queue()
        self.ws = None

        self._build_ui()
        self._start_loop_thread()
        self.root.after(100, self._pump_outgoing)

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=8)
        top.pack(fill="x")
        ttk.Label(top, text="Server").grid(row=0, column=0)
        ttk.Entry(top, textvariable=self.server_var, width=35).grid(row=0, column=1, padx=4)
        ttk.Label(top, text="Username").grid(row=0, column=2)
        ttk.Entry(top, textvariable=self.username_var, width=14).grid(row=0, column=3, padx=4)
        ttk.Button(top, text="Connect", command=self.connect).grid(row=0, column=4)

        mid = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        mid.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(mid)
        right = ttk.Frame(mid)
        mid.add(left, weight=3)
        mid.add(right, weight=2)

        self.log = tk.Text(left, height=25)
        self.log.pack(fill="both", expand=True)

        ttk.Label(right, text="Recipient (user or user@server)").pack(anchor="w")
        ttk.Entry(right, textvariable=self.to_var).pack(fill="x", pady=2)
        ttk.Label(right, text="Message").pack(anchor="w")
        self.msg_entry = ttk.Entry(right)
        self.msg_entry.pack(fill="x", pady=2)
        ttk.Button(right, text="Send DM", command=self.send_dm).pack(fill="x", pady=3)

        ttk.Separator(right).pack(fill="x", pady=6)

        ttk.Label(right, text="Group").pack(anchor="w")
        ttk.Entry(right, textvariable=self.group_var).pack(fill="x", pady=2)
        ttk.Button(right, text="Create Group", command=self.gcreate).pack(fill="x", pady=2)
        ttk.Button(right, text="Join Group", command=self.gjoin).pack(fill="x", pady=2)
        ttk.Button(right, text="Send Group Msg", command=self.gmsg).pack(fill="x", pady=2)

        ttk.Separator(right).pack(fill="x", pady=6)
        ttk.Button(right, text="Send Call Offer", command=self.call_offer).pack(fill="x")

    def _start_loop_thread(self):
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

    def _run_async(self, coro):
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def append_log(self, text):
        self.log.insert(tk.END, text + "\n")
        self.log.see(tk.END)

    def _pump_outgoing(self):
        while not self.outgoing.empty():
            self.append_log(self.outgoing.get())
        self.root.after(100, self._pump_outgoing)

    def connect(self):
        self._run_async(self._connect())

    async def _connect(self):
        self.ws = await websockets.connect(self.server_var.get())
        await self.ws.send(json.dumps({"type": "register", "username": self.username_var.get()}))
        self.outgoing.put("Connected and registered")
        self._run_async(self._reader())

    async def _reader(self):
        async for msg in self.ws:
            self.outgoing.put("< " + msg)

    def _send(self, payload):
        self._run_async(self.ws.send(json.dumps(payload)))

    def send_dm(self):
        self._send({"type": "dm", "from": self.username_var.get(), "to": self.to_var.get(), "text": self.msg_entry.get()})

    def gcreate(self):
        self._send({"type": "group_create", "group": self.group_var.get(), "creator": self.username_var.get()})

    def gjoin(self):
        self._send({"type": "group_join", "group": self.group_var.get(), "username": self.username_var.get()})

    def gmsg(self):
        self._send({"type": "group_msg", "group": self.group_var.get(), "from": self.username_var.get(), "text": self.msg_entry.get()})

    def call_offer(self):
        self._send({"type": "call_offer", "from": self.username_var.get(), "to": self.to_var.get(), "sdp": "desktop-offer-sdp"})

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    DesktopChatGUI().run()
