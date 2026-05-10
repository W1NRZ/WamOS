import json
import os
import shlex
import subprocess
import sys
import threading
import re
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, colorchooser, filedialog
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin, quote_plus

import requests
from bs4 import BeautifulSoup

APP_NAME = "WamOS"
DATA_DIR = Path.home() / ".wam_os"
DATA_FILE = DATA_DIR / "state.json"

# ── WamOS Theme: Red · Grey · White ────────────────────────────────────────
DARK_BG  = "#1a1a1a"
PANEL_BG = "#242424"
SURFACE  = "#2d2d2d"
SURFACE2 = "#3c3c3c"
ACCENT   = "#c0392b"   # WamOS Red
FG       = "#f5f5f5"   # Near-white
FG_DIM   = "#9e9e9e"   # Muted grey
GREEN    = "#27ae60"
RED      = "#e74c3c"
AMBER    = "#e67e22"
TEAL     = "#1abc9c"

FONT_MONO  = ("Consolas", 11)
FONT_UI    = ("Segoe UI", 10)
FONT_TITLE = ("Segoe UI", 11, "bold")

# ── Package Registry ────────────────────────────────────────────────────────
PACKAGE_REGISTRY = {
    # Python packages via pip
    "requests":      {"type": "pip", "pkg": "requests",     "desc": "HTTP library for Python",       "category": "Python"},
    "beautifulsoup4":{"type": "pip", "pkg": "beautifulsoup4","desc": "HTML/XML parsing library",      "category": "Python"},
    "numpy":         {"type": "pip", "pkg": "numpy",         "desc": "Numerical computing",           "category": "Python"},
    "pandas":        {"type": "pip", "pkg": "pandas",        "desc": "Data analysis & structures",    "category": "Python"},
    "pillow":        {"type": "pip", "pkg": "Pillow",        "desc": "Image processing (PIL fork)",   "category": "Python"},
    "flask":         {"type": "pip", "pkg": "flask",         "desc": "Lightweight web framework",     "category": "Python"},
    "matplotlib":    {"type": "pip", "pkg": "matplotlib",    "desc": "2D plotting library",           "category": "Python"},
    "scipy":         {"type": "pip", "pkg": "scipy",         "desc": "Scientific computing",          "category": "Python"},
    "cryptography":  {"type": "pip", "pkg": "cryptography",  "desc": "Cryptographic recipes",         "category": "Python"},
    "paramiko":      {"type": "pip", "pkg": "paramiko",      "desc": "SSH2 protocol library",         "category": "Python"},
    "yt-dlp":        {"type": "pip", "pkg": "yt-dlp",        "desc": "YouTube/media downloader",      "category": "Media"},
    "rich":          {"type": "pip", "pkg": "rich",          "desc": "Rich text & formatting",        "category": "Python"},
    "httpx":         {"type": "pip", "pkg": "httpx",         "desc": "Async HTTP client",             "category": "Python"},
    # Simulated system-level tools
    "nmap":          {"type": "system", "desc": "Network scanner & port mapper",   "category": "Network"},
    "curl":          {"type": "system", "desc": "URL transfer command line tool",  "category": "Network"},
    "wget":          {"type": "system", "desc": "Non-interactive file downloader", "category": "Network"},
    "ssh":           {"type": "system", "desc": "OpenSSH secure shell client",     "category": "Network"},
    "netcat":        {"type": "system", "desc": "TCP/UDP networking utility",      "category": "Network"},
    "git":           {"type": "system", "desc": "Distributed version control",     "category": "Dev"},
    "vim":           {"type": "system", "desc": "Improved vi text editor",         "category": "Dev"},
    "gcc":           {"type": "system", "desc": "GNU C compiler",                  "category": "Dev"},
    "node":          {"type": "system", "desc": "Node.js JavaScript runtime",      "category": "Dev"},
    "htop":          {"type": "system", "desc": "Interactive process viewer",      "category": "System"},
    "neofetch":      {"type": "system", "desc": "System info tool",                "category": "System"},
    "tree":          {"type": "system", "desc": "Directory tree viewer",           "category": "System"},
    "ffmpeg":        {"type": "system", "desc": "Audio/video converter",           "category": "Media"},
    "imagemagick":   {"type": "system", "desc": "Image manipulation suite",        "category": "Media"},
}

DEFAULT_STATE = {
    "filesystem": {
        "home": {
            "readme.txt": (
                "Welcome to WamOS\n\n"
                "A powerful virtual OS built with Python & Tkinter.\n\n"
                "── Apps ──────────────────────────────────\n"
                "  🌐 Browser    📁 Files     📝 Notes\n"
                "  ✏️  Editor    🖥️ Terminal   🧮 Calculator\n"
                "  📦 Packages  ⚙️  Settings\n\n"
                "── Terminal Commands ─────────────────────\n"
                "  ls, cd, pwd, cat, write, touch, mkdir, rm, mv\n"
                "  wam install <pkg>  |  wam list  |  wam search <term>\n"
            ),
            "documents": {},
            "downloads": {},
            "notes": {},
            "projects": {},
        }
    },
    "cwd": ["home"],
    "notes_list": {"Welcome to WamOS": "Welcome!\n\nThis is your note-taking app.\nCreate, rename and delete notes from the sidebar."},
    "wallpaper": "#1a1a1a",
    "wallpaper_image": "",
    "accent_color": "#c0392b",
    "font_size": 10,
    "username": "user",
    "bookmarks": [
        "https://en.wikipedia.org/wiki/Main_Page",
        "https://news.ycombinator.com",
        "https://github.com",
        "https://duckduckgo.com",
    ],
    "browser_history": [],
    "installed_packages": [],
}


def deep_copy(obj):
    return json.loads(json.dumps(obj))


def styled_button(parent, text, command, bg=None, fg=FG, width=None, **kw):
    if bg is None:
        bg = SURFACE2
    opts = dict(text=text, command=command, bg=bg, fg=fg,
                relief="flat", cursor="hand2", activebackground=ACCENT,
                activeforeground=FG, bd=0, pady=4, padx=8, font=FONT_UI)
    if width:
        opts["width"] = width
    opts.update(kw)
    return tk.Button(parent, **opts)


def styled_entry(parent, **kw):
    defaults = dict(bg=SURFACE2, fg=FG, insertbackground=FG,
                    relief="flat", font=FONT_UI, bd=4)
    defaults.update(kw)
    return tk.Entry(parent, **defaults)


# ─────────────────────────────────────────────────────────────────────────────
# Virtual filesystem
# ─────────────────────────────────────────────────────────────────────────────
class VirtualFS:
    def __init__(self, state):
        self.state = state

    def _root(self):
        return self.state["filesystem"]

    def _resolve(self, path=None):
        if path is None or path == "":
            parts = list(self.state["cwd"])
        elif path.startswith("/"):
            parts = [p for p in path.strip("/").split("/") if p]
        else:
            parts = list(self.state["cwd"])
            for part in path.split("/"):
                if not part or part == ".":
                    continue
                if part == "..":
                    if parts:
                        parts.pop()
                else:
                    parts.append(part)
        node = self._root()
        for part in parts:
            if part not in node or not isinstance(node[part], dict):
                raise FileNotFoundError(f"no such directory: /{'/'.join(parts)}")
            node = node[part]
        return node, parts

    def pwd(self):
        return "/" + "/".join(self.state["cwd"])

    def ls(self, path=None):
        node, _ = self._resolve(path)
        return [(name, isinstance(value, dict)) for name, value in sorted(node.items())]

    def cd(self, path):
        _, parts = self._resolve(path)
        self.state["cwd"] = parts
        return self.pwd()

    def mkdir(self, name):
        node, _ = self._resolve()
        if name in node:
            raise FileExistsError(name)
        node[name] = {}

    def touch(self, name):
        node, _ = self._resolve()
        if name in node and isinstance(node[name], dict):
            raise IsADirectoryError(name)
        node.setdefault(name, "")

    def write(self, name, content):
        node, _ = self._resolve()
        if name in node and isinstance(node[name], dict):
            raise IsADirectoryError(name)
        node[name] = content

    def cat(self, name):
        node, _ = self._resolve()
        if name not in node:
            raise FileNotFoundError(name)
        if isinstance(node[name], dict):
            raise IsADirectoryError(name)
        return node[name]

    def rm(self, name):
        node, _ = self._resolve()
        if name not in node:
            raise FileNotFoundError(name)
        del node[name]

    def rename(self, old, new):
        node, _ = self._resolve()
        if old not in node:
            raise FileNotFoundError(old)
        if new in node:
            raise FileExistsError(new)
        node[new] = node.pop(old)

    def size(self, name):
        node, _ = self._resolve()
        val = node.get(name, "")
        if isinstance(val, dict):
            return f"{len(val)} items"
        return f"{len(val)} chars"


