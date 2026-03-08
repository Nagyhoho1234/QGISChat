# Changelog

## 1.1.0 (2026-03-08)

### Added
- **Google Earth Engine integration** -- configure your GEE project in Settings, and ask the AI to query, process, and download GEE data directly into QGIS
- GEE project field in Settings dialog with help text
- Dynamic system prompt: appends GEE instructions only when a project is configured
- Multi-tool execution: handles multiple tool calls per response (fixes Anthropic tool_use/tool_result contract)
- Recursive follow-up processing for complex multi-step tasks (up to 10 rounds)
- Conversation history truncation (max 40 messages) with smart tool_use/tool_result boundary handling
- Debug JSONL logging of conversation history (`%APPDATA%/QGISChat/logs/conversation_*.jsonl` or `~/.local/share/QGISChat/logs/`)
- Rollback error recovery instead of full history clear on tool sync errors
- Enhanced raster context: cell size, band names, data types (up to 20 bands)

### Fixed
- Critical bug: only the last tool_use block was captured when the AI returned multiple tool calls in one response, causing `tool_use ids without tool_result blocks` errors
- Follow-up responses containing tool calls were silently dropped instead of being processed recursively
- System prompt now prevents the AI from using `subprocess` with `sys.executable` (which points to `qgis-bin.exe`, not `python.exe`, and launches a new QGIS instance)

### Changed
- Version bumped to 1.1.0 in metadata.txt
- Added `google earth engine,gee` to plugin tags

## 1.0.0 (2026-03-06)

Initial release.

- AI-powered chat dock panel for QGIS
- Natural language GIS task execution via PyQGIS code generation
- Map context awareness (layers, fields, extent, CRS, raster bands)
- Multi-provider support: Anthropic (Claude), OpenAI (GPT), Google Gemini, Ollama, OpenAI-compatible
- Settings dialog for provider selection, API key, model, and preferences
- Automatic error recovery with alternative approaches
- Confirmation dialog before executing generated code
- Code display toggle in chat
