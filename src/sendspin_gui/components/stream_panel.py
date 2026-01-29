"""Stream panel component for managing audio streaming."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk


class StreamPanel(ctk.CTkFrame):
    """Panel for configuring and controlling audio streaming."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        on_stream_file: Callable[[str, str], None],
        on_stream_test_tone: Callable[[int, float, str], None],
    ) -> None:
        super().__init__(parent)

        self._on_stream_file = on_stream_file
        self._on_stream_test_tone = on_stream_test_tone
        self._selected_file: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the panel UI."""
        self.grid_columnconfigure(0, weight=1)

        # Title
        title = ctk.CTkLabel(
            self,
            text="Audio Streaming",
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        title.grid(row=0, column=0, sticky="w", padx=10, pady=(10, 5))

        # Tabview for different stream sources
        self.tabview = ctk.CTkTabview(self, height=200)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

        # File tab
        file_tab = self.tabview.add("File")
        self._build_file_tab(file_tab)

        # Test tone tab
        tone_tab = self.tabview.add("Test Tone")
        self._build_tone_tab(tone_tab)

        # URL tab (placeholder for future)
        url_tab = self.tabview.add("URL")
        self._build_url_tab(url_tab)

    def _build_file_tab(self, parent: ctk.CTkFrame) -> None:
        """Build the file streaming tab."""
        parent.grid_columnconfigure(1, weight=1)

        # File selection
        ctk.CTkLabel(parent, text="Audio File:").grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        self.file_entry = ctk.CTkEntry(parent, placeholder_text="Select an audio file...")
        self.file_entry.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        browse_btn = ctk.CTkButton(
            parent,
            text="Browse",
            command=self._browse_file,
            width=80,
        )
        browse_btn.grid(row=0, column=2, padx=10, pady=10)

        # Target group selection
        ctk.CTkLabel(parent, text="Target Group:").grid(
            row=1, column=0, padx=10, pady=5, sticky="w"
        )

        self.file_group_entry = ctk.CTkEntry(
            parent,
            placeholder_text="Group ID (or 'all')",
        )
        self.file_group_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Stream button
        self.stream_file_btn = ctk.CTkButton(
            parent,
            text="Stream File",
            command=self._stream_file,
            fg_color="green",
            hover_color="darkgreen",
        )
        self.stream_file_btn.grid(row=2, column=0, columnspan=3, padx=10, pady=15)

        # Supported formats note
        formats_label = ctk.CTkLabel(
            parent,
            text="Supported: WAV, FLAC, MP3, OGG, AAC (requires ffmpeg)",
            text_color="gray",
            font=ctk.CTkFont(size=10),
        )
        formats_label.grid(row=3, column=0, columnspan=3, padx=10)

    def _build_tone_tab(self, parent: ctk.CTkFrame) -> None:
        """Build the test tone tab."""
        parent.grid_columnconfigure(1, weight=1)

        # Frequency
        ctk.CTkLabel(parent, text="Frequency (Hz):").grid(
            row=0, column=0, padx=10, pady=10, sticky="w"
        )

        self.freq_slider = ctk.CTkSlider(
            parent,
            from_=100,
            to=2000,
            number_of_steps=38,
        )
        self.freq_slider.set(440)
        self.freq_slider.grid(row=0, column=1, padx=5, pady=10, sticky="ew")

        self.freq_label = ctk.CTkLabel(parent, text="440 Hz", width=60)
        self.freq_label.grid(row=0, column=2, padx=10, pady=10)

        self.freq_slider.configure(
            command=lambda v: self.freq_label.configure(text=f"{int(v)} Hz")
        )

        # Duration
        ctk.CTkLabel(parent, text="Duration (sec):").grid(
            row=1, column=0, padx=10, pady=5, sticky="w"
        )

        self.duration_slider = ctk.CTkSlider(
            parent,
            from_=1,
            to=30,
            number_of_steps=29,
        )
        self.duration_slider.set(5)
        self.duration_slider.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        self.duration_label = ctk.CTkLabel(parent, text="5 sec", width=60)
        self.duration_label.grid(row=1, column=2, padx=10, pady=5)

        self.duration_slider.configure(
            command=lambda v: self.duration_label.configure(text=f"{int(v)} sec")
        )

        # Target group
        ctk.CTkLabel(parent, text="Target Group:").grid(
            row=2, column=0, padx=10, pady=5, sticky="w"
        )

        self.tone_group_entry = ctk.CTkEntry(
            parent,
            placeholder_text="Group ID (or 'all')",
        )
        self.tone_group_entry.grid(row=2, column=1, padx=5, pady=5, sticky="ew")

        # Play button
        self.play_tone_btn = ctk.CTkButton(
            parent,
            text="Play Test Tone",
            command=self._play_tone,
            fg_color="blue",
            hover_color="darkblue",
        )
        self.play_tone_btn.grid(row=3, column=0, columnspan=3, padx=10, pady=15)

    def _build_url_tab(self, parent: ctk.CTkFrame) -> None:
        """Build the URL streaming tab (placeholder)."""
        parent.grid_columnconfigure(0, weight=1)

        placeholder = ctk.CTkLabel(
            parent,
            text="URL streaming coming soon...\n\nThis will allow streaming from:\n• HTTP/HTTPS URLs\n• Internet radio streams\n• Other network sources",
            text_color="gray",
            justify="center",
        )
        placeholder.grid(row=0, column=0, padx=20, pady=40)

    def _browse_file(self) -> None:
        """Open file browser to select audio file."""
        filetypes = [
            ("Audio files", "*.wav *.flac *.mp3 *.ogg *.aac *.m4a"),
            ("WAV files", "*.wav"),
            ("FLAC files", "*.flac"),
            ("MP3 files", "*.mp3"),
            ("All files", "*.*"),
        ]

        filename = filedialog.askopenfilename(
            title="Select Audio File",
            filetypes=filetypes,
        )

        if filename:
            self._selected_file = filename
            self.file_entry.delete(0, "end")
            self.file_entry.insert(0, filename)

    def _stream_file(self) -> None:
        """Start streaming the selected file."""
        file_path = self.file_entry.get().strip()
        group_id = self.file_group_entry.get().strip() or "all"

        if not file_path:
            return

        if not Path(file_path).exists():
            return

        self._on_stream_file(file_path, group_id)

    def _play_tone(self) -> None:
        """Start playing a test tone."""
        frequency = int(self.freq_slider.get())
        duration = float(self.duration_slider.get())
        group_id = self.tone_group_entry.get().strip() or "all"

        self._on_stream_test_tone(frequency, duration, group_id)
