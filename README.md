# Simpad

Simpad is a small and practical tool for working with Python scripts. It is meant to be simple: open a file, edit it, and run it without extra setup.

## What it does

- Open and edit text files
- Create and edit Python scripts
- Add basic Python syntax highlighting
- Run Python code from the editor
- Save files with a simple interface

## Requirements

- Python 3.10+
- Tkinter

## Run from source

```bash
python simpad.py
```

## Build standalone files

### Linux

```bash
./build_app.sh
```

This creates a single executable file at:

```bash
dist/simpad-linux
```

### Windows

Run this on Windows:

```cmd
build_app.cmd
```

This creates a single executable file at:

```cmd
dist-win\simpad-win.exe
```

## Notes

The app keeps its settings in a local config file. When packaged as a standalone app, it uses a user-writable location so settings can still be saved.
