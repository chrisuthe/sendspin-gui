"""Event log component for displaying server events."""

from __future__ import annotations

import customtkinter as ctk


class EventLog(ctk.CTkFrame):
    """Panel for displaying server events and logs."""

    MAX_EVENTS = 500

    def __init__(self, parent: ctk.CTkFrame) -> None:
        super().__init__(parent)

        self._events: list[tuple[str, str]] = []
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Header with title and clear button
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        header_frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            header_frame,
            text="Event Log",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        # Filter dropdown
        self.filter_var = ctk.StringVar(value="all")
        filter_menu = ctk.CTkOptionMenu(
            header_frame,
            values=["all", "info", "success", "warning", "error"],
            variable=self.filter_var,
            command=self._apply_filter,
            width=100,
        )
        filter_menu.grid(row=0, column=1, padx=5)

        clear_btn = ctk.CTkButton(
            header_frame,
            text="Clear",
            command=self.clear,
            width=60,
            height=28,
            fg_color="gray",
            hover_color="darkgray",
        )
        clear_btn.grid(row=0, column=2)

        # Scrollable text area
        self.log_textbox = ctk.CTkTextbox(
            self,
            wrap="word",
            font=ctk.CTkFont(family="Consolas", size=11),
            state="disabled",
        )
        self.log_textbox.grid(row=1, column=0, sticky="nsew", padx=10, pady=(5, 10))

        # Configure text tags for different log levels
        self.log_textbox._textbox.tag_configure("info", foreground="#ffffff")
        self.log_textbox._textbox.tag_configure("success", foreground="#00ff00")
        self.log_textbox._textbox.tag_configure("warning", foreground="#ffff00")
        self.log_textbox._textbox.tag_configure("error", foreground="#ff4444")

    def add_event(self, message: str, level: str = "info") -> None:
        """Add an event to the log.

        Args:
            message: The event message
            level: Log level (info, success, warning, error)
        """
        self._events.append((message, level))

        # Trim if too many events
        if len(self._events) > self.MAX_EVENTS:
            self._events = self._events[-self.MAX_EVENTS:]

        # Check filter
        current_filter = self.filter_var.get()
        if current_filter != "all" and level != current_filter:
            return

        # Add to display
        self.log_textbox.configure(state="normal")
        self.log_textbox._textbox.insert("end", message + "\n", level)
        self.log_textbox.configure(state="disabled")

        # Auto-scroll to bottom
        self.log_textbox._textbox.see("end")

    def _apply_filter(self, filter_value: str) -> None:
        """Apply a filter to show only certain log levels."""
        self.log_textbox.configure(state="normal")
        self.log_textbox._textbox.delete("1.0", "end")

        for message, level in self._events:
            if filter_value == "all" or level == filter_value:
                self.log_textbox._textbox.insert("end", message + "\n", level)

        self.log_textbox.configure(state="disabled")
        self.log_textbox._textbox.see("end")

    def clear(self) -> None:
        """Clear all events."""
        self._events.clear()
        self.log_textbox.configure(state="normal")
        self.log_textbox._textbox.delete("1.0", "end")
        self.log_textbox.configure(state="disabled")
