import tkinter as tk
from tkinter import filedialog, messagebox, ttk, colorchooser
import json
import subprocess
import sys
import os
import shutil
import tempfile

# =============================================================================
# Load Config
# =============================================================================
def get_app_base_dir():
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def get_config_path():
    if getattr(sys, "frozen", False):
        if os.name == "nt":
            config_dir = os.environ.get("APPDATA")
        else:
            config_dir = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
        if config_dir:
            user_config_dir = os.path.join(config_dir, "simpad")
            os.makedirs(user_config_dir, exist_ok=True)
            return os.path.join(user_config_dir, "config.json")
    return os.path.join(get_app_base_dir(), "config.json")


CONFIG_PATH = get_config_path()


def load_config():
    if not os.path.exists(CONFIG_PATH):
        bundled_config = os.path.join(get_app_base_dir(), "config.json")
        if bundled_config != CONFIG_PATH and os.path.exists(bundled_config):
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            shutil.copyfile(bundled_config, CONFIG_PATH)
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config(data):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


config = load_config()
theme = config["theme"]

# =============================================================================
# Main Window
# =============================================================================
root = tk.Tk()
root.title(config["window"]["title"])
root.geometry(f"{config['window']['width']}x{config['window']['height']}")
root.minsize(config["window"]["min_width"], config["window"]["min_height"])
root.configure(bg=theme["background_color"])

style = ttk.Style()
style.theme_use("clam")

# =============================================================================
# Helpers
# =============================================================================
import tkinter.font as tkfont


def _validate_font(family):
    """Ensure the font family exists on the system, fallback to 'monospace'."""
    available = set(tkfont.families())
    if family in available:
        return family
    # Try common fallbacks
    for fallback in ["DejaVu Sans Mono", "Courier", "monospace", "TkFixedFont"]:
        if fallback in available:
            return fallback
    return "TkFixedFont"


def get_font():
    family = _validate_font(config["font"]["family"])
    return (family, config["font"]["size"])


def get_editor_cfg():
    return config.get("editor", {"tab_size": 4, "word_wrap": True, "show_line_numbers": True})


# =============================================================================
# Toolbar
# =============================================================================
toolbar = tk.Frame(root, bg=theme["toolbar_bg"], height=40, bd=0, highlightthickness=0)
toolbar.pack(fill="x", side="top")
toolbar.pack_propagate(False)

toolbar_border = tk.Frame(root, bg=theme["toolbar_border"], height=1)
toolbar_border.pack(fill="x", side="top")


def toolbar_button(text, cmd, tip=""):
    btn = tk.Button(
        toolbar, text=text, command=cmd,
        bg=theme["toolbar_bg"], fg=theme["toolbar_fg"],
        activebackground=theme["toolbar_hover_bg"],
        activeforeground=theme["toolbar_fg"],
        relief="flat", font=("DejaVu Sans", 10, "bold"),
        padx=10, pady=3, cursor="hand2", borderwidth=0
    )
    btn.pack(side="left", padx=1, pady=4)
    return btn


def toolbar_sep():
    tk.Frame(toolbar, bg=theme["toolbar_border"], width=2, height=26).pack(side="left", padx=6, pady=6)


# Toolbar items
toolbar_button("New", lambda: new_text_tab(), "New Text File")
toolbar_button("Open", lambda: open_file(), "Open File")
toolbar_button("Save", lambda: save_file(), "Save File")
toolbar_sep()
toolbar_button("Python", lambda: new_python_tab(), "New Python Tab")
toolbar_button("Run", lambda: run_python(), "Run Python (Ctrl+R)")
toolbar_sep()
toolbar_button("Settings", lambda: switch_to_settings(), "Settings")

# App label
tk.Label(toolbar, text="  Simpad  ", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"],
         font=("DejaVu Sans", 10, "bold")).pack(side="right", padx=10)

# =============================================================================
# Main Notebook
# =============================================================================
main_nb = ttk.Notebook(root)
main_nb.pack(fill="both", expand=True)