# ─────────────────────────────────────────────────────────────────────────────
# HTML → rich-text renderer (native, no Chromium)
# ─────────────────────────────────────────────────────────────────────────────
class RichHTMLRenderer:
    SKIP = {"script", "style", "noscript", "svg", "path", "iframe",
            "canvas", "video", "audio", "object", "embed"}

    def __init__(self, base_url=""):
        self.base_url = base_url
        self.links = []
        self._href_idx = {}

    def render(self, html):
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(list(self.SKIP)):
            tag.decompose()
        body = soup.body or soup
        lines = []
        self._walk(body, lines, 0)
        text = "\n".join(lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip(), self.links

    def _walk(self, node, lines, depth):
        from bs4 import NavigableString, Tag
        if isinstance(node, NavigableString):
            s = re.sub(r'[ \t\r\n]+', ' ', str(node))
            if s.strip():
                if lines:
                    lines[-1] = lines[-1] + s
                else:
                    lines.append(s)
            return
        if not isinstance(node, Tag):
            return
        tag = (node.name or "").lower()

        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = node.get_text(" ", strip=True)
            lines.append("")
            level = int(tag[1])
            if level == 1:
                lines.append(f"█ {text}")
                lines.append("═" * min(len(text) + 2, 72))
            elif level == 2:
                lines.append(f"▌ {text}")
                lines.append("─" * min(len(text) + 2, 72))
            elif level == 3:
                lines.append(f"◆ {text}")
            else:
                lines.append(f"• {text}")
            lines.append("")
            return

        if tag == "hr":
            lines.append("\n" + "─" * 72 + "\n")
            return
        if tag == "br":
            lines.append("")
            return
        if tag == "pre":
            lines.append("")
            for ln in node.get_text().splitlines():
                lines.append("  │ " + ln)
            lines.append("")
            return
        if tag == "blockquote":
            sub = []
            self._walk_children(node, sub, depth)
            for s in sub:
                lines.append("  ┃ " + s.lstrip())
            return
        if tag == "table":
            self._render_table(node, lines)
            return
        if tag == "ul":
            lines.append("")
            for child in node.children:
                if hasattr(child, "name") and child.name == "li":
                    sub = []
                    self._walk_children(child, sub, depth)
                    item = " ".join(s.strip() for s in sub if s.strip())
                    lines.append("  • " + item)
            lines.append("")
            return
        if tag == "ol":
            lines.append("")
            n = 1
            for child in node.children:
                if hasattr(child, "name") and child.name == "li":
                    sub = []
                    self._walk_children(child, sub, depth)
                    item = " ".join(s.strip() for s in sub if s.strip())
                    lines.append(f"  {n}. " + item)
                    n += 1
            lines.append("")
            return
        if tag == "a":
            href = node.get("href", "")
            text = node.get_text(" ", strip=True)
            if not text:
                self._walk_children(node, lines, depth)
                return
            if href:
                abs_href = urljoin(self.base_url, href)
                if abs_href not in self._href_idx:
                    self._href_idx[abs_href] = len(self.links)
                    self.links.append((text, abs_href))
                idx = self._href_idx[abs_href]
                token = f"[{text}]({idx + 1})"
            else:
                token = text
            if lines:
                lines[-1] += token
            else:
                lines.append(token)
            return
        if tag == "img":
            alt = node.get("alt", "").strip()
            if alt:
                tok = f"[img: {alt}]"
                if lines:
                    lines[-1] += " " + tok
                else:
                    lines.append(tok)
            return
        if tag in ("strong", "b"):
            t = node.get_text(" ", strip=True)
            if lines:
                lines[-1] += f"**{t}**"
            else:
                lines.append(f"**{t}**")
            return
        if tag in ("em", "i"):
            t = node.get_text(" ", strip=True)
            if lines:
                lines[-1] += f"_{t}_"
            else:
                lines.append(f"_{t}_")
            return
        if tag == "code" and (not node.parent or node.parent.name != "pre"):
            t = node.get_text()
            if lines:
                lines[-1] += f"`{t}`"
            else:
                lines.append(f"`{t}`")
            return

        block = tag in {"p", "div", "article", "section", "main", "aside",
                        "header", "footer", "figure", "figcaption", "details",
                        "summary", "li"}
        if block:
            lines.append("")
        self._walk_children(node, lines, depth)
        if block:
            lines.append("")

    def _walk_children(self, node, lines, depth):
        for child in node.children:
            self._walk(child, lines, depth)

    def _render_table(self, node, lines):
        rows = []
        for tr in node.find_all("tr"):
            row = [c.get_text(" ", strip=True) for c in tr.find_all(["td", "th"])]
            if row:
                rows.append(row)
        if not rows:
            return
        cols = max(len(r) for r in rows)
        widths = [max((len(r[i]) if i < len(r) else 0) for r in rows) for i in range(cols)]
        sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
        lines.append("")
        lines.append(sep)
        for ri, row in enumerate(rows):
            cells = [f" {(row[i] if i < len(row) else ''):<{widths[i]}} " for i in range(cols)]
            lines.append("|" + "|".join(cells) + "|")
            if ri == 0:
                lines.append(sep)
        lines.append(sep)
        lines.append("")


# ─────────────────────────────────────────────────────────────────────────────
# Base window
# ─────────────────────────────────────────────────────────────────────────────
class BaseWindow(tk.Toplevel):
    def __init__(self, app, title, size="700x480"):
        super().__init__(app.root)
        self.app = app
        self.title(f"{APP_NAME} — {title}")
        self.geometry(size)
        self.minsize(480, 300)
        self.configure(bg=DARK_BG)
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.app.register_window(self, title)
        self._build_titlebar(title)

    def _build_titlebar(self, title):
        bar = tk.Frame(self, bg=PANEL_BG, height=32)
        bar.pack(side="top", fill="x")
        bar.pack_propagate(False)
        # WamOS logo dot
        tk.Label(bar, text="●", bg=PANEL_BG, fg=ACCENT, font=("Segoe UI", 12)).pack(side="left", padx=(8, 2))
        tk.Label(bar, text=title, bg=PANEL_BG, fg=FG, font=FONT_TITLE).pack(side="left", padx=4)
        tk.Button(bar, text="✕", bg=PANEL_BG, fg=RED, relief="flat",
                  command=self._on_close, cursor="hand2", font=FONT_UI).pack(side="right", padx=6)
        tk.Button(bar, text="—", bg=PANEL_BG, fg=FG_DIM, relief="flat",
                  command=self.iconify, cursor="hand2", font=FONT_UI).pack(side="right", padx=2)

    def _on_close(self):
        self.app.unregister_window(self)
        self.destroy()


# ─────────────────────────────────────────────────────────────────────────────
# Terminal
# ─────────────────────────────────────────────────────────────────────────────
class TerminalWindow(BaseWindow):
    def __init__(self, app):
        super().__init__(app, "terminal", "860x540")
        self.history = []
        self.hist_idx = 0
        self._build()

    def _build(self):
        self.output = tk.Text(self, wrap="word", bg="#0f0f0f", fg="#e0e0e0",
                              insertbackground="#e0e0e0", font=FONT_MONO,
                              padx=10, pady=10, relief="flat", state="disabled")
        self.output.pack(fill="both", expand=True, padx=6, pady=(0, 0))
        bottom = tk.Frame(self, bg=PANEL_BG, height=40)
        bottom.pack(fill="x")
        bottom.pack_propagate(False)
        tk.Label(bottom, text="❯", bg=PANEL_BG, fg=ACCENT, font=("Segoe UI", 13, "bold")).pack(side="left", padx=(10, 4), pady=8)
        self.entry = tk.Entry(bottom, bg="#0f0f0f", fg="#e0e0e0",
                              insertbackground="#e0e0e0", relief="flat", font=FONT_MONO)
        self.entry.pack(side="left", fill="x", expand=True, pady=8)
        self.entry.bind("<Return>", lambda e: self.run())
        self.entry.bind("<Up>",    self.hist_up)
        self.entry.bind("<Down>",  self.hist_down)
        self.entry.focus()
        styled_button(bottom, "Run", self.run, bg=ACCENT).pack(side="right", padx=8, pady=6)
        self._print(f"  {APP_NAME} Terminal  —  type 'help' for commands\n", tag="accent")
        self.output.tag_configure("accent", foreground=ACCENT)
        self.output.tag_configure("err",    foreground=RED)
        self.output.tag_configure("ok",     foreground=GREEN)

    def _print(self, text="", tag=""):
        self.output.configure(state="normal")
        self.output.insert("end", text + "\n", tag)
        self.output.see("end")
        self.output.configure(state="disabled")

    def hist_up(self, e=None):
        if self.history and self.hist_idx > 0:
            self.hist_idx -= 1
            self.entry.delete(0, "end")
            self.entry.insert(0, self.history[self.hist_idx])

    def hist_down(self, e=None):
        if self.hist_idx < len(self.history) - 1:
            self.hist_idx += 1
            self.entry.delete(0, "end")
            self.entry.insert(0, self.history[self.hist_idx])
        else:
            self.hist_idx = len(self.history)
            self.entry.delete(0, "end")

    def run(self):
        cmd = self.entry.get().strip()
        if not cmd:
            return
        self.entry.delete(0, "end")
        self.history.append(cmd)
        self.hist_idx = len(self.history)
        self._print(f"\n  [{self.app.fs.pwd()}] ❯ {cmd}", tag="accent")
        if cmd == "clear":
            self.output.configure(state="normal")
            self.output.delete("1.0", "end")
            self.output.configure(state="disabled")
            return
        try:
            result = self.app.run_terminal_command(cmd, output_cb=self._print)
            if result:
                self._print(result)
        except Exception as e:
            self._print(f"  error: {e}", tag="err")


# ─────────────────────────────────────────────────────────────────────────────
# Files
# ─────────────────────────────────────────────────────────────────────────────
class FilesWindow(BaseWindow):
    def __init__(self, app):
        super().__init__(app, "files", "900x560")
        self._entries = []
        self._build()

    def _build(self):
        toolbar = tk.Frame(self, bg=PANEL_BG, height=38)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        styled_button(toolbar, "⬆ Up",    lambda: self._nav(".."),       bg=SURFACE2).pack(side="left", padx=4, pady=5)
        styled_button(toolbar, "⌂ Home",  lambda: self._nav_abs("/home"), bg=SURFACE2).pack(side="left", padx=2, pady=5)
        self.path_var = tk.StringVar(value=self.app.fs.pwd())
        pe = tk.Entry(toolbar, textvariable=self.path_var, bg=SURFACE2, fg=FG,
                      insertbackground=FG, relief="flat", font=FONT_MONO)
        pe.pack(side="left", fill="x", expand=True, padx=8, pady=7)
        pe.bind("<Return>", lambda e: self._nav_abs(self.path_var.get()))
        styled_button(toolbar, "↻ Refresh", self.refresh, bg=SURFACE2).pack(side="right", padx=4, pady=5)

        main = tk.Frame(self, bg=DARK_BG)
        main.pack(fill="both", expand=True)

        lf = tk.Frame(main, bg=SURFACE)
        lf.pack(side="left", fill="both", expand=True, padx=(6, 3), pady=6)
        header = tk.Frame(lf, bg=PANEL_BG)
        header.pack(fill="x")
        tk.Label(header, text="  Name",   bg=PANEL_BG, fg=FG_DIM, font=FONT_UI, anchor="w", width=28).pack(side="left")
        tk.Label(header, text="Type",     bg=PANEL_BG, fg=FG_DIM, font=FONT_UI, width=8).pack(side="left")
        tk.Label(header, text="Size",     bg=PANEL_BG, fg=FG_DIM, font=FONT_UI, width=12).pack(side="left")
        self.listbox = tk.Listbox(lf, bg=SURFACE, fg=FG, font=FONT_MONO,
                                  selectbackground=ACCENT, selectforeground=FG,
                                  relief="flat", bd=0, activestyle="none")
        scroll = tk.Scrollbar(lf, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.listbox.pack(fill="both", expand=True)
        self.listbox.bind("<Double-Button-1>", lambda e: self.open_selected())
        self.listbox.bind("<<ListboxSelect>>", self._on_select)

        right = tk.Frame(main, bg=PANEL_BG, width=230)
        right.pack(side="right", fill="y", padx=(3, 6), pady=6)
        right.pack_propagate(False)
        tk.Label(right, text="Preview", bg=PANEL_BG, fg=FG_DIM, font=FONT_TITLE).pack(pady=(10, 4))
        self.preview = tk.Text(right, bg=SURFACE, fg=FG_DIM, font=("Consolas", 9),
                               relief="flat", wrap="word", state="disabled", height=10)
        self.preview.pack(fill="x", padx=8, pady=4)
        self.info_label = tk.Label(right, text="", bg=PANEL_BG, fg=FG_DIM,
                                   font=("Segoe UI", 9), wraplength=210, justify="left")
        self.info_label.pack(fill="x", padx=8, pady=4)
        tk.Frame(right, bg=SURFACE2, height=1).pack(fill="x", padx=8, pady=8)
        tk.Label(right, text="Actions", bg=PANEL_BG, fg=FG_DIM, font=FONT_TITLE).pack(pady=(0, 4))
        for label, cmd in [("📄 Open", self.open_selected), ("✏️ Rename", self.rename_selected),
                            ("🗑 Delete", self.delete_selected), ("📁 New Folder", self.new_folder),
                            ("📝 New File", self.new_file)]:
            styled_button(right, label, cmd, bg=SURFACE2, width=18).pack(fill="x", padx=8, pady=3)
        self.refresh()

    def _nav(self, path):
        try:
            self.app.fs.cd(path)
            self.refresh()
        except Exception as e:
            messagebox.showerror("error", str(e), parent=self)

    def _nav_abs(self, path):
        try:
            self.app.fs.cd(path)
            self.refresh()
        except Exception as e:
            messagebox.showerror("error", str(e), parent=self)

    def refresh(self):
        self.path_var.set(self.app.fs.pwd())
        self.listbox.delete(0, "end")
        self._entries = []
        try:
            items = self.app.fs.ls()
        except Exception as e:
            self.listbox.insert("end", str(e))
            return
        for name, is_dir in items:
            icon = "📁" if is_dir else "📄"
            kind = "dir" if is_dir else "file"
            size = f"{len(self.app.fs.ls(name))} items" if is_dir else self.app.fs.size(name)
            self.listbox.insert("end", f"  {icon}  {name:<28} {kind:<10} {size}")
            self._entries.append((name, is_dir))
        self._clear_preview()

    def _on_select(self, e=None):
        sel = self.listbox.curselection()
        if not sel or sel[0] >= len(self._entries):
            return
        name, is_dir = self._entries[sel[0]]
        if not is_dir:
            try:
                content = self.app.fs.cat(name)
                self.preview.configure(state="normal")
                self.preview.delete("1.0", "end")
                self.preview.insert("1.0", content[:500] + ("…" if len(content) > 500 else ""))
                self.preview.configure(state="disabled")
                self.info_label.config(text=f"📄 {name}\n{len(content)} chars  •  {content.count(chr(10)) + 1} lines")
            except Exception:
                self._clear_preview()
        else:
            self._clear_preview()
            try:
                items = self.app.fs.ls(name)
                self.info_label.config(text=f"📁 {name}\n{len(items)} items")
            except Exception:
                self.info_label.config(text=f"📁 {name}")

    def _clear_preview(self):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.configure(state="disabled")
        self.info_label.config(text="")

    def _selected_entry(self):
        sel = self.listbox.curselection()
        if not sel or sel[0] >= len(self._entries):
            return None, None
        return self._entries[sel[0]]

    def open_selected(self):
        name, is_dir = self._selected_entry()
        if name is None:
            return
        if is_dir:
            self._nav(name)
        else:
            try:
                TextEditorWindow(self.app, name, self.app.fs.cat(name))
            except Exception as e:
                messagebox.showerror("error", str(e), parent=self)

    def rename_selected(self):
        name, _ = self._selected_entry()
        if name is None:
            return
        new_name = simpledialog.askstring("rename", "New name:", initialvalue=name, parent=self)
        if not new_name or new_name == name:
            return
        try:
            self.app.fs.rename(name, new_name)
            self.refresh()
        except Exception as e:
            messagebox.showerror("error", str(e), parent=self)

    def delete_selected(self):
        name, _ = self._selected_entry()
        if name is None:
            return
        if messagebox.askyesno("delete", f"Delete '{name}'?", parent=self):
            try:
                self.app.fs.rm(name)
                self.refresh()
            except Exception as e:
                messagebox.showerror("error", str(e), parent=self)

    def new_folder(self):
        name = simpledialog.askstring("new folder", "Folder name:", parent=self)
        if not name:
            return
        try:
            self.app.fs.mkdir(name)
            self.refresh()
        except Exception as e:
            messagebox.showerror("error", str(e), parent=self)

    def new_file(self):
        name = simpledialog.askstring("new file", "File name:", parent=self)
        if not name:
            return
        try:
            self.app.fs.touch(name)
            self.refresh()
        except Exception as e:
            messagebox.showerror("error", str(e), parent=self)


# ─────────────────────────────────────────────────────────────────────────────
# Text Editor
# ─────────────────────────────────────────────────────────────────────────────
class TextEditorWindow(BaseWindow):
    def __init__(self, app, filename="untitled.txt", content=""):
        super().__init__(app, f"editor — {filename}", "800x560")
        self.filename = filename
        self._build(content)

    def _build(self, content):
        toolbar = tk.Frame(self, bg=PANEL_BG, height=36)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        self.file_label = tk.Label(toolbar, text=self.filename, bg=PANEL_BG, fg=FG_DIM, font=FONT_UI)
        self.file_label.pack(side="left", padx=10)
        self.status_label = tk.Label(toolbar, text="", bg=PANEL_BG, fg=GREEN, font=FONT_UI)
        self.status_label.pack(side="left", padx=4)
        styled_button(toolbar, "💾 Save",  self.save,    bg=ACCENT).pack(side="right", padx=6, pady=4)
        styled_button(toolbar, "Save As…", self.save_as, bg=SURFACE2).pack(side="right", padx=2, pady=4)
        self.stats = tk.Label(self, text="", bg=SURFACE, fg=FG_DIM, font=("Segoe UI", 9), anchor="e")
        self.stats.pack(fill="x")
        self.text = tk.Text(self, wrap="word", undo=True, bg=SURFACE, fg=FG,
                            insertbackground=FG, font=FONT_MONO, padx=12, pady=10,
                            relief="flat", selectbackground=ACCENT, selectforeground=FG)
        sb = tk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True)
        self.text.insert("1.0", content)
        self.text.bind("<KeyRelease>", self._update_stats)
        self._update_stats()

    def _update_stats(self, e=None):
        content = self.text.get("1.0", "end-1c")
        words = len(content.split()) if content.strip() else 0
        self.stats.config(text=f"  {content.count(chr(10)) + 1} lines  •  {words} words  •  {len(content)} chars  ")

    def save(self):
        self.app.fs.write(self.filename, self.text.get("1.0", "end-1c"))
        self.app.save_state()
        self.status_label.config(text="✓ saved", fg=GREEN)
        self.after(1800, lambda: self.status_label.config(text=""))

    def save_as(self):
        new_name = simpledialog.askstring("save as", "File name:", initialvalue=self.filename, parent=self)
        if not new_name:
            return
        self.filename = new_name
        self.file_label.config(text=new_name)
        self.save()


# ─────────────────────────────────────────────────────────────────────────────
# Notes
# ─────────────────────────────────────────────────────────────────────────────
class NotesWindow(BaseWindow):
    def __init__(self, app):
        super().__init__(app, "notes", "900x580")
        self.notes = self.app.state.setdefault("notes_list", {"Untitled Note": ""})
        self.current = None
        self._build()

    def _build(self):
        main = tk.Frame(self, bg=DARK_BG)
        main.pack(fill="both", expand=True)
        sidebar = tk.Frame(main, bg=PANEL_BG, width=210)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)
        tk.Label(sidebar, text="Notes", bg=PANEL_BG, fg=FG, font=FONT_TITLE, pady=8).pack(fill="x", padx=10)
        styled_button(sidebar, "+ New Note", self.new_note, bg=ACCENT).pack(fill="x", padx=8, pady=4)
        self.notes_lb = tk.Listbox(sidebar, bg=SURFACE, fg=FG, font=FONT_UI,
                                   selectbackground=ACCENT, selectforeground=FG,
                                   relief="flat", bd=0, activestyle="none")
        self.notes_lb.pack(fill="both", expand=True, padx=4, pady=4)
        self.notes_lb.bind("<<ListboxSelect>>", self._on_note_select)
        styled_button(sidebar, "🗑 Delete", self.delete_note, bg=SURFACE2).pack(fill="x", padx=8, pady=4)
        styled_button(sidebar, "✏️ Rename",  self.rename_note, bg=SURFACE2).pack(fill="x", padx=8, pady=(0, 8))

        right = tk.Frame(main, bg=DARK_BG)
        right.pack(side="left", fill="both", expand=True)
        top_bar = tk.Frame(right, bg=PANEL_BG, height=36)
        top_bar.pack(fill="x")
        top_bar.pack_propagate(False)
        self.note_title_label = tk.Label(top_bar, text="Select or create a note",
                                          bg=PANEL_BG, fg=FG, font=FONT_TITLE)
        self.note_title_label.pack(side="left", padx=10)
        self.save_status = tk.Label(top_bar, text="", bg=PANEL_BG, fg=GREEN, font=FONT_UI)
        self.save_status.pack(side="left")
        self.stats_label = tk.Label(top_bar, text="", bg=PANEL_BG, fg=FG_DIM, font=("Segoe UI", 9))
        self.stats_label.pack(side="right", padx=10)
        styled_button(top_bar, "💾 Save", self.save_current, bg=ACCENT).pack(side="right", padx=6, pady=4)
        self.editor = tk.Text(right, wrap="word", undo=True, bg=SURFACE, fg=FG,
                              insertbackground=FG, font=("Segoe UI", 12), padx=16, pady=12,
                              relief="flat", selectbackground=ACCENT, selectforeground=FG, state="disabled")
        esb = tk.Scrollbar(right, orient="vertical", command=self.editor.yview)
        self.editor.configure(yscrollcommand=esb.set)
        esb.pack(side="right", fill="y")
        self.editor.pack(fill="both", expand=True)
        self.editor.bind("<KeyRelease>", self._update_stats)
        self._refresh_list()
        if self.notes:
            self.notes_lb.selection_set(0)
            self._load_note(list(self.notes.keys())[0])

    def _refresh_list(self):
        self.notes_lb.delete(0, "end")
        for name in self.notes:
            self.notes_lb.insert("end", f"  {name}")

    def _on_note_select(self, e=None):
        sel = self.notes_lb.curselection()
        if not sel:
            return
        name = list(self.notes.keys())[sel[0]]
        if name != self.current:
            self.save_current(silent=True)
            self._load_note(name)

    def _load_note(self, name):
        self.current = name
        self.note_title_label.config(text=name)
        self.editor.configure(state="normal")
        self.editor.delete("1.0", "end")
        self.editor.insert("1.0", self.notes.get(name, ""))
        self._update_stats()

    def _update_stats(self, e=None):
        if self.current is None:
            self.stats_label.config(text="")
            return
        content = self.editor.get("1.0", "end-1c")
        words = len(content.split()) if content.strip() else 0
        self.stats_label.config(text=f"{words} words  •  {len(content)} chars  ")

    def save_current(self, silent=False):
        if self.current is None:
            return
        self.notes[self.current] = self.editor.get("1.0", "end-1c")
        self.app.state["notes_list"] = self.notes
        self.app.save_state()
        if not silent:
            self.save_status.config(text="✓ saved", fg=GREEN)
            self.after(1800, lambda: self.save_status.config(text=""))

    def new_note(self):
        name = simpledialog.askstring("new note", "Note title:", parent=self)
        if not name:
            return
        if name in self.notes:
            messagebox.showwarning("exists", "A note with that name already exists.", parent=self)
            return
        self.notes[name] = ""
        self._refresh_list()
        idx = list(self.notes.keys()).index(name)
        self.notes_lb.selection_clear(0, "end")
        self.notes_lb.selection_set(idx)
        self._load_note(name)

    def delete_note(self):
        if self.current is None:
            return
        if messagebox.askyesno("delete", f"Delete '{self.current}'?", parent=self):
            del self.notes[self.current]
            self.current = None
            self.note_title_label.config(text="")
            self.editor.configure(state="disabled")
            self.editor.delete("1.0", "end")
            self._refresh_list()
            self.app.state["notes_list"] = self.notes
            self.app.save_state()

    def rename_note(self):
        if self.current is None:
            return
        new_name = simpledialog.askstring("rename", "New title:", initialvalue=self.current, parent=self)
        if not new_name or new_name == self.current:
            return
        content = self.notes.pop(self.current)
        self.notes[new_name] = content
        self.current = new_name
        self.note_title_label.config(text=new_name)
        self._refresh_list()
        self.app.state["notes_list"] = self.notes
        self.app.save_state()


