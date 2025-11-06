"""Simple desktop chat window that maintains session context using the OpenAI API.

Run with:
    python context_window.py

Requires the OPENAI_API_KEY environment variable to be set before launch.
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading

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
        # Typing placeholder animation state
        self._typing_anim_running: bool = False
        self._typing_anim_step: int = 0
        self._typing_after_id: str | None = None

    def _build_widgets(self) -> None:
        """Create the minimal UI controls."""

        self.chat_display = scrolledtext.ScrolledText(self.master, wrap=tk.WORD, height=20)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        # Tag for typing placeholder styling
        self.chat_display.tag_configure("typing_tag", foreground="gray")

        self.input_entry = tk.Entry(self.master, width=80)
        self.input_entry.grid(row=1, column=0, padx=(10, 0), pady=(0, 10), sticky="ew")
        self.input_entry.bind("<Return>", self._on_send)

        self.send_button = tk.Button(self.master, text="Send", command=self._on_send)
        self.send_button.grid(row=1, column=1, padx=(5, 10), pady=(0, 10), sticky="e")

        # Status label to indicate loading / typing state
        self.status_var = tk.StringVar(value="")
        self.status_label = tk.Label(self.master, textvariable=self.status_var, fg="gray")
        self.status_label.grid(row=2, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="w")

        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)

    def _on_send(self, event: tk.Event | None = None) -> None:
        """Send the current text to the model and display the response."""

        user_text = self.input_entry.get().strip()
        if not user_text:
            return

        self.input_entry.delete(0, tk.END)
        # Show the user's message immediately in the chat window
        self._append_message("You", user_text)
        self.history.append({"role": "user", "content": user_text})

        # Enter loading state and fetch response on a background thread
        self._set_loading(True, message="Assistant is typing...")
        self._start_typing_placeholder()
        thread = threading.Thread(target=self._fetch_response, daemon=True)
        thread.start()

    def _fetch_response(self) -> None:
        """Background worker to query the model and dispatch UI updates back on the main thread."""
        try:
            response_text = self._query_model()
        except Exception as error:  # pragma: no cover - user feedback only
            # Schedule error handling on the Tkinter main loop
            self.master.after(0, lambda: self._on_response_error(error))
            return

        # Schedule UI update on the Tkinter main loop
        self.master.after(0, lambda: self._on_response_ready(response_text))

    def _on_response_ready(self, response_text: str) -> None:
        """Handle successful model response on the UI thread."""
        self._remove_typing_placeholder()
        self.history.append({"role": "assistant", "content": response_text})
        self._append_message("Assistant", response_text)
        self._set_loading(False)

    def _on_response_error(self, error: Exception) -> None:  # pragma: no cover - user feedback only
        """Handle an error from the background request on the UI thread."""
        messagebox.showerror("OpenAI Error", str(error))
        self._remove_typing_placeholder()
        self._set_loading(False)

    def _set_loading(self, is_loading: bool, message: str | None = None) -> None:
        """Enable or disable UI loading state and optional status message."""
        if is_loading:
            self.input_entry.configure(state=tk.DISABLED)
            self.send_button.configure(state=tk.DISABLED)
            if message is not None:
                self.status_var.set(message)
        else:
            self.input_entry.configure(state=tk.NORMAL)
            self.send_button.configure(state=tk.NORMAL)
            self.status_var.set("")

    def _start_typing_placeholder(self) -> None:
        """Insert a placeholder line in the chat and start animating dots."""
        if self._typing_anim_running:
            return
        self.chat_display.configure(state=tk.NORMAL)
        start_index = self.chat_display.index(tk.END)
        placeholder = "Assistant: typing...\n\n"
        self.chat_display.insert(tk.END, placeholder)
        end_index = self.chat_display.index(tk.END)
        self.chat_display.tag_add("typing_tag", start_index, end_index)
        self.chat_display.configure(state=tk.DISABLED)
        self.chat_display.see(tk.END)

        self._typing_anim_running = True
        self._typing_anim_step = 0
        self._schedule_typing_animation()

    def _schedule_typing_animation(self) -> None:
        if not self._typing_anim_running:
            return
        ranges = self.chat_display.tag_ranges("typing_tag")
        if len(ranges) >= 2:
            start, end = ranges[0], ranges[1]
            dots = "." * (self._typing_anim_step % 3 + 1)
            text = f"Assistant: typing{dots}\n\n"
            self.chat_display.configure(state=tk.NORMAL)
            self.chat_display.delete(start, end)
            self.chat_display.insert(start, text)
            new_end = self.chat_display.index(f"{start}+{len(text)}c")
            self.chat_display.tag_add("typing_tag", start, new_end)
            self.chat_display.configure(state=tk.DISABLED)
            self.chat_display.see(tk.END)
            self._typing_anim_step += 1
        # Schedule next frame
        self._typing_after_id = self.master.after(500, self._schedule_typing_animation)

    def _remove_typing_placeholder(self) -> None:
        """Remove the typing placeholder and stop the animation if running."""
        if self._typing_after_id is not None:
            try:
                self.master.after_cancel(self._typing_after_id)
            except Exception:
                pass
            self._typing_after_id = None
        if self._typing_anim_running:
            ranges = self.chat_display.tag_ranges("typing_tag")
            if len(ranges) >= 2:
                start, end = ranges[0], ranges[1]
                self.chat_display.configure(state=tk.NORMAL)
                self.chat_display.delete(start, end)
                self.chat_display.configure(state=tk.DISABLED)
            self.chat_display.tag_remove("typing_tag", "1.0", tk.END)
        self._typing_anim_running = False

    def _query_model(self) -> str:
        """Send the conversation history to the model and return the reply."""

        messages = [{"role": msg["role"], "content": msg["content"]} for msg in self.history]

        if hasattr(self.client, "responses"):
            response = self.client.responses.create(model=MODEL_NAME, input=messages)
            return response.output_text.strip()

        # Fallback for older OpenAI Python SDK versions (<1.0)
        completion = self.client.chat.completions.create(model=MODEL_NAME, messages=messages)
        message = completion.choices[0].message
        # "message" can be either a dict (legacy) or an object with a ``content`` attribute.
        if isinstance(message, dict):
            return (message.get("content") or "").strip()
        return (getattr(message, "content", "") or "").strip()

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
