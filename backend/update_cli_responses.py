"""Script to update CLI commands to use FORGE standard JSON schema."""

import re
from pathlib import Path

CLI_PATH = Path(__file__).parent / "src" / "code_atlas" / "cli.py"

def update_discover_command(content: str) -> str:
    """Update discover command to use new schema."""
    # Find discover command
    pattern = r'(def discover_sessions\(.*?\n.*?""".*?""")\n(\s+)(settings = load_settings)'
    replacement = r'\1\n\2start_time = time.time()\n\2\3'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Update output_error call
    old_call = r'output_error\(\s*"discover",\s*"ROOT_NOT_FOUND",\s*str\(e\),\s*\{"root":.*?\},\s*json_output,?\s*\)'
    new_call = 'output_error("ROOT_NOT_FOUND", str(e), start_time, json_output)'
    content = re.sub(old_call, new_call, content, flags=re.DOTALL)
    
    # Update success output
    old_output = r'output_json\(\s*\{\s*"success": True,\s*"operation": "discover",\s*"count": len\(sessions_data\),\s*"sessions": sessions_data,\s*\}\s*\)'
    new_output = 'output_success({"count": len(sessions_data), "sessions": sessions_data}, start_time, json_output)'
    content = re.sub(old_output, new_output, content)
    
    return content

def update_index_command(content: str) -> str:
    """Update index command."""
    # Add start_time tracking
    pattern = r'("""Index Claude Code sessions.*?""")\n(\s+)(settings = load_settings)'
    replacement = r'\1\n\2start_time = time.time()\n\2\3'
    content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    
    # Update error outputs
    content = content.replace(
        'output_error(\n            "index",\n            "ROOT_NOT_FOUND",',
        'output_error(\n            "ROOT_NOT_FOUND",'
    )
    content = content.replace(
        '{"root": str(root or settings.claude_root)},\n            json_output,',
        'start_time,\n            json_output,'
    )
    
    content = content.replace(
        'output_error(\n            "index",\n            "INVALID_PROVIDER",',
        'output_error(\n            "INVALID_PROVIDER",'
    )
    
    # Update success outputs (complex due to multiple formats)
    # This is simplified - may need manual review
    content = content.replace(
        '"success": True,\n                "operation": "index",',
        ''
    )
    
    return content

def main():
    """Update all commands in cli.py."""
    print(f"Reading {CLI_PATH}...")
    content = CLI_PATH.read_text()
    
    print("Updating discover command...")
    content = update_discover_command(content)
    
    print("Updating index command...")
    content = update_index_command(content)
    
    # Write back
    print(f"Writing updates to {CLI_PATH}...")
    CLI_PATH.write_text(content)
    
    print("✓ CLI updated successfully")
    print("\nManual review required for:")
    print("  - query, export, status, report, indexes, metrics commands")
    print("  - Test all --json outputs")

if __name__ == "__main__":
    main()