# ─────────────────────────────────────────────────────────────────────────────
# Calculator
# ─────────────────────────────────────────────────────────────────────────────
class CalculatorWindow(BaseWindow):
    def __init__(self, app):
        super().__init__(app, "calculator", "340x500")
        self.resizable(False, False)
        self._expr = ""
        self._just_evaled = False
        self._build()

    def _build(self):
        display_frame = tk.Frame(self, bg=SURFACE, pady=10)
        display_frame.pack(fill="x", padx=8, pady=(4, 2))
        self.history_label = tk.Label(display_frame, text="", bg=SURFACE, fg=FG_DIM,
                                      font=("Consolas", 10), anchor="e")
        self.history_label.pack(fill="x", padx=10)
        self.display = tk.Label(display_frame, text="0", bg=SURFACE, fg=FG,
                                font=("Consolas", 28, "bold"), anchor="e")
        self.display.pack(fill="x", padx=10)
        btn_frame = tk.Frame(self, bg=DARK_BG)
        btn_frame.pack(fill="both", expand=True, padx=8, pady=4)

        def mk(text, row, col, cmd, bg=SURFACE2, fg=FG, cs=1):
            b = tk.Button(btn_frame, text=text, command=cmd, bg=bg, fg=fg,
                          relief="flat", cursor="hand2", activebackground=ACCENT,
                          activeforeground=FG, font=("Consolas", 14, "bold"), bd=0)
            b.grid(row=row, column=col, columnspan=cs, sticky="nsew", padx=3, pady=3, ipady=10)

        for i in range(5):
            btn_frame.rowconfigure(i, weight=1)
        for i in range(4):
            btn_frame.columnconfigure(i, weight=1)

        mk("C",  0, 0, self.clear,                  bg=SURFACE2, fg=GREEN)
        mk("±",  0, 1, self.negate)
        mk("%",  0, 2, lambda: self.op("%"))
        mk("÷",  0, 3, lambda: self.op("/"),         bg=ACCENT)
        mk("7",  1, 0, lambda: self.digit("7"))
        mk("8",  1, 1, lambda: self.digit("8"))
        mk("9",  1, 2, lambda: self.digit("9"))
        mk("×",  1, 3, lambda: self.op("*"),         bg=ACCENT)
        mk("4",  2, 0, lambda: self.digit("4"))
        mk("5",  2, 1, lambda: self.digit("5"))
        mk("6",  2, 2, lambda: self.digit("6"))
        mk("−",  2, 3, lambda: self.op("-"),         bg=ACCENT)
        mk("1",  3, 0, lambda: self.digit("1"))
        mk("2",  3, 1, lambda: self.digit("2"))
        mk("3",  3, 2, lambda: self.digit("3"))
        mk("+",  3, 3, lambda: self.op("+"),         bg=ACCENT)
        mk("0",  4, 0, lambda: self.digit("0"),      cs=2)
        mk(".",  4, 2, lambda: self.digit("."))
        mk("=",  4, 3, self.evaluate,                bg=ACCENT, fg=FG)
        self.bind("<Key>", self._key)
        self.focus_set()

    def _key(self, e):
        c = e.char
        if c in "0123456789.":
            self.digit(c)
        elif c in "+-*/%":
            self.op(c)
        elif c in ("=", "\r"):
            self.evaluate()
        elif e.keysym == "BackSpace":
            self._expr = self._expr[:-1]
            self._update()
        elif c in ("c", "C"):
            self.clear()

    def digit(self, d):
        if self._just_evaled:
            self._expr = ""
            self._just_evaled = False
        if d == "." and "." in re.split(r"[+\-*/%]", self._expr)[-1]:
            return
        self._expr += d
        self._update()

    def op(self, o):
        self._just_evaled = False
        if self._expr and self._expr[-1] in "+-*/%":
            self._expr = self._expr[:-1]
        if not self._expr:
            self._expr = "0"
        self._expr += o
        self._update()

    def negate(self):
        if not self._expr or self._expr == "0":
            return
        try:
            val = float(eval(self._expr, {"__builtins__": {}}, {}))
            self._expr = str(int(-val) if (-val).is_integer() else -val)
        except Exception:
            pass
        self._update()

    def clear(self):
        self._expr = ""
        self._just_evaled = False
        self.history_label.config(text="")
        self.display.config(text="0", fg=FG)

    def evaluate(self):
        if not self._expr:
            return
        try:
            result = eval(self._expr, {"__builtins__": {}}, {})
            if isinstance(result, float) and result.is_integer():
                result = int(result)
            self.history_label.config(text=self._expr + " =")
            self._expr = str(result)
            self.display.config(text=self._expr, fg=FG)
            self._just_evaled = True
        except ZeroDivisionError:
            self.display.config(text="÷ 0", fg=RED)
            self._expr = ""
        except Exception:
            self.display.config(text="Error", fg=RED)
            self._expr = ""

    def _update(self):
        self.display.config(text=self._expr or "0", fg=FG)


