"""Server control panel component."""

from __future__ import annotations

import uuid
from collections.abc import Callable

import customtkinter as ctk


class ServerPanel(ctk.CTkFrame):
    """Panel for controlling the Sendspin server."""

    def __init__(
        self,
        parent: ctk.CTk,
        on_start: Callable[[str, str, int, bool], None],
        on_stop: Callable[[], None],
    ) -> None:
        super().__init__(parent)

        self._on_start = on_start
        self._on_stop = on_stop
        self._is_running = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        # Configure grid
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(3, weight=1)

        # Title
        title = ctk.CTkLabel(
            self,
            text="Server Configuration",
            font=ctk.CTkFont(size=16, weight="bold"),
        )
        title.grid(row=0, column=0, columnspan=7, sticky="w", padx=10, pady=(10, 5))

        # Row 1: Server ID and Name
        ctk.CTkLabel(self, text="Server ID:").grid(row=1, column=0, padx=(10, 5), pady=5, sticky="e")
        self.server_id_entry = ctk.CTkEntry(self, width=200)
        self.server_id_entry.insert(0, str(uuid.uuid4())[:8])
        self.server_id_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        ctk.CTkLabel(self, text="Server Name:").grid(row=1, column=2, padx=(20, 5), pady=5, sticky="e")
        self.server_name_entry = ctk.CTkEntry(self, width=200)
        self.server_name_entry.insert(0, "Sendspin Test Server")
        self.server_name_entry.grid(row=1, column=3, padx=5, pady=5, sticky="ew")

        # Row 2: Port and mDNS toggle
        ctk.CTkLabel(self, text="Port:").grid(row=2, column=0, padx=(10, 5), pady=5, sticky="e")
        self.port_entry = ctk.CTkEntry(self, width=100)
        self.port_entry.insert(0, "8765")
        self.port_entry.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        self.mdns_var = ctk.BooleanVar(value=True)
        self.mdns_checkbox = ctk.CTkCheckBox(
            self,
            text="Enable mDNS",
            variable=self.mdns_var,
        )
        self.mdns_checkbox.grid(row=2, column=2, padx=(20, 5), pady=5, sticky="w")

        # Log level dropdown
        ctk.CTkLabel(self, text="Log Level:").grid(row=2, column=3, padx=(10, 5), pady=5, sticky="e")
        self.log_level_var = ctk.StringVar(value="INFO")
        self.log_level_menu = ctk.CTkOptionMenu(
            self,
            values=["DEBUG", "INFO", "WARNING", "ERROR"],
            variable=self.log_level_var,
            width=100,
        )
        self.log_level_menu.grid(row=2, column=4, padx=5, pady=5, sticky="w")

        # Start/Stop button
        self.start_stop_btn = ctk.CTkButton(
            self,
            text="Start Server",
            command=self._toggle_server,
            width=120,
            fg_color="green",
            hover_color="darkgreen",
        )
        self.start_stop_btn.grid(row=1, column=5, rowspan=2, padx=20, pady=10)

        # Status indicator
        self.status_frame = ctk.CTkFrame(self, width=20, height=20, corner_radius=10)
        self.status_frame.grid(row=1, column=6, rowspan=2, padx=(0, 10), pady=10)
        self._update_status_indicator()

    def _toggle_server(self) -> None:
        """Toggle server start/stop."""
        if self._is_running:
            self._on_stop()
        else:
            server_id = self.server_id_entry.get().strip()
            server_name = self.server_name_entry.get().strip()
            try:
                port = int(self.port_entry.get().strip())
            except ValueError:
                port = 8765
            enable_mdns = self.mdns_var.get()

            self._on_start(server_id, server_name, port, enable_mdns)

    def set_server_state(self, is_running: bool) -> None:
        """Update the UI to reflect server state."""
        self._is_running = is_running
        self._update_status_indicator()

        if is_running:
            self.start_stop_btn.configure(
                text="Stop Server",
                fg_color="red",
                hover_color="darkred",
            )
            # Disable config fields while running
            self.server_id_entry.configure(state="disabled")
            self.server_name_entry.configure(state="disabled")
            self.port_entry.configure(state="disabled")
            self.mdns_checkbox.configure(state="disabled")
            self.log_level_menu.configure(state="disabled")
        else:
            self.start_stop_btn.configure(
                text="Start Server",
                fg_color="green",
                hover_color="darkgreen",
            )
            # Re-enable config fields
            self.server_id_entry.configure(state="normal")
            self.server_name_entry.configure(state="normal")
            self.port_entry.configure(state="normal")
            self.mdns_checkbox.configure(state="normal")
            self.log_level_menu.configure(state="normal")

    def _update_status_indicator(self) -> None:
        """Update the status indicator color."""
        color = "#00ff00" if self._is_running else "#ff0000"
        self.status_frame.configure(fg_color=color)

    def get_log_level(self) -> str:
        """Get the selected log level."""
        return self.log_level_var.get()
