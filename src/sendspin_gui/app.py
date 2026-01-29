"""Main application class for Sendspin GUI."""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import time
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk
from aiosendspin.server import (
    ClientAddedEvent,
    ClientEvent,
    ClientRemovedEvent,
    GroupDeletedEvent,
    GroupEvent,
    GroupMemberAddedEvent,
    GroupMemberRemovedEvent,
    GroupStateChangedEvent,
    SendspinClient,
    SendspinEvent,
    SendspinGroup,
    SendspinServer,
)
from aiosendspin.server.metadata import Metadata, RepeatMode
from aiosendspin.server.stream import AudioCodec, AudioFormat, MediaStream

from .components.clients_panel import ClientsPanel
from .components.event_log import EventLog
from .components.groups_panel import GroupsPanel
from .components.server_panel import ServerPanel
from .components.stream_panel import StreamPanel
from .utils.async_bridge import AsyncBridge
from .utils.audio_decoder import decode_audio_streaming, get_audio_info
from .utils.audio_gen import generate_sine_wave
from .utils.log_handler import GUILogHandler

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Callable


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
        self._subscribed_clients: set[str] = set()  # Track which clients we've subscribed to

        # Streaming state tracking
        self._active_stream_future: asyncio.Future | None = None
        self._stream_paused = False
        self._stream_pause_event: asyncio.Event | None = None

        # Metadata tracking
        self._active_group: SendspinGroup | None = None
        self._stream_start_time: float | None = None
        self._stream_duration_ms: int = 0
        self._pause_accumulated_ms: int = 0
        self._pause_start_time: float | None = None
        self._progress_future: asyncio.Future | None = None
        self._stream_title: str = ""

        # Logging handler for aiosendspin
        self._log_handler: GUILogHandler | None = None
        self._aiosendspin_logger = logging.getLogger("aiosendspin")

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
            on_stream_url=self._stream_url,
            on_pause_resume=self._pause_resume_stream,
            on_stop=self._stop_stream,
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

    def _on_library_log(self, message: str, level: str) -> None:
        """Handle log messages from aiosendspin library (called from async thread)."""
        # Schedule UI update on main thread
        self.after(0, lambda: self._log_event(message, level))

    def _update_status(self, message: str) -> None:
        """Update the status bar."""
        self.status_label.configure(text=message)

    def _start_server(self, server_id: str, server_name: str, port: int, enable_mdns: bool) -> None:
        """Start the Sendspin server."""
        # Set up logging for aiosendspin
        log_level_str = self.server_panel.get_log_level()
        log_level = getattr(logging, log_level_str, logging.INFO)

        self._log_handler = GUILogHandler(self._on_library_log)
        self._log_handler.setLevel(log_level)
        self._aiosendspin_logger.addHandler(self._log_handler)
        self._aiosendspin_logger.setLevel(log_level)

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
            # Schedule UI updates on main thread
            def update_ui() -> None:
                if error:
                    self._log_event(f"Failed to start server: {error}", "error")
                    self.server_panel.set_server_state(False)
                else:
                    self._log_event(f"Server started on port {port}", "success")
                    status = f"Server running: {server_name} ({server_id}) on port {port}"
                    self._update_status(status)
                    self.server_panel.set_server_state(True)
            self.after(0, update_ui)

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
            # Schedule UI updates on main thread
            def update_ui() -> None:
                # Unsubscribe from events
                for unsub in self._event_unsubscribers:
                    unsub()
                self._event_unsubscribers.clear()
                self._subscribed_clients.clear()

                # Remove logging handler
                if self._log_handler:
                    self._aiosendspin_logger.removeHandler(self._log_handler)
                    self._log_handler = None

                self._server = None

                if error:
                    self._log_event(f"Error stopping server: {error}", "error")
                else:
                    self._log_event("Server stopped", "info")

                self._update_status("Server stopped")
                self.server_panel.set_server_state(False)
                self.clients_panel.clear()
                self.groups_panel.clear()
            self.after(0, update_ui)

        self._log_event("Stopping server...")
        self._async_bridge.run_coroutine(_stop(), on_complete)

    def _on_server_event(self, server: SendspinServer, event: SendspinEvent) -> None:
        """Handle server events (called from async thread)."""
        # Schedule UI update on main thread
        # Capture event in closure to avoid reference issues
        def handle_event(evt: SendspinEvent = event) -> None:
            self._handle_server_event(evt)
        self.after(0, handle_event)

    def _handle_server_event(self, event: SendspinEvent) -> None:
        """Handle server event on main thread."""
        try:
            if isinstance(event, ClientAddedEvent):
                self._log_event(f"Client connected: {event.client_id}", "success")
                self._refresh_clients()
            elif isinstance(event, ClientRemovedEvent):
                self._log_event(f"Client disconnected: {event.client_id}", "warning")
                self._refresh_clients()
            else:
                self._log_event(f"Server event: {type(event).__name__}", "info")
        except Exception as e:
            self._log_event(f"Error handling event: {e}", "error")
            import traceback
            traceback.print_exc()

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
            # Subscribe to client events only if not already subscribed
            if client.client_id not in self._subscribed_clients:
                unsub = client.add_event_listener(self._on_client_event)
                self._event_unsubscribers.append(unsub)
                self._subscribed_clients.add(client.client_id)

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
            # Schedule UI updates on main thread
            def update_ui() -> None:
                if error:
                    self._log_event(f"Failed to create group: {error}", "error")
                else:
                    msg = f"Created group '{group_name}' with {len(client_ids)} clients"
                    self._log_event(msg, "success")
                    self._refresh_clients()
                    self._refresh_groups()
            self.after(0, update_ui)

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
                group = client.group  # Capture the group reference

                async def _stop(g: SendspinGroup = group) -> None:
                    await g.stop(stop_time_us=0)

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
                # Schedule UI updates on main thread
                def update_ui() -> None:
                    if e:
                        self._log_event(f"Error removing client: {e}", "error")
                    else:
                        self._log_event(f"Removed {client_id} from group", "info")
                        self._refresh_clients()
                        self._refresh_groups()
                self.after(0, update_ui)

            self._async_bridge.run_coroutine(_remove(), on_complete)

    async def _wrap_with_pause_support(
        self,
        source: AsyncGenerator[bytes, None],
        pause_event: asyncio.Event,
    ) -> AsyncGenerator[bytes, None]:
        """Wrap an audio source generator with pause support.

        Args:
            source: The original audio source generator
            pause_event: Event to control pause/resume (clear=pause, set=play)

        Yields:
            Audio chunks from the source, pausing when the event is cleared
        """
        async for chunk in source:
            # Wait for the pause event (blocks if cleared)
            await pause_event.wait()
            yield chunk

    def _set_stream_metadata(
        self,
        group: SendspinGroup,
        title: str,
        duration_ms: int,
        progress_ms: int = 0,
        paused: bool = False,
    ) -> None:
        """Set metadata on a group for the current stream.

        Args:
            group: Target group to set metadata on
            title: Track title to display
            duration_ms: Total duration in milliseconds (0 for unknown/live)
            progress_ms: Current progress in milliseconds
            paused: Whether playback is paused
        """
        metadata = Metadata(
            title=title,
            artist="Sendspin GUI",
            album="Test Playback",
            album_artist="Sendspin GUI",
            track=1,
            year=2024,
            track_duration=duration_ms,
            track_progress=progress_ms,
            playback_speed=0 if paused else 1000,  # 0 = paused, 1000 = normal
            repeat=RepeatMode.OFF,
            shuffle=False,
        )
        group.set_metadata(metadata)

    def _start_progress_updates(self) -> None:
        """Start the background task that updates metadata progress."""
        if self._active_group is None:
            return

        async def _update_progress() -> None:
            """Periodically update metadata with current progress."""
            while True:
                await asyncio.sleep(1.0)  # Update every second

                if self._active_group is None or self._stream_start_time is None:
                    break

                # Calculate progress accounting for pauses
                if self._stream_paused:
                    # When paused, use the accumulated time before pause
                    progress_ms = self._pause_accumulated_ms
                else:
                    elapsed = time.time() - self._stream_start_time
                    progress_ms = int(elapsed * 1000) - self._pause_accumulated_ms

                # Don't exceed duration (if known)
                if self._stream_duration_ms > 0:
                    progress_ms = min(progress_ms, self._stream_duration_ms)

                self._set_stream_metadata(
                    self._active_group,
                    self._stream_title,
                    self._stream_duration_ms,
                    progress_ms,
                    self._stream_paused,
                )

        self._progress_future = self._async_bridge.run_coroutine(
            _update_progress(), lambda r, e: None
        )

    def _stop_progress_updates(self) -> None:
        """Stop the progress update task."""
        if self._progress_future:
            self._progress_future.cancel()
            self._progress_future = None

    def _clear_metadata_state(self) -> None:
        """Clear all metadata tracking state."""
        self._stop_progress_updates()
        if self._active_group:
            self._active_group.set_metadata(None)  # Clear metadata on clients
        self._active_group = None
        self._stream_start_time = None
        self._stream_duration_ms = 0
        self._pause_accumulated_ms = 0
        self._pause_start_time = None
        self._stream_title = ""

    def _stream_file(self, file_path: str, group_id: str) -> None:
        """Stream an audio file to a group."""
        if self._server is None:
            self._log_event("Server not running", "error")
            return

        # Stop any existing stream first
        if self._active_stream_future:
            self._stop_stream()

        # Find the target group
        target_group: SendspinGroup | None = None
        for client in self._server.clients:
            if client.group:
                if group_id == "all" or client.group.group_id == group_id:
                    target_group = client.group
                    break

        if target_group is None:
            self._log_event(f"No group found matching '{group_id}'", "error")
            return

        # Get filename for display
        from pathlib import Path
        filename = Path(file_path).name
        self._log_event(f"Streaming '{filename}' to group {target_group.group_id[:8]}...", "info")

        # Get audio duration
        audio_info = get_audio_info(file_path)
        duration_ms = int(audio_info.get("duration", 0) * 1000)

        # Set up pause support
        self._stream_pause_event = asyncio.Event()
        self._stream_pause_event.set()  # Start in playing state
        self._stream_paused = False

        # Set up metadata
        self._active_group = target_group
        self._stream_title = filename
        self._stream_duration_ms = duration_ms
        self._stream_start_time = time.time()
        self._pause_accumulated_ms = 0

        # Set initial metadata
        self._set_stream_metadata(target_group, filename, duration_ms, 0, False)

        # Start progress updates
        self._start_progress_updates()

        # Update UI
        self.stream_panel.set_streaming_state(True, False)

        # Audio format - decode to 48kHz stereo 16-bit PCM
        audio_format = AudioFormat(
            sample_rate=48000,
            bit_depth=16,
            channels=2,
            codec=AudioCodec.PCM,
        )

        async def _stream() -> None:
            # Wrap the audio source with pause support
            source = decode_audio_streaming(
                file_path,
                target_sample_rate=audio_format.sample_rate,
                target_channels=audio_format.channels,
                target_bit_depth=audio_format.bit_depth,
            )
            wrapped_source = self._wrap_with_pause_support(source, self._stream_pause_event)

            # Create media stream with pause-aware source
            media_stream = MediaStream(
                main_channel_source=wrapped_source,
                main_channel_format=audio_format,
            )

            # Start playback
            await target_group.play_media(media_stream)

        def on_complete(result: int | None, error: Exception | None) -> None:
            def update_ui() -> None:
                self._active_stream_future = None
                self._stream_pause_event = None
                self._stream_paused = False
                self._clear_metadata_state()
                self.stream_panel.set_streaming_state(False, False)

                if error and not isinstance(
                        error, (asyncio.CancelledError, concurrent.futures.CancelledError)
                    ):
                    self._log_event(f"File streaming error: {error}", "error")
                elif not error:
                    self._log_event(f"File streaming completed: {filename}", "success")
            self.after(0, update_ui)

        # Store future reference and start streaming
        self._active_stream_future = self._async_bridge.run_coroutine(_stream(), on_complete)

    def _stream_test_tone(self, frequency: int, duration: float, group_id: str) -> None:
        """Stream a test tone to a group."""
        if self._server is None:
            self._log_event("Server not running", "error")
            return

        # Stop any existing stream first
        if self._active_stream_future:
            self._stop_stream()

        # Find the target group
        target_group: SendspinGroup | None = None
        for client in self._server.clients:
            if client.group:
                if group_id == "all" or client.group.group_id == group_id:
                    target_group = client.group
                    break

        if target_group is None:
            self._log_event(f"No group found matching '{group_id}'", "error")
            return

        msg = f"Streaming {frequency}Hz tone for {duration}s to {target_group.group_id[:8]}..."
        self._log_event(msg, "info")

        # Calculate duration in ms
        duration_ms = int(duration * 1000)
        title = f"{frequency}Hz Test Tone"

        # Set up pause support
        self._stream_pause_event = asyncio.Event()
        self._stream_pause_event.set()  # Start in playing state
        self._stream_paused = False

        # Set up metadata
        self._active_group = target_group
        self._stream_title = title
        self._stream_duration_ms = duration_ms
        self._stream_start_time = time.time()
        self._pause_accumulated_ms = 0

        # Set initial metadata
        self._set_stream_metadata(target_group, title, duration_ms, 0, False)

        # Start progress updates
        self._start_progress_updates()

        # Update UI
        self.stream_panel.set_streaming_state(True, False)

        # Audio format - use 48kHz stereo 16-bit PCM (widely supported)
        audio_format = AudioFormat(
            sample_rate=48000,
            bit_depth=16,
            channels=2,
            codec=AudioCodec.PCM,
        )

        async def _stream() -> None:
            # Wrap the audio source with pause support
            source = generate_sine_wave(
                frequency=frequency,
                duration=duration,
                sample_rate=audio_format.sample_rate,
                channels=audio_format.channels,
                bit_depth=audio_format.bit_depth,
            )
            wrapped_source = self._wrap_with_pause_support(source, self._stream_pause_event)

            # Create media stream with pause-aware source
            media_stream = MediaStream(
                main_channel_source=wrapped_source,
                main_channel_format=audio_format,
            )

            # Start playback
            await target_group.play_media(media_stream)

        def on_complete(result: int | None, error: Exception | None) -> None:
            def update_ui() -> None:
                self._active_stream_future = None
                self._stream_pause_event = None
                self._stream_paused = False
                self._clear_metadata_state()
                self.stream_panel.set_streaming_state(False, False)

                if error and not isinstance(
                        error, (asyncio.CancelledError, concurrent.futures.CancelledError)
                    ):
                    self._log_event(f"Test tone error: {error}", "error")
                elif not error:
                    self._log_event("Test tone playback completed", "success")
            self.after(0, update_ui)

        # Store future reference and start streaming
        self._active_stream_future = self._async_bridge.run_coroutine(_stream(), on_complete)

    def _stream_url(self, url: str, group_id: str) -> None:
        """Stream audio from a URL to a group."""
        if self._server is None:
            self._log_event("Server not running", "error")
            return

        # Stop any existing stream first
        if self._active_stream_future:
            self._stop_stream()

        # Find the target group
        target_group: SendspinGroup | None = None
        for client in self._server.clients:
            if client.group:
                if group_id == "all" or client.group.group_id == group_id:
                    target_group = client.group
                    break

        if target_group is None:
            self._log_event(f"No group found matching '{group_id}'", "error")
            return

        self._log_event(f"Streaming URL to group {target_group.group_id[:8]}...", "info")
        self._log_event(f"URL: {url}", "debug")

        # Truncate URL for title (keep last part)
        title = url.split("/")[-1][:50] if "/" in url else url[:50]
        if not title or title == url[:50]:
            title = "URL Stream"

        # Set up pause support
        self._stream_pause_event = asyncio.Event()
        self._stream_pause_event.set()  # Start in playing state
        self._stream_paused = False

        # Set up metadata (duration=0 for unknown/live streams)
        self._active_group = target_group
        self._stream_title = title
        self._stream_duration_ms = 0  # Unknown duration for URL streams
        self._stream_start_time = time.time()
        self._pause_accumulated_ms = 0

        # Set initial metadata
        self._set_stream_metadata(target_group, title, 0, 0, False)

        # Start progress updates (will show elapsed time even without duration)
        self._start_progress_updates()

        # Update UI
        self.stream_panel.set_streaming_state(True, False)

        # Audio format - decode to 48kHz stereo 16-bit PCM
        audio_format = AudioFormat(
            sample_rate=48000,
            bit_depth=16,
            channels=2,
            codec=AudioCodec.PCM,
        )

        async def _stream() -> None:
            # Wrap the audio source with pause support
            source = decode_audio_streaming(
                url,
                target_sample_rate=audio_format.sample_rate,
                target_channels=audio_format.channels,
                target_bit_depth=audio_format.bit_depth,
            )
            wrapped_source = self._wrap_with_pause_support(source, self._stream_pause_event)

            # Create media stream with pause-aware source
            media_stream = MediaStream(
                main_channel_source=wrapped_source,
                main_channel_format=audio_format,
            )

            # Start playback
            await target_group.play_media(media_stream)

        def on_complete(result: int | None, error: Exception | None) -> None:
            def update_ui() -> None:
                self._active_stream_future = None
                self._stream_pause_event = None
                self._stream_paused = False
                self._clear_metadata_state()
                self.stream_panel.set_streaming_state(False, False)

                if error and not isinstance(
                        error, (asyncio.CancelledError, concurrent.futures.CancelledError)
                    ):
                    self._log_event(f"URL streaming error: {error}", "error")
                elif not error:
                    self._log_event("URL streaming completed", "success")
            self.after(0, update_ui)

        # Store future reference and start streaming
        self._active_stream_future = self._async_bridge.run_coroutine(_stream(), on_complete)

    def _pause_resume_stream(self) -> None:
        """Toggle pause/resume on the current stream."""
        if self._stream_pause_event is None:
            return

        self._stream_paused = not self._stream_paused

        if self._stream_paused:
            # Clear the event to pause (wait() will block)
            self._stream_pause_event.clear()
            self._pause_start_time = time.time()
            self._log_event("Stream paused", "info")
        else:
            # Set the event to resume (wait() will pass)
            self._stream_pause_event.set()
            # Track accumulated pause time
            if self._pause_start_time:
                self._pause_accumulated_ms += int((time.time() - self._pause_start_time) * 1000)
                self._pause_start_time = None
            self._log_event("Stream resumed", "info")

        # Update metadata with pause state
        if self._active_group and self._stream_start_time:
            elapsed = time.time() - self._stream_start_time
            progress_ms = int(elapsed * 1000) - self._pause_accumulated_ms
            if self._stream_paused and self._pause_start_time:
                # Use progress at pause time
                progress_ms = int((self._pause_start_time - self._stream_start_time) * 1000)
                progress_ms -= self._pause_accumulated_ms
            self._set_stream_metadata(
                self._active_group,
                self._stream_title,
                self._stream_duration_ms,
                max(0, progress_ms),
                self._stream_paused,
            )

        # Update UI
        self.stream_panel.set_streaming_state(True, self._stream_paused)

    def _stop_stream(self) -> None:
        """Stop the current stream."""
        if self._active_stream_future is None:
            return

        # Cancel the streaming future
        self._active_stream_future.cancel()
        self._active_stream_future = None

        # Reset pause state
        self._stream_paused = False
        if self._stream_pause_event:
            self._stream_pause_event.set()  # Unblock if paused
            self._stream_pause_event = None

        # Clear metadata
        self._clear_metadata_state()

        # Stop playback on all groups
        if self._server:
            async def _stop_all_groups() -> None:
                for client in self._server.clients:
                    if client.group:
                        try:
                            await client.group.stop()
                        except Exception:
                            pass  # Ignore errors during stop

            self._async_bridge.run_coroutine(_stop_all_groups(), lambda r, e: None)

        self._log_event("Stream stopped", "info")
        self.stream_panel.set_streaming_state(False, False)

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