# ─────────────────────────────────────────────────────────────────────────────
# Browser  ── fully native, no Chrome, multi-tab, rich HTML renderer
# ─────────────────────────────────────────────────────────────────────────────
class _Tab:
    def __init__(self):
        self.url      = "about:blank"
        self.title    = "New Tab"
        self.history: list[str] = []
        self.hist_pos = -1
        self.links:   list[tuple[str, str]] = []
        self._text    = ""


SEARCH_ENGINES = {
    "DuckDuckGo": "https://html.duckduckgo.com/html/?q={}",
    "Bing":       "https://www.bing.com/search?q={}",
    "Google":     "https://www.google.com/search?q={}",
}

START_TEXT = f"""\
█ WamOS Browser
════════════════════════════════════════════════════════

  Native browser — no Chrome, no redirect. Pages load in-app.
  Type any URL or search term and press Enter.

▌ Quick Links
────────────────────────────────────────────────────────
  [Wikipedia](1)   — free encyclopedia
  [Hacker News](2) — tech community
  [GitHub](3)      — code hosting
  [DuckDuckGo](4)  — private search

▌ Tips
────────────────────────────────────────────────────────
  • Click any [numbered link] to follow it
  • Use ◀ ▶ to navigate history, ↺ to reload
  • Switch search engine from the dropdown
  • Bookmark pages with ★
  • Open extra tabs with + Tab
"""
START_LINKS = [
    ("Wikipedia",   "https://en.wikipedia.org/wiki/Main_Page"),
    ("Hacker News", "https://news.ycombinator.com"),
    ("GitHub",      "https://github.com"),
    ("DuckDuckGo",  "https://duckduckgo.com"),
]


