#!/usr/bin/env python3
"""
Fix for TTS engine initialization in Podgen.
This script patches the TTSService module to properly handle engine creation.
"""

import os
import sys
from pathlib import Path

def fix_tts_init():
    """Fix the TTS service initialization issue."""
    # Identify the base project directory
    if os.path.exists("src/podgen"):
        base_dir = Path(".")
    elif os.path.exists("../src/podgen"):
        base_dir = Path("..")
    else:
        print("ERROR: Cannot find Podgen source directory.")
        return False
    
    # Path to the file that needs to be fixed
    tts_init_path = base_dir / "src" / "podgen" / "services" / "tts" / "__init__.py"
    
    if not tts_init_path.exists():
        print(f"ERROR: Cannot find {tts_init_path}")
        return False
    
    # Read current content
    current_content = tts_init_path.read_text()
    
    # Create improved create_engine function
    new_create_engine = """
def create_engine(
    provider: TTSProvider,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    **kwargs
) -> Optional[TTSEngine]:
    """Create appropriate TTS engine based on provider."""
    if provider not in PROVIDER_MAP:
        return None
        
    engine_class = PROVIDER_MAP[provider]
    if not model_name and provider in DEFAULT_MODELS:
        model_name = DEFAULT_MODELS[provider]
        
    # Filter kwargs based on the engine class
    import inspect
    engine_params = inspect.signature(engine_class.__init__).parameters
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in engine_params}
    
    # Add API key for cloud services only
    if provider in [TTSProvider.ELEVENLABS, TTSProvider.OPENAI] and api_key:
        filtered_kwargs['api_key'] = api_key
        
    return engine_class(model_name=model_name, **filtered_kwargs)
"""
    
    # Replace the function in the content
    import re
    pattern = r"def create_engine\([^)]*\)[^:]*:[^#]+?return engine_class\([^)]*\)"
    if not re.search(pattern, current_content, re.DOTALL):
        print("WARNING: Could not find the create_engine function pattern.")
        # Fallback to simpler replacement
        old_func = "def create_engine("
        if old_func in current_content:
            start_idx = current_content.find(old_func)
            end_idx = current_content.find("__all__", start_idx)
            if end_idx > start_idx:
                # Find the last return statement before __all__
                last_return = current_content.rfind("return", start_idx, end_idx)
                if last_return > 0:
                    end_func_idx = current_content.find("\n\n", last_return)
                    if end_func_idx > 0:
                        new_content = current_content[:start_idx] + new_create_engine + current_content[end_func_idx:]
                        tts_init_path.write_text(new_content)
                        print(f"Applied simplified replacement to {tts_init_path}")
                        return True
    else:
        # Apply the regex replacement
        new_content = re.sub(pattern, new_create_engine.strip(), current_content, flags=re.DOTALL)
        tts_init_path.write_text(new_content)
        print(f"Fixed {tts_init_path}")
        return True
    
    print("ERROR: Could not apply the fix automatically.")
    return False

# Additionally, let's create a fix for the async_app.py file which calls the create_engine function
def fix_async_app():
    """Fix the TTS engine creation in AsyncApp."""
    if os.path.exists("src/podgen"):
        base_dir = Path(".")
    elif os.path.exists("../src/podgen"):
        base_dir = Path("..")
    else:
        print("ERROR: Cannot find Podgen source directory.")
        return False
    
    # Path to the file that needs to be fixed
    async_app_path = base_dir / "src" / "podgen" / "cli" / "async_app.py"
    
    if not async_app_path.exists():
        print(f"ERROR: Cannot find {async_app_path}")
        return False
    
    # Read current content
    current_content = async_app_path.read_text()
    
    # Find the tts engine creation and fix it
    old_code = """
                tts_engine = create_engine(
                    provider=self.model_config.tts_type,
                    model_name=self.model_config.tts_model,
                    api_key=self._get_tts_api_key()
                )
"""
    
    new_code = """
                # Create TTS engine with proper parameters
                tts_engine = create_engine(
                    provider=self.model_config.tts_type,
                    model_name=self.model_config.tts_model,
                    api_key=self._get_tts_api_key(),
                    device=getattr(settings, 'device', 'cpu')
                )
"""
    
    if old_code.strip() in current_content:
        new_content = current_content.replace(old_code, new_code)
        async_app_path.write_text(new_content)
        print(f"Fixed {async_app_path}")
        return True
    else:
        print(f"WARNING: Could not find the exact code pattern in {async_app_path}")
        return False

def main():
    """Apply all fixes."""
    tts_fixed = fix_tts_init()
    app_fixed = fix_async_app()
    
    if tts_fixed or app_fixed:
        print("\nFixes applied successfully! Try running Podgen again.")
    else:
        print("\nCould not apply automatic fixes. Manual intervention may be required.")
        print("The error is in the TTS engine initialization - the 'api_key' parameter is being")
        print("passed to CoquiTTSEngine which doesn't accept it. You'll need to modify the")
        print("create_engine function to filter parameters based on the engine type.")

if __name__ == "__main__":
    main()
