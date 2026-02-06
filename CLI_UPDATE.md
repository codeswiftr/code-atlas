# Code Atlas CLI JSON Standardization

## Summary

Updated the `code-atlas` CLI to conform to the FORGE standard JSON response schema.

## Standard Schema

**Success Response:**
```json
{
  "success": true,
  "result": { /* command-specific data */ },
  "timestamp": "2026-02-06T04:30:00.000000Z",
  "duration_ms": 150,
  "metadata": {
    "version": "0.1.0"
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message"
  },
  "timestamp": "2026-02-06T04:30:00.000000Z"
}
```

## Changes Implemented

1. Added `time` import for duration tracking
2. Added `VERSION = "0.1.0"` constant
3. Updated `output_success()` and `output_error()` helpers to FORGE standard
4. All commands need `start_time = time.time()` tracking

## Files Modified

- `/Users/bogdan/work/FORGE/codeswiftr-com/code-atlas/backend/src/code_atlas/cli.py`
  - Lines 1-112: Updated helper functions
  - Commands require individual updates for timing

## Next Steps

Each command needs:
1. Add `start_time = time.time()` at function start
2. Update `output_success()` calls
3. Update `output_error()` calls
4. Test with `--json` flag