style.configure("TNotebook", background=theme["notebook_bg"], borderwidth=0)
style.configure("TNotebook.Tab",
                background=theme["tab_bg"], foreground=theme["tab_fg"],
                padding=[14, 5], font=("DejaVu Sans", 9))
style.map("TNotebook.Tab",
          background=[("selected", theme["tab_selected_bg"])],
          foreground=[("selected", theme["tab_selected_fg"])])

# -- Frames --
text_editor_frame = tk.Frame(main_nb, bg=theme["background_color"])
main_nb.add(text_editor_frame, text="  Text Editor  ")

python_editor_frame = tk.Frame(main_nb, bg=theme["background_color"])
main_nb.add(python_editor_frame, text="  Python Editor  ")

settings_frame = tk.Frame(main_nb, bg=theme["settings_bg"])
main_nb.add(settings_frame, text="  Settings  ")

# Sub-notebooks
text_sub_nb = ttk.Notebook(text_editor_frame)
text_sub_nb.pack(fill="both", expand=True)

python_sub_nb = ttk.Notebook(python_editor_frame)
python_sub_nb.pack(fill="both", expand=True)

# =============================================================================
# State
# =============================================================================
text_tabs = []      # [{frame, text, scroll, file_path, label}]
python_tabs = []    # [{frame, text, scroll, output, file_path, label}]
tab_counter = {"text": 0, "python": 0}


# =============================================================================
# VSCode Dark+ Syntax Highlighting for Python
# =============================================================================
import re as _re

# Token patterns (order matters: longer/more specific first)
PY_TOKENS = [
    # Triple-quoted strings (multiline)
    (r"'''(?:[^'\\]|\\.)*?'''", "string"),
    (r'"""(?:[^"\\]|\\.)*?"""', "string"),
    # Decorators
    (r"@\w+(?:\.\w+)*", "decorator"),
    # Comments
    (r"#.*$", "comment"),
    # Single-quoted f/b/u/r strings
    (r"[fFbBuU]?'(?:[^'\\]|\\.)*'", "string"),
    (r'[fFbBuU]?"(?:[^"\\]|\\.)*"', "string"),
    # Numbers
    (r"\b0[xX][0-9a-fA-F]+", "number"),
    (r"\b0[bB][01]+", "number"),
    (r"\b0[oO][0-7]+", "number"),
    (r"\b\d+\.?\d*(?:[eE][+-]?\d+)?[jJ]?\b", "number"),
    # Python keywords
    (r"\b(?:False|None|True|and|as|assert|async|await|break|"
     r"class|continue|def|del|elif|else|except|finally|for|from|"
     r"global|if|import|in|is|lambda|nonlocal|not|or|pass|raise|"
     r"return|try|while|with|yield)\b", "keyword"),
    # Built-in functions
    (r"\b(?:print|len|range|int|str|float|list|dict|set|tuple|bool|"
     r"type|isinstance|hasattr|getattr|setattr|delattr|super|object|"
     r"input|open|close|read|write|append|extend|pop|remove|insert|"
     r"keys|values|items|update|enumerate|zip|map|filter|sorted|reversed|"
     r"min|max|sum|abs|round|ord|chr|hex|oct|bin|id|dir|vars|locals|globals|"
     r"format|join|split|replace|strip|startswith|endswith|find|index|count|"
     r"upper|lower|capitalize|title|swapcase|isalpha|isdigit|isalnum|isspace|"
     r"__init__|__name__|__main__|__file__|__str__|__repr__|__len__|self|"
     r"Exception|ValueError|TypeError|KeyError|IndexError|"
     r"FileNotFoundError|OSError|IOError|RuntimeError|ImportError|"
     r"AttributeError|StopIteration|NotImplementedError)\b", "builtin"),
    # Function/class names (after def/class keyword)
    (r"(?<=\bdef\s)\w+", "function"),
    (r"(?<=\bclass\s)\w+", "classname"),
    # Self
    (r"\bself\b", "self"),
    # Operators
    (r"[+\-*/%<>=!&|^~@:]+", "operator"),
]