class BrowserWindow(BaseWindow):
    def __init__(self, app, url=None):
        super().__init__(app, "browser", "1150x740")
        self._tabs: list[_Tab] = []
        self._active = 0
        self._engine_var = tk.StringVar(value="DuckDuckGo")
        self._build()
        self._new_tab(url or "about:blank", switch=True)

    def _build(self):
        # Tab strip
        self._tab_strip = tk.Frame(self, bg=PANEL_BG, height=30)
        self._tab_strip.pack(side="top", fill="x")
        self._tab_strip.pack_propagate(False)

        # Navigation bar
        nav = tk.Frame(self, bg=PANEL_BG, height=44)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        styled_button(nav, "◀", self.go_back,                       bg=SURFACE2, width=3).pack(side="left", padx=(6, 2), pady=6)
        styled_button(nav, "▶", self.go_forward,                     bg=SURFACE2, width=3).pack(side="left", padx=2, pady=6)
        styled_button(nav, "↺", self.reload,                         bg=SURFACE2, width=3).pack(side="left", padx=2, pady=6)
        styled_button(nav, "⌂", lambda: self.navigate("about:blank"), bg=SURFACE2, width=3).pack(side="left", padx=2, pady=6)

        self._url_var = tk.StringVar()
        url_e = tk.Entry(nav, textvariable=self._url_var, bg=SURFACE2, fg=FG,
                         insertbackground=FG, relief="flat", font=FONT_MONO)
        url_e.pack(side="left", fill="x", expand=True, padx=8, pady=8)
        url_e.bind("<Return>",  lambda e: self._go())
        url_e.bind("<FocusIn>", lambda e: url_e.select_range(0, "end"))

        styled_button(nav, "Go", self._go, bg=ACCENT).pack(side="left", padx=2, pady=6)

        eng_menu = tk.OptionMenu(nav, self._engine_var, *SEARCH_ENGINES.keys())
        eng_menu.config(bg=SURFACE2, fg=FG, activebackground=ACCENT, relief="flat",
                        font=("Segoe UI", 9), highlightthickness=0, bd=0, padx=4)
        eng_menu["menu"].config(bg=SURFACE2, fg=FG, activebackground=ACCENT)
        eng_menu.pack(side="left", padx=4, pady=6)

        styled_button(nav, "★", self.add_bookmark, bg=SURFACE2, width=2).pack(side="left", padx=2, pady=6)
        styled_button(nav, "+ Tab", self._on_new_tab, bg=SURFACE2).pack(side="left", padx=4, pady=6)

        # Bookmarks bar
        self._bm_bar = tk.Frame(self, bg="#141414", height=26)
        self._bm_bar.pack(fill="x")
        self._bm_bar.pack_propagate(False)
        self._rebuild_bookmarks()

        # Status bar
        self._status = tk.Label(self, text="  WamOS Native Browser — no external browser required",
                                bg="#0a0a0a", fg=FG_DIM, font=("Segoe UI", 9), anchor="w", padx=8)
        self._status.pack(fill="x", side="bottom")

        # Content area
        cf = tk.Frame(self, bg="#0a0a0a")
        cf.pack(fill="both", expand=True)
        self._content = tk.Text(
            cf, wrap="word", bg="#0f0f0f", fg=FG,
            font=("Segoe UI", 11), padx=22, pady=16,
            relief="flat", state="disabled", cursor="arrow",
            selectbackground=ACCENT, selectforeground=FG,
            spacing1=2, spacing3=2
        )
        vsb = tk.Scrollbar(cf, orient="vertical", command=self._content.yview)
        self._content.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._content.pack(fill="both", expand=True)

        # Text tags
        self._content.tag_configure("h1",     font=("Segoe UI", 20, "bold"), foreground=FG,      spacing1=8, spacing3=4)
        self._content.tag_configure("h2",     font=("Segoe UI", 15, "bold"), foreground=ACCENT,  spacing1=6, spacing3=2)
        self._content.tag_configure("h3",     font=("Segoe UI", 12, "bold"), foreground=FG_DIM,  spacing1=4)
        self._content.tag_configure("rule",   foreground=SURFACE2)
        self._content.tag_configure("code",   font=FONT_MONO, background=SURFACE, foreground="#e0e0e0")
        self._content.tag_configure("bold",   font=("Segoe UI", 11, "bold"))
        self._content.tag_configure("italic", font=("Segoe UI", 11, "italic"), foreground=FG_DIM)
        self._content.tag_configure("dim",    foreground=FG_DIM)
        self._content.tag_configure("amber",  foreground=AMBER)
        self._content.tag_configure("err",    foreground=RED)
        self._content.tag_configure("link",   foreground=ACCENT, underline=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────

    def _new_tab(self, url="about:blank", switch=True):
        tab = _Tab()
        self._tabs.append(tab)
        idx = len(self._tabs) - 1
        if switch:
            self._active = idx
        self._rebuild_strip()
        if switch:
            self.navigate(url, tab=tab)

    def _on_new_tab(self):
        self._new_tab("about:blank", switch=True)

    def _switch_tab(self, idx):
        self._active = idx
        tab = self._tabs[idx]
        self._url_var.set(tab.url)
        self._rebuild_strip()
        if tab._text:
            self._render_text(tab._text, tab.links)
        else:
            self._set_plain("(empty)", "dim")

    def _close_tab(self, idx):
        if len(self._tabs) == 1:
            self._tabs[idx] = _Tab()
            self._switch_tab(0)
            self.navigate("about:blank", tab=self._tabs[0])
            return
        del self._tabs[idx]
        new = min(self._active, len(self._tabs) - 1)
        self._active = new
        self._rebuild_strip()
        self._switch_tab(new)

    def _rebuild_strip(self):
        for w in self._tab_strip.winfo_children():
            w.destroy()
        for i, tab in enumerate(self._tabs):
            active = (i == self._active)
            bg = ACCENT if active else SURFACE2
            f = tk.Frame(self._tab_strip, bg=bg, padx=2, pady=2)
            f.pack(side="left", padx=2, pady=3)
            title = (tab.title[:18] + "…") if len(tab.title) > 18 else tab.title
            lbl = tk.Label(f, text=f"  {title}  ", bg=bg, fg=FG, font=FONT_UI, cursor="hand2")
            lbl.pack(side="left")
            lbl.bind("<Button-1>", lambda e, idx=i: self._switch_tab(idx))
            cl = tk.Label(f, text=" ✕ ", bg=bg, fg=FG if active else FG_DIM,
                          font=("Segoe UI", 9), cursor="hand2")
            cl.pack(side="left")
            cl.bind("<Button-1>", lambda e, idx=i: self._close_tab(idx))

    # ── Navigation ────────────────────────────────────────────────────────────

    def _go(self):
        self.navigate(self._url_var.get().strip())

    def _normalize(self, raw):
        raw = raw.strip()
        if not raw or raw == "about:blank":
            return "about:blank"
        if raw.startswith(("http://", "https://")):
            return raw
        if re.match(r'^[\w\-]+\.[\w.\-]+(/|$)', raw) and " " not in raw:
            return "https://" + raw
        tmpl = SEARCH_ENGINES[self._engine_var.get()]
        return tmpl.format(quote_plus(raw))

    def navigate(self, url, push_history=True, tab=None):
        url = self._normalize(url)
        if tab is None:
            tab = self._tabs[self._active]
        tab.url = url
        self._url_var.set(url)

        if push_history:
            if tab.hist_pos < len(tab.history) - 1:
                tab.history = tab.history[:tab.hist_pos + 1]
            tab.history.append(url)
            tab.hist_pos = len(tab.history) - 1

        if url == "about:blank":
            tab.title = "New Tab"
            tab._text = START_TEXT
            tab.links = list(START_LINKS)
            self._render_text(START_TEXT, START_LINKS)
            self._rebuild_strip()
            self._status.config(text="  WamOS Native Browser — home")
            return

        self._set_plain(f"  ⌛  Loading {url} …", "amber")
        self._status.config(text=f"  Fetching …")
        threading.Thread(target=self._fetch, args=(url, tab), daemon=True).start()

    def _fetch(self, url, tab):
        try:
            r = requests.get(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
                    "Accept-Language": "en-US,en;q=0.9",
                },
                timeout=20,
                allow_redirects=True,
            )
            ct = r.headers.get("content-type", "")
            if "html" not in ct and "text" not in ct:
                self.after(0, lambda: self._set_plain(
                    f"  Cannot display binary content.\n  Content-Type: {ct}\n  URL: {url}", "dim"))
                return

            renderer = RichHTMLRenderer(base_url=url)
            text, links = renderer.render(r.text)

            soup_title = BeautifulSoup(r.text, "html.parser").find("title")
            title = soup_title.get_text(strip=True) if soup_title else urlparse(url).netloc
            title = title[:60]

            capped = []
            for ln in text.splitlines():
                capped.append(ln[:400] + " …" if len(ln) > 400 else ln)
            text = "\n".join(capped)

            if links:
                text += "\n\n" + "─" * 72 + "\nLinks on this page:\n"
                for i, (lbl, href) in enumerate(links, 1):
                    short = href if len(href) < 68 else href[:65] + "…"
                    text += f"  [{lbl}]({i})  →  {short}\n"

            def done():
                tab.title = title
                tab._text = text
                tab.links = links
                if self._tabs[self._active] is tab:
                    self._render_text(text, links)
                    self._status.config(
                        text=f"  ✓  {title}  •  {len(text):,} chars  •  {len(links)} links")
                self._rebuild_strip()
                hist = self.app.state.setdefault("browser_history", [])
                if not hist or hist[-1] != url:
                    hist.append(url)
                    if len(hist) > 200:
                        self.app.state["browser_history"] = hist[-200:]

            self.after(0, done)

        except requests.exceptions.Timeout:
            self.after(0, lambda: self._error(url, "Request timed out (20 s)"))
        except requests.exceptions.SSLError as exc:
            self.after(0, lambda: self._error(url, f"SSL error: {exc}"))
        except requests.exceptions.ConnectionError as exc:
            self.after(0, lambda: self._error(url, f"Connection error: {exc}"))
        except Exception as exc:
            self.after(0, lambda: self._error(url, str(exc)))

    def _error(self, url, msg):
        t = (f"█ Page could not be loaded\n"
             f"══════════════════════════════════════\n\n"
             f"  URL: {url}\n\n"
             f"  {msg}\n\n"
             f"  • Check your internet connection\n"
             f"  • The site may block automated requests\n"
             f"  • Try a different URL or search term\n")
        self._set_plain(t, "err")
        self._status.config(text="  ✗  Failed to load page")

    def go_back(self):
        tab = self._tabs[self._active]
        if tab.hist_pos > 0:
            tab.hist_pos -= 1
            self.navigate(tab.history[tab.hist_pos], push_history=False, tab=tab)

    def go_forward(self):
        tab = self._tabs[self._active]
        if tab.hist_pos < len(tab.history) - 1:
            tab.hist_pos += 1
            self.navigate(tab.history[tab.hist_pos], push_history=False, tab=tab)

    def reload(self):
        tab = self._tabs[self._active]
        if tab.url:
            self.navigate(tab.url, push_history=False, tab=tab)

    def _rebuild_bookmarks(self):
        for w in self._bm_bar.winfo_children():
            w.destroy()
        tk.Label(self._bm_bar, text=" ★ ", bg="#141414", fg=ACCENT,
                 font=("Segoe UI", 9)).pack(side="left")
        for bm in self.app.state.get("bookmarks", []):
            label = bm.replace("https://", "").replace("http://", "").split("/")[0][:22]
            tk.Button(
                self._bm_bar, text=label, bg="#141414", fg=FG_DIM,
                relief="flat", cursor="hand2", font=("Segoe UI", 9),
                activebackground=SURFACE2, activeforeground=FG, bd=0, padx=6,
                command=lambda u=bm: self.navigate(u)
            ).pack(side="left", pady=2)

    def add_bookmark(self):
        url = self._url_var.get().strip()
        if not url or url == "about:blank":
            return
        bms = self.app.state.setdefault("bookmarks", [])
        if url not in bms:
            bms.append(url)
            self.app.save_state()
            self._rebuild_bookmarks()
            self._status.config(text="  ★  Bookmarked")

    def _set_plain(self, text, tag=""):
        self._content.configure(state="normal")
        self._content.delete("1.0", "end")
        self._content.insert("end", text, tag)
        self._content.configure(state="disabled")
        self._content.yview_moveto(0)

    def _render_text(self, text, links):
        self._content.configure(state="normal")
        self._content.delete("1.0", "end")

        INLINE = re.compile(
            r'(\*\*[^*]+\*\*)'
            r'|(_[^_\n]+_)'
            r'|(`[^`\n]+`)'
            r'|(\[([^\]\n]+)\]\((\d+)\))'
        )

        for line in text.split("\n"):
            if line.startswith("█ "):
                self._content.insert("end", line[2:] + "\n", "h1")
                continue
            if line.startswith("▌ "):
                self._content.insert("end", line[2:] + "\n", "h2")
                continue
            if line.startswith("◆ "):
                self._content.insert("end", line[2:] + "\n", "h3")
                continue
            if re.match(r'^[═─]{4,}$', line.strip()):
                self._content.insert("end", line + "\n", "rule")
                continue
            if line.startswith("  │ "):
                self._content.insert("end", line + "\n", "code")
                continue
            if line.startswith("  ┃ "):
                self._content.insert("end", line[4:] + "\n", "italic")
                continue

            pos = 0
            for m in INLINE.finditer(line):
                before = line[pos:m.start()]
                if before:
                    self._content.insert("end", before)
                full = m.group(0)
                if full.startswith("**"):
                    self._content.insert("end", full[2:-2], "bold")
                elif full.startswith("_") and full.endswith("_"):
                    self._content.insert("end", full[1:-1], "italic")
                elif full.startswith("`"):
                    self._content.insert("end", full[1:-1], "code")
                elif m.group(4):
                    lbl = m.group(5)
                    n = int(m.group(6)) - 1
                    tn = f"_link_{n}"
                    self._content.tag_configure(tn, foreground=ACCENT, underline=True)
                    self._content.tag_bind(tn, "<Button-1>",
                        lambda e, i=n, lks=links: self._follow(i, lks))
                    self._content.tag_bind(tn, "<Enter>",
                        lambda e, i=n, lks=links: self._hover(i, lks))
                    self._content.tag_bind(tn, "<Leave>",
                        lambda e: (self._content.configure(cursor="arrow"),
                                   self._status.config(text="")))
                    self._content.insert("end", lbl, (tn, "link"))
                pos = m.end()
            rest = line[pos:]
            if rest:
                self._content.insert("end", rest)
            self._content.insert("end", "\n")

        self._content.configure(state="disabled")
        self._content.yview_moveto(0)

    def _follow(self, idx, links):
        if 0 <= idx < len(links):
            _, href = links[idx]
            if href:
                self.navigate(href)

    def _hover(self, idx, links):
        self._content.configure(cursor="hand2")
        if 0 <= idx < len(links):
            self._status.config(text=f"  → {links[idx][1]}")


