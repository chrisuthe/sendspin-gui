"""Groups panel component for managing Sendspin groups."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import customtkinter as ctk


class GroupsPanel(ctk.CTkFrame):
    """Panel for displaying and managing Sendspin groups."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_play: Callable[[str], None],
        on_stop: Callable[[str], None],
        on_set_volume: Callable[[str, int], None],
        on_remove_client: Callable[[str, str], None],
    ) -> None:
        super().__init__(parent)

        self._on_play = on_play
        self._on_stop = on_stop
        self._on_set_volume = on_set_volume
        self._on_remove_client = on_remove_client
        self._groups: list[dict[str, Any]] = []
        self._group_frames: dict[str, ctk.CTkFrame] = {}
        self._expanded_groups: set[str] = set()

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
            text="Groups",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w")

        self.group_count_label = ctk.CTkLabel(
            title_frame,
            text="(0)",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self.group_count_label.grid(row=0, column=1, sticky="w", padx=5)

        # Scrollable frame for groups
        self.groups_scroll = ctk.CTkScrollableFrame(self)
        self.groups_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        self.groups_scroll.grid_columnconfigure(0, weight=1)

        # Empty state label
        self.empty_label = ctk.CTkLabel(
            self.groups_scroll,
            text="No groups created.\nSelect clients and create a group.",
            text_color="gray",
            justify="center",
        )
        self.empty_label.grid(row=0, column=0, pady=20)

    def update_groups(self, groups: list[dict[str, Any]]) -> None:
        """Update the groups list."""
        self._groups = groups

        # Clear existing group frames
        for frame in self._group_frames.values():
            frame.destroy()
        self._group_frames.clear()

        # Update count
        self.group_count_label.configure(text=f"({len(groups)})")

        if not groups:
            self.empty_label.grid(row=0, column=0, pady=20)
            return

        self.empty_label.grid_forget()

        # Create group entries
        for i, group in enumerate(groups):
            frame = self._create_group_frame(group, i)
            self._group_frames[group["id"]] = frame

    def _create_group_frame(self, group: dict[str, Any], row: int) -> ctk.CTkFrame:
        """Create a frame for a single group."""
        frame = ctk.CTkFrame(self.groups_scroll)
        frame.grid(row=row, column=0, sticky="ew", pady=2)
        frame.grid_columnconfigure(1, weight=1)

        # Main info row
        main_frame = ctk.CTkFrame(frame, fg_color="transparent")
        main_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=5)
        main_frame.grid_columnconfigure(1, weight=1)

        # Expand/collapse button
        is_expanded = group["id"] in self._expanded_groups
        expand_btn = ctk.CTkButton(
            main_frame,
            text="▼" if is_expanded else "▶",
            width=25,
            height=25,
            command=lambda gid=group["id"]: self._toggle_expand(gid),
        )
        expand_btn.grid(row=0, column=0, padx=(0, 5))

        # Group name and state
        info_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        info_frame.grid(row=0, column=1, sticky="ew")
        info_frame.grid_columnconfigure(0, weight=1)

        name_label = ctk.CTkLabel(
            info_frame,
            text=group["name"] or group["id"][:12],
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
        )
        name_label.grid(row=0, column=0, sticky="w")

        state_color = {
            "playing": "#00ff00",
            "paused": "#ffff00",
            "stopped": "#888888",
            "buffering": "#ff8800",
        }.get(group.get("state", "").lower(), "#888888")

        state_label = ctk.CTkLabel(
            info_frame,
            text=f"● {group.get('state', 'unknown')}",
            text_color=state_color,
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        state_label.grid(row=1, column=0, sticky="w")

        # Client count
        client_count = len(group.get("clients", []))
        clients_label = ctk.CTkLabel(
            main_frame,
            text=f"{client_count} client{'s' if client_count != 1 else ''}",
            text_color="gray",
        )
        clients_label.grid(row=0, column=2, padx=10)

        # Playback controls
        controls_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        controls_frame.grid(row=0, column=3, padx=5)

        play_btn = ctk.CTkButton(
            controls_frame,
            text="▶",
            width=30,
            height=30,
            command=lambda gid=group["id"]: self._on_play(gid),
        )
        play_btn.grid(row=0, column=0, padx=2)

        stop_btn = ctk.CTkButton(
            controls_frame,
            text="■",
            width=30,
            height=30,
            fg_color="gray",
            command=lambda gid=group["id"]: self._on_stop(gid),
        )
        stop_btn.grid(row=0, column=1, padx=2)

        # Volume slider
        volume_frame = ctk.CTkFrame(frame, fg_color="transparent")
        volume_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 5))
        volume_frame.grid_columnconfigure(1, weight=1)

        vol_label = ctk.CTkLabel(volume_frame, text="Vol:")
        vol_label.grid(row=0, column=0, padx=(0, 5))

        volume_slider = ctk.CTkSlider(
            volume_frame,
            from_=0,
            to=100,
            number_of_steps=100,
            command=lambda v, gid=group["id"]: self._on_set_volume(gid, int(v)),
        )
        volume_slider.set(group.get("volume", 100))
        volume_slider.grid(row=0, column=1, sticky="ew")

        vol_value = ctk.CTkLabel(
            volume_frame,
            text=f"{group.get('volume', 100)}%",
            width=40,
        )
        vol_value.grid(row=0, column=2, padx=5)

        # Mute indicator
        if group.get("muted"):
            mute_label = ctk.CTkLabel(
                volume_frame,
                text="MUTED",
                text_color="red",
                font=ctk.CTkFont(size=10),
            )
            mute_label.grid(row=0, column=3, padx=5)

        # Expanded client list
        if is_expanded:
            clients_frame = ctk.CTkFrame(frame)
            clients_frame.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 5))
            clients_frame.grid_columnconfigure(0, weight=1)

            for i, client_id in enumerate(group.get("clients", [])):
                client_row = ctk.CTkFrame(clients_frame, fg_color="transparent")
                client_row.grid(row=i, column=0, sticky="ew", pady=1)
                client_row.grid_columnconfigure(0, weight=1)

                client_label = ctk.CTkLabel(
                    client_row,
                    text=f"  • {client_id[:20]}...",
                    anchor="w",
                    font=ctk.CTkFont(size=11),
                )
                client_label.grid(row=0, column=0, sticky="w")

                remove_btn = ctk.CTkButton(
                    client_row,
                    text="✕",
                    width=20,
                    height=20,
                    fg_color="transparent",
                    hover_color="red",
                    command=lambda gid=group["id"], cid=client_id: self._on_remove_client(gid, cid),
                )
                remove_btn.grid(row=0, column=1, padx=5)

        return frame

    def _toggle_expand(self, group_id: str) -> None:
        """Toggle group expansion."""
        if group_id in self._expanded_groups:
            self._expanded_groups.discard(group_id)
        else:
            self._expanded_groups.add(group_id)

        # Refresh display
        self.update_groups(self._groups)

    def clear(self) -> None:
        """Clear all groups."""
        self.update_groups([])
        self._expanded_groups.clear()