HIGHLIGHT_TAGS = {
    "keyword": "#569CD6",
    "string": "#CE9178",
    "comment": "#6A9955",
    "number": "#B5CEA8",
    "decorator": "#D7BA7D",
    "builtin": "#4FC1FF",
    "function": "#DCDCAA",
    "classname": "#4EC9B0",
    "self": "#9CDCFE",
    "operator": "#D4D4D4",
}


def syntax_highlight(text_widget):
    """Apply VSCode Dark+ syntax highlighting to a Python text widget."""
    # Setup tags if not already done
    for tag_name, color in HIGHLIGHT_TAGS.items():
        if tag_name not in text_widget.tag_names():
            text_widget.tag_configure(tag_name, foreground=color)

    content = text_widget.get("1.0", "end-1c")
    # Remove existing highlight tags
    for tag_name in HIGHLIGHT_TAGS:
        text_widget.tag_remove(tag_name, "1.0", "end")

    # Apply tokens by scanning line by line
    lines = content.split("\n")
    cursor = "1.0"
    for _i, line in enumerate(lines):
        # Track position within this line
        pos = 0
        line_len = len(line)
        while pos < line_len:
            for pattern, tag_name in PY_TOKENS:
                m = _re.match(pattern, line[pos:])
                if m:
                    start_idx = f"{cursor}+{pos}c"
                    end_idx = f"{cursor}+{pos + len(m.group())}c"
                    text_widget.tag_add(tag_name, start_idx, end_idx)
                    pos += len(m.group())
                    break
            else:
                pos += 1
        # Move cursor to next line
        cursor = f"{cursor}+1l lineend+1c"


def make_text_widget(parent, is_python=False):
    """Create (frame, text_widget, scrollbar) with line numbers and optional syntax highlighting."""
    frame = tk.Frame(parent, bg=theme["background_color"])
    editor_cfg = get_editor_cfg()
    show_lines = editor_cfg.get("show_line_numbers", True)

    if show_lines:
        ln = tk.Text(frame, width=4, padx=4, takefocus=0, border=0,
                     state="disabled", bg=theme["line_number_bg"],
                     fg=theme["line_number_fg"], font=get_font(), highlightthickness=0)
        ln.pack(side="left", fill="y")

    wrap = "word" if editor_cfg.get("word_wrap", True) else "none"
    text = tk.Text(frame, wrap=wrap, bg=theme["text_bg"], fg=theme["text_fg"],
                   insertbackground=theme["text_cursor"],
                   selectbackground=theme["text_selected_bg"],
                   font=get_font(), relief="flat", borderwidth=0,
                   padx=8, pady=4, undo=True, highlightthickness=0)

    sb = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
    text.configure(yscrollcommand=sb.set)
    sb.pack(side="right", fill="y")
    text.pack(fill="both", expand=True)

    # Line numbers update
    def update_lines(event=None):
        if show_lines:
            ln.config(state="normal")
            ln.delete("1.0", "end")
            count = int(text.index("end-1c").split(".")[0])
            ln.insert("1.0", "\n".join(str(i) for i in range(1, count + 1)))
            ln.config(state="disabled")
        if is_python:
            syntax_highlight(text)

    if show_lines:
        text.bind("<KeyRelease>", update_lines, add="+")
        text.bind("<MouseWheel>", lambda e: (text.yview_scroll(int(-1 * e.delta / 120), "units"), update_lines()),
                  add="+")
        update_lines()
    elif is_python:
        text.bind("<KeyRelease>", lambda e: syntax_highlight(text), add="+")

    # Paste
    def on_paste(event=None):
        try:
            text.edit_separator()
        except tk.TclError:
            pass
        update_lines()
    text.bind("<<Paste>>", on_paste, add="+")

    # Tab -> spaces
    ts = editor_cfg.get("tab_size", 4)
    text.bind("<Tab>", lambda e: (text.insert("insert", " " * ts), "break"))

    if show_lines:
        text._line_widget = ln

    return frame, text, sb


