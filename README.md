# Sendspin GUI

A GUI wrapper for testing and iterating on the [aiosendspin](https://github.com/Sendspin/aiosendspin) server without needing to integrate with Music Assistant.

## Features

- **Server Management**: Start/stop the Sendspin server with configurable settings
- **Client Discovery**: Automatic mDNS discovery of Sendspin clients on your network
- **Group Management**: Create and manage client groups for synchronized playback
- **Audio Streaming**: Stream audio files or test tones to groups
- **Event Logging**: Real-time event log with filtering capabilities

## Installation

### Prerequisites

- Python 3.11 or higher
- pip

### Install from source

```bash
cd "Z:\Code Projects\sendspin-gui"
pip install -e .
```

### Install dependencies only

```bash
pip install aiosendspin customtkinter pillow
```

## Usage

### Run the GUI

```bash
# Using the installed command
sendspin-gui

# Or run as a module
python -m sendspin_gui
```

### Quick Start

1. **Start the server**: Configure the server ID, name, and port, then click "Start Server"
2. **Connect clients**: Sendspin clients on your network will be discovered automatically (if mDNS is enabled)
3. **Create groups**: Select clients and click "Create Group" to group them for synchronized playback
4. **Stream audio**: Use the Stream panel to play test tones or audio files to your groups

## GUI Overview

### Server Panel
- Configure server ID and name
- Set the server port (default: 8765)
- Enable/disable mDNS for automatic discovery
- Start/stop the server

### Clients Panel
- View all connected clients
- See client roles and group membership
- Select clients to create groups
- Disconnect individual clients

### Groups Panel
- View all active groups
- Playback controls (play/stop)
- Volume control per group
- Expand groups to see and manage members

### Stream Panel
- **File**: Browse and stream audio files (WAV, FLAC, MP3, etc.)
- **Test Tone**: Generate sine wave test tones at configurable frequencies
- **URL**: (Coming soon) Stream from network URLs

### Event Log
- Real-time server events
- Filter by event type (info, success, warning, error)
- Clear log functionality

## Development

### Project Structure

```
sendspin-gui/
├── src/
│   └── sendspin_gui/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py              # Main application
│       ├── components/
│       │   ├── __init__.py
│       │   ├── server_panel.py
│       │   ├── clients_panel.py
│       │   ├── groups_panel.py
│       │   ├── event_log.py
│       │   └── stream_panel.py
│       └── utils/
│           ├── __init__.py
│           └── async_bridge.py
├── pyproject.toml
└── README.md
```

### Running in development

```bash
# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Run the app
python -m sendspin_gui
```

### Code style

The project uses ruff for linting:

```bash
ruff check src/
ruff format src/
```

## Architecture Notes

The GUI uses `customtkinter` for a modern appearance and runs the asyncio event loop in a separate thread to avoid blocking the UI. The `AsyncBridge` utility handles communication between the tkinter main thread and the async server operations.

## Related Projects

- [aiosendspin](https://github.com/Sendspin/aiosendspin) - The underlying async Sendspin protocol library
- [sendspin](https://pypi.org/project/sendspin/) - A synchronized audio player built on aiosendspin
- [Music Assistant](https://music-assistant.io/) - Full-featured music server that uses aiosendspin

## License

MIT
