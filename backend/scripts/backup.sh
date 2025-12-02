#!/usr/bin/env bash
#
# backup.sh - Backup script for Code Atlas databases
#
# Creates timestamped backups of:
# - SQLite databases (jobs.db, api_keys.db)
# - FalkorDB data (optional RDB dump)
#
# Usage: ./backup.sh [OPTIONS]
#

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data}"
BACKUP_DIR="${BACKUP_DIR:-$PROJECT_ROOT/backups}"
KEEP_BACKUPS="${KEEP_BACKUPS:-7}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"
INCLUDE_FALKORDB="${INCLUDE_FALKORDB:-false}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Timestamp for backup files
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_SUBDIR="$BACKUP_DIR/backup_$TIMESTAMP"

# Logging functions
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Show help
show_help() {
    cat <<EOF
Usage: backup.sh [OPTIONS]

Backup script for Code Atlas databases.

OPTIONS:
    --output-dir DIR    Backup output directory (default: ./backups)
    --keep N            Number of backups to keep (default: 7)
    --include-falkordb  Include FalkorDB RDB dump
    --data-dir DIR      Data directory containing SQLite databases
    --help              Show this help message

ENVIRONMENT VARIABLES:
    DATA_DIR            Data directory (default: ./data)
    BACKUP_DIR          Backup directory (default: ./backups)
    KEEP_BACKUPS        Number of backups to retain (default: 7)
    REDIS_HOST          FalkorDB host (default: localhost)
    REDIS_PORT          FalkorDB port (default: 6379)

EXAMPLES:
    # Basic backup
    ./backup.sh

    # Keep last 14 backups
    ./backup.sh --keep 14

    # Include FalkorDB dump
    ./backup.sh --include-falkordb

    # Custom output directory
    ./backup.sh --output-dir /mnt/backups

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --output-dir)
            BACKUP_DIR="$2"
            BACKUP_SUBDIR="$BACKUP_DIR/backup_$TIMESTAMP"
            shift 2
            ;;
        --keep)
            KEEP_BACKUPS="$2"
            shift 2
            ;;
        --include-falkordb)
            INCLUDE_FALKORDB=true
            shift
            ;;
        --data-dir)
            DATA_DIR="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Create backup directory
create_backup_dir() {
    log_info "Creating backup directory: $BACKUP_SUBDIR"
    mkdir -p "$BACKUP_SUBDIR"
}

# Backup SQLite databases
backup_sqlite() {
    log_info "Backing up SQLite databases..."

    local db_files=("jobs.db" "api_keys.db")
    local backed_up=0

    for db_file in "${db_files[@]}"; do
        local src="$DATA_DIR/$db_file"
        local dst="$BACKUP_SUBDIR/$db_file"

        if [[ -f "$src" ]]; then
            # Use SQLite backup command for consistency
            if command -v sqlite3 &> /dev/null; then
                sqlite3 "$src" ".backup '$dst'"
                log_info "  ✓ Backed up $db_file"
                ((backed_up++))
            else
                # Fallback to cp if sqlite3 not available
                cp "$src" "$dst"
                log_warn "  ⚠ Copied $db_file (sqlite3 not available for consistent backup)"
                ((backed_up++))
            fi
        else
            log_warn "  ⚠ Database not found: $db_file"
        fi
    done

    if [[ $backed_up -eq 0 ]]; then
        log_warn "No SQLite databases were backed up"
    else
        log_info "Backed up $backed_up SQLite database(s)"
    fi
}