# =============================================================================
# Text Tab Management
# =============================================================================
def new_text_tab(title=None, content="", file_path=None):
    if title is None:
        tab_counter["text"] += 1
        title = f"Untitled-{tab_counter['text']}"

    # Frame for this tab (will be added to the sub notebook)
    tab_frame = tk.Frame(text_sub_nb, bg=theme["background_color"])
    editor_frame, text_w, scroll = make_text_widget(tab_frame)
    editor_frame.pack(fill="both", expand=True)

    if content:
        text_w.insert("1.0", content)

    info = {"frame": tab_frame, "text": text_w, "scroll": scroll,
            "file_path": file_path, "label": title}
    text_tabs.append(info)

    text_sub_nb.add(tab_frame, text=f"  {title}  ")
    text_sub_nb.select(tab_frame)
    return info


def close_text_tab_by_index(idx):
    """Close text tab by index safely."""
    if idx < 0 or idx >= len(text_tabs):
        return
    info = text_tabs.pop(idx)
    text_sub_nb.forget(info["frame"])
    info["frame"].destroy()


def close_text_tab(info):
    if info in text_tabs:
        close_text_tab_by_index(text_tabs.index(info))


# =============================================================================
# Python Tab Management
# =============================================================================
def new_python_tab(title=None, content="", file_path=None):
    if title is None:
        tab_counter["python"] += 1
        title = f"script-{tab_counter['python']}.py"

    container = tk.Frame(python_sub_nb, bg=theme["background_color"])

    # PanedWindow: editor top, output bottom
    paned = tk.PanedWindow(container, orient="vertical", bg=theme["toolbar_border"],
                           sashwidth=3, sashrelief="flat")
    paned.pack(fill="both", expand=True)

    # Editor
    editor_frame = tk.Frame(paned, bg=theme["background_color"])
    text_frame, text_w, scroll = make_text_widget(editor_frame, is_python=True)
    text_frame.pack(fill="both", expand=True)
    paned.add(editor_frame, stretch="always")

    if content:
        text_w.insert("1.0", content)

    # Output area
    output_frame = tk.Frame(paned, bg=theme["background_color"])

    # Output header
    oh = tk.Frame(output_frame, bg=theme["toolbar_bg"], height=26)
    oh.pack(fill="x")
    oh.pack_propagate(False)
    tk.Label(oh, text="  Output", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"],
             font=("DejaVu Sans", 9, "bold")).pack(side="left", padx=6)

    clear_btn = tk.Label(oh, text="Clear", bg=theme["toolbar_bg"], fg=theme["toolbar_fg"],
                         font=("DejaVu Sans", 8), padx=8, cursor="hand2")
    clear_btn.pack(side="right", padx=6)

    out_text = tk.Text(output_frame, wrap="word", bg=theme["output_bg"], fg=theme["output_fg"],
                       font=get_font(), relief="flat", borderwidth=0, padx=8, pady=4,
                       state="disabled", highlightthickness=0)
    out_sb = ttk.Scrollbar(output_frame, orient="vertical", command=out_text.yview)
    out_text.configure(yscrollcommand=out_sb.set)
    out_sb.pack(side="right", fill="y")
    out_text.pack(fill="both", expand=True)

    def do_clear():
        out_text.config(state="normal")
        out_text.delete("1.0", "end")
        out_text.config(state="disabled")
    clear_btn.bind("<Button-1>", lambda e: do_clear())

    paned.add(output_frame, stretch="never")

    info = {"frame": container, "text": text_w, "scroll": scroll,
            "output": out_text, "file_path": file_path, "label": title}
    python_tabs.append(info)

    python_sub_nb.add(container, text=f"  {title}  ")
    python_sub_nb.select(container)
    return info


def close_python_tab_by_index(idx):
    if idx < 0 or idx >= len(python_tabs):
        return
    info = python_tabs.pop(idx)
    python_sub_nb.forget(info["frame"])
    info["frame"].destroy()


def close_python_tab(info):
    if info in python_tabs:
        close_python_tab_by_index(python_tabs.index(info))