# ─────────────────────────────────────────────────────────────────────────────
# Package Manager
# ─────────────────────────────────────────────────────────────────────────────
class PackageManagerWindow(BaseWindow):
    def __init__(self, app):
        super().__init__(app, "packages", "900x600")
        self._filter_var = tk.StringVar()
        self._cat_var    = tk.StringVar(value="All")
        self._build()

    def _build(self):
        # Toolbar
        tb = tk.Frame(self, bg=PANEL_BG, height=44)
        tb.pack(fill="x")
        tb.pack_propagate(False)
        tk.Label(tb, text="📦  WamOS Package Manager", bg=PANEL_BG, fg=FG, font=FONT_TITLE).pack(side="left", padx=12)

        # Category filter
        categories = ["All", "Python", "Network", "Dev", "System", "Media"]
        cat_menu = tk.OptionMenu(tb, self._cat_var, *categories, command=lambda _: self._refresh_list())
        cat_menu.config(bg=SURFACE2, fg=FG, activebackground=ACCENT, relief="flat",
                        font=FONT_UI, highlightthickness=0, bd=0, padx=6)
        cat_menu["menu"].config(bg=SURFACE2, fg=FG, activebackground=ACCENT)
        cat_menu.pack(side="right", padx=8, pady=8)
        tk.Label(tb, text="Category:", bg=PANEL_BG, fg=FG_DIM, font=FONT_UI).pack(side="right", pady=8)

        # Search bar
        search_frame = tk.Frame(self, bg=SURFACE, height=36)
        search_frame.pack(fill="x")
        search_frame.pack_propagate(False)
        tk.Label(search_frame, text="🔍", bg=SURFACE, fg=FG_DIM, font=FONT_UI).pack(side="left", padx=8)
        se = tk.Entry(search_frame, textvariable=self._filter_var, bg=SURFACE, fg=FG,
                      insertbackground=FG, relief="flat", font=FONT_UI)
        se.pack(side="left", fill="x", expand=True, pady=6)
        se.bind("<KeyRelease>", lambda e: self._refresh_list())

        # Main layout
        main = tk.Frame(self, bg=DARK_BG)
        main.pack(fill="both", expand=True)

        # Left: package list
        lf = tk.Frame(main, bg=SURFACE)
        lf.pack(side="left", fill="both", expand=True, padx=(6, 3), pady=6)
        hdr = tk.Frame(lf, bg=PANEL_BG)
        hdr.pack(fill="x")
        tk.Label(hdr, text="  Package",   bg=PANEL_BG, fg=FG_DIM, font=FONT_UI, width=20, anchor="w").pack(side="left")
        tk.Label(hdr, text="Category",    bg=PANEL_BG, fg=FG_DIM, font=FONT_UI, width=10).pack(side="left")
        tk.Label(hdr, text="Type",        bg=PANEL_BG, fg=FG_DIM, font=FONT_UI, width=8).pack(side="left")
        tk.Label(hdr, text="Status",      bg=PANEL_BG, fg=FG_DIM, font=FONT_UI, width=10).pack(side="left")
        self._listbox = tk.Listbox(lf, bg=SURFACE, fg=FG, font=FONT_MONO,
                                   selectbackground=ACCENT, selectforeground=FG,
                                   relief="flat", bd=0, activestyle="none")
        scr = tk.Scrollbar(lf, orient="vertical", command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scr.set)
        scr.pack(side="right", fill="y")
        self._listbox.pack(fill="both", expand=True)
        self._listbox.bind("<<ListboxSelect>>", self._on_select)

        # Right: detail + action panel
        right = tk.Frame(main, bg=PANEL_BG, width=260)
        right.pack(side="right", fill="y", padx=(3, 6), pady=6)
        right.pack_propagate(False)

        tk.Label(right, text="Package Details", bg=PANEL_BG, fg=FG, font=FONT_TITLE).pack(pady=(12, 4))
        self._name_lbl  = tk.Label(right, text="—", bg=PANEL_BG, fg=FG,      font=("Segoe UI", 12, "bold"))
        self._name_lbl.pack(padx=12, anchor="w")
        self._cat_lbl   = tk.Label(right, text="",  bg=PANEL_BG, fg=ACCENT,   font=("Segoe UI", 9))
        self._cat_lbl.pack(padx=12, anchor="w")
        self._desc_lbl  = tk.Label(right, text="",  bg=PANEL_BG, fg=FG_DIM,   font=FONT_UI, wraplength=230, justify="left")
        self._desc_lbl.pack(padx=12, pady=6, anchor="w")
        self._type_lbl  = tk.Label(right, text="",  bg=PANEL_BG, fg=FG_DIM,   font=("Segoe UI", 9))
        self._type_lbl.pack(padx=12, anchor="w")
        self._stat_lbl  = tk.Label(right, text="",  bg=PANEL_BG, fg=GREEN,    font=("Segoe UI", 9, "bold"))
        self._stat_lbl.pack(padx=12, pady=4, anchor="w")

        tk.Frame(right, bg=SURFACE2, height=1).pack(fill="x", padx=10, pady=10)

        self._install_btn = styled_button(right, "⬇ Install", self._install_selected, bg=ACCENT, width=20)
        self._install_btn.pack(fill="x", padx=12, pady=4)
        self._remove_btn  = styled_button(right, "🗑 Uninstall", self._remove_selected, bg=SURFACE2, width=20)
        self._remove_btn.pack(fill="x", padx=12, pady=4)

        tk.Frame(right, bg=SURFACE2, height=1).pack(fill="x", padx=10, pady=10)

        # Log / output
        tk.Label(right, text="Output", bg=PANEL_BG, fg=FG_DIM, font=FONT_TITLE).pack(padx=12, anchor="w")
        self._log = tk.Text(right, bg=SURFACE, fg="#a3e635", font=("Consolas", 9),
                            relief="flat", wrap="word", state="disabled", height=8)
        self._log.pack(fill="both", expand=True, padx=8, pady=(4, 8))

        self._pkg_keys = []  # visible package names in list
        self._refresh_list()

    def _installed(self):
        return self.app.state.get("installed_packages", [])

    def _refresh_list(self):
        self._listbox.delete(0, "end")
        self._pkg_keys = []
        q   = self._filter_var.get().lower()
        cat = self._cat_var.get()
        for name, info in sorted(PACKAGE_REGISTRY.items()):
            if q and q not in name.lower() and q not in info["desc"].lower():
                continue
            if cat != "All" and info.get("category", "") != cat:
                continue
            status    = "✓ installed" if name in self._installed() else "available"
            type_tag  = "pip" if info["type"] == "pip" else "system"
            self._listbox.insert("end",
                f"  {name:<22} {info.get('category',''):<12} {type_tag:<8} {status}")
            self._pkg_keys.append(name)

    def _on_select(self, e=None):
        sel = self._listbox.curselection()
        if not sel or sel[0] >= len(self._pkg_keys):
            return
        name = self._pkg_keys[sel[0]]
        info = PACKAGE_REGISTRY[name]
        self._name_lbl.config(text=name)
        self._cat_lbl.config(text=info.get("category", ""))
        self._desc_lbl.config(text=info["desc"])
        self._type_lbl.config(text=f"Type: {info['type'].upper()}" +
                              (f"  |  pip pkg: {info.get('pkg','')}" if info["type"] == "pip" else " (simulated)"))
        if name in self._installed():
            self._stat_lbl.config(text="● Installed", fg=GREEN)
            self._install_btn.config(state="disabled", bg=SURFACE2)
            self._remove_btn.config(state="normal",   bg=RED)
        else:
            self._stat_lbl.config(text="○ Not installed", fg=FG_DIM)
            self._install_btn.config(state="normal",  bg=ACCENT)
            self._remove_btn.config(state="disabled", bg=SURFACE2)

    def _log_write(self, text):
        self._log.configure(state="normal")
        self._log.insert("end", text + "\n")
        self._log.see("end")
        self._log.configure(state="disabled")

    def _install_selected(self):
        sel = self._listbox.curselection()
        if not sel or sel[0] >= len(self._pkg_keys):
            return
        name = self._pkg_keys[sel[0]]
        info = PACKAGE_REGISTRY[name]
        self._install_btn.config(state="disabled", text="Installing…")
        self._log_write(f"[wam] Installing {name}…")

        def do_install():
            if info["type"] == "pip":
                try:
                    result = subprocess.run(
                        [sys.executable, "-m", "pip", "install", info["pkg"], "--quiet"],
                        capture_output=True, text=True, timeout=120
                    )
                    if result.returncode == 0:
                        self.after(0, lambda: self._finish_install(name, success=True,
                                   msg=f"[pip] {info['pkg']} installed successfully."))
                    else:
                        err = result.stderr.strip().splitlines()[-1] if result.stderr else "Unknown error"
                        self.after(0, lambda: self._finish_install(name, success=False,
                                   msg=f"[pip] Error: {err}"))
                except subprocess.TimeoutExpired:
                    self.after(0, lambda: self._finish_install(name, success=False,
                               msg="[pip] Timed out after 120 s."))
                except Exception as ex:
                    self.after(0, lambda: self._finish_install(name, success=False, msg=str(ex)))
            else:
                # Simulated system install
                import time; time.sleep(1.2)
                self.after(0, lambda: self._finish_install(name, success=True,
                           msg=f"[sys] {name} registered in WamOS package store."))

        threading.Thread(target=do_install, daemon=True).start()

    def _finish_install(self, name, success, msg):
        self._log_write(msg)
        if success:
            pkgs = self.app.state.setdefault("installed_packages", [])
            if name not in pkgs:
                pkgs.append(name)
            self.app.save_state()
        self._install_btn.config(text="⬇ Install")
        self._refresh_list()
        self._on_select()

    def _remove_selected(self):
        sel = self._listbox.curselection()
        if not sel or sel[0] >= len(self._pkg_keys):
            return
        name = self._pkg_keys[sel[0]]
        if not messagebox.askyesno("uninstall", f"Remove '{name}' from WamOS?", parent=self):
            return
        pkgs = self.app.state.get("installed_packages", [])
        if name in pkgs:
            pkgs.remove(name)
            self.app.save_state()
        self._log_write(f"[wam] {name} removed.")
        self._refresh_list()
        self._on_select()


