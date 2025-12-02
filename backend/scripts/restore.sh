#!/usr/bin/env bash
#
# restore.sh - Restore script for Code Atlas databases
#
# Restores from backup archives created by backup.sh
#
# Usage: ./restore.sh BACKUP_FILE [OPTIONS]
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"
RESTORE_FALKORDB="${RESTORE_FALKORDB:-false}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
DRY_RUN="${DRY_RUN:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Show help
show_help() {
    cat <<EOF
Usage: restore.sh BACKUP_FILE [OPTIONS]

Restore Code Atlas databases from a backup archive.

ARGUMENTS:
    BACKUP_FILE         Path to backup archive (.tar.gz)

OPTIONS:
    --data-dir DIR      Target data directory (default: ./data)
    --include-falkordb  Also restore FalkorDB RDB dump
    --dry-run           Show what would be restored without doing it
    --force             Skip confirmation prompt
    --help              Show this help message

ENVIRONMENT VARIABLES:
    DATA_DIR            Target data directory (default: ./data)
    REDIS_HOST          FalkorDB host (default: localhost)
    REDIS_PORT          FalkorDB port (default: 6379)

EXAMPLES:
    # Basic restore
    ./restore.sh backups/backup_20240101_120000.tar.gz

    # Restore with FalkorDB
    ./restore.sh backup.tar.gz --include-falkordb

    # Preview restore without making changes
    ./restore.sh backup.tar.gz --dry-run

    # Force restore without confirmation
    ./restore.sh backup.tar.gz --force

EOF
}

# Variables
BACKUP_FILE=""
FORCE=false

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --include-falkordb)
            RESTORE_FALKORDB=true
            shift
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --help)
            show_help
            exit 0
            ;;
        -*)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
        *)
            if [[ -z "$BACKUP_FILE" ]]; then
                BACKUP_FILE="$1"
            else
                log_error "Unexpected argument: $1"
                show_help
                exit 1
            fi
            shift
            ;;
    esac
done

# Validate backup file
validate_backup() {
    if [[ -z "$BACKUP_FILE" ]]; then
        log_error "No backup file specified"
        show_help
        exit 1
    fi

    if [[ ! -f "$BACKUP_FILE" ]]; then
        log_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi

    if [[ ! "$BACKUP_FILE" =~ \.tar\.gz$ ]]; then
        log_error "Backup file must be a .tar.gz archive"
        exit 1
    fi

    log_info "Backup file: $BACKUP_FILE"
}

# Extract and validate backup contents
validate_contents() {
    log_info "Validating backup contents..."

    # Create temp directory for extraction
    TEMP_DIR=$(mktemp -d)
    trap 'rm -rf "$TEMP_DIR"' EXIT

    # Extract archive
    tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

    # Find the backup subdirectory
    BACKUP_SUBDIR=$(find "$TEMP_DIR" -maxdepth 1 -type d -name "backup_*" | head -1)

    if [[ -z "$BACKUP_SUBDIR" ]]; then
        log_error "Invalid backup archive: no backup directory found"
        exit 1
    fi

    # Check for manifest
    if [[ -f "$BACKUP_SUBDIR/manifest.json" ]]; then
        log_info "  ✓ Found manifest.json"
        if command -v jq &> /dev/null; then
            local created_at
            created_at=$(jq -r '.created_at' "$BACKUP_SUBDIR/manifest.json")
            log_info "  Backup created: $created_at"
        fi
    else
        log_warn "  ⚠ No manifest.json found"
    fi

    # List contents
    log_info "  Contents:"
    local db_count=0
    local rdb_count=0

    for file in "$BACKUP_SUBDIR"/*; do
        local filename
        filename=$(basename "$file")
        local size
        size=$(du -h "$file" | cut -f1)

        if [[ "$filename" == *.db ]]; then
            log_info "    - $filename ($size)"
            ((db_count++))
        elif [[ "$filename" == *.rdb ]]; then
            log_info "    - $filename ($size)"
            ((rdb_count++))
        fi
    done

    log_info "  Found: $db_count SQLite database(s), $rdb_count FalkorDB dump(s)"

    # Warn if FalkorDB dump exists but not restoring
    if [[ $rdb_count -gt 0 ]] && [[ "$RESTORE_FALKORDB" != "true" ]]; then
        log_warn "  FalkorDB dump found but --include-falkordb not specified"
    fi
}

# Confirm restore
confirm_restore() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info ""
        log_info "[DRY RUN] Would restore to: $DATA_DIR"
        log_info "[DRY RUN] No changes made"
        exit 0
    fi

    if [[ "$FORCE" != "true" ]]; then
        log_warn ""
        log_warn "This will overwrite existing databases in: $DATA_DIR"
        read -p "Continue? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Restore cancelled"
            exit 0
        fi
    fi
}

# Restore SQLite databases
restore_sqlite() {
    log_info "Restoring SQLite databases..."

    # Create data directory if it doesn't exist
    mkdir -p "$DATA_DIR"

    local restored=0
    for db_file in "$BACKUP_SUBDIR"/*.db; do
        if [[ -f "$db_file" ]]; then
            local filename
            filename=$(basename "$db_file")
            local target="$DATA_DIR/$filename"

            # Backup existing file
            if [[ -f "$target" ]]; then
                mv "$target" "$target.bak"
                log_info "  Backed up existing $filename"
            fi

            # Copy restored file
            cp "$db_file" "$target"
            log_info "  ✓ Restored $filename"
            ((restored++))
        fi
    done

    log_info "Restored $restored SQLite database(s)"
}

# Restore FalkorDB
restore_falkordb() {
    if [[ "$RESTORE_FALKORDB" != "true" ]]; then
        return
    fi

    local rdb_file="$BACKUP_SUBDIR/falkordb_dump.rdb"

    if [[ ! -f "$rdb_file" ]]; then
        log_warn "No FalkorDB dump found in backup"
        return
    fi

    log_info "Restoring FalkorDB..."

    if ! command -v redis-cli &> /dev/null; then
        log_error "redis-cli not found, cannot restore FalkorDB"
        return 1
    fi

    # Get FalkorDB data directory
    local rdb_dir
    rdb_dir=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" CONFIG GET dir 2>/dev/null | tail -1)

    if [[ -z "$rdb_dir" ]]; then
        log_error "Could not determine FalkorDB data directory"
        return 1
    fi

    log_warn "FalkorDB restore requires manual steps:"
    log_warn "  1. Stop FalkorDB service"
    log_warn "  2. Copy $rdb_file to $rdb_dir/dump.rdb"
    log_warn "  3. Start FalkorDB service"
    log_info ""
    log_info "Or run these commands:"
    log_info "  docker compose stop falkordb"
    log_info "  cp $rdb_file $rdb_dir/dump.rdb"
    log_info "  docker compose start falkordb"
}

# Main execution
main() {
    log_info "=== Code Atlas Restore ==="
    log_info ""

    validate_backup
    validate_contents
    confirm_restore
    restore_sqlite
    restore_falkordb

    log_info ""
    log_info "=== Restore Complete ==="
}

main