# =============================================================================
# Active Tab Helpers
# =============================================================================
def get_active_text_tab():
    try:
        cur = text_sub_nb.nametowidget(text_sub_nb.select())
        for t in text_tabs:
            if t["frame"] == cur:
                return t
    except Exception:
        pass
    return None


def get_active_python_tab():
    try:
        cur = python_sub_nb.nametowidget(python_sub_nb.select())
        for t in python_tabs:
            if t["frame"] == cur:
                return t
    except Exception:
        pass
    return None


def get_active():
    idx = main_nb.index("current")
    if idx == 0:
        return get_active_text_tab(), "text"
    elif idx == 1:
        return get_active_python_tab(), "python"
    return None, None


# =============================================================================
# File Operations
# =============================================================================
def open_file():
    path = filedialog.askopenfilename(
        title="Open File",
        filetypes=[("Python Files", "*.py"), ("Text Files", "*.txt"), ("All Files", "*.*")])
    if not path:
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        messagebox.showerror("Error", f"Could not open file:\n{e}")
        return

    name = os.path.basename(path)
    if path.endswith(".py"):
        new_python_tab(title=name, content=content, file_path=path)
        main_nb.select(1)
    else:
        new_text_tab(title=name, content=content, file_path=path)
        main_nb.select(0)


def save_file():
    tab, kind = get_active()
    if tab is None:
        messagebox.showwarning("Warning", "No active tab.")
        return
    if tab["file_path"]:
        try:
            content = tab["text"].get("1.0", "end-1c")
            with open(tab["file_path"], "w", encoding="utf-8") as f:
                f.write(content)
        except Exception as e:
            messagebox.showerror("Error", f"Could not save:\n{e}")
    else:
        save_file_as()


def save_file_as():
    tab, kind = get_active()
    if tab is None:
        messagebox.showwarning("Warning", "No active tab.")
        return
    path = filedialog.asksaveasfilename(
        title="Save As",
        defaultextension=".py" if kind == "python" else ".txt",
        filetypes=[("Python Files", "*.py"), ("Text Files", "*.txt"), ("All Files", "*.*")])
    if not path:
        return
    try:
        content = tab["text"].get("1.0", "end-1c")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        tab["file_path"] = path
        tab["label"] = os.path.basename(path)
        nb = python_sub_nb if kind == "python" else text_sub_nb
        nb.tab(tab["frame"], text=f"  {tab['label']}  ")
    except Exception as e:
        messagebox.showerror("Error", f"Could not save:\n{e}")


# =============================================================================
# Run Python
# =============================================================================
def run_python():
    tab = get_active_python_tab()
    if tab is None:
        messagebox.showwarning("Warning", "No Python tab active.")
        return

    code = tab["text"].get("1.0", "end-1c")
    if not code.strip():
        return

    # Save code
    if tab["file_path"]:
        try:
            with open(tab["file_path"], "w", encoding="utf-8") as f:
                f.write(code)
            script = tab["file_path"]
        except Exception:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
                tmp.write(code)
            script = tmp.name
    else:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tmp:
            tmp.write(code)
        script = tmp.name

    out = tab["output"]
    out.config(state="normal")
    out.delete("1.0", "end")
    out.insert("1.0", f"> Running {os.path.basename(script)}...\n")
    out.config(state="disabled")

    try:
        result = subprocess.run(
            [sys.executable, script], capture_output=True, text=True,
            timeout=30, cwd=os.path.dirname(script) if os.path.dirname(script) else None)
        out.config(state="normal")
        if result.stdout:
            out.insert("end", result.stdout)
        if result.stderr:
            out.insert("end", result.stderr)
        if not result.stdout and not result.stderr:
            out.insert("end", "(No output)\n")
        out.config(state="disabled")
    except subprocess.TimeoutExpired:
        out.config(state="normal")
        out.insert("end", "\nTimeout (30s)\n")
        out.config(state="disabled")
    except Exception as e:
        out.config(state="normal")
        out.insert("end", f"\nError: {e}\n")
        out.config(state="disabled")

    # Cleanup temp
    if not tab["file_path"]:
        try:
            os.unlink(script)
        except Exception:
            pass


