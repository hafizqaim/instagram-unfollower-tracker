"""
Instagram Unfollower Tracker
Analyzes your Instagram data export (following.json) to show who you follow,
with optional followers file if your export included one.
"""

import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox
from pathlib import Path
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from ttkbootstrap.toast import ToastNotification
import threading
import zipfile
import tempfile
from datetime import datetime

# ── colour tokens ──────────────────────────────────────────────────────────────
PALETTE = {
    "bg":       "#0F0F14",
    "surface":  "#1A1A24",
    "surface2": "#22222F",
    "border":   "#2E2E40",
    "accent":   "#C77DFF",
    "accent2":  "#7B2FBE",
    "green":    "#4CC9A0",
    "red":      "#FF6B6B",
    "yellow":   "#FFD166",
    "text":     "#F0EFF5",
    "subtext":  "#9896A8",
    "card":     "#1E1E2C",
}


# ── parser ─────────────────────────────────────────────────────────────────────

def _extract_usernames_from_data(data) -> list[tuple[str, int]]:
    """
    Returns list of (username, timestamp) from any Instagram export JSON shape.
    Handles all known formats:
      - {"relationships_following": [{title, string_list_data:[{href,timestamp}]}, ...]}
      - [{title, string_list_data:[{value, href, timestamp}]}, ...]   (older format)
    Username is in entry["title"] OR string_list_data[0]["value"].
    """
    results = []

    def _process_entry(entry: dict):
        username = None
        timestamp = 0
        # username: prefer title field (your format), fall back to string_list_data.value
        if "title" in entry and entry["title"]:
            username = entry["title"].strip().lower()
        elif "string_list_data" in entry:
            for sld in entry["string_list_data"]:
                if "value" in sld and sld["value"]:
                    username = sld["value"].strip().lower()
                    break
        # timestamp from string_list_data
        if "string_list_data" in entry:
            for sld in entry["string_list_data"]:
                if "timestamp" in sld:
                    timestamp = sld["timestamp"]
                    break
        if username:
            results.append((username, timestamp))

    if isinstance(data, list):
        for entry in data:
            if isinstance(entry, dict):
                _process_entry(entry)

    elif isinstance(data, dict):
        for key, val in data.items():
            if isinstance(val, list):
                for entry in val:
                    if isinstance(entry, dict):
                        _process_entry(entry)

    return results