# Backup FalkorDB
backup_falkordb() {
    if [[ "$INCLUDE_FALKORDB" != "true" ]]; then
        return
    fi

    log_info "Backing up FalkorDB..."

    if ! command -v redis-cli &> /dev/null; then
        log_error "redis-cli not found, skipping FalkorDB backup"
        return 1
    fi

    # Trigger BGSAVE and wait for completion
    log_info "  Triggering FalkorDB BGSAVE..."
    redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" BGSAVE &> /dev/null || {
        log_error "Failed to trigger BGSAVE"
        return 1
    }

    # Wait for BGSAVE to complete
    local max_wait=60
    local waited=0
    while [[ $waited -lt $max_wait ]]; do
        local lastsave_before
        local lastsave_after

        lastsave_before=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE 2>/dev/null || echo "0")
        sleep 1
        lastsave_after=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" LASTSAVE 2>/dev/null || echo "0")

        if [[ "$lastsave_before" == "$lastsave_after" ]] && [[ $waited -gt 2 ]]; then
            break
        fi

        ((waited++))
    done

    # Get RDB file location and copy
    local rdb_dir
    rdb_dir=$(redis-cli -h "$REDIS_HOST" -p "$REDIS_PORT" CONFIG GET dir 2>/dev/null | tail -1)

    if [[ -n "$rdb_dir" ]] && [[ -f "$rdb_dir/dump.rdb" ]]; then
        cp "$rdb_dir/dump.rdb" "$BACKUP_SUBDIR/falkordb_dump.rdb"
        log_info "  ✓ Backed up FalkorDB RDB dump"
    else
        log_warn "  ⚠ Could not locate FalkorDB RDB file"
    fi
}

# Create backup manifest
create_manifest() {
    log_info "Creating backup manifest..."

    local manifest="$BACKUP_SUBDIR/manifest.json"
    local files_count
    files_count=$(find "$BACKUP_SUBDIR" -type f | wc -l)

    cat > "$manifest" <<EOF
{
  "timestamp": "$TIMESTAMP",
  "created_at": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "source": {
    "data_dir": "$DATA_DIR",
    "hostname": "$(hostname)"
  },
  "files": {
    "count": $files_count,
    "sqlite": $(ls -1 "$BACKUP_SUBDIR"/*.db 2>/dev/null | wc -l || echo 0),
    "falkordb": $(ls -1 "$BACKUP_SUBDIR"/*.rdb 2>/dev/null | wc -l || echo 0)
  }
}
EOF

    log_info "  ✓ Created manifest.json"
}

# Compress backup
compress_backup() {
    log_info "Compressing backup..."

    local archive="$BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
    tar -czf "$archive" -C "$BACKUP_DIR" "backup_$TIMESTAMP"

    # Remove uncompressed directory
    rm -rf "$BACKUP_SUBDIR"

    local size
    size=$(du -h "$archive" | cut -f1)
    log_info "  ✓ Created archive: $archive ($size)"
}

# Rotate old backups
rotate_backups() {
    log_info "Rotating old backups (keeping last $KEEP_BACKUPS)..."

    local backup_count
    backup_count=$(find "$BACKUP_DIR" -maxdepth 1 -name "backup_*.tar.gz" -type f | wc -l)

    if [[ $backup_count -gt $KEEP_BACKUPS ]]; then
        local to_delete=$((backup_count - KEEP_BACKUPS))
        log_info "  Removing $to_delete old backup(s)..."

        find "$BACKUP_DIR" -maxdepth 1 -name "backup_*.tar.gz" -type f -printf '%T@ %p\n' | \
            sort -n | head -n "$to_delete" | cut -d' ' -f2- | \
            xargs -r rm -f

        log_info "  ✓ Removed $to_delete old backup(s)"
    else
        log_info "  No rotation needed ($backup_count backups exist)"
    fi
}

# Main execution
main() {
    log_info "=== Code Atlas Backup ==="
    log_info "Timestamp: $TIMESTAMP"
    log_info ""

    # Validate data directory
    if [[ ! -d "$DATA_DIR" ]]; then
        log_error "Data directory not found: $DATA_DIR"
        exit 1
    fi

    create_backup_dir
    backup_sqlite
    backup_falkordb
    create_manifest
    compress_backup
    rotate_backups

    log_info ""
    log_info "=== Backup Complete ==="
    log_info "Location: $BACKUP_DIR/backup_$TIMESTAMP.tar.gz"
}

main