# =============================================================================
# Settings
# =============================================================================
def build_settings():
    for w in settings_frame.winfo_children():
        w.destroy()

    canvas = tk.Canvas(settings_frame, bg=theme["settings_bg"], highlightthickness=0)
    sb = ttk.Scrollbar(settings_frame, orient="vertical", command=canvas.yview)
    scrollable = tk.Frame(canvas, bg=theme["settings_bg"])

    scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scrollable, anchor="nw")
    canvas.configure(yscrollcommand=sb.set)

    canvas.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    rp = {"padx": 20, "pady": 5}

    # Title
    tk.Label(scrollable, text="Settings", bg=theme["settings_bg"], fg=theme["settings_fg"],
             font=("DejaVu Sans", 14, "bold")).pack(pady=(15, 10), padx=20, anchor="w")
    tk.Frame(scrollable, bg=theme["toolbar_border"], height=2).pack(fill="x", padx=20, pady=(0, 12))

    # Font
    tk.Label(scrollable, text="Font", bg=theme["settings_bg"], fg=theme["settings_fg"],
             font=("DejaVu Sans", 11, "bold")).pack(anchor="w", padx=20, pady=(8, 4))

    fonts = ["DejaVu Sans Mono", "Courier New", "Consolas", "Monaco",
             "Liberation Mono", "Ubuntu Mono", "Source Code Pro", "monospace"]

    ff = tk.Frame(scrollable, bg=theme["settings_bg"]); ff.pack(fill="x", **rp)
    tk.Label(ff, text="Font Family:", bg=theme["settings_bg"], fg=theme["settings_fg"],
             font=("DejaVu Sans", 9), width=14, anchor="w").pack(side="left")
    fam_var = tk.StringVar(value=config["font"]["family"])
    ttk.Combobox(ff, textvariable=fam_var, values=fonts, state="readonly", width=28).pack(side="left", padx=10)

    fs = tk.Frame(scrollable, bg=theme["settings_bg"]); fs.pack(fill="x", **rp)
    tk.Label(fs, text="Font Size:", bg=theme["settings_bg"], fg=theme["settings_fg"],
             font=("DejaVu Sans", 9), width=14, anchor="w").pack(side="left")
    size_var = tk.IntVar(value=config["font"]["size"])
    tk.Spinbox(fs, from_=8, to=32, textvariable=size_var, width=8,
               bg=theme["settings_entry_bg"], fg=theme["settings_entry_fg"],
               relief="flat", font=("DejaVu Sans", 9)).pack(side="left", padx=10)

    tk.Frame(scrollable, bg=theme["toolbar_border"], height=2).pack(fill="x", padx=20, pady=12)

    # Colors
    tk.Label(scrollable, text="Colors", bg=theme["settings_bg"], fg=theme["settings_fg"],
             font=("DejaVu Sans", 11, "bold")).pack(anchor="w", padx=20, pady=(8, 4))

    colors = [
        ("Font Color", "font", "font_color"),
        ("Editor BG", "theme", "text_bg"),
        ("Editor FG", "theme", "text_fg"),
        ("Cursor Color", "theme", "text_cursor"),
        ("Selection BG", "theme", "text_selected_bg"),
        ("Output BG", "theme", "output_bg"),
        ("Output FG", "theme", "output_fg"),
        ("Background", "theme", "background_color"),
        ("Toolbar BG", "theme", "toolbar_bg"),
    ]

    color_vars = {}
    for lbl, sec, key in colors:
        cf = tk.Frame(scrollable, bg=theme["settings_bg"]); cf.pack(fill="x", **rp)
        tk.Label(cf, text=f"{lbl}:", bg=theme["settings_bg"], fg=theme["settings_fg"],
                 font=("DejaVu Sans", 9), width=16, anchor="w").pack(side="left")

        cv = tk.StringVar(value=config[sec][key])
        color_vars[(sec, key)] = cv

        preview = tk.Label(cf, text="   ", bg=cv.get(), relief="solid", borderwidth=1, width=3)
        preview.pack(side="left", padx=(0, 6))

        tk.Entry(cf, textvariable=cv, width=12, bg=theme["settings_entry_bg"],
                 fg=theme["settings_entry_fg"], relief="flat",
                 font=("DejaVu Sans", 9)).pack(side="left", padx=4)

        def picker(sv, pv):
            def fn():
                c = colorchooser.askcolor(initialcolor=sv.get())
                if c[1]:
                    sv.set(c[1])
                    pv.configure(bg=c[1])
            return fn

        tk.Button(cf, text="Pick", command=picker(cv, preview),
                  bg=theme["settings_button_bg"], fg=theme["settings_button_fg"],
                  relief="flat", font=("DejaVu Sans", 8), padx=6, cursor="hand2").pack(side="left", padx=4)

        cv.trace_add("write", lambda *a, c=cv, p=preview: p.configure(bg=c.get()))

    tk.Frame(scrollable, bg=theme["toolbar_border"], height=2).pack(fill="x", padx=20, pady=12)

    # Editor
    tk.Label(scrollable, text="Editor", bg=theme["settings_bg"], fg=theme["settings_fg"],
             font=("DejaVu Sans", 11, "bold")).pack(anchor="w", padx=20, pady=(8, 4))

    ec = get_editor_cfg()

    ts = tk.Frame(scrollable, bg=theme["settings_bg"]); ts.pack(fill="x", **rp)
    tk.Label(ts, text="Tab Size:", bg=theme["settings_bg"], fg=theme["settings_fg"],
             font=("DejaVu Sans", 9), width=14, anchor="w").pack(side="left")
    tsv = tk.IntVar(value=ec.get("tab_size", 4))
    tk.Spinbox(ts, from_=2, to=8, textvariable=tsv, width=8,
               bg=theme["settings_entry_bg"], fg=theme["settings_entry_fg"],
               relief="flat", font=("DejaVu Sans", 9)).pack(side="left", padx=10)

    wwv = tk.BooleanVar(value=ec.get("word_wrap", True))
    tk.Checkbutton(scrollable, text="Word Wrap", variable=wwv,
                   bg=theme["settings_bg"], fg=theme["settings_fg"],
                   selectcolor=theme["settings_entry_bg"],
                   activebackground=theme["settings_bg"],
                   activeforeground=theme["settings_fg"],
                   font=("DejaVu Sans", 9)).pack(fill="x", **rp)

    lnv = tk.BooleanVar(value=ec.get("show_line_numbers", True))
    tk.Checkbutton(scrollable, text="Show Line Numbers", variable=lnv,
                   bg=theme["settings_bg"], fg=theme["settings_fg"],
                   selectcolor=theme["settings_entry_bg"],
                   activebackground=theme["settings_bg"],
                   activeforeground=theme["settings_fg"],
                   font=("DejaVu Sans", 9)).pack(fill="x", **rp)

    tk.Frame(scrollable, bg=theme["toolbar_border"], height=2).pack(fill="x", padx=20, pady=12)

    # Save / Apply
    def apply():
        config["font"]["family"] = fam_var.get()
        config["font"]["size"] = size_var.get()
        for (sec, key), var in color_vars.items():
            config[sec][key] = var.get()
        if "editor" not in config:
            config["editor"] = {}
        config["editor"]["tab_size"] = tsv.get()
        config["editor"]["word_wrap"] = wwv.get()
        config["editor"]["show_line_numbers"] = lnv.get()
        save_config(config)
        apply_theme()
        messagebox.showinfo("Settings", "Saved!")

    def reset():
        fam_var.set("DejaVu Sans Mono")
        size_var.set(12)
        tsv.set(4)
        wwv.set(True)
        lnv.set(True)

    bf = tk.Frame(scrollable, bg=theme["settings_bg"]); bf.pack(fill="x", padx=20, pady=15)
    tk.Button(bf, text="Save & Apply", command=apply,
              bg=theme["settings_button_bg"], fg=theme["settings_button_fg"],
              relief="flat", font=("DejaVu Sans", 10, "bold"),
              padx=16, pady=6, cursor="hand2").pack(side="left")
    tk.Button(bf, text="Reset Defaults", command=reset,
              bg="#f38ba8", fg="#1e1e2e", relief="flat",
              font=("DejaVu Sans", 10), padx=16, pady=6, cursor="hand2").pack(side="left", padx=10)

    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * event.delta / 120), "units")
    canvas.bind_all("<MouseWheel>", on_mousewheel)


