# Podgen

Podgen is an AI-powered system for generating conversational podcasts from text content. It converts input text into engaging multi-speaker conversations with synthesized voices and professional audio production.

## Features

- Convert text content into natural conversations
- Multiple speaker personas with distinct voices and personalities
- High-quality text-to-speech synthesis
- Professional audio post-processing
- Extensible plugin architecture

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

