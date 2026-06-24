"""
Instagram Unfollower Tracker
Analyzes your Instagram data export to find who doesn't follow you back.
"""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.scrolled import ScrolledFrame
from ttkbootstrap.toast import ToastNotification
import threading
import time
import zipfile
import tempfile


# ── colour tokens ──────────────────────────────────────────────────────────────
PALETTE = {
    "bg":           "#0F0F14",
    "surface":      "#1A1A24",
    "surface2":     "#22222F",
    "border":       "#2E2E40",
    "accent":       "#C77DFF",   # purple
    "accent2":      "#7B2FBE",
    "green":        "#4CC9A0",
    "red":          "#FF6B6B",
    "yellow":       "#FFD166",
    "text":         "#F0EFF5",
    "subtext":      "#9896A8",
    "card":         "#1E1E2C",
}


def parse_instagram_export(path: str) -> tuple[set, set]:
    """
    Parse Instagram data export — handles both ZIP and folder formats.
    Returns (followers_set, following_set) of usernames.
    """
    path = Path(path)
    tmp_dir = None

    # If it's a ZIP, extract to temp dir first
    if path.suffix.lower() == ".zip":
        tmp_dir = tempfile.mkdtemp()
        with zipfile.ZipFile(path, "r") as z:
            z.extractall(tmp_dir)
        base = Path(tmp_dir)
    else:
        base = path

    followers: set[str] = set()
    following: set[str] = set()

    # ── locate followers file ──────────────────────────────────────────────────
    follower_candidates = [
        base / "connections" / "followers_and_following" / "followers_1.json",
        base / "followers_and_following" / "followers_1.json",
        base / "followers.json",
    ]
    # Also look in nested year/account folders
    for f in base.rglob("followers_1.json"):
        follower_candidates.insert(0, f)

    for candidate in follower_candidates:
        if candidate.exists():
            followers = _extract_usernames(candidate)
            break

    # ── locate following file ──────────────────────────────────────────────────
    following_candidates = [
        base / "connections" / "followers_and_following" / "following.json",
        base / "followers_and_following" / "following.json",
        base / "following.json",
    ]
    for f in base.rglob("following.json"):
        following_candidates.insert(0, f)

    for candidate in following_candidates:
        if candidate.exists():
            following = _extract_usernames(candidate)
            break

    return followers, following


def _extract_usernames(filepath: Path) -> set[str]:
    """Extract Instagram usernames from an export JSON file."""
    usernames: set[str] = set()
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Instagram export formats vary:
        # Format A: list of {"string_list_data": [{"value": "username", ...}], ...}
        if isinstance(data, list):
            for entry in data:
                if isinstance(entry, dict):
                    for sld in entry.get("string_list_data", []):
                        if "value" in sld:
                            usernames.add(sld["value"].lower())

        # Format B: {"relationships_following": [...]} or {"relationships_followers": [...]}
        elif isinstance(data, dict):
            for key, val in data.items():
                if isinstance(val, list):
                    for entry in val:
                        for sld in entry.get("string_list_data", []):
                            if "value" in sld:
                                usernames.add(sld["value"].lower())

    except (json.JSONDecodeError, KeyError, TypeError, OSError) as e:
        print(f"[warn] Could not parse {filepath}: {e}")

    return usernames