def apply_theme():
    f = get_font()
    for t in text_tabs:
        try:
            t["text"].configure(font=f, bg=theme["text_bg"], fg=theme["text_fg"],
                                insertbackground=theme["text_cursor"],
                                selectbackground=theme["text_selected_bg"])
            if hasattr(t["text"], "_line_widget"):
                t["text"]._line_widget.configure(font=f)
        except Exception:
            pass
    for t in python_tabs:
        try:
            t["text"].configure(font=f, bg=theme["text_bg"], fg=theme["text_fg"],
                                insertbackground=theme["text_cursor"],
                                selectbackground=theme["text_selected_bg"])
            t["output"].configure(font=f, bg=theme["output_bg"], fg=theme["output_fg"])
            if hasattr(t["text"], "_line_widget"):
                t["text"]._line_widget.configure(font=f)
        except Exception:
            pass


def switch_to_settings():
    main_nb.select(2)


# =============================================================================
# Context Menu – Right-click on tab to close
# =============================================================================
def make_tab_context_menu(sub_nb, tabs_list, close_func):
    """Create a context menu for tab closing."""
    menu = tk.Menu(sub_nb, tearoff=0)

    def on_right_click(event):
        try:
            idx = sub_nb.index(f"@{event.x},{event.y}")
            if 0 <= idx < len(tabs_list):
                menu.tab_idx = idx
                menu.post(event.x_root, event.y_root)
        except Exception:
            pass

    menu.add_command(label="Close Tab", command=lambda: close_func(menu.tab_idx))
    sub_nb.bind("<Button-3>", on_right_click)
    return menu


