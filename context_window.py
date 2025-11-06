"""Simple desktop chat window that maintains session context using the OpenAI API.

Run with:
    python context_window.py

Requires the OPENAI_API_KEY environment variable to be set before launch.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, scrolledtext

try:
    from openai import OpenAI
except ImportError as exc:  # pragma: no cover - helpful startup message
    raise SystemExit(
        "The OpenAI Python client is required. Install it with 'pip install openai'."
    ) from exc


MODEL_NAME = "gpt-4o-mini"


class ContextChatApp:
    """Tkinter UI that maintains a running context with the OpenAI Responses API."""

    def __init__(self, master: tk.Tk) -> None:
        self.master = master
        master.title("OpenAI Context Window")

        self.client = OpenAI()
        self.history: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Keep replies concise and stay on topic."
                ),
            }
        ]

        self._build_widgets()

    def _build_widgets(self) -> None:
        """Create the minimal UI controls."""

        self.chat_display = scrolledtext.ScrolledText(self.master, wrap=tk.WORD, height=20)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        self.input_entry = tk.Entry(self.master, width=80)
        self.input_entry.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="ew")
        self.input_entry.bind("<Return>", self._on_send)

        send_button = tk.Button(self.master, text="Send", command=self._on_send)
        send_button.grid(row=1, column=1, padx=(5, 10), pady=(0, 10), sticky="e")

        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)

    def _on_send(self, event: tk.Event | None = None) -> None:
        """Send the current text to the model and display the response."""

        user_text = self.input_entry.get().strip()
        if not user_text:
            return

        self.input_entry.delete(0, tk.END)
        self._append_message("You", user_text)
        self.history.append({"role": "user", "content": user_text})

        try:
            response_text = self._query_model()
        except Exception as error:  # pragma: no cover - user feedback only
            messagebox.showerror("OpenAI Error", str(error))
            return

        self.history.append({"role": "assistant", "content": response_text})
        self._append_message("Assistant", response_text)

    def _query_model(self) -> str:
        """Send the conversation history to the model and return the reply."""

        response = self.client.responses.create(
            model=MODEL_NAME,
            input=[{"role": msg["role"], "content": msg["content"]} for msg in self.history],
        )
        return response.output_text.strip()

    def _append_message(self, speaker: str, text: str) -> None:
        self.chat_display.configure(state=tk.NORMAL)
        self.chat_display.insert(tk.END, f"{speaker}: {text}\n\n")
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)


def main() -> None:
    root = tk.Tk()

    if not os.getenv("OPENAI_API_KEY"):
        messagebox.showerror(
            "Missing API Key",
            "Set the OPENAI_API_KEY environment variable before launching the app.",
            parent=root,
        )
        root.destroy()
        return

    ContextChatApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
