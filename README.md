# GIS Chat for QGIS

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![QGIS 3.34+](https://img.shields.io/badge/QGIS-3.34%2B-589632.svg)](https://qgis.org)

AI-powered chat assistant for QGIS. Ask questions in natural language and let the AI execute GIS operations for you — including Google Earth Engine integration.

![GIS Chat Screenshot](docs/screenshot.png)

## Features

- **Natural language GIS operations** -- describe what you want, get it done
- **Map context awareness** -- automatically reads your layers, fields, extent, CRS, and raster band info
- **PyQGIS code generation & execution** -- generates and runs Python code directly in QGIS
- **Google Earth Engine integration** -- query, process, and download GEE data directly from the chat
- **Multi-provider support** -- choose the AI backend that works for you
- **Multi-tool execution** -- handles complex tasks requiring multiple sequential operations
- **Automatic error recovery** -- retries alternative approaches when a tool fails
- **Conversation history management** -- smart truncation with debug JSONL logging

### Supported AI Providers

| Provider | Cost | Setup |
|----------|------|-------|
| **Google Gemini** | Free tier available | [Get API key](https://aistudio.google.com/apikey) |
| **Ollama** | Free (local) | [Install Ollama](https://ollama.com) |
| **Anthropic (Claude)** | Paid | [Get API key](https://console.anthropic.com/settings/keys) |
| **OpenAI (GPT)** | Paid | [Get API key](https://platform.openai.com/api-keys) |
| **OpenAI-compatible** | Varies | LM Studio, vLLM, Azure OpenAI, etc. |

## Installation

### From ZIP

1. Download the latest release ZIP from [Releases](https://github.com/Nagyhoho1234/QGISChat/releases/latest)
2. In QGIS: **Plugins > Manage and Install Plugins > Install from ZIP**
3. Select the downloaded ZIP and click **Install Plugin**

### Manual

1. Clone or download this repository
2. Copy the `QGISChat` folder to your QGIS plugins directory:
   - Windows: `%APPDATA%/QGIS/QGIS3/profiles/default/python/plugins/`
   - Linux: `~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/`
   - macOS: `~/Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins/`
3. Restart QGIS and enable "GIS Chat" in **Plugins > Manage and Install Plugins**

## Google Earth Engine Setup (Optional)

GIS Chat can query, process, and download data from Google Earth Engine directly. To enable:

1. **Install the GEE Python package** in your QGIS Python environment:
   ```
   pip install earthengine-api
   ```
2. **Authenticate** (one-time):
   ```python
   import ee
   ee.Authenticate()
   ```
3. **Configure in GIS Chat** -- go to Settings and enter your GEE project ID (e.g. `my-gee-project`).

If you don't have a GEE project, create one at [code.earthengine.google.com](https://code.earthengine.google.com/).

After setup, you can ask things like *"Load recent Sentinel-2 NDVI for my study area from GEE"* and the AI will handle the full workflow.

## Usage

1. Click the **GIS Chat** button in the toolbar (or **Plugins > GIS Chat > GIS Chat**)
2. Go to **Settings** to configure your AI provider and API key
3. Type a GIS task in plain language

### Examples

| You say | GIS Chat does |
|---------|---------------|
| "Buffer the roads layer by 500 meters" | Runs `processing.run("native:buffer", ...)` |
| "How many features are in the parcels layer?" | Queries feature count and reports |
| "Select buildings within 1 km of the river" | Runs `native:selectbylocation` |
| "Add a new text field called 'Status' to parcels" | Runs `native:addfieldtoattributestable` |
| "What CRS is this project using?" | Reads map context and answers directly |
| "Export selected features to GeoPackage" | Generates and runs the export code |
| "Load recent Sentinel-2 NDVI from GEE for my area" | Queries GEE, downloads, and adds the raster to QGIS |

## Project Structure

```
QGISChat/
├── __init__.py          # Plugin entry point
├── metadata.txt         # QGIS plugin metadata
├── plugin.py            # Main plugin class (toolbar, menu)
├── chat_dock.py         # Chat dock widget (PyQt5 UI)
├── llm_service.py       # Multi-provider LLM client
├── map_context.py       # QGIS map context builder
├── code_executor.py     # Python code execution
├── settings.py          # Settings via QgsSettings
├── settings_dialog.py   # Settings dialog
├── icon.png             # Plugin icon
└── LICENSE
```

## Security

- API keys are stored in QGIS settings (QgsSettings) -- local to your machine only
- Keys are never transmitted anywhere except to the selected AI provider's API endpoint
- All AI requests go directly from your machine to the provider -- no intermediary server

## Citation

If you use GIS Chat in your research, please cite the preprint:

> Fehér, Zs. Z. (2026). GIS Chat: Bridging Natural Language and Desktop GIS Automation with LLM-Powered GIS Plugins. *EarthArXiv preprint, submitted to SoftwareX*. DOI: [10.31223/X54Z09](https://doi.org/10.31223/X54Z09)

```bibtex
@article{feher2026gischat,
  title={GIS Chat: Bridging Natural Language and Desktop GIS Automation with LLM-Powered GIS Plugins},
  author={Feh{\'e}r, Zsolt Zolt{\'a}n},
  year={2026},
  doi={10.31223/X54Z09},
  note={EarthArXiv preprint, submitted to SoftwareX}
}
```

## License

MIT License -- see [LICENSE](LICENSE) for details.

Copyright (c) 2026 Zsolt Zoltan Feher
