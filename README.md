# Strudel LLM Fork

This is a fork of [Strudel](https://github.com/tidalcycles/strudel) for experimenting with Large Language Model (LLM) integration.

## Original Strudel

Strudel is a JavaScript port of [TidalCycles](https://tidalcycles.org/), bringing live coding patterns to the web browser. For the original project, see:

- **Original Repository**: https://github.com/tidalcycles/strudel
- **Website**: https://strudel.cc/
- **Documentation**: https://strudel.cc/learn/

## LLM Integration Features

This fork adds:

- **MCP (Model Context Protocol) Server**: FastAPI server for LLM communication
- **WebSocket Support**: Real-time communication between LLMs and Strudel
- **Session Management**: Multi-session support for concurrent LLM connections
- **Code Execution**: LLMs can play, stop, and retrieve code from Strudel
- **Docker Production Build**: Complete containerization for deployment

## MCP Server - The Core Innovation

This fork's main feature is the **Python FastAPI MCP (Model Context Protocol) Server** that enables LLMs to interact with Strudel in real-time.

### What the MCP Server Does

The MCP server (`strudel_mcp_server.py`) provides:

- **WebSocket Communication**: Real-time bidirectional communication with LLMs
- **Session Management**: Multiple concurrent LLM sessions with unique session IDs
- **Code Execution**: LLMs can play/stop patterns and retrieve current code
- **Static Site Serving**: Serves the built Strudel website
- **Documentation Routes**: Comprehensive routing for all Strudel docs

### LLM Integration Features

- **Play Code**: LLMs send code to execute in Strudel
- **Stop Playback**: LLMs can stop current patterns
- **Get Current Code**: LLMs can retrieve what's currently in the editor
- **Session Tracking**: Each LLM connection gets a unique session ID
- **Real-time Status**: Connection status monitoring

### Architecture

```
LLM (Claude Code) ←→ WebSocket ←→ MCP Server ←→ Strudel Web Interface
```

1. **LLM connects** via WebSocket with session ID
2. **MCP server** manages connections and message routing
3. **Strudel interface** displays session info and executes code
4. **Real-time sync** between LLM commands and audio output

## Deployment

### Production (MCP Server)
```bash
# Build production container with MCP server
docker build -t strudel-prod .

# Run MCP server on port 8080
docker run -p 8080:8080 strudel-prod
```

### Development (Optional)
```bash
# Traditional Strudel development
pnpm install && pnpm dev  # Port 4321
```

### Docker Build Script
```bash
./docker-build.sh prod    # MCP production build
./docker-build.sh dev     # Development build
./docker-build.sh         # Build both
```

## Using the MCP Server

1. **Deploy** the container to your server (Coolify, etc.)
2. **Access** the web interface: `http://your-server:8080/strudel/`
3. **Connect LLMs** via WebSocket: `ws://your-server:8080/ws?session_id=your_id`
4. **LLMs can now** play code, stop playback, and get current code
5. **Session info** displays in the Strudel header

## Deployment

This fork is designed for deployment with:
- **Coolify** on Digital Ocean
- **Docker** containers
- **FastAPI** backend
- **Static site** serving

### GitHub Mirror

A deployment mirror is maintained at: https://github.com/calvinw/strudel-llm-mirror

Use `./sync-to-github.sh` to sync changes to the mirror for deployment.

## License

Same as original Strudel: AGPL-3.0-or-later

## Contributing

This is an experimental fork. For the main Strudel project, contribute to:
https://github.com/tidalcycles/strudel