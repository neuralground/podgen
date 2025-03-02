# Podgen

Podgen is an AI-powered system for generating conversational podcasts from text content. It converts input text into engaging multi-speaker conversations with synthesized voices and professional audio production.

## Features

- Convert text content into natural conversations
- Multiple speaker personas with distinct voices and personalities
- High-quality text-to-speech synthesis
- Professional audio post-processing
- Extensible plugin architecture
- Secure API key management

## Installation

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install podgen
pip install -e .
```

## Quick Start

```python
from podgen.services.conversation import ConversationGenerator
from podgen.services.tts import TTSService
from podgen.services.audio import AudioProcessor
from podgen.config import initialize_api_keys

# Initialize API keys securely
initialize_api_keys(interactive=True)

# Initialize services
conversation = ConversationGenerator()
tts = TTSService()
audio = AudioProcessor()

# Generate a podcast
text = "Your input text here..."
dialogue = conversation.generate_dialogue(text)
audio_files = tts.synthesize_dialogue(dialogue)
podcast = audio.combine_audio_files(audio_files, "podcast.wav")
```

## Configuration

Copy `.env.example` to `.env` and adjust the settings:

```bash
cp .env.example .env
```

### Secure API Key Management

Podgen now uses secure credential storage for API keys:

```bash
# Set up API keys securely
python -m podgen.cli --setup-keys

# Or use the key management tool
python -m podgen.tools.keymanager store openai-api
python -m podgen.tools.keymanager store elevenlabs-api
```

For more information on the security enhancements, see the [API Security Upgrade Guide](docs/security-upgrade.md).

## CLI Usage

The Podgen CLI provides a full-featured interface for generating podcasts:

```bash
# Start the CLI
python -m podgen.cli

# Available commands:
/add source <file or URL>    # Add content
/list sources                # Show all sources
/add conversation            # Generate a podcast
/list conversations          # Show all podcasts
/play <id>                   # Play a podcast
/show conversation <id>      # Show details
/key set <service>           # Set API key
/key check                   # Check keys
/help                        # Show help
```

## Development

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src tests
isort src tests

# Type checking
mypy src tests
```

## Models and Providers

Podgen supports multiple LLM and TTS providers:

### LLM Providers
- OpenAI API
- Ollama (local)

### TTS Providers
- ElevenLabs
- OpenAI
- Coqui TTS (local)
- Bark (local)

Use the `install_models.py` script to set up local models:

```bash
python install_models.py coqui  # Install Coqui TTS
python install_models.py bark   # Install Bark
python install_models.py ollama # Install Ollama
```