# ─────────────────────────────────────────────────────────────────────────────
# Settings
# ─────────────────────────────────────────────────────────────────────────────
class SettingsWindow(BaseWindow):
    def __init__(self, app):
        super().__init__(app, "settings", "560x520")
        self._build()

    def _build(self):
        style = ttk.Style(self)
        style.configure("TNotebook",     background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=SURFACE2, foreground=FG, padding=[12, 5], font=FONT_UI)
        style.map("TNotebook.Tab", background=[("selected", ACCENT)])

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=8)

        # ── Profile tab ────────────────────────────────────────────────────
        profile = tk.Frame(nb, bg=DARK_BG)
        nb.add(profile, text=" Profile ")
        tk.Label(profile, text="Username", bg=DARK_BG, fg=FG_DIM, font=FONT_UI).pack(anchor="w", padx=24, pady=(22, 4))
        self.uname = styled_entry(profile)
        self.uname.insert(0, self.app.state.get("username", "user"))
        self.uname.pack(fill="x", padx=24)

        # ── Appearance tab ─────────────────────────────────────────────────
        appear = tk.Frame(nb, bg=DARK_BG)
        nb.add(appear, text=" Appearance ")

        # Wallpaper color
        tk.Label(appear, text="Wallpaper Color", bg=DARK_BG, fg=FG_DIM, font=FONT_UI).pack(anchor="w", padx=24, pady=(18, 4))
        wp_row = tk.Frame(appear, bg=DARK_BG)
        wp_row.pack(fill="x", padx=24)
        self.wp_var = tk.StringVar(value=self.app.state.get("wallpaper", DARK_BG))
        self.wp_entry = styled_entry(wp_row, textvariable=self.wp_var)
        self.wp_entry.pack(side="left", fill="x", expand=True)
        self.wp_preview = tk.Label(wp_row, bg=self.wp_var.get(), width=5, relief="flat")
        self.wp_preview.pack(side="left", padx=8, ipady=8)
        self.wp_var.trace_add("write", self._update_wp_preview)
        styled_button(wp_row, "Pick…", self._pick_wallpaper, bg=SURFACE2).pack(side="left")

        # Wallpaper image
        tk.Label(appear, text="Background Image (path to PNG/GIF/JPEG)", bg=DARK_BG, fg=FG_DIM, font=FONT_UI).pack(anchor="w", padx=24, pady=(14, 4))
        img_row = tk.Frame(appear, bg=DARK_BG)
        img_row.pack(fill="x", padx=24)
        self.img_var = tk.StringVar(value=self.app.state.get("wallpaper_image", ""))
        img_entry = styled_entry(img_row, textvariable=self.img_var)
        img_entry.pack(side="left", fill="x", expand=True)
        styled_button(img_row, "Browse…", self._browse_image, bg=SURFACE2).pack(side="left", padx=(6, 0))
        styled_button(img_row, "Clear",   self._clear_image,  bg=SURFACE2).pack(side="left", padx=(4, 0))

        # Accent color
        tk.Label(appear, text="Accent Color", bg=DARK_BG, fg=FG_DIM, font=FONT_UI).pack(anchor="w", padx=24, pady=(14, 4))
        ac_row = tk.Frame(appear, bg=DARK_BG)
        ac_row.pack(fill="x", padx=24)
        self.ac_var = tk.StringVar(value=self.app.state.get("accent_color", ACCENT))
        self.ac_entry = styled_entry(ac_row, textvariable=self.ac_var)
        self.ac_entry.pack(side="left", fill="x", expand=True)
        self.ac_preview = tk.Label(ac_row, bg=self.ac_var.get(), width=5, relief="flat")
        self.ac_preview.pack(side="left", padx=8, ipady=8)
        self.ac_var.trace_add("write", self._update_ac_preview)
        styled_button(ac_row, "Pick…", self._pick_accent, bg=SURFACE2).pack(side="left")

        # Presets row
        tk.Label(appear, text="Quick Presets", bg=DARK_BG, fg=FG_DIM, font=FONT_UI).pack(anchor="w", padx=24, pady=(14, 6))
        presets_frame = tk.Frame(appear, bg=DARK_BG)
        presets_frame.pack(fill="x", padx=24)
        presets = [
            ("WamOS Red",    "#1a1a1a", "#c0392b"),
            ("Dark Blue",    "#0d1117", "#58a6ff"),
            ("Deep Purple",  "#120a1e", "#8b5cf6"),
            ("Forest Green", "#0a1a0e", "#22c55e"),
            ("Midnight",     "#080808", "#e2e8f0"),
        ]
        for label, wall, acc in presets:
            def apply_preset(w=wall, a=acc):
                self.wp_var.set(w)
                self.ac_var.set(a)
            tk.Button(presets_frame, text=label, command=apply_preset,
                      bg=acc, fg="#000" if acc in ("#e2e8f0", "#22c55e", "#58a6ff") else "#fff",
                      relief="flat", cursor="hand2", font=("Segoe UI", 9), padx=8, pady=4, bd=0
                      ).pack(side="left", padx=(0, 6), pady=2)

        # ── System tab ─────────────────────────────────────────────────────
        system = tk.Frame(nb, bg=DARK_BG)
        nb.add(system, text=" System ")
        tk.Label(system, text="System Information", bg=DARK_BG, fg=FG, font=FONT_TITLE).pack(anchor="w", padx=24, pady=(18, 8))
        info_frame = tk.Frame(system, bg=SURFACE, padx=16, pady=12)
        info_frame.pack(fill="x", padx=24)
        pkgs_count = len(self.app.state.get("installed_packages", []))
        py_ver     = sys.version.split()[0]
        infos = [
            ("OS",              APP_NAME),
            ("Python",          py_ver),
            ("Data directory",  str(DATA_DIR)),
            ("Installed pkgs",  str(pkgs_count)),
            ("Files",           str(len(self.app.state["filesystem"].get("home", {}))) + " items in home"),
            ("Notes",           str(len(self.app.state.get("notes_list", {}))) + " notes"),
        ]
        for key, val in infos:
            row = tk.Frame(info_frame, bg=SURFACE)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=f"{key}:", bg=SURFACE, fg=FG_DIM, font=FONT_UI, width=16, anchor="w").pack(side="left")
            tk.Label(row, text=val,        bg=SURFACE, fg=FG,     font=FONT_UI, anchor="w").pack(side="left")

        styled_button(system, "🗑  Reset All Data", self._reset_data, bg=RED, fg=FG).pack(anchor="w", padx=24, pady=16)

        # ── About tab ──────────────────────────────────────────────────────
        about = tk.Frame(nb, bg=DARK_BG)
        nb.add(about, text=" About ")
        tk.Label(about, text="\nWamOS", bg=DARK_BG, fg=ACCENT, font=("Segoe UI", 26, "bold")).pack()
        tk.Label(about, text="Virtual Operating System", bg=DARK_BG, fg=FG, font=("Segoe UI", 12)).pack()
        tk.Label(about, text="Built with Python & Tkinter\n", bg=DARK_BG, fg=FG_DIM, font=FONT_UI).pack()
        tk.Frame(about, bg=SURFACE2, height=1).pack(fill="x", padx=40, pady=8)
        tk.Label(about, text=(
            "Apps:  Browser · Files · Notes · Editor\n"
            "       Terminal · Calculator · Packages · Settings\n\n"
            "Native browser — no Chrome or external app required.\n"
            "Package manager — install Python libs via pip."
        ), bg=DARK_BG, fg=FG_DIM, font=FONT_UI, justify="center").pack(pady=8)

        # Save button
        styled_button(self, "✓  Save Settings", self.save, bg=ACCENT, pady=8).pack(fill="x", padx=20, pady=10)

    def _update_wp_preview(self, *_):
        try:
            self.wp_preview.config(bg=self.wp_var.get())
        except Exception:
            pass

    def _update_ac_preview(self, *_):
        try:
            self.ac_preview.config(bg=self.ac_var.get())
        except Exception:
            pass

    def _pick_wallpaper(self):
        c = colorchooser.askcolor(color=self.wp_var.get(), parent=self)
        if c and c[1]:
            self.wp_var.set(c[1])

    def _pick_accent(self):
        c = colorchooser.askcolor(color=self.ac_var.get(), parent=self)
        if c and c[1]:
            self.ac_var.set(c[1])

    def _browse_image(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Select background image",
            filetypes=[("Images", "*.png *.gif *.ppm *.pgm *.jpg *.jpeg"), ("All files", "*.*")]
        )
        if path:
            self.img_var.set(path)

    def _clear_image(self):
        self.img_var.set("")

    def _reset_data(self):
        if messagebox.askyesno("Reset", "This will erase all WamOS data. Continue?", parent=self):
            self.app.state.update(deep_copy(DEFAULT_STATE))
            self.app.save_state()
            messagebox.showinfo("Reset", "Data reset. Please restart WamOS.", parent=self)

    def save(self):
        self.app.state["username"] = self.uname.get().strip() or "user"

        wp = self.wp_var.get().strip() or DARK_BG
        self.app.state["wallpaper"] = wp

        img = self.img_var.get().strip()
        self.app.state["wallpaper_image"] = img

        ac = self.ac_var.get().strip() or ACCENT
        self.app.state["accent_color"] = ac

        self.app.apply_wallpaper(wp, img)
        self.app.apply_accent(ac)
        self.app.taskbar_user.config(text=self.app.state["username"])
        self.app.save_state()

        lbl = tk.Label(self, text="✓  Settings saved", bg=DARK_BG, fg=GREEN, font=FONT_UI)
        lbl.pack()
        self.after(2200, lbl.destroy)


