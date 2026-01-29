"""Audio decoding utilities using PyAV for file and URL streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from pathlib import Path

import av
import numpy as np
from av.audio.resampler import AudioResampler


async def decode_audio_source(
    source: str,
    *,
    target_sample_rate: int = 48000,
    target_channels: int = 2,
    target_bit_depth: int = 16,
    chunk_duration_ms: int = 25,
) -> AsyncGenerator[bytes, None]:
    """Decode audio from a file or URL to PCM chunks.

    Uses PyAV (ffmpeg) to decode various audio formats and resample
    to the target format.

    Args:
        source: File path or URL to the audio source
        target_sample_rate: Target sample rate in Hz (default 48000)
        target_channels: Target number of channels (default 2 for stereo)
        target_bit_depth: Target bit depth (16 or 24, default 16)
        chunk_duration_ms: Target chunk duration in milliseconds (default 25)

    Yields:
        Chunks of raw PCM audio data in the target format
    """
    # Determine the target format string for PyAV
    if target_bit_depth == 16:
        target_format = "s16"  # signed 16-bit
    elif target_bit_depth == 24:
        target_format = "s32"  # Use 32-bit and truncate (PyAV doesn't have s24)
    else:
        raise ValueError(f"Unsupported bit depth: {target_bit_depth}")

    # Layout string for channels
    if target_channels == 1:
        target_layout = "mono"
    elif target_channels == 2:
        target_layout = "stereo"
    else:
        target_layout = f"{target_channels}c"

    # Calculate target samples per chunk
    samples_per_chunk = int(target_sample_rate * chunk_duration_ms / 1000)
    bytes_per_sample = 2 if target_bit_depth == 16 else 4  # s16 or s32
    bytes_per_frame = bytes_per_sample * target_channels
    target_chunk_bytes = samples_per_chunk * bytes_per_frame

    # Buffer for accumulating decoded audio
    pcm_buffer = bytearray()

    # Run the blocking decode in a thread pool
    loop = asyncio.get_event_loop()

    def decode_sync() -> list[bytes]:
        """Synchronous decode function to run in thread pool."""
        chunks: list[bytes] = []
        buffer = bytearray()

        try:
            # Open the container (works with files and URLs)
            container = av.open(source)

            # Find the audio stream
            audio_stream = None
            for stream in container.streams:
                if stream.type == "audio":
                    audio_stream = stream
                    break

            if audio_stream is None:
                raise ValueError(f"No audio stream found in {source}")

            # Create resampler for format conversion
            resampler = AudioResampler(
                format=target_format,
                layout=target_layout,
                rate=target_sample_rate,
            )

            # Decode all frames
            for packet in container.demux(audio_stream):
                for frame in packet.decode():
                    # Resample the frame
                    resampled_frames = resampler.resample(frame)

                    for resampled in resampled_frames:
                        # Get raw bytes from the frame
                        raw_data = resampled.to_ndarray()

                        # Convert to bytes (interleaved format)
                        if target_bit_depth == 16:
                            pcm_bytes = raw_data.astype("<i2").tobytes()
                        else:  # 24-bit via 32-bit
                            # Convert 32-bit to 24-bit by taking upper 3 bytes
                            pcm_32 = raw_data.astype("<i4").tobytes()
                            pcm_bytes = bytearray()
                            for i in range(0, len(pcm_32), 4):
                                # Take bytes 1-3 (skip LSB for 24-bit)
                                pcm_bytes.extend(pcm_32[i + 1 : i + 4])
                            pcm_bytes = bytes(pcm_bytes)

                        buffer.extend(pcm_bytes)

                        # Emit full chunks
                        while len(buffer) >= target_chunk_bytes:
                            chunks.append(bytes(buffer[:target_chunk_bytes]))
                            del buffer[:target_chunk_bytes]

            # Flush the resampler
            resampled_frames = resampler.resample(None)
            for resampled in resampled_frames:
                raw_data = resampled.to_ndarray()
                if target_bit_depth == 16:
                    pcm_bytes = raw_data.astype("<i2").tobytes()
                else:
                    pcm_32 = raw_data.astype("<i4").tobytes()
                    pcm_bytes = bytearray()
                    for i in range(0, len(pcm_32), 4):
                        pcm_bytes.extend(pcm_32[i + 1 : i + 4])
                    pcm_bytes = bytes(pcm_bytes)
                buffer.extend(pcm_bytes)

            # Emit remaining chunks
            while len(buffer) >= target_chunk_bytes:
                chunks.append(bytes(buffer[:target_chunk_bytes]))
                del buffer[:target_chunk_bytes]

            # Emit final partial chunk (padded with silence)
            if buffer:
                buffer.extend(b"\x00" * (target_chunk_bytes - len(buffer)))
                chunks.append(bytes(buffer))

            container.close()

        except Exception as e:
            raise RuntimeError(f"Failed to decode audio: {e}") from e

        return chunks

    # Run decode in thread pool and yield chunks
    chunks = await loop.run_in_executor(None, decode_sync)
    for chunk in chunks:
        yield chunk


async def decode_audio_streaming(
    source: str,
    *,
    target_sample_rate: int = 48000,
    target_channels: int = 2,
    target_bit_depth: int = 16,
    chunk_duration_ms: int = 25,
) -> AsyncGenerator[bytes, None]:
    """Decode audio with streaming (yields chunks as they're decoded).

    This version yields chunks incrementally rather than buffering the entire file.
    Better for large files and live streams.

    Args:
        source: File path or URL to the audio source
        target_sample_rate: Target sample rate in Hz (default 48000)
        target_channels: Target number of channels (default 2 for stereo)
        target_bit_depth: Target bit depth (16 or 24, default 16)
        chunk_duration_ms: Target chunk duration in milliseconds (default 25)

    Yields:
        Chunks of raw PCM audio data in the target format
    """
    # Determine the target format string for PyAV
    if target_bit_depth == 16:
        target_format = "s16"
    elif target_bit_depth == 24:
        target_format = "s32"
    else:
        raise ValueError(f"Unsupported bit depth: {target_bit_depth}")

    # Layout string for channels
    if target_channels == 1:
        target_layout = "mono"
    elif target_channels == 2:
        target_layout = "stereo"
    else:
        target_layout = f"{target_channels}c"

    # Calculate target samples per chunk
    samples_per_chunk = int(target_sample_rate * chunk_duration_ms / 1000)
    bytes_per_sample = 2 if target_bit_depth == 16 else 4
    bytes_per_frame = bytes_per_sample * target_channels
    target_chunk_bytes = samples_per_chunk * bytes_per_frame

    loop = asyncio.get_event_loop()

    # Use a queue to pass chunks from decoder thread to async generator
    import queue

    chunk_queue: queue.Queue[bytes | None | Exception] = queue.Queue(maxsize=100)

    def decode_thread() -> None:
        """Decode in a separate thread and push chunks to queue."""
        buffer = bytearray()

        try:
            container = av.open(source)

            audio_stream = None
            for stream in container.streams:
                if stream.type == "audio":
                    audio_stream = stream
                    break

            if audio_stream is None:
                chunk_queue.put(ValueError(f"No audio stream found in {source}"))
                return

            resampler = AudioResampler(
                format=target_format,
                layout=target_layout,
                rate=target_sample_rate,
            )

            for packet in container.demux(audio_stream):
                for frame in packet.decode():
                    resampled_frames = resampler.resample(frame)

                    for resampled in resampled_frames:
                        raw_data = resampled.to_ndarray()

                        if target_bit_depth == 16:
                            pcm_bytes = raw_data.astype("<i2").tobytes()
                        else:
                            pcm_32 = raw_data.astype("<i4").tobytes()
                            pcm_bytes = bytearray()
                            for i in range(0, len(pcm_32), 4):
                                pcm_bytes.extend(pcm_32[i + 1 : i + 4])
                            pcm_bytes = bytes(pcm_bytes)

                        buffer.extend(pcm_bytes)

                        while len(buffer) >= target_chunk_bytes:
                            chunk_queue.put(bytes(buffer[:target_chunk_bytes]))
                            del buffer[:target_chunk_bytes]

            # Flush resampler
            resampled_frames = resampler.resample(None)
            for resampled in resampled_frames:
                raw_data = resampled.to_ndarray()
                if target_bit_depth == 16:
                    pcm_bytes = raw_data.astype("<i2").tobytes()
                else:
                    pcm_32 = raw_data.astype("<i4").tobytes()
                    pcm_bytes = bytearray()
                    for i in range(0, len(pcm_32), 4):
                        pcm_bytes.extend(pcm_32[i + 1 : i + 4])
                    pcm_bytes = bytes(pcm_bytes)
                buffer.extend(pcm_bytes)

            while len(buffer) >= target_chunk_bytes:
                chunk_queue.put(bytes(buffer[:target_chunk_bytes]))
                del buffer[:target_chunk_bytes]

            if buffer:
                buffer.extend(b"\x00" * (target_chunk_bytes - len(buffer)))
                chunk_queue.put(bytes(buffer))

            container.close()

        except Exception as e:
            chunk_queue.put(e)

        finally:
            chunk_queue.put(None)  # Signal end

    # Start decode thread
    import threading

    thread = threading.Thread(target=decode_thread, daemon=True)
    thread.start()

    # Yield chunks as they become available
    while True:
        # Poll the queue with a short timeout to allow async cooperation
        try:
            item = await loop.run_in_executor(
                None, lambda: chunk_queue.get(timeout=0.1)
            )
        except queue.Empty:
            continue

        if item is None:
            break
        if isinstance(item, Exception):
            raise item
        yield item


def get_audio_info(source: str) -> dict[str, str | int | float]:
    """Get information about an audio source.

    Args:
        source: File path or URL to the audio source

    Returns:
        Dictionary with audio information (duration, sample_rate, channels, codec, etc.)
    """
    try:
        container = av.open(source)

        audio_stream = None
        for stream in container.streams:
            if stream.type == "audio":
                audio_stream = stream
                break

        if audio_stream is None:
            return {"error": "No audio stream found"}

        info = {
            "duration": float(container.duration / av.time_base) if container.duration else 0,
            "sample_rate": audio_stream.rate or 0,
            "channels": audio_stream.channels or 0,
            "codec": audio_stream.codec_context.name if audio_stream.codec_context else "unknown",
            "bit_rate": audio_stream.bit_rate or 0,
        }

        container.close()
        return info

    except Exception as e:
        return {"error": str(e)}