def _load_json_file(filepath: Path):
    """Load and return parsed JSON, or None on error."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[warn] Could not read {filepath}: {e}")
        return None


def parse_file(filepath: str) -> list[tuple[str, int]]:
    """Parse a single JSON file and return (username, timestamp) list."""
    data = _load_json_file(Path(filepath))
    if data is None:
        return []
    return _extract_usernames_from_data(data)


def parse_zip_export(zip_path: str) -> tuple[list, list]:
    """
    Extract a ZIP export and return (following_entries, followers_entries).
    Each is a list of (username, timestamp).
    """
    tmp_dir = tempfile.mkdtemp()
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(tmp_dir)
    base = Path(tmp_dir)

    following_entries = []
    followers_entries = []

    # Search for following.json
    for candidate in list(base.rglob("following.json")):
        data = _load_json_file(candidate)
        if data:
            following_entries = _extract_usernames_from_data(data)
            break

    # Search for followers files (may not exist)
    for pattern in ["followers_1.json", "followers.json"]:
        found = list(base.rglob(pattern))
        for candidate in found:
            data = _load_json_file(candidate)
            if data:
                followers_entries = _extract_usernames_from_data(data)
                break
        if followers_entries:
            break

    return following_entries, followers_entries


# ── main app ───────────────────────────────────────────────────────────────────

class InstagramTracker(ttk.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("Instagram Unfollower Tracker")
        self.geometry("1020x700")
        self.minsize(860, 580)
        self.configure(bg=PALETTE["bg"])

        # Data state
        self.following_entries: list[tuple[str, int]] = []   # (username, timestamp)
        self.followers_entries: list[tuple[str, int]] = []
        self.has_followers_data = False
        self.results: dict[str, list] = {}

        # UI state
        self.active_tab = tk.StringVar(value="all_following")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_list())

        # File paths
        self.following_path = ""
        self.followers_path = ""
        self.zip_path = ""

        self._apply_custom_styles()
        self._build_ui()

    def _apply_custom_styles(self):
        s = ttk.Style()
        s.configure("Dark.TFrame",    background=PALETTE["bg"])
        s.configure("Surface.TFrame", background=PALETTE["surface"])
        s.configure("Card.TFrame",    background=PALETTE["card"])
        s.configure("Border.TFrame",  background=PALETTE["border"])
        s.configure("Title.TLabel",
                    background=PALETTE["bg"], foreground=PALETTE["text"],
                    font=("Segoe UI", 20, "bold"))

    # ── layout ─────────────────────────────────────────────────────────────────
    def _build_ui(self):
        outer = ttk.Frame(self, style="Dark.TFrame")
        outer.pack(fill=BOTH, expand=True)

        # Sidebar
        self.sidebar = ttk.Frame(outer, style="Surface.TFrame", width=270)
        self.sidebar.pack(side=LEFT, fill=Y)
        self.sidebar.pack_propagate(False)
        self._build_sidebar()

        # Divider
        ttk.Frame(outer, style="Border.TFrame", width=1).pack(side=LEFT, fill=Y)

        # Main
        self.main_panel = ttk.Frame(outer, style="Dark.TFrame")
        self.main_panel.pack(side=LEFT, fill=BOTH, expand=True)
        self._build_main_panel()

    # ── sidebar ────────────────────────────────────────────────────────────────
    def _build_sidebar(self):
        sb = self.sidebar

        # Brand
        brand = ttk.Frame(sb, style="Surface.TFrame")
        brand.pack(fill=X, padx=20, pady=(24, 0))
        tk.Label(brand, text="◈", bg=PALETTE["surface"], fg=PALETTE["accent"],
                 font=("Segoe UI", 20)).pack(side=LEFT, padx=(0, 8))
        name_col = ttk.Frame(brand, style="Surface.TFrame")
        name_col.pack(side=LEFT)
        tk.Label(name_col, text="IG Tracker", bg=PALETTE["surface"],
                 fg=PALETTE["text"], font=("Segoe UI", 14, "bold")).pack(anchor=W)
        tk.Label(name_col, text="by hafizqaim", bg=PALETTE["surface"],
                 fg=PALETTE["subtext"], font=("Segoe UI", 8)).pack(anchor=W)

        ttk.Separator(sb).pack(fill=X, padx=20, pady=18)

        # Section label
        tk.Label(sb, text="LOAD YOUR DATA", bg=PALETTE["surface"],
                 fg=PALETTE["subtext"], font=("Segoe UI", 8, "bold")).pack(anchor=W, padx=20)
        ttk.Frame(sb, style="Surface.TFrame", height=8).pack()

        # Following file row
        self._file_row(sb, "Following File *", "following.json",
                       "following_path_var", self._pick_following)

        # Followers file row (optional)
        self._file_row(sb, "Followers File (optional)", "followers_1.json",
                       "followers_path_var", self._pick_followers)

        # OR divider
        ttk.Frame(sb, style="Surface.TFrame", height=4).pack()
        or_row = ttk.Frame(sb, style="Surface.TFrame")
        or_row.pack(fill=X, padx=20)
        ttk.Separator(or_row).pack(side=LEFT, fill=X, expand=True)
        tk.Label(or_row, text="  or  ", bg=PALETTE["surface"],
                 fg=PALETTE["subtext"], font=("Segoe UI", 8)).pack(side=LEFT)
        ttk.Separator(or_row).pack(side=LEFT, fill=X, expand=True)
        ttk.Frame(sb, style="Surface.TFrame", height=6).pack()

        ttk.Button(sb, text="📦  Load ZIP Export", bootstyle="secondary-outline",
                   command=self._pick_zip, width=26).pack(padx=20, pady=(0, 14))

        # Analyze
        self.analyze_btn = ttk.Button(sb, text="Analyze  →", bootstyle="primary",
                                      command=self._start_analysis, width=26)
        self.analyze_btn.pack(padx=20, pady=(0, 6))

        self.status_label = tk.Label(sb, text="Load following.json to begin",
                                     bg=PALETTE["surface"], fg=PALETTE["subtext"],
                                     font=("Segoe UI", 8), wraplength=230, justify=CENTER)
        self.status_label.pack(padx=20, pady=(0, 16))

        ttk.Separator(sb).pack(fill=X, padx=20, pady=(0, 14))

        # Nav
        tk.Label(sb, text="VIEWS", bg=PALETTE["surface"],
                 fg=PALETTE["subtext"], font=("Segoe UI", 8, "bold")).pack(anchor=W, padx=20, pady=(0, 6))

        self._nav_tabs = {}
        nav_items = [
            ("all_following",      "📋", "All Following"),
            ("not_following_back", "👻", "Not Following Back"),
            ("fans",               "❤️",  "Your Fans"),
            ("mutual",             "🤝", "Mutual Follows"),
            ("all_followers",      "👥", "All Followers"),
        ]
        for key, icon, label in nav_items:
            self._make_nav_btn(sb, key, icon, label)

        ttk.Separator(sb).pack(fill=X, padx=20, pady=14)
        ttk.Button(sb, text="💾  Export Results", bootstyle="success-outline",
                   command=self._export_results, width=26).pack(padx=20)

        # Stretch + hint
        ttk.Frame(sb, style="Surface.TFrame").pack(fill=Y, expand=True)
        hint = ("How to get your data:\nSettings → Your Activity\n"
                "→ Download Your Information\n→ Select JSON format")
        tk.Label(sb, text=hint, bg=PALETTE["surface"], fg=PALETTE["subtext"],
                 font=("Segoe UI", 8), justify=LEFT, wraplength=230).pack(
            padx=20, pady=(0, 18), anchor=W)

    def _file_row(self, parent, label, hint, var_attr, command):
        frame = ttk.Frame(parent, style="Surface.TFrame")
        frame.pack(fill=X, padx=20, pady=(0, 10))
        tk.Label(frame, text=label, bg=PALETTE["surface"],
                 fg=PALETTE["subtext"], font=("Segoe UI", 8)).pack(anchor=W)
        row = ttk.Frame(frame, style="Surface.TFrame")
        row.pack(fill=X, pady=(2, 0))
        var = tk.StringVar(value="")
        setattr(self, var_attr, var)
        ttk.Entry(row, textvariable=var, font=("Segoe UI", 8), width=20).pack(
            side=LEFT, fill=X, expand=True, padx=(0, 4))
        ttk.Button(row, text="📂", bootstyle="secondary-outline",
                   command=command, width=3).pack(side=LEFT)

    def _make_nav_btn(self, parent, key, icon, label):
        frame = tk.Frame(parent, bg=PALETTE["surface"], cursor="hand2")
        frame.pack(fill=X, padx=12, pady=1)

        icon_lbl  = tk.Label(frame, text=icon,  bg=PALETTE["surface"],
                             fg=PALETTE["subtext"], font=("Segoe UI", 11), padx=12, pady=8)
        text_lbl  = tk.Label(frame, text=label, bg=PALETTE["surface"],
                             fg=PALETTE["subtext"], font=("Segoe UI", 10), anchor=W)
        count_lbl = tk.Label(frame, text="—",   bg=PALETTE["surface"],
                             fg=PALETTE["subtext"], font=("Segoe UI", 9), padx=12)

        icon_lbl.pack(side=LEFT)
        text_lbl.pack(side=LEFT, fill=X, expand=True)
        count_lbl.pack(side=RIGHT)

        for w in (frame, icon_lbl, text_lbl, count_lbl):
            w.bind("<Button-1>", lambda e, k=key: self._switch_tab(k))

        self._nav_tabs[key] = {
            "frame": frame, "icon": icon_lbl,
            "text": text_lbl, "count": count_lbl
        }

    # ── main panel ─────────────────────────────────────────────────────────────
    def _build_main_panel(self):
        mp = self.main_panel

        # Header row
        header = ttk.Frame(mp, style="Dark.TFrame")
        header.pack(fill=X, padx=32, pady=(26, 0))

        self.page_title = tk.Label(header, text="All Following",
                                   bg=PALETTE["bg"], fg=PALETTE["text"],
                                   font=("Segoe UI", 20, "bold"))
        self.page_title.pack(side=LEFT)

        # Search
        search_wrap = ttk.Frame(header, style="Dark.TFrame")
        search_wrap.pack(side=RIGHT)
        tk.Label(search_wrap, text="🔍", bg=PALETTE["bg"],
                 fg=PALETTE["subtext"], font=("Segoe UI", 12)).pack(side=LEFT, padx=(0, 6))
        se = ttk.Entry(search_wrap, textvariable=self.search_var,
                       font=("Segoe UI", 10), width=24)
        se.pack(side=LEFT)
        se.insert(0, "Search username…")
        se.bind("<FocusIn>",  lambda e: se.delete(0, END) if se.get() == "Search username…" else None)
        se.bind("<FocusOut>", lambda e: se.insert(0, "Search username…") if not se.get() else None)

        # Stat cards
        self.cards_frame = ttk.Frame(mp, style="Dark.TFrame")
        self.cards_frame.pack(fill=X, padx=32, pady=18)
        self._build_stat_cards()

        # No-followers banner (shown when followers data is absent)
        self.no_followers_banner = tk.Frame(mp, bg="#2A1F10",
                                            highlightbackground="#5C3D11",
                                            highlightthickness=1)
        tk.Label(self.no_followers_banner,
                 text="⚠️  No followers file found — "
                      "comparisons (Not Following Back, Fans, Mutual) unavailable. "
                      "Load followers_1.json if you have it.",
                 bg="#2A1F10", fg=PALETTE["yellow"],
                 font=("Segoe UI", 9), wraplength=680, justify=LEFT).pack(
            padx=14, pady=8, anchor=W)

        # List sub-header
        list_head = ttk.Frame(mp, style="Dark.TFrame")
        list_head.pack(fill=X, padx=32, pady=(0, 10))
        self.list_count_label = tk.Label(list_head, text="Load data to see results",
                                         bg=PALETTE["bg"], fg=PALETTE["subtext"],
                                         font=("Segoe UI", 9))
        self.list_count_label.pack(side=LEFT)

        # List area
        self.list_container = ttk.Frame(mp, style="Dark.TFrame")
        self.list_container.pack(fill=BOTH, expand=True, padx=32, pady=(0, 20))
        self._build_empty_state()

    def _build_stat_cards(self):
        for w in self.cards_frame.winfo_children():
            w.destroy()
        cards = [
            ("following_stat", "Following",         PALETTE["accent"], "📋"),
            ("followers_stat", "Followers",          PALETTE["green"],  "👥"),
            ("unfollowers_stat","Not Following Back",PALETTE["red"],    "👻"),
            ("fans_stat",      "Your Fans",          PALETTE["yellow"], "❤️"),
            ("mutual_stat",    "Mutual",             "#61DAFB",        "🤝"),
        ]
        for attr, label, color, icon in cards:
            card = tk.Frame(self.cards_frame, bg=PALETTE["card"],
                            highlightbackground=PALETTE["border"],
                            highlightthickness=1)
            card.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 8))
            tk.Label(card, text=icon,  bg=PALETTE["card"], fg=color,
                     font=("Segoe UI", 13)).pack(anchor=W, padx=12, pady=(10, 0))
            num = tk.Label(card, text="—", bg=PALETTE["card"],
                           fg=PALETTE["text"], font=("Segoe UI", 22, "bold"))
            num.pack(anchor=W, padx=12)
            tk.Label(card, text=label, bg=PALETTE["card"],
                     fg=PALETTE["subtext"], font=("Segoe UI", 8)).pack(anchor=W, padx=12, pady=(0, 10))
            setattr(self, attr, num)

    def _build_empty_state(self):
        for w in self.list_container.winfo_children():
            w.destroy()
        wrap = tk.Frame(self.list_container, bg=PALETTE["bg"])
        wrap.pack(expand=True, fill=BOTH)
        tk.Label(wrap, text="◈",  bg=PALETTE["bg"], fg=PALETTE["border"],
                 font=("Segoe UI", 52)).pack(pady=(70, 10))
        tk.Label(wrap, text="No data loaded yet", bg=PALETTE["bg"],
                 fg=PALETTE["subtext"], font=("Segoe UI", 13, "bold")).pack()
        tk.Label(wrap, text="Load following.json from your Instagram data export\nusing the panel on the left.",
                 bg=PALETTE["bg"], fg=PALETTE["subtext"],
                 font=("Segoe UI", 10), justify=CENTER).pack(pady=(6, 0))

    # ── file pickers ───────────────────────────────────────────────────────────
    def _pick_following(self):
        p = filedialog.askopenfilename(title="Select following.json",
                                       filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if p:
            self.following_path = p
            self.following_path_var.set(os.path.basename(p))
            self._set_status(f"✓ {os.path.basename(p)} loaded", PALETTE["green"])

    def _pick_followers(self):
        p = filedialog.askopenfilename(title="Select followers_1.json (optional)",
                                       filetypes=[("JSON", "*.json"), ("All", "*.*")])
        if p:
            self.followers_path = p
            self.followers_path_var.set(os.path.basename(p))
            self._set_status(f"✓ {os.path.basename(p)} loaded", PALETTE["green"])

    def _pick_zip(self):
        p = filedialog.askopenfilename(title="Select Instagram export ZIP",
                                       filetypes=[("ZIP", "*.zip"), ("All", "*.*")])
        if p:
            self.zip_path = p
            self.following_path = ""
            self.followers_path = ""
            self.following_path_var.set("(from ZIP)")
            self.followers_path_var.set("(from ZIP)")
            self._set_status(f"✓ ZIP ready: {os.path.basename(p)}", PALETTE["green"])

    # ── analysis ───────────────────────────────────────────────────────────────
    def _start_analysis(self):
        if not self.following_path and not self.zip_path:
            messagebox.showwarning("Missing File",
                                   "Please load following.json or a ZIP export first.")
            return
        self.analyze_btn.configure(state=DISABLED)
        self._set_status("Analyzing…", PALETTE["accent"])
        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _run_analysis(self):
        try:
            following_entries = []
            followers_entries = []

            if self.zip_path and not self.following_path:
                following_entries, followers_entries = parse_zip_export(self.zip_path)
            else:
                if self.following_path:
                    following_entries = parse_file(self.following_path)
                if self.followers_path:
                    followers_entries = parse_file(self.followers_path)

            if not following_entries:
                self.after(0, lambda: (
                    messagebox.showerror("No Data Found",
                        "Could not read any accounts from the file.\n\n"
                        "Make sure you selected the correct following.json "
                        "from your Instagram data export (JSON format)."),
                    self._set_status("No data found", PALETTE["red"]),
                    self.analyze_btn.configure(state=NORMAL)
                ))
                return

            self.following_entries = sorted(following_entries, key=lambda x: x[1], reverse=True)
            self.followers_entries = followers_entries
            self.has_followers_data = bool(followers_entries)

            following_set = {u for u, _ in following_entries}
            followers_set = {u for u, _ in followers_entries}

            self.results = {
                "all_following":      self.following_entries,
                "all_followers":      self.followers_entries,
                "not_following_back": [(u, t) for u, t in self.following_entries
                                       if u not in followers_set],
                "fans":               [(u, t) for u, t in self.followers_entries
                                       if u not in following_set],
                "mutual":             [(u, t) for u, t in self.following_entries
                                       if u in followers_set],
            }

            self.after(0, self._update_ui_after_analysis)

        except Exception as e:
            import traceback
            traceback.print_exc()
            self.after(0, lambda: (
                messagebox.showerror("Error", str(e)),
                self._set_status("Error during analysis", PALETTE["red"]),
                self.analyze_btn.configure(state=NORMAL)
            ))

    def _update_ui_after_analysis(self):
        n_following = len(self.results["all_following"])
        n_followers = len(self.results["all_followers"])
        n_unf       = len(self.results["not_following_back"])
        n_fans      = len(self.results["fans"])
        n_mutual    = len(self.results["mutual"])

        self.following_stat.configure(text=str(n_following))
        self.followers_stat.configure(text=str(n_followers) if self.has_followers_data else "—")
        self.unfollowers_stat.configure(text=str(n_unf) if self.has_followers_data else "—")
        self.fans_stat.configure(text=str(n_fans) if self.has_followers_data else "—")
        self.mutual_stat.configure(text=str(n_mutual) if self.has_followers_data else "—")

        # Nav badge counts
        for key, tab in self._nav_tabs.items():
            count = len(self.results.get(key, []))
            tab["count"].configure(
                text=str(count) if (self.has_followers_data or key in ("all_following", "all_followers"))
                else "N/A"
            )

        # Show/hide no-followers banner
        if not self.has_followers_data:
            self.no_followers_banner.pack(fill=X, padx=32, pady=(0, 8), before=self.list_container)
        else:
            self.no_followers_banner.pack_forget()

        status = f"Done — {n_following} following"
        if self.has_followers_data:
            status += f", {n_followers} followers, {n_unf} not following back"
        self._set_status(status, PALETTE["green"])
        self.analyze_btn.configure(state=NORMAL)

        # Switch to appropriate default tab
        if not self.has_followers_data:
            self._switch_tab("all_following")
        else:
            self._switch_tab("not_following_back")

    # ── tab switching ──────────────────────────────────────────────────────────
    def _switch_tab(self, key):
        # Block comparison tabs if no followers data
        comparison_tabs = {"not_following_back", "fans", "mutual", "all_followers"}
        if not self.has_followers_data and key in comparison_tabs and self.results:
            messagebox.showinfo("Followers Data Needed",
                                "Load a followers_1.json file to unlock this view.\n\n"
                                "Instagram sometimes omits the followers file from exports —\n"
                                "try re-requesting your data and selecting 'Followers and following'.")
            return

        self.active_tab.set(key)

        titles = {
            "all_following":      "All Following",
            "not_following_back": "Not Following Back",
            "fans":               "Your Fans",
            "mutual":             "Mutual Follows",
            "all_followers":      "All Followers",
        }
        self.page_title.configure(text=titles.get(key, ""))

        # Highlight active nav
        for k, tab in self._nav_tabs.items():
            active = (k == key)
            bg     = PALETTE["surface2"] if active else PALETTE["surface"]
            fg     = PALETTE["accent"]   if active else PALETTE["subtext"]
            fw     = "bold" if active else "normal"
            tab["frame"].configure(bg=bg)
            tab["icon"].configure(bg=bg, fg=fg)
            tab["text"].configure(bg=bg, fg=fg, font=("Segoe UI", 10, fw))
            tab["count"].configure(bg=bg)

        self._render_list()

    # ── list rendering ─────────────────────────────────────────────────────────
    def _render_list(self):
        key = self.active_tab.get()
        raw = self.results.get(key, [])

        query = self.search_var.get().lower().strip()
        if query == "search username…":
            query = ""

        filtered = [(u, t) for u, t in raw if query in u] if query else list(raw)

        for w in self.list_container.winfo_children():
            w.destroy()

        if not self.results:
            self._build_empty_state()
            return

        suffix = f' matching "{query}"' if query else ""
        self.list_count_label.configure(
            text=f"{len(filtered)} account{'s' if len(filtered) != 1 else ''}{suffix}")

        if not filtered:
            wrap = tk.Frame(self.list_container, bg=PALETTE["bg"])
            wrap.pack(expand=True, fill=BOTH)
            tk.Label(wrap, text="🔍", bg=PALETTE["bg"], fg=PALETTE["border"],
                     font=("Segoe UI", 34)).pack(pady=(60, 8))
            tk.Label(wrap, text="No results", bg=PALETTE["bg"],
                     fg=PALETTE["subtext"], font=("Segoe UI", 12, "bold")).pack()
            return

        # Canvas + scrollbar
        canvas = tk.Canvas(self.list_container, bg=PALETTE["bg"],
                           highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self.list_container, orient=VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        inner = tk.Frame(canvas, bg=PALETTE["bg"])
        win = canvas.create_window((0, 0), window=inner, anchor=NW)

        inner.bind("<Configure>", lambda e: (
            canvas.configure(scrollregion=canvas.bbox("all")),
            canvas.itemconfig(win, width=canvas.winfo_width())
        ))
        canvas.bind("<Configure>", lambda e: canvas.itemconfig(win, width=e.width))
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        # Tag config per tab
        tag_cfg = {
            "all_following":      (PALETTE["accent"], "Following"),
            "not_following_back": (PALETTE["red"],    "Not following you"),
            "fans":               (PALETTE["yellow"], "Follows you"),
            "mutual":             (PALETTE["green"],  "Mutual"),
            "all_followers":      (PALETTE["accent"], "Follower"),
        }
        tag_color, tag_text = tag_cfg.get(key, (PALETTE["subtext"], ""))

        cols = 3
        for i, (username, ts) in enumerate(filtered):
            r, c = divmod(i, cols)
            cell = tk.Frame(inner, bg=PALETTE["surface2"],
                            highlightbackground=PALETTE["border"],
                            highlightthickness=1)
            cell.grid(row=r, column=c, padx=5, pady=4, sticky="nsew")
            inner.columnconfigure(c, weight=1)

            # Avatar letter
            av_color = self._avatar_color(username)
            tk.Label(cell, text=username[0].upper(),
                     bg=av_color, fg=PALETTE["text"],
                     font=("Segoe UI", 12, "bold"), width=3, height=1).pack(
                side=LEFT, padx=(10, 8), pady=12)

            # Info
            info = tk.Frame(cell, bg=PALETTE["surface2"])
            info.pack(side=LEFT, fill=X, expand=True, pady=10)
            tk.Label(info, text=f"@{username}", bg=PALETTE["surface2"],
                     fg=PALETTE["text"], font=("Segoe UI", 10, "bold"), anchor=W).pack(anchor=W)
            sub_row = tk.Frame(info, bg=PALETTE["surface2"])
            sub_row.pack(anchor=W)
            tk.Label(sub_row, text=tag_text, bg=PALETTE["surface2"],
                     fg=tag_color, font=("Segoe UI", 8)).pack(side=LEFT)
            if ts:
                date_str = datetime.fromtimestamp(ts).strftime("  ·  %b %Y")
                tk.Label(sub_row, text=date_str, bg=PALETTE["surface2"],
                         fg=PALETTE["subtext"], font=("Segoe UI", 8)).pack(side=LEFT)

            # Open on Instagram button
            ig_btn = tk.Label(cell, text="↗", bg=PALETTE["surface2"],
                              fg=PALETTE["subtext"], font=("Segoe UI", 14),
                              cursor="hand2", padx=4)
            ig_btn.pack(side=RIGHT, pady=12)
            ig_url = f"https://www.instagram.com/{username}/"
            ig_btn.bind("<Button-1>", lambda e, url=ig_url: self._open_url(url))
            ig_btn.bind("<Enter>", lambda e, w=ig_btn: w.configure(fg=PALETTE["green"]))
            ig_btn.bind("<Leave>", lambda e, w=ig_btn: w.configure(fg=PALETTE["subtext"]))

            # Copy button
            cp_btn = tk.Label(cell, text="⧉", bg=PALETTE["surface2"],
                              fg=PALETTE["subtext"], font=("Segoe UI", 13),
                              cursor="hand2", padx=8)
            cp_btn.pack(side=RIGHT, pady=12)
            cp_btn.bind("<Button-1>", lambda e, u=username: self._copy_username(u))
            cp_btn.bind("<Enter>", lambda e, w=cp_btn: w.configure(fg=PALETTE["accent"]))
            cp_btn.bind("<Leave>", lambda e, w=cp_btn: w.configure(fg=PALETTE["subtext"]))

    def _avatar_color(self, username: str) -> str:
        colors = ["#7B2FBE", "#1B4D8E", "#1B6E4D", "#7A2E2E", "#5C4A1E", "#2E4A6E"]
        return colors[sum(ord(c) for c in username) % len(colors)]

    def _filter_list(self):
        if self.results:
            self._render_list()

    def _copy_username(self, username: str):
        self.clipboard_clear()
        self.clipboard_append(f"@{username}")
        ToastNotification(title="Copied!", message=f"@{username} copied",
                          duration=1800, bootstyle="success").show_toast()

    def _open_url(self, url: str):
        import webbrowser
        webbrowser.open(url)

    # ── export ─────────────────────────────────────────────────────────────────
    def _export_results(self):
        if not self.results:
            messagebox.showwarning("No Data", "Run an analysis first.")
            return
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text file", "*.txt"), ("JSON file", "*.json")],
            initialfile="instagram_analysis"
        )
        if not path:
            return

        if path.endswith(".json"):
            output = {k: [u for u, _ in v] for k, v in self.results.items()}
            with open(path, "w", encoding="utf-8") as f:
                json.dump(output, f, indent=2)
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write("Instagram Unfollower Tracker — Results\n")
                f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
                f.write("=" * 50 + "\n\n")
                sections = [
                    ("ALL FOLLOWING",       "all_following"),
                    ("NOT FOLLOWING BACK",  "not_following_back"),
                    ("YOUR FANS",           "fans"),
                    ("MUTUAL FOLLOWS",      "mutual"),
                    ("ALL FOLLOWERS",       "all_followers"),
                ]
                for title, key in sections:
                    entries = self.results.get(key, [])
                    f.write(f"{title} ({len(entries)})\n")
                    f.write("-" * 40 + "\n")
                    for u, _ in entries:
                        f.write(f"  @{u}\n")
                    f.write("\n")

        messagebox.showinfo("Exported", f"Saved to:\n{path}")

    def _set_status(self, msg: str, color=None):
        self.status_label.configure(text=msg, fg=color or PALETTE["subtext"])


# ── entry ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = InstagramTracker()
    app.mainloop()