# ─────────────────────────────────────────────────────────────────────────────
# WamOS shell
# ─────────────────────────────────────────────────────────────────────────────
class WamOS:
    def __init__(self):
        global ACCENT
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.state = self._load_state()
        self.fs    = VirtualFS(self.state)
        self._open_windows = {}

        # Apply saved accent
        saved_accent = self.state.get("accent_color", ACCENT)
        ACCENT = saved_accent

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("1280x800")
        self.root.minsize(960, 600)
        self.root.configure(bg=self.state.get("wallpaper", DARK_BG))
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

        style = ttk.Style(self.root)
        try:
            style.theme_use("default")
        except Exception:
            pass
        style.configure("TNotebook",     background=DARK_BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=SURFACE2, foreground=FG, padding=[10, 4], font=FONT_UI)
        style.map("TNotebook.Tab",       background=[("selected", ACCENT)])

        self._build_ui()
        self._apply_bg_image(self.state.get("wallpaper_image", ""))
        self.update_clock()
        self.root.after(5000, self._autosave_loop)

    def _load_state(self):
        if DATA_FILE.exists():
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    state = json.load(f)
                for k, v in DEFAULT_STATE.items():
                    state.setdefault(k, deep_copy(v))
                return state
            except Exception:
                pass
        return deep_copy(DEFAULT_STATE)

    def save_state(self):
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def _autosave_loop(self):
        self.save_state()
        self.root.after(5000, self._autosave_loop)

    def _build_ui(self):
        # ── Top bar ─────────────────────────────────────────────────────────
        self.topbar = tk.Frame(self.root, bg=PANEL_BG, height=38)
        self.topbar.pack(side="top", fill="x")
        self.topbar.pack_propagate(False)

        # WamOS logo + start button
        logo_frame = tk.Frame(self.topbar, bg=ACCENT)
        logo_frame.pack(side="left")
        tk.Button(logo_frame, text=f"  ⊞ {APP_NAME}  ", command=self.toggle_menu,
                  bg=ACCENT, fg=FG, relief="flat", cursor="hand2",
                  font=("Segoe UI", 10, "bold"), bd=0, padx=6).pack(pady=4, padx=2)

        self.clock_label = tk.Label(self.topbar, text="", bg=PANEL_BG, fg=FG, font=FONT_UI)
        self.clock_label.pack(side="right", padx=14)

        self.taskbar_user = tk.Label(self.topbar, text=self.state.get("username", "user"),
                                     bg=PANEL_BG, fg=FG_DIM, font=FONT_UI)
        self.taskbar_user.pack(side="right", padx=8)
        tk.Frame(self.topbar, bg=SURFACE2, width=1).pack(side="right", fill="y", pady=6)

        # ── Desktop ─────────────────────────────────────────────────────────
        self.desktop = tk.Frame(self.root, bg=self.state.get("wallpaper", DARK_BG))
        self.desktop.pack(fill="both", expand=True)
        self.desktop.bind("<Button-1>", lambda e: self.close_menu())
        self._bg_label = None  # background image label

        # ── Taskbar ─────────────────────────────────────────────────────────
        self.taskbar = tk.Frame(self.root, bg=PANEL_BG, height=42)
        self.taskbar.pack(side="bottom", fill="x")
        self.taskbar.pack_propagate(False)
        self.taskbar_windows_frame = tk.Frame(self.taskbar, bg=PANEL_BG)
        self.taskbar_windows_frame.pack(side="left", fill="y", padx=4)

        # ── Desktop icons ───────────────────────────────────────────────────
        self.icon_frame = tk.Frame(self.desktop, bg=self.state.get("wallpaper", DARK_BG))
        self.icon_frame.place(x=18, y=18)
        self._build_desktop_icons()

        # ── Start menu ──────────────────────────────────────────────────────
        self.start_menu = tk.Frame(self.root, bg=SURFACE, bd=0, relief="flat")
        self.menu_open  = False
        self._build_start_menu()
        self.root.bind("<Escape>", lambda e: self.close_menu())

    def _build_desktop_icons(self):
        for w in self.icon_frame.winfo_children():
            w.destroy()
        apps = [
            ("🌐", "browser",   self.open_browser),
            ("📁", "files",     self.open_files),
            ("📝", "notes",     self.open_notes),
            ("✏️",  "editor",   self.open_editor),
            ("🖥️", "terminal",  self.open_terminal),
            ("🧮", "calculator",self.open_calculator),
            ("📦", "packages",  self.open_packages),
            ("⚙️",  "settings", self.open_settings),
        ]
        bg = self.state.get("wallpaper", DARK_BG)
        for i, (icon, label, cmd) in enumerate(apps):
            col = tk.Frame(self.icon_frame, bg=bg)
            col.grid(row=i, column=0, padx=4, pady=5, sticky="w")
            tk.Button(col, text=f"{icon}\n{label}", command=cmd,
                      bg=SURFACE, fg=FG, relief="flat", cursor="hand2",
                      activebackground=ACCENT, font=FONT_UI, width=8, height=3,
                      bd=0, wraplength=70).pack()

    def _build_start_menu(self):
        for w in self.start_menu.winfo_children():
            w.destroy()
        header = tk.Frame(self.start_menu, bg=ACCENT, height=52)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(header, text=f"  {APP_NAME}", bg=ACCENT, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left", padx=12, pady=12)
        items = [
            ("🌐  Browser",    self.open_browser),
            ("📁  Files",      self.open_files),
            ("📝  Notes",      self.open_notes),
            ("✏️   Editor",    self.open_editor),
            ("🖥️  Terminal",   self.open_terminal),
            ("🧮  Calculator", self.open_calculator),
            ("📦  Packages",   self.open_packages),
            ("⚙️   Settings",  self.open_settings),
        ]
        for label, action in items:
            def _cmd(a=action):
                self.close_menu()
                a()
            tk.Button(self.start_menu, text=f"  {label}", anchor="w", width=24,
                      command=_cmd, bg=SURFACE, fg=FG, relief="flat",
                      activebackground=ACCENT, cursor="hand2", font=FONT_UI,
                      pady=7, bd=0).pack(fill="x")
        tk.Frame(self.start_menu, bg=SURFACE2, height=1).pack(fill="x", padx=6, pady=4)
        tk.Button(self.start_menu, text="  ⏻  Shut Down", anchor="w", width=24,
                  command=self.shutdown, bg=SURFACE, fg=RED, relief="flat",
                  activebackground="#2a0a0a", cursor="hand2", font=FONT_UI,
                  pady=7, bd=0).pack(fill="x")

    def toggle_menu(self):
        if self.menu_open:
            self.close_menu()
        else:
            self.start_menu.place(x=6, rely=1.0, anchor="sw", in_=self.root)
            self.start_menu.lift()
            self.menu_open = True

    def close_menu(self):
        self.start_menu.place_forget()
        self.menu_open = False

    def apply_wallpaper(self, color, image_path=""):
        self.root.configure(bg=color)
        self.desktop.configure(bg=color)
        self.icon_frame.configure(bg=color)
        for w in self.icon_frame.winfo_children():
            try:
                w.configure(bg=color)
                for child in w.winfo_children():
                    try:
                        child.configure(bg=color)
                    except Exception:
                        pass
            except Exception:
                pass
        self._apply_bg_image(image_path)

    def _apply_bg_image(self, path):
        # Remove old background label
        if self._bg_label:
            try:
                self._bg_label.destroy()
            except Exception:
                pass
            self._bg_label = None
        if not path or not os.path.exists(path):
            return
        try:
            try:
                from PIL import Image, ImageTk
                img = Image.open(path)
                # Will resize on configure
                self._pil_img_path = path
                self._bg_photo = ImageTk.PhotoImage(img)
            except ImportError:
                # Fallback: tkinter native (PNG, GIF, PPM only)
                self._bg_photo = tk.PhotoImage(file=path)

            self._bg_label = tk.Label(self.desktop, image=self._bg_photo, bg=self.state.get("wallpaper", DARK_BG))
            self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)
            self._bg_label.lower()  # keep below icons
        except Exception as ex:
            print(f"Background image error: {ex}")

    def apply_accent(self, color):
        global ACCENT
        ACCENT = color
        # Rebuild start menu + desktop with new accent
        self._build_start_menu()
        self._build_desktop_icons()

    def update_clock(self):
        self.clock_label.config(text=datetime.now().strftime(" %a %b %d   %H:%M:%S "))
        self.root.after(1000, self.update_clock)

    def register_window(self, win, title):
        self._open_windows[id(win)] = (win, title)
        self._rebuild_taskbar()

    def unregister_window(self, win):
        self._open_windows.pop(id(win), None)
        self._rebuild_taskbar()

    def _rebuild_taskbar(self):
        for w in self.taskbar_windows_frame.winfo_children():
            w.destroy()
        for wid, (win, title) in list(self._open_windows.items()):
            def _focus(w=win):
                try:
                    w.deiconify()
                    w.lift()
                    w.focus_force()
                except Exception:
                    pass
            tk.Button(self.taskbar_windows_frame, text=f"  {title}  ",
                      command=_focus, bg=SURFACE2, fg=FG, relief="flat",
                      cursor="hand2", font=FONT_UI, pady=6, bd=0,
                      activebackground=ACCENT).pack(side="left", padx=3, pady=6)

    def open_terminal(self):   TerminalWindow(self)
    def open_files(self):      FilesWindow(self)
    def open_notes(self):      NotesWindow(self)
    def open_editor(self):     TextEditorWindow(self)
    def open_calculator(self): CalculatorWindow(self)
    def open_browser(self):    BrowserWindow(self)
    def open_packages(self):   PackageManagerWindow(self)
    def open_settings(self):   SettingsWindow(self)

    def run_terminal_command(self, cmd, output_cb=None):
        """Execute a terminal command and return output string."""
        parts = shlex.split(cmd)
        if not parts:
            return ""
        command, *args = parts

        # ── wam package manager ─────────────────────────────────────────────
        if command == "wam":
            sub = args[0] if args else ""
            if sub == "list":
                pkgs = self.state.get("installed_packages", [])
                if not pkgs:
                    return "  No packages installed. Use: wam install <package>"
                return "  Installed packages:\n" + "\n".join(f"  ✓  {p}" for p in pkgs)

            if sub == "search":
                q = " ".join(args[1:]).lower()
                if not q:
                    return "  usage: wam search <term>"
                results = [(n, i) for n, i in PACKAGE_REGISTRY.items()
                           if q in n.lower() or q in i["desc"].lower()]
                if not results:
                    return f"  No packages found for '{q}'"
                lines = [f"  {'Name':<24} {'Type':<8} {'Category':<12} Description"]
                lines.append("  " + "─" * 62)
                for name, info in sorted(results):
                    lines.append(f"  {name:<24} {info['type']:<8} {info.get('category',''):<12} {info['desc']}")
                return "\n".join(lines)

            if sub == "install":
                if not args[1:]:
                    return "  usage: wam install <package>"
                name = args[1].lower()
                if name not in PACKAGE_REGISTRY:
                    return f"  Package '{name}' not found. Try: wam search {name}"
                if name in self.state.get("installed_packages", []):
                    return f"  '{name}' is already installed."
                if output_cb:
                    output_cb(f"  [wam] Installing {name}…")
                info = PACKAGE_REGISTRY[name]
                if info["type"] == "pip":
                    try:
                        result = subprocess.run(
                            [sys.executable, "-m", "pip", "install", info["pkg"], "--quiet"],
                            capture_output=True, text=True, timeout=120
                        )
                        if result.returncode == 0:
                            pkgs = self.state.setdefault("installed_packages", [])
                            if name not in pkgs:
                                pkgs.append(name)
                            self.save_state()
                            return f"  ✓  {name} installed successfully."
                        else:
                            err = result.stderr.strip().splitlines()[-1] if result.stderr else "Unknown"
                            return f"  ✗  pip error: {err}"
                    except Exception as ex:
                        return f"  ✗  {ex}"
                else:
                    pkgs = self.state.setdefault("installed_packages", [])
                    if name not in pkgs:
                        pkgs.append(name)
                    self.save_state()
                    return f"  ✓  {name} registered in WamOS."

            if sub == "remove":
                if not args[1:]:
                    return "  usage: wam remove <package>"
                name = args[1].lower()
                pkgs = self.state.get("installed_packages", [])
                if name not in pkgs:
                    return f"  '{name}' is not installed."
                pkgs.remove(name)
                self.save_state()
                return f"  ✓  {name} removed."

            return ("  WamOS Package Manager\n"
                    "  usage: wam <command> [args]\n"
                    "  commands:\n"
                    "    wam install <pkg>   install a package\n"
                    "    wam remove <pkg>    remove a package\n"
                    "    wam list            list installed packages\n"
                    "    wam search <term>   search available packages")

        # ── Built-in commands ───────────────────────────────────────────────
        if command == "help":
            return (
                f"  {APP_NAME} Terminal  —  available commands\n"
                "  ─────────────────────────────────────────────\n"
                "  ls [path]           list directory contents\n"
                "  cd <path>           change directory\n"
                "  pwd                 print working directory\n"
                "  cat <file>          read file contents\n"
                "  write <f> <text>    write text to file\n"
                "  touch <file>        create empty file\n"
                "  mkdir <dir>         create directory\n"
                "  rm <name>           delete file or directory\n"
                "  mv <old> <new>      rename file or directory\n"
                "  echo <text>         print text\n"
                "  date                show current date/time\n"
                "  whoami              show username\n"
                "  sysinfo             system information\n"
                "  clear               clear terminal\n"
                "  ─────────────────────────────────────────────\n"
                "  wam install <pkg>   install a package\n"
                "  wam remove <pkg>    remove a package\n"
                "  wam list            list installed packages\n"
                "  wam search <term>   search packages"
            )
        if command == "pwd":    return f"  {self.fs.pwd()}"
        if command == "ls":
            items = self.fs.ls(args[0] if args else None)
            if not items:
                return "  (empty)"
            return "\n".join(f"  {'📁' if d else '📄'}  {n}" for n, d in items)
        if command == "cd":     return f"  {self.fs.cd(args[0] if args else '')}"
        if command == "cat":
            if not args: return "  usage: cat <file>"
            return self.fs.cat(args[0])
        if command == "touch":
            if not args: return "  usage: touch <file>"
            self.fs.touch(args[0]); return "  ok"
        if command == "mkdir":
            if not args: return "  usage: mkdir <dir>"
            self.fs.mkdir(args[0]); return "  ok"
        if command == "rm":
            if not args: return "  usage: rm <name>"
            self.fs.rm(args[0]); return "  ok"
        if command == "mv":
            if len(args) < 2: return "  usage: mv <old> <new>"
            self.fs.rename(args[0], args[1]); return "  ok"
        if command == "write":
            if len(args) < 2: return "  usage: write <file> <text>"
            self.fs.write(args[0], " ".join(args[1:])); return "  ok"
        if command == "echo":   return "  " + " ".join(args)
        if command == "date":   return "  " + datetime.now().strftime("%A, %B %d %Y   %H:%M:%S")
        if command == "whoami": return f"  {self.state.get('username', 'user')}"
        if command == "sysinfo":
            pkgs = len(self.state.get("installed_packages", []))
            return (
                f"  ┌─ {APP_NAME} System Info ──────────────────────\n"
                f"  │  Python     {sys.version.split()[0]}\n"
                f"  │  Platform   {sys.platform}\n"
                f"  │  Data dir   {DATA_DIR}\n"
                f"  │  Packages   {pkgs} installed\n"
                f"  │  Accent     {self.state.get('accent_color', ACCENT)}\n"
                f"  └────────────────────────────────────────────"
            )
        return f"  command not found: {command}  (type 'help')"

    def shutdown(self):
        self.save_state()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    WamOS().run()