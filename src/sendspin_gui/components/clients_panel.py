"""Clients panel component for displaying and managing connected clients."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk


class ClientsPanel(ctk.CTkFrame):
    """Panel for displaying and managing connected Sendspin clients."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_create_group: Callable[[list[str], str], None],
        on_disconnect_client: Callable[[str], None],
    ) -> None:
        super().__init__(parent)

        self._on_create_group = on_create_group
        self._on_disconnect_client = on_disconnect_client
        self._clients: list[dict[str, Any]] = []
        self._selected_clients: set[str] = set()
        self._client_frames: dict[str, ctk.CTkFrame] = {}
        self._client_checkboxes: dict[str, ctk.CTkCheckBox] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        title_frame.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(
            title_frame,
            text="Connected Clients",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        self.client_count_label = ctk.CTkLabel(
            title_frame,
            text="(0)",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.client_count_label.grid(row=0, column=1, sticky="w", padx=5)

        # Scrollable frame for clients
        self.clients_scroll = ctk.CTkScrollableFrame(self)
        self.clients_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.clients_scroll.grid_columnconfigure(0, weight=1)

        # Empty state label
        self.empty_label = ctk.CTkLabel(
            self.clients_scroll,
            text="No clients connected.\nStart the server and connect clients.",
            text_color="gray",
            justify="center",
        )
        self.empty_label.grid(row=0, column=0, pady=20)

        # Action buttons
        actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        actions_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=10)
        actions_frame.grid_columnconfigure(1, weight=1)

        self.group_name_entry = ctk.CTkEntry(
            actions_frame,
            placeholder_text="Group name...",
            width=150,
        )
        self.group_name_entry.grid(row=0, column=0, padx=(0, 5))

        self.create_group_btn = ctk.CTkButton(
            actions_frame,
            text="Create Group",
            command=self._create_group,
            width=100,
        )
        self.create_group_btn.grid(row=0, column=1, padx=5, sticky="w")

        self.disconnect_btn = ctk.CTkButton(
            actions_frame,
            text="Disconnect",
            command=self._disconnect_selected,
            width=100,
            fg_color="gray",
            hover_color="darkgray",
        )
        self.disconnect_btn.grid(row=0, column=2, padx=5)

    def update_clients(self, clients: list[dict[str, Any]]) -> None:
        """Update the clients list."""
        self._clients = clients

        # Clear existing client frames
        for frame in self._client_frames.values():
            frame.destroy()
        self._client_frames.clear()
        self._client_checkboxes.clear()

        # Update count
        self.client_count_label.configure(text=f"({len(clients)})")

        if not clients:
            self.empty_label.grid(row=0, column=0, pady=20)
            return

        self.empty_label.grid_forget()

        # Create client entries
        for i, client in enumerate(clients):
            frame = self._create_client_frame(client, i)
            self._client_frames[client["id"]] = frame

    def _create_client_frame(self, client: dict[str, Any], row: int) -> ctk.CTkFrame:
        """Create a frame for a single client."""
        frame = ctk.CTkFrame(self.clients_scroll)
        frame.grid(row=row, column=0, sticky="ew", pady=2)
        frame.grid_columnconfigure(1, weight=1)

        # Selection checkbox
        var = ctk.BooleanVar(value=client["id"] in self._selected_clients)
        checkbox = ctk.CTkCheckBox(
            frame,
            text="",
            variable=var,
            width=20,
            command=lambda cid=client["id"], v=var: self._toggle_selection(cid, v),
        )
        checkbox.grid(row=0, column=0, padx=5, pady=5)
        self._client_checkboxes[client["id"]] = checkbox

        # Client info
        info_frame = ctk.CTkFrame(frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        info_frame.grid_columnconfigure(0, weight=1)

        name_label = ctk.CTkLabel(
            info_frame,
            text=client["name"] or client["id"],
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="w")

        # Roles
        roles_text = ", ".join(client.get("roles", []))
        roles_label = ctk.CTkLabel(
            info_frame,
            text=f"Roles: {roles_text}" if roles_text else "No roles",
            text_color="gray",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        roles_label.grid(row=1, column=0, sticky="w")

        # Group indicator
        if client.get("group_id"):
            group_label = ctk.CTkLabel(
                frame,
                text=f"Group: {client['group_id'][:8]}...",
                text_color="#4a9eff",
                font=ctk.CTkFont(size=11),
            )
            group_label.grid(row=0, column=2, padx=10)

        return frame

    def _toggle_selection(self, client_id: str, var: ctk.BooleanVar) -> None:
        """Toggle client selection."""
        if var.get():
            self._selected_clients.add(client_id)
        else:
            self._selected_clients.discard(client_id)

    def _create_group(self) -> None:
        """Create a group from selected clients."""
        if not self._selected_clients:
            return

        group_name = self.group_name_entry.get().strip()
        if not group_name:
            group_name = f"Group-{len(self._selected_clients)}"

        self._on_create_group(list(self._selected_clients), group_name)
        self._selected_clients.clear()
        self.group_name_entry.delete(0, "end")

        # Uncheck all checkboxes
        for checkbox in self._client_checkboxes.values():
            checkbox.deselect()

    def _disconnect_selected(self) -> None:
        """Disconnect selected clients."""
        for client_id in list(self._selected_clients):
            self._on_disconnect_client(client_id)

        self._selected_clients.clear()

    def clear(self) -> None:
        """Clear all clients."""
        self.update_clients([])
        self._selected_clients.clear()
