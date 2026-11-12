# Conversation archive imports

Conversation imports are optional and disabled by default. The Website Template does
not collect conversations from AI services. A project owner exports a conversation and
explicitly imports that file when `features.conversation_logging` is `true` in
`config/site.json`.

```powershell
python tools/core/import_conversation.py --root . --source PATH_TO_EXPORT
```

Supported formats are `.md`, `.txt`, `.json`, and `.jsonl`. The importer copies the
file bytes unchanged, leaves the source in place, records its SHA-256 in the imported
filename, and skips content already present by hash. The archive path is configured
as `paths.conversation_archive`; the default is `AI/history/conversations`. The path
must remain inside the project. It is ignored by Git as user-owned history.

Existing provider-specific archives and fixed consumer archive roots remain untouched.
This tool does not discover, move, rename, or migrate existing archives. Conversation
transcripts are provenance, not decision records; durable human reasons belong in
`WHY.md`, and adopted behavior belongs in `SPEC.md`.

Exit codes: `0` imported/already present, `2` blocked input or unsafe configuration,
`3` unexpected failure, and `4` imports disabled.
