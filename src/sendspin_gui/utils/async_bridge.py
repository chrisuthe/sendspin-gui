"""Bridge between asyncio event loop and tkinter main thread."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable, Coroutine
from typing import Any, TypeVar

T = TypeVar("T")


class AsyncBridge:
    """Manages an asyncio event loop in a separate thread for GUI applications.

    This allows running async code from synchronous GUI callbacks.
    """

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._started = threading.Event()

    def start(self) -> None:
        """Start the async event loop in a background thread."""
        if self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._started.wait(timeout=5.0)

    def _run_loop(self) -> None:
        """Run the event loop (called in background thread)."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._started.set()
        self._loop.run_forever()

    def stop(self) -> None:
        """Stop the async event loop and thread."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None
            self._loop = None

    @property
    def loop(self) -> asyncio.AbstractEventLoop:
        """Get the running event loop."""
        if self._loop is None:
            raise RuntimeError("AsyncBridge not started")
        return self._loop

    def run_coroutine(
        self,
        coro: Coroutine[Any, Any, T],
        callback: Callable[[T | None, Exception | None], None] | None = None,
    ) -> asyncio.Future[T]:
        """Schedule a coroutine to run in the async loop.

        Args:
            coro: The coroutine to run
            callback: Optional callback(result, exception) called when complete

        Returns:
            A Future that can be used to get the result
        """
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)

        if callback is not None:
            def on_done(f: asyncio.Future[T]) -> None:
                try:
                    result = f.result()
                    callback(result, None)
                except Exception as e:
                    callback(None, e)

            future.add_done_callback(on_done)

        return future

    def run_coroutine_sync(self, coro: Coroutine[Any, Any, T], timeout: float = 30.0) -> T:
        """Run a coroutine and wait for the result synchronously.

        Warning: This will block the calling thread. Don't use from GUI thread
        for long-running operations.
        """
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)
        return future.result(timeout=timeout)
