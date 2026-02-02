# Driver Template and Checklist

Use `drivers/_template.py` as a starting point. Copy the file, rename it, and keep
only the interface you need.

Checklist:
- Implement the required interface methods.
- Add a `PROBE_PRIORITY` and `@classmethod probe(config)` if you want auto-detect.
- Keep `connect()` and `disconnect()` safe and idempotent.
- Expose `connected` when possible (used by the UI and coordinator).

Auto-detect notes:
- `probe(config)` should be fast and non-destructive.
- For serial devices, you can optionally add `probe_port(port, config)` to test a port.
