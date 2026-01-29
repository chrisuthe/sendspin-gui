"""Audio generation utilities for test tones."""

from __future__ import annotations

import math
import struct
from collections.abc import AsyncGenerator


async def generate_sine_wave(
    frequency: int,
    duration: float,
    sample_rate: int = 48000,
    channels: int = 2,
    bit_depth: int = 16,
    chunk_duration_ms: int = 25,
) -> AsyncGenerator[bytes, None]:
    """Generate a sine wave as PCM audio chunks.

    Args:
        frequency: Frequency of the sine wave in Hz
        duration: Duration of the tone in seconds
        sample_rate: Sample rate in Hz (default 48000)
        channels: Number of audio channels (default 2 for stereo)
        bit_depth: Bit depth (16 or 24, default 16)
        chunk_duration_ms: Duration of each chunk in milliseconds (default 25)

    Yields:
        Chunks of raw PCM audio data
    """
    # Calculate parameters
    samples_per_chunk = int(sample_rate * chunk_duration_ms / 1000)
    total_samples = int(sample_rate * duration)
    bytes_per_sample = bit_depth // 8
    frame_size = bytes_per_sample * channels

    # Amplitude (leave some headroom)
    if bit_depth == 16:
        amplitude = 32000  # Max is 32767
        pack_format = "<h"  # little-endian signed short
    elif bit_depth == 24:
        amplitude = 8388000  # Max is 8388607
        pack_format = None  # Need custom packing for 24-bit
    else:
        raise ValueError(f"Unsupported bit depth: {bit_depth}")

    sample_index = 0
    angular_frequency = 2 * math.pi * frequency / sample_rate

    while sample_index < total_samples:
        # Calculate how many samples in this chunk
        remaining = total_samples - sample_index
        chunk_samples = min(samples_per_chunk, remaining)

        # Generate samples for this chunk
        chunk_data = bytearray()

        for i in range(chunk_samples):
            # Calculate sine value
            t = sample_index + i
            value = int(amplitude * math.sin(angular_frequency * t))

            # Pack the sample
            if bit_depth == 16:
                sample_bytes = struct.pack(pack_format, value)
            else:  # 24-bit
                # Pack as 3 bytes, little-endian
                if value < 0:
                    value = value + 0x1000000  # Convert to unsigned
                sample_bytes = bytes([
                    value & 0xFF,
                    (value >> 8) & 0xFF,
                    (value >> 16) & 0xFF,
                ])

            # Write to all channels
            for _ in range(channels):
                chunk_data.extend(sample_bytes)

        sample_index += chunk_samples
        yield bytes(chunk_data)
