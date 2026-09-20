# Clipboard Manager

A searchable history of everything you have copied, recallable without leaving the keyboard.

Windows keeps one clipboard slot, so copying anything destroys what was there before. This watches the
clipboard from the tray and keeps the last 500 text clips in a local SQLite database, so an overwrite
is no longer a loss.

## How it works

- Polls the clipboard from a background thread and writes new text to `history.db` (SQLite).
- History is **capped at 500 entries and deduplicated** — recopying the same text bumps the existing
  row to the top rather than inserting a duplicate.
- **`Ctrl+Alt+Shift+V`** opens a small popup listing recent clips. Type to filter, Enter or
  double-click to copy one back.

## Notes from building it

- **Dedup is exact-text-match.** The same text with one stray leading space counts as a separate
  entry. Known, not fixed — it is visible in real history data.
- The popup originally rebuilt every row on each hover and arrow-key move, which flickered visibly.
  Fixed by restyling only the row that changed.
- `history.db` holds whatever you copied, which can include passwords pasted from a manager. It is
  gitignored, and it is worth knowing the file exists before pointing any backup tool at this folder.

**Stack:** Python, Tkinter, SQLite, `keyboard`, `pystray`, Pillow.

## Part of a suite

One of seven small Windows tray utilities built as separate, self-contained apps: each has its own
folder, its own virtualenv and its own `run.bat`, with no shared runtime. They are deliberately not a
framework — the only thing they share is a set of conventions.

| Convention | Why |
|---|---|
| Single-instance guard via a `.singleton.lock` file | An earlier `.instance.lock` design could get stuck after a force-kill and leave the app permanently unlaunchable |
| Relaunch brings the existing window forward | Previously a second launch silently did nothing, which was indistinguishable from the app being broken |
| Config lives in `config.json`, read at startup | Edit it, then fully exit the tray icon and relaunch — a running process never re-reads it |
| Tray icon generated in code (`icon.py`) | No binary asset to keep in sync |

## Running it

```
run.bat
```

That creates the virtualenv on first run, installs `requirements.txt`, and starts the app. Windows
only — these use Win32 APIs and a system tray.

## License

MIT — see [LICENSE](LICENSE).
