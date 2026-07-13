# Simpad

Simpad is a simple single-file Python text and Python editor with a small built-in toolbar, tabbed editing, syntax highlighting for Python, and a run output panel.

## Features

- Create and edit text files
- Create and edit Python scripts
- Python syntax highlighting
- Run Python code from the editor
- Save/load files with a simple interface
- Packaged as a single-file application for Linux and Windows

## Requirements

- Python 3.10+
- Tkinter (usually bundled with Python on most systems)

## Run from source

```bash
python simpad.py
```

## Build standalone executables

### Linux

```bash
./build_app.sh
```

This creates a single executable at:

```bash
dist/simpad-linux
```

### Windows

Run the batch script on Windows:

```cmd
build_app.cmd
```

This creates a single executable at:

```cmd
dist-win\simpad-win.exe
```

## Notes

The application stores its configuration in a local config file. When packaged as a standalone app, it uses a user-writable config location so settings can still be saved.