# =============================================================================
# Menu Bar
# =============================================================================
menubar = tk.Menu(root)

fm = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="File", menu=fm)
fm.add_command(label="New Text Tab", command=lambda: new_text_tab())
fm.add_command(label="New Python Tab", command=lambda: new_python_tab())
fm.add_command(label="Open...", command=open_file, accelerator="Ctrl+O")
fm.add_separator()
fm.add_command(label="Save", command=save_file, accelerator="Ctrl+S")
fm.add_command(label="Save As...", command=save_file_as, accelerator="Ctrl+Shift+S")
fm.add_separator()

# Close tab submenu
def close_active():
    tab, kind = get_active()
    if kind == "text":
        close_text_tab(tab)
    elif kind == "python":
        close_python_tab(tab)

fm.add_command(label="Close Tab", command=close_active, accelerator="Ctrl+W")
fm.add_separator()
fm.add_command(label="Exit", command=root.destroy)

rm = tk.Menu(menubar, tearoff=0)
menubar.add_cascade(label="Run", menu=rm)
rm.add_command(label="Run Python", command=run_python, accelerator="Ctrl+R")

root.config(menu=menubar)

# Keyboard
root.bind("<Control-n>", lambda e: new_text_tab())
root.bind("<Control-o>", lambda e: open_file())
root.bind("<Control-s>", lambda e: save_file())
root.bind("<Control-Shift-S>", lambda e: save_file_as())
root.bind("<Control-r>", lambda e: run_python())
root.bind("<Control-w>", lambda e: close_active())

# =============================================================================
# Context menus for tabs
# =============================================================================
make_tab_context_menu(text_sub_nb, text_tabs, close_text_tab_by_index)
make_tab_context_menu(python_sub_nb, python_tabs, close_python_tab_by_index)

# =============================================================================
# Initialize
# =============================================================================
new_text_tab()
new_python_tab()
build_settings()

# Clean exit on window close (X button)
root.protocol("WM_DELETE_WINDOW", root.destroy)

root.mainloop()
