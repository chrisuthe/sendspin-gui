"""Main application class for Sendspin GUI."""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from aiosendspin.server import (
    SendspinServer,
    SendspinClient,
    SendspinGroup,
    SendspinEvent,
    ClientAddedEvent,
    ClientRemovedEvent,
    ClientEvent,
    GroupEvent,
    GroupStateChangedEvent,
    GroupMemberAddedEvent,
    GroupMemberRemovedEvent,
    GroupDeletedEvent,
)

from .utils.async_bridge import AsyncBridge
from .components.server_panel import ServerPanel
from .components.clients_panel import ClientsPanel
from .components.groups_panel import GroupsPanel
from .components.event_log import EventLog
from .components.stream_panel import StreamPanel

if TYPE_CHECKING:
    from collections.abc import Callable


class SendspinGUIApp(ctk.CTk):
    """Main GUI application for testing aiosendspin server."""

    def __init__(self) -> None:
        super().__init__()

        self.title("Sendspin Server GUI - Test Environment")
        self.geometry("1200x800")
        self.minsize(900, 600)

        # Set appearance
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Async bridge for running server operations
        self._async_bridge = AsyncBridge()
        self._async_bridge.start()

        # Server instance
        self._server: SendspinServer | None = None
        self._event_unsubscribers: list[Callable[[], None]] = []

        # Build UI
        self._build_ui()

        # Handle window close
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self) -> None:
        """Build the main UI layout."""
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=2)
        self.grid_rowconfigure(0, weight=0)  # Server panel
        self.grid_rowconfigure(1, weight=1)  # Main content
        self.grid_rowconfigure(2, weight=1)  # Event log

        # Server control panel (top)
        self.server_panel = ServerPanel(
            self,
            on_start=self._start_server,
            on_stop=self._stop_server,
        )
        self.server_panel.grid(row=0, column=0, columnspan=2, sticky="ew", padx=10, pady=(10, 5))

        # Left column - Clients and Groups
        left_frame = ctk.CTkFrame(self)
        left_frame.grid(row=1, column=0, sticky="nsew", padx=(10, 5), pady=5)
        left_frame.grid_rowconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        self.clients_panel = ClientsPanel(
            left_frame,
            on_create_group=self._create_group,
            on_disconnect_client=self._disconnect_client,
        )
        self.clients_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.groups_panel = GroupsPanel(
            left_frame,
            on_play=self._play_group,
            on_stop=self._stop_group,
            on_set_volume=self._set_group_volume,
            on_remove_client=self._remove_client_from_group,
        )
        self.groups_panel.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Right column - Stream panel and Event log
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=1, column=1, rowspan=2, sticky="nsew", padx=(5, 10), pady=5)
        right_frame.grid_rowconfigure(0, weight=1)
        right_frame.grid_rowconfigure(1, weight=2)
        right_frame.grid_columnconfigure(0, weight=1)

        self.stream_panel = StreamPanel(
            right_frame,
            on_stream_file=self._stream_file,
            on_stream_test_tone=self._stream_test_tone,
        )
        self.stream_panel.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        self.event_log = EventLog(right_frame)
        self.event_log.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)

        # Bottom status bar in left column
        self.status_label = ctk.CTkLabel(
            self,
            text="Server stopped",
            anchor="w",
        )
        self.status_label.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))

    def _log_event(self, message: str, level: str = "info") -> None:
        """Log an event to the event log panel."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        self.event_log.add_event(f"[{timestamp}] {message}", level)

    def _update_status(self, message: str) -> None:
        """Update the status bar."""
        self.status_label.configure(text=message)

    def _start_server(self, server_id: str, server_name: str, port: int, enable_mdns: bool) -> None:
        """Start the Sendspin server."""
        async def _start() -> None:
            loop = asyncio.get_running_loop()
            self._server = SendspinServer(
                loop=loop,
                server_id=server_id,
                server_name=server_name,
            )

            # Subscribe to server events
            unsub = self._server.add_event_listener(self._on_server_event)
            self._event_unsubscribers.append(unsub)

            await self._server.start_server(
                host="0.0.0.0",
                port=port,
                discover_clients=enable_mdns,
            )

        def on_complete(result: None, error: Exception | None) -> None:
            if error:
                self._log_event(f"Failed to start server: {error}", "error")
                self.server_panel.set_server_state(False)
            else:
                self._log_event(f"Server started on port {port}", "success")
                self._update_status(f"Server running: {server_name} ({server_id}) on port {port}")
                self.server_panel.set_server_state(True)

        self._log_event(f"Starting server '{server_name}'...")
        self._async_bridge.run_coroutine(_start(), on_complete)

    def _stop_server(self) -> None:
        """Stop the Sendspin server."""
        if self._server is None:
            return

        async def _stop() -> None:
            if self._server:
                await self._server.close()

        def on_complete(result: None, error: Exception | None) -> None:
            # Unsubscribe from events
            for unsub in self._event_unsubscribers:
                unsub()
            self._event_unsubscribers.clear()

            self._server = None

            if error:
                self._log_event(f"Error stopping server: {error}", "error")
            else:
                self._log_event("Server stopped", "info")

            self._update_status("Server stopped")
            self.server_panel.set_server_state(False)
            self.clients_panel.clear()
            self.groups_panel.clear()

        self._log_event("Stopping server...")
        self._async_bridge.run_coroutine(_stop(), on_complete)

    def _on_server_event(self, event: SendspinEvent) -> None:
        """Handle server events (called from async thread)."""
        # Schedule UI update on main thread
        self.after(0, lambda: self._handle_server_event(event))

    def _handle_server_event(self, event: SendspinEvent) -> None:
        """Handle server event on main thread."""
        if isinstance(event, ClientAddedEvent):
            self._log_event(f"Client connected: {event.client_id}", "success")
            self._refresh_clients()
        elif isinstance(event, ClientRemovedEvent):
            self._log_event(f"Client disconnected: {event.client_id}", "warning")
            self._refresh_clients()
        else:
            self._log_event(f"Server event: {type(event).__name__}", "info")

    def _on_client_event(self, client: SendspinClient, event: ClientEvent) -> None:
        """Handle client events."""
        self.after(0, lambda: self._log_event(
            f"Client {client.client_id}: {type(event).__name__}", "info"
        ))

    def _on_group_event(self, group: SendspinGroup, event: GroupEvent) -> None:
        """Handle group events."""
        def handle() -> None:
            if isinstance(event, GroupStateChangedEvent):
                self._log_event(f"Group {group.group_id}: state -> {event.state}", "info")
            elif isinstance(event, GroupMemberAddedEvent):
                self._log_event(f"Group {group.group_id}: added {event.client_id}", "info")
            elif isinstance(event, GroupMemberRemovedEvent):
                self._log_event(f"Group {group.group_id}: removed {event.client_id}", "info")
            elif isinstance(event, GroupDeletedEvent):
                self._log_event(f"Group {group.group_id}: deleted", "warning")
            else:
                self._log_event(f"Group {group.group_id}: {type(event).__name__}", "info")
            self._refresh_groups()

        self.after(0, handle)

    def _refresh_clients(self) -> None:
        """Refresh the clients list."""
        if self._server is None:
            self.clients_panel.clear()
            return

        clients_data = []
        for client in self._server.clients:
            # Subscribe to client events if not already
            unsub = client.add_event_listener(self._on_client_event)
            self._event_unsubscribers.append(unsub)

            clients_data.append({
                "id": client.client_id,
                "name": client.name,
                "roles": [r.value for r in client.roles],
                "group_id": client.group.group_id if client.group else None,
            })

        self.clients_panel.update_clients(clients_data)

    def _refresh_groups(self) -> None:
        """Refresh the groups list."""
        if self._server is None:
            self.groups_panel.clear()
            return

        # Collect unique groups from clients
        groups: dict[str, SendspinGroup] = {}
        for client in self._server.clients:
            if client.group and client.group.group_id not in groups:
                groups[client.group.group_id] = client.group

        groups_data = []
        for group in groups.values():
            groups_data.append({
                "id": group.group_id,
                "name": group.group_name,
                "state": str(group.state),
                "volume": group.volume,
                "muted": group.muted,
                "clients": [c.client_id for c in group.clients],
            })

        self.groups_panel.update_groups(groups_data)

    def _create_group(self, client_ids: list[str], group_name: str) -> None:
        """Create a new group with the selected clients."""
        if self._server is None or not client_ids:
            return

        async def _create() -> None:
            group = SendspinGroup(group_name=group_name)

            # Subscribe to group events
            unsub = group.add_event_listener(self._on_group_event)
            self._event_unsubscribers.append(unsub)

            for cid in client_ids:
                client = self._server.get_client(cid)
                if client:
                    await group.add_client(client)

        def on_complete(result: None, error: Exception | None) -> None:
            if error:
                self._log_event(f"Failed to create group: {error}", "error")
            else:
                self._log_event(f"Created group '{group_name}' with {len(client_ids)} clients", "success")
                self._refresh_clients()
                self._refresh_groups()

        self._async_bridge.run_coroutine(_create(), on_complete)

    def _disconnect_client(self, client_id: str) -> None:
        """Disconnect a client."""
        if self._server is None:
            return

        client = self._server.get_client(client_id)
        if client is None:
            return

        async def _disconnect() -> None:
            await client.disconnect(retry_connection=False)

        self._async_bridge.run_coroutine(_disconnect(), lambda r, e: None)

    def _play_group(self, group_id: str) -> None:
        """Start playback on a group."""
        self._log_event(f"Play requested for group {group_id}", "info")
        # Implementation depends on having a stream ready

    def _stop_group(self, group_id: str) -> None:
        """Stop playback on a group."""
        if self._server is None:
            return

        # Find the group
        for client in self._server.clients:
            if client.group and client.group.group_id == group_id:
                async def _stop() -> None:
                    await client.group.stop(stop_time_us=0)

                self._async_bridge.run_coroutine(_stop(), lambda r, e: None)
                self._log_event(f"Stop requested for group {group_id}", "info")
                return

    def _set_group_volume(self, group_id: str, volume: int) -> None:
        """Set volume for a group."""
        if self._server is None:
            return

        for client in self._server.clients:
            if client.group and client.group.group_id == group_id:
                client.group.set_volume(volume)
                self._log_event(f"Volume set to {volume} for group {group_id}", "info")
                return

    def _remove_client_from_group(self, group_id: str, client_id: str) -> None:
        """Remove a client from a group."""
        if self._server is None:
            return

        client = self._server.get_client(client_id)
        if client and client.group:
            async def _remove() -> None:
                await client.ungroup()

            def on_complete(r: None, e: Exception | None) -> None:
                if e:
                    self._log_event(f"Error removing client: {e}", "error")
                else:
                    self._log_event(f"Removed {client_id} from group", "info")
                    self._refresh_clients()
                    self._refresh_groups()

            self._async_bridge.run_coroutine(_remove(), on_complete)

    def _stream_file(self, file_path: str, group_id: str) -> None:
        """Stream an audio file to a group."""
        self._log_event(f"Streaming {file_path} to group {group_id}", "info")
        # Full implementation would use ffmpeg/av to decode and stream

    def _stream_test_tone(self, frequency: int, duration: float, group_id: str) -> None:
        """Stream a test tone to a group."""
        self._log_event(f"Streaming {frequency}Hz test tone for {duration}s to group {group_id}", "info")
        # Full implementation would generate sine wave and stream

    def _on_close(self) -> None:
        """Handle window close event."""
        if self._server is not None:
            self._stop_server()

        # Give server time to stop
        self.after(500, self._finish_close)

    def _finish_close(self) -> None:
        """Finish closing the application."""
        self._async_bridge.stop()
        self.destroy()

    def run(self) -> None:
        """Run the application."""
        self.mainloop()