class InstagramTracker(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Instagram Unfollower Tracker")
        self.geometry("980x680")
        self.minsize(860, 580)
        self.configure(bg=PALETTE["bg"])

        # State
        self.followers: set[str] = set()
        self.following: set[str] = set()
        self.results: dict[str, set] = {}
        self.active_tab = tk.StringVar(value="not_following_back")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_list())

        self._apply_custom_styles()
        self._build_ui()

    # ── styles ─────────────────────────────────────────────────────────────────
    def _apply_custom_styles(self):
        s = ttk.Style()
        s.configure("Dark.TFrame", background=PALETTE["bg"])
        s.configure("Surface.TFrame", background=PALETTE["surface"])
        s.configure("Card.TFrame", background=PALETTE["card"])
        s.configure("Border.TFrame", background=PALETTE["border"])

        s.configure("Title.TLabel",
                    background=PALETTE["bg"],
                    foreground=PALETTE["text"],
                    font=("Segoe UI", 22, "bold"))
        s.configure("Sub.TLabel",
                    background=PALETTE["bg"],
                    foreground=PALETTE["subtext"],
                    font=("Segoe UI", 10))
        s.configure("Stat.TLabel",
                    background=PALETTE["card"],
                    foreground=PALETTE["text"],
                    font=("Segoe UI", 26, "bold"))
        s.configure("StatLabel.TLabel",
                    background=PALETTE["card"],
                    foreground=PALETTE["subtext"],
                    font=("Segoe UI", 9))
        s.configure("Tag.TLabel",
                    background=PALETTE["card"],
                    foreground=PALETTE["accent"],
                    font=("Segoe UI", 9))
        s.configure("SectionTitle.TLabel",
                    background=PALETTE["bg"],
                    foreground=PALETTE["text"],
                    font=("Segoe UI", 12, "bold"))
        s.configure("Username.TLabel",
                    background=PALETTE["surface2"],
                    foreground=PALETTE["text"],
                    font=("Segoe UI", 10))
        s.configure("Handle.TLabel",
                    background=PALETTE["surface2"],
                    foreground=PALETTE["subtext"],
                    font=("Segoe UI", 9))

    # ── main layout ────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Outer container
        outer = ttk.Frame(self, style="Dark.TFrame")
        outer.pack(fill=BOTH, expand=True, padx=0, pady=0)

        # ── sidebar ────────────────────────────────────────────────────────────
        self.sidebar = ttk.Frame(outer, style="Surface.TFrame", width=260)
        self.sidebar.pack(side=LEFT, fill=Y, padx=0, pady=0)
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # Separator
        sep = ttk.Frame(outer, style="Border.TFrame", width=1)
        sep.pack(side=LEFT, fill=Y)

        # ── main panel ────────────────────────────────────────────────────────
        self.main_panel = ttk.Frame(outer, style="Dark.TFrame")
        self.main_panel.pack(side=LEFT, fill=BOTH, expand=True)
        self._build_main_panel()

    def _build_sidebar(self):
        # Logo / brand
        logo_frame = ttk.Frame(self.sidebar, style="Surface.TFrame")
        logo_frame.pack(fill=X, padx=20, pady=(28, 0))

        logo_icon = ttk.Label(logo_frame,
                              text="◈",
                              background=PALETTE["surface"],
                              foreground=PALETTE["accent"],
                              font=("Segoe UI", 22))
        logo_icon.pack(side=LEFT, padx=(0, 8))

        title_wrap = ttk.Frame(logo_frame, style="Surface.TFrame")
        title_wrap.pack(side=LEFT)
        ttk.Label(title_wrap, text="IG Tracker",
                  background=PALETTE["surface"],
                  foreground=PALETTE["text"],
                  font=("Segoe UI", 14, "bold")).pack(anchor=W)
        ttk.Label(title_wrap, text="Unfollower Analyzer",
                  background=PALETTE["surface"],
                  foreground=PALETTE["subtext"],
                  font=("Segoe UI", 8)).pack(anchor=W)

        ttk.Separator(self.sidebar).pack(fill=X, padx=20, pady=20)

        # Upload section
        ttk.Label(self.sidebar,
                  text="DATA EXPORT",
                  background=PALETTE["surface"],
                  foreground=PALETTE["subtext"],
                  font=("Segoe UI", 8, "bold")).pack(anchor=W, padx=20)

        ttk.Frame(self.sidebar, style="Surface.TFrame", height=8).pack()

        # Followers file
        self._build_file_row(
            label="Followers File",
            hint="followers_1.json",
            attr="followers_path",
            command=self._pick_followers_file
        )

        # Following file
        self._build_file_row(
            label="Following File",
            hint="following.json",
            attr="following_path",
            command=self._pick_following_file
        )

        # OR zip
        ttk.Frame(self.sidebar, style="Surface.TFrame", height=4).pack()
        or_row = ttk.Frame(self.sidebar, style="Surface.TFrame")
        or_row.pack(fill=X, padx=20)
        ttk.Separator(or_row).pack(side=LEFT, fill=X, expand=True)
        ttk.Label(or_row, text="  or  ",
                  background=PALETTE["surface"],
                  foreground=PALETTE["subtext"],
                  font=("Segoe UI", 8)).pack(side=LEFT)
        ttk.Separator(or_row).pack(side=LEFT, fill=X, expand=True)
        ttk.Frame(self.sidebar, style="Surface.TFrame", height=4).pack()

        ttk.Button(self.sidebar,
                   text="📦  Load ZIP Export",
                   bootstyle="secondary-outline",
                   command=self._pick_zip,
                   width=24).pack(padx=20, pady=(0, 16))

        # Analyze button
        self.analyze_btn = ttk.Button(
            self.sidebar,
            text="Analyze  →",
            bootstyle="primary",
            command=self._start_analysis,
            width=24
        )
        self.analyze_btn.pack(padx=20, pady=(0, 8))

        # Status label
        self.status_label = ttk.Label(
            self.sidebar,
            text="Load your data files to begin",
            background=PALETTE["surface"],
            foreground=PALETTE["subtext"],
            font=("Segoe UI", 8),
            wraplength=220,
            justify=CENTER
        )
        self.status_label.pack(padx=20, pady=(0, 20))

        ttk.Separator(self.sidebar).pack(fill=X, padx=20, pady=(0, 20))

        # Navigation tabs
        ttk.Label(self.sidebar,
                  text="VIEWS",
                  background=PALETTE["surface"],
                  foreground=PALETTE["subtext"],
                  font=("Segoe UI", 8, "bold")).pack(anchor=W, padx=20, pady=(0, 8))

        self.nav_buttons = {}
        nav_items = [
            ("not_following_back", "👻", "Not Following Back"),
            ("fans",              "❤️",  "Your Fans"),
            ("mutual",           "🤝", "Mutual Follows"),
            ("all_following",    "📋", "All Following"),
            ("all_followers",    "👥", "All Followers"),
        ]
        for key, icon, label in nav_items:
            btn = self._nav_button(key, icon, label)
            self.nav_buttons[key] = btn

        # Export
        ttk.Separator(self.sidebar).pack(fill=X, padx=20, pady=20)
        ttk.Button(self.sidebar,
                   text="💾  Export Results",
                   bootstyle="success-outline",
                   command=self._export_results,
                   width=24).pack(padx=20)

        # Spacer + how-to
        ttk.Frame(self.sidebar, style="Surface.TFrame").pack(fill=Y, expand=True)

        how_to = ttk.Label(
            self.sidebar,
            text="How to get your data:\nSettings → Your Activity\n→ Download Your Information\n→ Select JSON format",
            background=PALETTE["surface"],
            foreground=PALETTE["subtext"],
            font=("Segoe UI", 8),
            justify=LEFT,
            wraplength=220
        )
        how_to.pack(padx=20, pady=(0, 20), anchor=W)

    def _build_file_row(self, label, hint, attr, command):
        frame = ttk.Frame(self.sidebar, style="Surface.TFrame")
        frame.pack(fill=X, padx=20, pady=(0, 10))

        ttk.Label(frame, text=label,
                  background=PALETTE["surface"],
                  foreground=PALETTE["subtext"],
                  font=("Segoe UI", 8)).pack(anchor=W)

        row = ttk.Frame(frame, style="Surface.TFrame")
        row.pack(fill=X, pady=(2, 0))

        path_var = tk.StringVar(value="")
        setattr(self, attr + "_var", path_var)
        setattr(self, attr, "")

        entry = ttk.Entry(row, textvariable=path_var, font=("Segoe UI", 8), width=18)
        entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 4))

        btn = ttk.Button(row, text="📂", bootstyle="secondary-outline",
                         command=command, width=3)
        btn.pack(side=LEFT)

    def _nav_button(self, key, icon, label):
        is_active = self.active_tab.get() == key

        btn_frame = ttk.Frame(self.sidebar, style="Surface.TFrame")
        btn_frame.pack(fill=X, padx=12, pady=1)
        btn_frame.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))

        fg = PALETTE["accent"] if is_active else PALETTE["subtext"]
        bg = PALETTE["surface2"] if is_active else PALETTE["surface"]

        inner = tk.Frame(btn_frame, bg=bg, cursor="hand2")
        inner.pack(fill=X)
        inner.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))

        icon_lbl = tk.Label(inner, text=icon, bg=bg, fg=fg,
                            font=("Segoe UI", 11), padx=12, pady=8)
        icon_lbl.pack(side=LEFT)
        icon_lbl.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))

        text_lbl = tk.Label(inner, text=label, bg=bg, fg=fg,
                            font=("Segoe UI", 10, "bold" if is_active else "normal"),
                            anchor=W)
        text_lbl.pack(side=LEFT, fill=X, expand=True)
        text_lbl.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))

        # Count badge
        count_lbl = tk.Label(inner, text="—", bg=bg,
                             fg=PALETTE["subtext"], font=("Segoe UI", 9))
        count_lbl.pack(side=RIGHT, padx=12)
        count_lbl.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))

        setattr(self, f"nav_count_{key}", count_lbl)
        setattr(self, f"nav_frame_{key}", inner)
        setattr(self, f"nav_icon_{key}", icon_lbl)
        setattr(self, f"nav_text_{key}", text_lbl)

        return btn_frame

    # ── main panel ────────────────────────────────────────────────────────────
    def _build_main_panel(self):
        # Header
        header = ttk.Frame(self.main_panel, style="Dark.TFrame")
        header.pack(fill=X, padx=32, pady=(28, 0))

        self.page_title = ttk.Label(header,
                                    text="Not Following Back",
                                    style="Title.TLabel")
        self.page_title.pack(side=LEFT)

        # Search bar
        search_frame = ttk.Frame(header, style="Dark.TFrame")
        search_frame.pack(side=RIGHT)
        ttk.Label(search_frame, text="🔍",
                  background=PALETTE["bg"],
                  foreground=PALETTE["subtext"],
                  font=("Segoe UI", 12)).pack(side=LEFT, padx=(0, 6))
        search_entry = ttk.Entry(search_frame,
                                 textvariable=self.search_var,
                                 font=("Segoe UI", 10),
                                 width=22)
        search_entry.pack(side=LEFT)
        search_entry.insert(0, "Search username…")
        search_entry.bind("<FocusIn>", lambda e: (
            search_entry.delete(0, END) if search_entry.get() == "Search username…" else None))
        search_entry.bind("<FocusOut>", lambda e: (
            search_entry.insert(0, "Search username…") if not search_entry.get() else None))

        # Stats cards
        self.stats_frame = ttk.Frame(self.main_panel, style="Dark.TFrame")
        self.stats_frame.pack(fill=X, padx=32, pady=20)
        self._build_stat_cards()

        # List area
        list_header = ttk.Frame(self.main_panel, style="Dark.TFrame")
        list_header.pack(fill=X, padx=32, pady=(0, 12))

        self.list_count_label = ttk.Label(list_header,
                                          text="Load data to see results",
                                          background=PALETTE["bg"],
                                          foreground=PALETTE["subtext"],
                                          font=("Segoe UI", 9))
        self.list_count_label.pack(side=LEFT)

        # Scrollable list
        self.list_container = ttk.Frame(self.main_panel, style="Dark.TFrame")
        self.list_container.pack(fill=BOTH, expand=True, padx=32, pady=(0, 20))
        self._build_empty_state()

    def _build_stat_cards(self):
        for w in self.stats_frame.winfo_children():
            w.destroy()

        cards = [
            ("followers_count", "Followers",    PALETTE["green"],  "👥"),
            ("following_count", "Following",    PALETTE["accent"], "📋"),
            ("unfollowers_count","Not Following Back", PALETTE["red"],   "👻"),
            ("fans_count",      "Your Fans",    PALETTE["yellow"], "❤️"),
            ("mutual_count",    "Mutual",       "#61DAFB",         "🤝"),
        ]
        for attr, label, color, icon in cards:
            card = tk.Frame(self.stats_frame, bg=PALETTE["card"],
                            highlightbackground=PALETTE["border"],
                            highlightthickness=1)
            card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 10))

            tk.Label(card, text=icon, bg=PALETTE["card"],
                     fg=color, font=("Segoe UI", 14)).pack(anchor=W, padx=14, pady=(12, 0))

            count_lbl = tk.Label(card, text="—", bg=PALETTE["card"],
                                 fg=PALETTE["text"], font=("Segoe UI", 24, "bold"))
            count_lbl.pack(anchor=W, padx=14)
            setattr(self, attr, count_lbl)

            tk.Label(card, text=label, bg=PALETTE["card"],
                     fg=PALETTE["subtext"], font=("Segoe UI", 8)).pack(anchor=W, padx=14, pady=(0, 12))

    def _build_empty_state(self):
        for w in self.list_container.winfo_children():
            w.destroy()

        empty = tk.Frame(self.list_container, bg=PALETTE["bg"])
        empty.pack(expand=True, fill=BOTH)

        tk.Label(empty, text="◈", bg=PALETTE["bg"],
                 fg=PALETTE["border"], font=("Segoe UI", 56)).pack(pady=(80, 12))
        tk.Label(empty, text="No data loaded yet",
                 bg=PALETTE["bg"], fg=PALETTE["subtext"],
                 font=("Segoe UI", 14, "bold")).pack()
        tk.Label(empty, text="Load your Instagram data export files\nusing the panel on the left",
                 bg=PALETTE["bg"], fg=PALETTE["subtext"],
                 font=("Segoe UI", 10), justify=CENTER).pack(pady=(6, 0))

    # ── file pickers ───────────────────────────────────────────────────────────
    def _pick_followers_file(self):
        path = filedialog.askopenfilename(
            title="Select followers_1.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.followers_path = path
            self.followers_path_var.set(os.path.basename(path))
            self._set_status(f"✓ Followers: {os.path.basename(path)}", PALETTE["green"])

    def _pick_following_file(self):
        path = filedialog.askopenfilename(
            title="Select following.json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.following_path = path
            self.following_path_var.set(os.path.basename(path))
            self._set_status(f"✓ Following: {os.path.basename(path)}", PALETTE["green"])

    def _pick_zip(self):
        path = filedialog.askopenfilename(
            title="Select Instagram export ZIP",
            filetypes=[("ZIP files", "*.zip"), ("All files", "*.*")]
        )
        if path:
            self.zip_path = path
            self._set_status(f"✓ ZIP: {os.path.basename(path)}", PALETTE["green"])
            self.followers_path_var.set("(from ZIP)")
            self.following_path_var.set("(from ZIP)")

    # ── analysis ───────────────────────────────────────────────────────────────
    def _start_analysis(self):
        self.analyze_btn.configure(state=DISABLED)
        self._set_status("Analyzing…", PALETTE["accent"])
        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _run_analysis(self):
        try:
            # Determine input source
            if hasattr(self, "zip_path") and self.zip_path and \
               (not hasattr(self, "followers_path") or not self.followers_path or
                    "from ZIP" in (getattr(self, "followers_path_var", None) or
                                   type("", (), {"get": lambda s: ""})()).get()):
                followers, following = parse_instagram_export(self.zip_path)
            else:
                followers = set()
                following = set()
                if hasattr(self, "followers_path") and self.followers_path and \
                   "from ZIP" not in getattr(self, "followers_path_var", type("", (), {"get": lambda s: ""})()).get():
                    followers = _extract_usernames(Path(self.followers_path))
                if hasattr(self, "following_path") and self.following_path and \
                   "from ZIP" not in getattr(self, "following_path_var", type("", (), {"get": lambda s: ""})()).get():
                    following = _extract_usernames(Path(self.following_path))

            if not followers and not following:
                self.after(0, lambda: (
                    messagebox.showerror("No Data Found",
                        "Could not find followers or following data.\n\n"
                        "Make sure you selected the correct files from your\n"
                        "Instagram data export (JSON format)."),
                    self._set_status("No data found", PALETTE["red"]),
                    setattr(self, "_enable_btn", True)
                ))
                self.after(0, lambda: self.analyze_btn.configure(state=NORMAL))
                return

            self.followers = followers
            self.following = following

            # Compute results
            not_following_back = following - followers    # I follow them, they don't follow me
            fans              = followers - following     # they follow me, I don't follow them
            mutual            = followers & following     # both follow each other

            self.results = {
                "not_following_back": not_following_back,
                "fans":              fans,
                "mutual":            mutual,
                "all_following":     following,
                "all_followers":     followers,
            }

            self.after(0, self._update_ui_after_analysis)

        except Exception as e:
            self.after(0, lambda: (
                messagebox.showerror("Error", str(e)),
                self._set_status("Error during analysis", PALETTE["red"]),
                self.analyze_btn.configure(state=NORMAL)
            ))

    def _update_ui_after_analysis(self):
        # Update stat cards
        self.followers_count.configure(text=str(len(self.followers)))
        self.following_count.configure(text=str(len(self.following)))
        self.unfollowers_count.configure(text=str(len(self.results["not_following_back"])))
        self.fans_count.configure(text=str(len(self.results["fans"])))
        self.mutual_count.configure(text=str(len(self.results["mutual"])))

        # Update nav badge counts
        for key in ["not_following_back", "fans", "mutual", "all_following", "all_followers"]:
            lbl = getattr(self, f"nav_count_{key}", None)
            if lbl:
                lbl.configure(text=str(len(self.results[key])))

        self._set_status("Analysis complete ✓", PALETTE["green"])
        self.analyze_btn.configure(state=NORMAL)
        self._switch_tab(self.active_tab.get())

    # ── tab switching ──────────────────────────────────────────────────────────
    def _switch_tab(self, key):
        self.active_tab.set(key)

        titles = {
            "not_following_back": "Not Following Back",
            "fans":               "Your Fans",
            "mutual":             "Mutual Follows",
            "all_following":      "All Following",
            "all_followers":      "All Followers",
        }
        self.page_title.configure(text=titles.get(key, ""))

        # Update nav highlight
        for k in ["not_following_back", "fans", "mutual", "all_following", "all_followers"]:
            frame = getattr(self, f"nav_frame_{k}", None)
            icon  = getattr(self, f"nav_icon_{k}",  None)
            text  = getattr(self, f"nav_text_{k}",  None)
            count = getattr(self, f"nav_count_{k}",  None)
            if frame:
                is_active = (k == key)
                bg = PALETTE["surface2"] if is_active else PALETTE["surface"]
                fg = PALETTE["accent"]   if is_active else PALETTE["subtext"]
                font_w = "bold" if is_active else "normal"
                frame.configure(bg=bg)
                if icon:  icon.configure(bg=bg, fg=fg)
                if text:  text.configure(bg=bg, fg=fg, font=("Segoe UI", 10, font_w))
                if count: count.configure(bg=bg)

        self._render_list()

    def _render_list(self):
        key = self.active_tab.get()
        data = self.results.get(key, set())
        query = self.search_var.get().lower().strip()
        if query == "search username…":
            query = ""

        filtered = sorted([u for u in data if query in u], key=str.lower)

        for w in self.list_container.winfo_children():
            w.destroy()

        if not self.results:
            self._build_empty_state()
            return

        count = len(filtered)
        match_suffix = f' matching "{query}"' if query else ""
        self.list_count_label.configure(
            text=f"{count} account{'s' if count != 1 else ''}{match_suffix}")

        if not filtered:
            empty = tk.Frame(self.list_container, bg=PALETTE["bg"])
            empty.pack(expand=True, fill=BOTH)
            tk.Label(empty, text="🔍", bg=PALETTE["bg"], fg=PALETTE["border"],
                     font=("Segoe UI", 36)).pack(pady=(60, 8))
            tk.Label(empty, text="No results found",
                     bg=PALETTE["bg"], fg=PALETTE["subtext"],
                     font=("Segoe UI", 12, "bold")).pack()
            return

        # Canvas + scrollbar for smooth scrolling
        canvas = tk.Canvas(self.list_container, bg=PALETTE["bg"],
                           highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(self.list_container, orient=VERTICAL,
                                  command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        inner = tk.Frame(canvas, bg=PALETTE["bg"])
        canvas_window = canvas.create_window((0, 0), window=inner, anchor=NW)

        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
            canvas.itemconfig(canvas_window, width=canvas.winfo_width())

        inner.bind("<Configure>", on_configure)
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(
            canvas_window, width=canvas.winfo_width()))

        # Bind mousewheel
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # Tag colours per tab
        tag_cfg = {
            "not_following_back": (PALETTE["red"],    "Not following you"),
            "fans":               (PALETTE["yellow"], "Follows you"),
            "mutual":             (PALETTE["green"],  "Mutual"),
            "all_following":      (PALETTE["accent"], "Following"),
            "all_followers":      (PALETTE["accent"], "Follower"),
        }
        tag_color, tag_text = tag_cfg.get(self.active_tab.get(), (PALETTE["subtext"], ""))

        # Render rows in chunks for performance
        cols = 3
        for i, username in enumerate(filtered):
            row_i = i // cols
            col_i = i % cols

            cell = tk.Frame(inner, bg=PALETTE["surface2"],
                            highlightbackground=PALETTE["border"],
                            highlightthickness=1)
            cell.grid(row=row_i, column=col_i, padx=5, pady=4, sticky="nsew")
            inner.columnconfigure(col_i, weight=1)

            # Avatar placeholder
            av = tk.Label(cell,
                          text=username[0].upper(),
                          bg=PALETTE["accent2"],
                          fg=PALETTE["text"],
                          font=("Segoe UI", 13, "bold"),
                          width=3, height=1)
            av.pack(side=LEFT, padx=(10, 8), pady=12)

            info = tk.Frame(cell, bg=PALETTE["surface2"])
            info.pack(side=LEFT, fill=X, expand=True, pady=10)

            tk.Label(info, text=f"@{username}",
                     bg=PALETTE["surface2"], fg=PALETTE["text"],
                     font=("Segoe UI", 10, "bold"), anchor=W).pack(anchor=W)

            tk.Label(info, text=tag_text,
                     bg=PALETTE["surface2"], fg=tag_color,
                     font=("Segoe UI", 8), anchor=W).pack(anchor=W)

            # Copy button
            copy_btn = tk.Label(cell, text="⧉", bg=PALETTE["surface2"],
                                fg=PALETTE["subtext"], font=("Segoe UI", 13),
                                cursor="hand2", padx=10)
            copy_btn.pack(side=RIGHT, pady=12)
            copy_btn.bind("<Button-1>",
                          lambda e, u=username: self._copy_username(u))
            copy_btn.bind("<Enter>",
                          lambda e, w=copy_btn: w.configure(fg=PALETTE["accent"]))
            copy_btn.bind("<Leave>",
                          lambda e, w=copy_btn: w.configure(fg=PALETTE["subtext"]))

    def _filter_list(self):
        if self.results:
            self._render_list()

    def _copy_username(self, username):
        self.clipboard_clear()
        self.clipboard_append(f"@{username}")
        toast = ToastNotification(
            title="Copied!",
            message=f"@{username} copied to clipboard",
            duration=2000,
            bootstyle="success"
        )
        toast.show_toast()

    # ── export ─────────────────────────────────────────────────────────────────
    def _export_results(self):
        if not self.results:
            messagebox.showwarning("No Data", "Run an analysis first.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("JSON file", "*.json"), ("All files", "*.*")],
            initialfile="instagram_analysis"
        )
        if not path:
            return

        if path.endswith(".json"):
            output = {k: sorted(list(v)) for k, v in self.results.items()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write("Instagram Unfollower Tracker — Results\n")
                f.write("=" * 50 + "\n\n")

                sections = [
                    ("NOT FOLLOWING BACK", "not_following_back"),
                    ("YOUR FANS (they follow you, you don't follow back)", "fans"),
                    ("MUTUAL FOLLOWS", "mutual"),
                    ("ALL FOLLOWING", "all_following"),
                    ("ALL FOLLOWERS", "all_followers"),
                ]
                for title, key in sections:
                    data = sorted(self.results.get(key, set()))
                    f.write(f"{title} ({len(data)})\n")
                    f.write("-" * 40 + "\n")
                    for u in data:
                        f.write(f"  @{u}\n")
                    f.write("\n")

        messagebox.showinfo("Exported", f"Results saved to:\n{path}")

    def _set_status(self, msg, color=None):
        self.status_label.configure(
            text=msg,
            foreground=color or PALETTE["subtext"]
        )


# ── entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = InstagramTracker()
    app.mainloop()
