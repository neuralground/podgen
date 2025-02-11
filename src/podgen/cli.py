import typer
from pathlib import Path
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt, Confirm
from rich.table import Table
from .models.conversation_style import ConversationStyle, SpeakerPersonality
from .models.conversation_config import ConversationConfig
from .services.llm_service import LLMService
from .services.tts import TTSService
from .services.audio import AudioProcessor
from .storage.json_storage import JSONStorage
from . import config

app = typer.Typer()
console = Console()
storage = JSONStorage(Path(config.settings.data_dir))

DEFAULT_CONFIG = ConversationConfig(
    style=ConversationStyle.CASUAL,
    num_speakers=2,
    speakers=[
        SpeakerPersonality(
            name="Host",
            voice_id="p335",
            gender="neutral",
            style="Engaging and friendly host",
            verbosity=1.0,
            formality=0.8
        ),
        SpeakerPersonality(
            name="Guest",
            voice_id="p347",
            gender="neutral",
            style="Knowledgeable guest",
            verbosity=1.0,
            formality=1.0
        )
    ]
)

def handle_command(cmd: str) -> None:
    """Handle CLI commands starting with /"""
    parts = cmd[1:].split()
    command = parts[0]
    args = parts[1:]
    
    if command == "speakers":
        if not args:
            # List speakers
            speakers = storage.list_speakers()
            table = Table("Name", "Gender", "Style")
            for name in speakers:
                speaker = storage.get_speaker(name)
                if speaker:
                    table.add_row(name, speaker.gender, speaker.style)
            console.print(table)
        elif args[0] == "new":
            # Create new speaker
            name = Prompt.ask("Speaker name")
            gender = Prompt.ask("Gender", choices=["male", "female", "neutral"])
            voice_id = Prompt.ask("Voice ID")
            style = Prompt.ask("Speaking style")
            verbosity = float(Prompt.ask("Verbosity (0.1-2.0)", default="1.0"))
            formality = float(Prompt.ask("Formality (0.1-2.0)", default="1.0"))
            
            speaker = SpeakerPersonality(
                name=name,
                voice_id=voice_id,
                gender=gender,
                style=style,
                verbosity=verbosity,
                formality=formality
            )
            storage.save_speaker(name, speaker)
            console.print(f"[green]Created speaker profile: {name}")
        elif args[0] == "delete":
            if len(args) < 2:
                console.print("[red]Please specify speaker name")
                return
            if storage.delete_speaker(args[1]):
                console.print(f"[green]Deleted speaker: {args[1]}")
            else:
                console.print(f"[red]Speaker not found: {args[1]}")
    
    elif command == "formats":
        if not args:
            # List formats
            formats = storage.list_formats()
            table = Table("Name", "Style", "Speakers")
            for name in formats:
                fmt = storage.get_format(name)
                if fmt:
                    table.add_row(name, fmt.style.value, str(fmt.num_speakers))
            console.print(table)
        elif args[0] == "new":
            # Create new format
            name = Prompt.ask("Format name")
            style = Prompt.ask(
                "Style",
                choices=[s.value for s in ConversationStyle]
            )
            num_speakers = int(Prompt.ask("Number of speakers", default="2"))
            
            # Select speakers
            speakers = []
            available_speakers = storage.list_speakers()
            for i in range(num_speakers):
                speaker_name = Prompt.ask(
                    f"Speaker {i+1}",
                    choices=available_speakers
                )
                speaker = storage.get_speaker(speaker_name)
                if speaker:
                    speakers.append(speaker)
            
            config = ConversationConfig(
                style=ConversationStyle(style),
                num_speakers=num_speakers,
                speakers=speakers
            )
            storage.save_format(name, config)
            console.print(f"[green]Created conversation format: {name}")
        elif args[0] == "delete":
            if len(args) < 2:
                console.print("[red]Please specify format name")
                return
            if storage.delete_format(args[1]):
                console.print(f"[green]Deleted format: {args[1]}")
            else:
                console.print(f"[red]Format not found: {args[1]}")
    
    else:
        console.print(f"[red]Unknown command: {command}")
        console.print("Available commands:")
        console.print("  /speakers - List speaker profiles")
        console.print("  /speakers new - Create new speaker profile")
        console.print("  /speakers delete <name> - Delete speaker profile")
        console.print("  /formats - List conversation formats")
        console.print("  /formats new - Create new conversation format")
        console.print("  /formats delete <name> - Delete conversation format")

@app.command()
def main(
    input_text: Optional[str] = typer.Argument(None, help="Input text (optional)"),
    format: Optional[str] = typer.Option(None, help="Named conversation format"),
    output_dir: Path = typer.Option(
        Path("output"),
        help="Directory for output files"
    ),
):
    """Interactive podcast generator."""
    try:
        # Initialize services
        llm = LLMService(config.settings.openai_api_key)
        tts = TTSService()
        audio = AudioProcessor()
        
        # Get conversation config
        conv_config = DEFAULT_CONFIG
        if format:
            stored_format = storage.get_format(format)
            if stored_format:
                conv_config = stored_format
            else:
                console.print(f"[red]Format not found: {format}")
                return
        
        # Store input text from command line
        current_text = input_text
        
        while True:
            # Get input text
            if current_text:
                text_to_process = current_text
                current_text = None  # Clear for next iteration
            else:
                text_to_process = Prompt.ask("\nEnter text to convert (or /command)")
                if text_to_process.startswith("/"):
                    handle_command(text_to_process)
                    continue
                if not text_to_process:
                    break
            
            # Generate and process
            with console.status("Generating conversation..."):
                dialogue = llm.generate_conversation(
                    text_to_process,
                    conv_config
                )
            
            # Synthesize speech
            audio_files = []
            with console.status("Synthesizing speech..."):
                for i, turn in enumerate(dialogue.turns):
                    output_file = output_dir / f"turn_{i}.wav"
                    audio_file = tts.synthesize_turn(turn, output_file)
                    audio_files.append(audio_file)
            
            # Combine audio
            with console.status("Creating final audio..."):
                final_output = output_dir / "podcast.wav"
                audio.combine_audio_files(audio_files, final_output)
            
            console.print(
                f"[green]Generated podcast saved to: {final_output}"
            )
            
            if input_text:  # If we started with command line text, exit
                break
    
    except Exception as e:
        console.print(f"[red]Error: {str(e)}")
        raise typer.Exit(1)

if __name__ == "__main__":
    app()

