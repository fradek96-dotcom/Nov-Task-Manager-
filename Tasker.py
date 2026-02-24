import json
import os
import uuid
import calendar
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple

import ttkbootstrap as tb
from ttkbootstrap.constants import *
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
import tkinter.font as tkfont


APP_TITLE = "Úkolníček"
DATA_FILE = "tasks.json"


# ----------------------------
# Date helpers
# ----------------------------
def now_str() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M")


def iso_today() -> str:
    return date.today().isoformat()


def iso_tomorrow() -> str:
    return (date.today() + timedelta(days=1)).isoformat()


def iso_to_cz(iso: str) -> str:
    try:
        y, m, d = iso.split("-")
        return f"{d}.{m}.{y}"
    except Exception:
        return ""


def cz_to_iso(cz: str) -> Optional[str]:
    cz = cz.strip()
    if not cz:
        return None
    try:
        parts = cz.split(".")
        if len(parts) != 3:
            return None
        d = int(parts[0])
        m = int(parts[1])
        y = int(parts[2])
        dt = date(y, m, d)
        return dt.isoformat()
    except Exception:
        return None


# ----------------------------
# Data model
# ----------------------------
@dataclass
class Task:
    id: str
    title: str
    done: bool = False
    priority: int = 2
    created_at: str = ""
    notes: str = ""
    planned_for: str = ""  # ISO YYYY-MM-DD or ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = now_str()
        if self.planned_for is None:
            self.planned_for = ""


@dataclass
class SubTask:
    id: str
    title: str
    done: bool = False
    created_at: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = now_str()


@dataclass
class Project:
    id: str
    title: str
    done: bool = False
    created_at: str = ""
    notes: str = ""
    subtasks: List[SubTask] = None  # type: ignore

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = now_str()
        if self.subtasks is None:
            self.subtasks = []


# ----------------------------
# Storage (schema v2 + migration)
# ----------------------------
class Store:
    def __init__(self, path: str):
        self.path = path
        self.tasks: List[Task] = []
        self.projects: List[Project] = []

    def load(self) -> None:
        if not os.path.exists(self.path):
            self.tasks = []
            self.projects = []
            return

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            # old format: list of tasks
            if isinstance(raw, list):
                self.tasks = [Task(**item) for item in raw]
                self.projects = []
                self.save()
                return

            if isinstance(raw, dict):
                schema = raw.get("schema", None)

                if schema == 2:
                    tasks_raw = raw.get("tasks", [])
                    projs_raw = raw.get("projects", [])

                    self.tasks = [Task(**t) for t in tasks_raw]

                    projects: List[Project] = []
                    for p in projs_raw:
                        st_raw = p.get("subtasks", []) or []
                        subtasks = [SubTask(**s) for s in st_raw]
                        p_copy = dict(p)
                        p_copy["subtasks"] = subtasks
                        projects.append(Project(**p_copy))
                    self.projects = projects
                    return

                # v1-ish dict
                tasks_raw = raw.get("tasks", [])
                self.tasks = [Task(**t) for t in tasks_raw]
                self.projects = []
                self.save()
                return

            messagebox.showwarning("Data", "Neznámý formát dat. Začínám s prázdnými daty.")
            self.tasks = []
            self.projects = []

        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se načíst data:\n{e}")
            self.tasks = []
            self.projects = []

    def save(self) -> None:
        try:
            payload = {
                "schema": 2,
                "tasks": [asdict(t) for t in self.tasks],
                "projects": [
                    {
                        **{k: v for k, v in asdict(p).items() if k != "subtasks"},
                        "subtasks": [asdict(st) for st in p.subtasks],
                    }
                    for p in self.projects
                ],
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showerror("Chyba", f"Nepodařilo se uložit data:\n{e}")

    # helpers
    def get_task(self, task_id: str) -> Optional[Task]:
        for t in self.tasks:
            if t.id == task_id:
                return t
        return None

    def delete_task(self, task_id: str) -> bool:
        for i, t in enumerate(self.tasks):
            if t.id == task_id:
                del self.tasks[i]
                return True
        return False

    def get_project(self, project_id: str) -> Optional[Project]:
        for p in self.projects:
            if p.id == project_id:
                return p
        return None

    def delete_project(self, project_id: str) -> bool:
        for i, p in enumerate(self.projects):
            if p.id == project_id:
                del self.projects[i]
                return True
        return False


# ----------------------------
# UI styles / fonts
# ----------------------------
ZEBRA_EVEN = "#202736"
ZEBRA_ODD = "#293347"
DONE_FG = "#93a0b8"

SPACE_1 = 8
SPACE_2 = 12
SPACE_3 = 16


def setup_global_fonts_and_styles(root: tb.Window) -> None:
    default_font = tkfont.nametofont("TkDefaultFont")
    default_font.configure(size=12)
    root.option_add("*Font", default_font)

    heading_font = tkfont.nametofont("TkHeadingFont")
    heading_font.configure(size=12, weight="bold")

    title_font = tkfont.Font(family=default_font.cget("family"), size=13, weight="bold")

    small_ui_font = tkfont.Font(family=default_font.cget("family"), size=11)
    label_bold_font = tkfont.Font(family=default_font.cget("family"), size=11, weight="bold")

    style = ttk.Style()
    style.configure("Treeview", rowheight=42, borderwidth=0)
    style.configure("Treeview.Heading", font=heading_font, padding=(10, 8))
    style.map("Treeview", background=[("selected", "#2f6ca7")], foreground=[("selected", "#ffffff")])

    style.configure("UiCard.TLabelframe", padding=SPACE_2 + 2)
    style.configure("UiCard.TLabelframe.Label", font=title_font)

    style.configure("UiLabel.TLabel", font=small_ui_font)
    style.configure("UiLabelBold.TLabel", font=label_bold_font)
    style.configure("UiHint.TLabel", font=small_ui_font, foreground="#9eb0c9")

    style.configure("TButton", padding=(12, 7))
    style.configure("TEntry", padding=6)
    style.configure("TCombobox", padding=4)
    style.configure("TNotebook.Tab", padding=(14, 8), font=label_bold_font)


def apply_tree_zebra_style(tree: ttk.Treeview) -> None:
    tree.tag_configure("even", background=ZEBRA_EVEN)
    tree.tag_configure("odd", background=ZEBRA_ODD)
    tree.tag_configure("done", foreground=DONE_FG)


class DatePickerPopup(tk.Toplevel):
    def __init__(self, parent, initial_iso: Optional[str], on_select):
        super().__init__(parent)
        self.title("Vyber datum")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._on_select = on_select
        self._selected_date: Optional[date] = None

        initial = date.today()
        if initial_iso:
            try:
                initial = date.fromisoformat(initial_iso)
            except ValueError:
                initial = date.today()

        self._current_year = initial.year
        self._current_month = initial.month

        root = tb.Frame(self, padding=SPACE_2)
        root.grid(row=0, column=0, sticky="nsew")

        header = tb.Frame(root)
        header.grid(row=0, column=0, columnspan=7, sticky="ew", pady=(0, SPACE_1))
        header.grid_columnconfigure(1, weight=1)

        tb.Button(header, text="◀", width=3, command=self._prev_month).grid(row=0, column=0, padx=(0, SPACE_1))
        self._month_label = tb.Label(header, text="", anchor="center", style="UiLabelBold.TLabel")
        self._month_label.grid(row=0, column=1, sticky="ew")
        tb.Button(header, text="▶", width=3, command=self._next_month).grid(row=0, column=2, padx=(SPACE_1, 0))

        weekday_names = ["Po", "Út", "St", "Čt", "Pá", "So", "Ne"]
        for idx, name in enumerate(weekday_names):
            tb.Label(root, text=name, style="UiLabelBold.TLabel", width=3, anchor="center").grid(
                row=1, column=idx, padx=1, pady=(0, 2)
            )

        self._day_buttons: List[tb.Button] = []
        for r in range(6):
            for c in range(7):
                btn = tb.Button(root, text="", width=3, command=lambda d=0: self._pick_day(d))
                btn.grid(row=2 + r, column=c, padx=1, pady=1)
                self._day_buttons.append(btn)

        bottom = tb.Frame(root)
        bottom.grid(row=8, column=0, columnspan=7, sticky="ew", pady=(SPACE_1, 0))
        tb.Button(bottom, text="Bez data", bootstyle=SECONDARY, command=self._clear_date).pack(side=LEFT)
        tb.Button(bottom, text="Zavřít", command=self.destroy).pack(side=RIGHT)

        self.bind("<Escape>", lambda *_: self.destroy())
        self._render_calendar()

    def _render_calendar(self) -> None:
        self._month_label.configure(text=f"{self._current_month:02d}.{self._current_year}")

        month_matrix = calendar.monthcalendar(self._current_year, self._current_month)
        flat_days = [d for week in month_matrix for d in week]
        while len(flat_days) < len(self._day_buttons):
            flat_days.append(0)

        for btn, day_num in zip(self._day_buttons, flat_days):
            if day_num == 0:
                btn.configure(text="", state="disabled")
                continue

            btn.configure(text=str(day_num), state="normal", command=lambda d=day_num: self._pick_day(d))

    def _prev_month(self) -> None:
        self._current_month -= 1
        if self._current_month < 1:
            self._current_month = 12
            self._current_year -= 1
        self._render_calendar()

    def _next_month(self) -> None:
        self._current_month += 1
        if self._current_month > 12:
            self._current_month = 1
            self._current_year += 1
        self._render_calendar()

    def _pick_day(self, day_num: int) -> None:
        self._selected_date = date(self._current_year, self._current_month, day_num)
        self._on_select(self._selected_date.isoformat())
        self.destroy()

    def _clear_date(self) -> None:
        self._on_select("")
        self.destroy()


# ----------------------------
# UI: Tasks tab
# ----------------------------
class TasksTab(tb.Frame):
    def __init__(self, master, store: Store):
        super().__init__(master, padding=0)
        self.store = store

        self.view_var = tb.StringVar(value="active")  # active|done
        self.filter_var = tb.StringVar(value="all")   # all|unplanned|today|tomorrow|date
        self.filter_date_var = tb.StringVar(value=iso_to_cz(iso_today()))

        self.new_plan_var = tb.StringVar(value="unplanned")  # unplanned|today|tomorrow|date
        self.new_plan_date_var = tb.StringVar(value=iso_to_cz(iso_today()))

        self.selected_task_id: Optional[str] = None

        self._build_ui()
        apply_tree_zebra_style(self.tree)

        self.refresh_table()
        self._clear_detail()

    def current_view_done(self) -> bool:
        return self.view_var.get() == "done"

    def _planned_from_new_controls(self) -> str:
        mode = self.new_plan_var.get()
        if mode == "unplanned":
            return ""
        if mode == "today":
            return iso_today()
        if mode == "tomorrow":
            return iso_tomorrow()
        if mode == "date":
            iso = cz_to_iso(self.new_plan_date_var.get())
            return iso or ""
        return ""

    def _planned_filter_target(self) -> Tuple[str, Optional[str]]:
        mode = self.filter_var.get()
        if mode == "all":
            return ("all", None)
        if mode == "unplanned":
            return ("unplanned", None)
        if mode == "today":
            return ("date", iso_today())
        if mode == "tomorrow":
            return ("date", iso_tomorrow())
        if mode == "date":
            return ("date", cz_to_iso(self.filter_date_var.get()))
        return ("all", None)

    def _passes_filter(self, t: Task) -> bool:
        mode, iso = self._planned_filter_target()
        if mode == "all":
            return True
        if mode == "unplanned":
            return (t.planned_for or "") == ""
        if mode == "date":
            if not iso:
                return True
            return (t.planned_for or "") == iso
        return True

    def _update_new_plan_date_state(self) -> None:
        self.new_plan_date_entry.configure(state="normal" if self.new_plan_var.get() == "date" else "disabled")

    def _update_filter_date_state(self) -> None:
        self.filter_date_entry.configure(state="normal" if self.filter_var.get() == "date" else "disabled")

    def _build_ui(self) -> None:
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        top_card = tb.Labelframe(self, text="Nový úkol", style="UiCard.TLabelframe")
        top_card.grid(row=0, column=0, sticky="ew", padx=SPACE_2, pady=(SPACE_2, SPACE_1))
        top_card.grid_columnconfigure(1, weight=1)
        top_card.grid_columnconfigure(7, weight=0)

        tb.Label(top_card, text="Úkol:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.new_title_var = tb.StringVar()
        self.new_entry = tb.Entry(top_card, textvariable=self.new_title_var)
        self.new_entry.grid(row=0, column=1, sticky="ew", padx=(SPACE_1, SPACE_3))
        self.new_entry.bind("<Return>", lambda e: self.add_task())

        tb.Label(top_card, text="Priorita:", style="UiLabel.TLabel").grid(row=0, column=2, sticky="w")
        self.new_priority_var = tb.StringVar(value="2")
        tb.Combobox(
            top_card, textvariable=self.new_priority_var, values=["1", "2", "3"], width=6, state="readonly"
        ).grid(row=0, column=3, sticky="w", padx=(SPACE_1, SPACE_3))

        tb.Label(top_card, text="Plán:", style="UiLabel.TLabel").grid(row=0, column=4, sticky="w")
        tb.Combobox(
            top_card,
            textvariable=self.new_plan_var,
            values=["unplanned", "today", "tomorrow", "date"],
            width=12,
            state="readonly",
        ).grid(row=0, column=5, sticky="w", padx=(SPACE_1, SPACE_1))
        self.new_plan_var.trace_add("write", lambda *_: self._update_new_plan_date_state())

        self.new_plan_date_entry = tb.Entry(top_card, textvariable=self.new_plan_date_var, width=12, state="disabled")
        self.new_plan_date_entry.grid(row=0, column=6, sticky="w", padx=(0, SPACE_3))

        tb.Button(top_card, text="Přidat", bootstyle=SUCCESS, command=self.add_task).grid(row=0, column=7, sticky="e")
        tb.Label(top_card, text="Datum: DD.MM.RRRR", style="UiHint.TLabel").grid(
            row=1, column=5, columnspan=3, sticky="w", pady=(SPACE_1, 0)
        )

        center = tb.Frame(self, padding=0)
        center.grid(row=1, column=0, sticky="nsew", padx=SPACE_2, pady=(0, SPACE_1))
        center.grid_columnconfigure(0, weight=3)
        center.grid_columnconfigure(1, weight=2)
        center.grid_rowconfigure(0, weight=1)

        list_card = tb.Labelframe(center, text="Seznam úkolů", style="UiCard.TLabelframe")
        list_card.grid(row=0, column=0, sticky="nsew", padx=(0, SPACE_1))
        list_card.grid_columnconfigure(0, weight=1)
        list_card.grid_rowconfigure(0, weight=1)

        columns = ("title", "planned", "created", "priority")
        self.tree = ttk.Treeview(list_card, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("title", text="Název")
        self.tree.heading("planned", text="Plán")
        self.tree.heading("created", text="Vytvořeno")
        self.tree.heading("priority", text="Priorita")

        self.tree.column("title", width=420, anchor="w")
        self.tree.column("planned", width=110, anchor="center")
        self.tree.column("created", width=160, anchor="center")
        self.tree.column("priority", width=90, anchor="center")

        self.tree.grid(row=0, column=0, sticky="nsew")

        sb = tb.Scrollbar(list_card, orient="vertical", command=self.tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=sb.set)

        self.tree.bind("<<TreeviewSelect>>", lambda e: self.load_selected_to_detail())
        self.tree.bind("<Double-1>", lambda e: self.toggle_done_selected())

        detail = tb.Labelframe(center, text="Detail úkolu", style="UiCard.TLabelframe")
        detail.grid(row=0, column=1, sticky="nsew", padx=(SPACE_1, 0))
        detail.grid_columnconfigure(0, weight=1)
        detail.grid_rowconfigure(1, weight=1)

        row1 = tb.Frame(detail)
        row1.grid(row=0, column=0, sticky="ew")
        row1.grid_columnconfigure(1, weight=1)

        tb.Label(row1, text="Název:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.detail_title_var = tb.StringVar()
        tb.Entry(row1, textvariable=self.detail_title_var).grid(row=0, column=1, sticky="ew", padx=(SPACE_1, SPACE_3))

        tb.Label(row1, text="Priorita:", style="UiLabel.TLabel").grid(row=1, column=0, sticky="w", pady=(SPACE_1, 0))
        self.detail_priority_var = tb.StringVar(value="2")
        tb.Combobox(
            row1, textvariable=self.detail_priority_var, values=["1", "2", "3"], width=8, state="readonly"
        ).grid(row=1, column=1, sticky="w", padx=(SPACE_1, 0), pady=(SPACE_1, 0))

        tb.Label(row1, text="Plán:", style="UiLabel.TLabel").grid(row=2, column=0, sticky="w", pady=(SPACE_1, 0))
        self.detail_planned_var = tb.StringVar(value="")
        planned_controls = tb.Frame(row1)
        planned_controls.grid(row=2, column=1, sticky="w", padx=(SPACE_1, 0), pady=(SPACE_1, 0))
        tb.Entry(planned_controls, textvariable=self.detail_planned_var, width=14, state="readonly").pack(side=LEFT)
        tb.Button(planned_controls, text="📅", width=3, command=self.open_detail_date_picker).pack(side=LEFT, padx=(SPACE_1, 0))

        tb.Label(row1, text="Vytvořeno:", style="UiLabel.TLabel").grid(row=3, column=0, sticky="w", pady=(SPACE_1, 0))
        self.detail_created_var = tb.StringVar(value="")
        tb.Entry(row1, textvariable=self.detail_created_var, width=18, state="readonly").grid(
            row=3, column=1, sticky="w", padx=(SPACE_1, 0), pady=(SPACE_1, 0)
        )

        row2 = tb.Frame(detail)
        row2.grid(row=1, column=0, sticky="nsew", pady=(SPACE_2, 0))
        row2.grid_columnconfigure(0, weight=1)
        row2.grid_rowconfigure(1, weight=1)

        tb.Label(row2, text="Poznámka:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.detail_notes = tb.Text(row2, height=4, wrap="word")
        self.detail_notes.grid(row=1, column=0, sticky="nsew", pady=(SPACE_1, 0))

        row3 = tb.Frame(detail)
        row3.grid(row=2, column=0, sticky="ew", pady=(SPACE_2, 0))
        tb.Button(row3, text="Uložit změny", bootstyle=PRIMARY, command=self.save_detail_changes).pack(side=LEFT)

        bottom = tb.Labelframe(self, text="Filtr a akce", style="UiCard.TLabelframe")
        bottom.grid(row=2, column=0, sticky="ew", padx=SPACE_2, pady=(0, SPACE_2))
        bottom.grid_columnconfigure(7, weight=1)

        tb.Label(bottom, text="Zobrazit:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        tb.Radiobutton(bottom, text="Aktivní", value="active", variable=self.view_var, command=self.on_view_change).grid(
            row=0, column=1, sticky="w", padx=(SPACE_1, SPACE_1)
        )
        tb.Radiobutton(bottom, text="Vyřešené", value="done", variable=self.view_var, command=self.on_view_change).grid(
            row=0, column=2, sticky="w", padx=(0, SPACE_3)
        )

        tb.Label(bottom, text="Filtr:", style="UiLabel.TLabel").grid(row=0, column=3, sticky="w")
        tb.Combobox(
            bottom, textvariable=self.filter_var, values=["all", "unplanned", "today", "tomorrow", "date"],
            width=12, state="readonly"
        ).grid(row=0, column=4, sticky="w", padx=(SPACE_1, SPACE_1))
        self.filter_var.trace_add("write", lambda *_: (self._update_filter_date_state(), self.refresh_table(), self._clear_detail()))

        self.filter_date_entry = tb.Entry(bottom, textvariable=self.filter_date_var, width=12, state="disabled")
        self.filter_date_entry.grid(row=0, column=5, sticky="w", padx=(0, SPACE_3))
        self.filter_date_var.trace_add("write", lambda *_: (self.refresh_table(), self._clear_detail()))

        self.toggle_btn = tb.Button(bottom, text="Hotovo", bootstyle=SUCCESS, command=self.toggle_done_selected)
        self.toggle_btn.grid(row=0, column=6, sticky="w")
        tb.Button(bottom, text="Smazat", bootstyle=DANGER, command=self.delete_selected).grid(
            row=0, column=7, sticky="w", padx=(SPACE_1, 0)
        )

        self.status_var = tb.StringVar(value="")
        tb.Label(bottom, textvariable=self.status_var, anchor="e", style="UiHint.TLabel").grid(
            row=0, column=8, sticky="e", padx=(SPACE_2, 0)
        )

        self._update_new_plan_date_state()
        self._update_filter_date_state()
        self.after(50, lambda: self.new_entry.focus_set())

    def on_view_change(self) -> None:
        self.refresh_table()
        self._clear_detail()
        self.toggle_btn.configure(text="Vrátit" if self.current_view_done() else "Hotovo",
                                 bootstyle=WARNING if self.current_view_done() else SUCCESS)

    def refresh_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        show_done = self.current_view_done()
        visible_idx = 0
        for t in self.store.tasks:
            if t.done != show_done:
                continue
            if not self._passes_filter(t):
                continue

            planned = iso_to_cz(t.planned_for) if (t.planned_for or "") else ""
            tags = ["even" if visible_idx % 2 == 0 else "odd"]
            if t.done:
                tags.append("done")

            self.tree.insert("", "end", iid=t.id, values=(t.title, planned, t.created_at, t.priority), tags=tuple(tags))
            visible_idx += 1

        total = len(self.store.tasks)
        done = sum(1 for t in self.store.tasks if t.done)
        active = total - done
        mode = "Vyřešené" if show_done else "Aktivní"
        self.status_var.set(f"{mode}: {visible_idx} | Aktivní: {active} | Vyřešené: {done} | Celkem: {total}")

    def add_task(self) -> None:
        title = self.new_title_var.get().strip()
        if not title:
            return

        try:
            pr = int(self.new_priority_var.get())
            if pr not in (1, 2, 3):
                raise ValueError
        except ValueError:
            messagebox.showwarning("Priorita", "Priorita musí být 1, 2 nebo 3.")
            return

        planned_iso = self._planned_from_new_controls()
        if self.new_plan_var.get() == "date" and not planned_iso:
            messagebox.showwarning("Plán", "Datum plánu zadej jako DD.MM.RRRR (např. 23.02.2026).")
            return

        self.store.tasks.insert(0, Task(id=str(uuid.uuid4()), title=title, priority=pr, planned_for=planned_iso))
        self.store.save()

        self.new_title_var.set("")
        self.new_priority_var.set("2")
        self.new_plan_var.set("unplanned")
        self._update_new_plan_date_state()

        if self.current_view_done():
            self.view_var.set("active")
            self.on_view_change()
        else:
            self.refresh_table()

        self.after(20, lambda: self.new_entry.focus_set())

    def _get_selected_id(self) -> Optional[str]:
        sel = self.tree.selection()
        return sel[0] if sel else None

    def load_selected_to_detail(self) -> None:
        task_id = self._get_selected_id()
        if not task_id:
            self._clear_detail()
            return

        t = self.store.get_task(task_id)
        if not t:
            self._clear_detail()
            return

        self.selected_task_id = t.id
        self.detail_title_var.set(t.title)
        self.detail_priority_var.set(str(t.priority))
        self.detail_created_var.set(t.created_at)
        self.detail_planned_var.set(iso_to_cz(t.planned_for) if (t.planned_for or "") else "")

        self.detail_notes.delete("1.0", "end")
        self.detail_notes.insert("1.0", t.notes or "")

    def save_detail_changes(self) -> None:
        if not self.selected_task_id:
            return
        t = self.store.get_task(self.selected_task_id)
        if not t:
            self._clear_detail()
            return

        title = self.detail_title_var.get().strip()
        if not title:
            messagebox.showwarning("Název", "Název úkolu nemůže být prázdný.")
            return

        try:
            pr = int(self.detail_priority_var.get())
            if pr not in (1, 2, 3):
                raise ValueError
        except ValueError:
            messagebox.showwarning("Priorita", "Priorita musí být 1, 2 nebo 3.")
            return

        planned_cz = self.detail_planned_var.get().strip()
        planned_iso = ""
        if planned_cz:
            iso = cz_to_iso(planned_cz)
            if not iso:
                messagebox.showwarning("Plán", "Datum plánu zadej jako DD.MM.RRRR (např. 23.02.2026).")
                return
            planned_iso = iso

        t.title = title
        t.priority = pr
        t.planned_for = planned_iso
        t.notes = self.detail_notes.get("1.0", "end").rstrip()

        self.store.save()
        self.refresh_table()
        try:
            self.tree.selection_set(t.id)
        except Exception:
            pass

    def open_detail_date_picker(self) -> None:
        current_iso = cz_to_iso(self.detail_planned_var.get())
        picker = DatePickerPopup(self, current_iso, self._on_detail_date_picked)
        picker.wait_window()

    def _on_detail_date_picked(self, selected_iso: str) -> None:
        self.detail_planned_var.set(iso_to_cz(selected_iso) if selected_iso else "")

    def toggle_done_selected(self) -> None:
        task_id = self._get_selected_id()
        if not task_id:
            return
        t = self.store.get_task(task_id)
        if not t:
            return
        t.done = not t.done
        self.store.save()
        self.refresh_table()
        self._clear_detail()

    def delete_selected(self) -> None:
        task_id = self._get_selected_id()
        if not task_id:
            return
        t = self.store.get_task(task_id)
        if not t:
            return
        if not messagebox.askyesno("Smazat", f"Opravdu smazat úkol?\n\n{t.title}"):
            return
        self.store.delete_task(task_id)
        self.store.save()
        self.refresh_table()
        self._clear_detail()

    def _clear_detail(self) -> None:
        self.selected_task_id = None
        self.detail_title_var.set("")
        self.detail_priority_var.set("2")
        self.detail_created_var.set("")
        self.detail_planned_var.set("")
        self.detail_notes.delete("1.0", "end")


# ----------------------------
# UI: Projects tab (splitter + fixed bottom via grid)
# ----------------------------
class ProjectsTab(tb.Frame):
    def __init__(self, master, store: Store):
        super().__init__(master, padding=0)
        self.store = store

        self.view_var = tb.StringVar(value="active")
        self.selected_project_id: Optional[str] = None
        self.selected_subtask_id: Optional[str] = None

        self._build_ui()
        apply_tree_zebra_style(self.projects_tree)
        self._setup_projects_tree_style()
        apply_tree_zebra_style(self.sub_tree)

        self.refresh_projects()
        self._clear_project_detail()

    def _setup_projects_tree_style(self) -> None:
        project_font = tkfont.Font(size=12, weight="bold")
        self.projects_tree.tag_configure("project_even", background="#273244", font=project_font)
        self.projects_tree.tag_configure("project_odd", background="#2c394d", font=project_font)
        self.projects_tree.tag_configure("project_done", foreground=DONE_FG)

    def current_view_done(self) -> bool:
        return self.view_var.get() == "done"

    def _build_ui(self) -> None:
        # IMPORTANT: use grid so bottom bar is always visible
        self.grid_rowconfigure(1, weight=1)  # paned expands
        self.grid_columnconfigure(0, weight=1)

        # Top add bar
        top = tb.Labelframe(self, text="Nový projekt", style="UiCard.TLabelframe")
        top.grid(row=0, column=0, sticky="ew", padx=SPACE_2, pady=(SPACE_2, 0))
        top.grid_columnconfigure(1, weight=1)

        tb.Label(top, text="Projekt:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.new_title_var = tb.StringVar()
        self.new_entry = tb.Entry(top, textvariable=self.new_title_var)
        self.new_entry.grid(row=0, column=1, sticky="ew", padx=(SPACE_1, SPACE_3))
        self.new_entry.bind("<Return>", lambda e: self.add_project())
        tb.Button(top, text="Přidat projekt", bootstyle=SUCCESS, command=self.add_project).grid(row=0, column=2, sticky="e")

        # Splitter
        self.paned = ttk.Panedwindow(self, orient="vertical")
        self.paned.grid(row=1, column=0, sticky="nsew", padx=SPACE_2, pady=(SPACE_1, SPACE_1))

        # Pane top: projects list
        pane_top = tb.Frame(self.paned)
        self.paned.add(pane_top, weight=1)
        pane_top.grid_columnconfigure(0, weight=1)
        pane_top.grid_rowconfigure(0, weight=1)

        columns = ("title", "created", "state")
        self.projects_tree = ttk.Treeview(pane_top, columns=columns, show="headings", selectmode="browse")
        self.projects_tree.heading("title", text="Název projektu")
        self.projects_tree.heading("created", text="Datum")
        self.projects_tree.heading("state", text="Stav")
        self.projects_tree.column("title", width=520, anchor="w")
        self.projects_tree.column("created", width=150, anchor="center")
        self.projects_tree.column("state", width=120, anchor="center")
        self.projects_tree.grid(row=0, column=0, sticky="nsew")

        sb = tb.Scrollbar(pane_top, orient="vertical", command=self.projects_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.projects_tree.configure(yscrollcommand=sb.set)

        self.projects_tree.bind("<<TreeviewSelect>>", lambda e: self.load_selected_project())
        self.projects_tree.bind("<Double-1>", lambda e: self.toggle_project_done())

        # Pane bottom: detail + subtasks
        pane_bottom = tb.Frame(self.paned)
        self.paned.add(pane_bottom, weight=3)
        pane_bottom.grid_columnconfigure(0, weight=1)
        pane_bottom.grid_rowconfigure(0, weight=1)

        detail = tb.Labelframe(pane_bottom, text="Detail projektu", style="UiCard.TLabelframe")
        detail.grid(row=0, column=0, sticky="nsew")
        detail.grid_columnconfigure(0, weight=1)

        row1 = tb.Frame(detail)
        row1.grid(row=0, column=0, sticky="ew")
        row1.grid_columnconfigure(0, weight=1)

        tb.Label(row1, text="Vytvořeno:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="e")
        self.proj_created_var = tb.StringVar(value="")
        tb.Entry(row1, textvariable=self.proj_created_var, width=18, state="readonly").grid(row=0, column=1, sticky="e", padx=(8, 0))

        row2 = tb.Frame(detail)
        row2.grid(row=1, column=0, sticky="ew", pady=(SPACE_1, 0))
        row2.grid_columnconfigure(0, weight=1)

        tb.Label(row2, text="Popis / poznámka projektu:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.proj_notes = tb.Text(row2, height=2, wrap="word")
        self.proj_notes.grid(row=1, column=0, sticky="ew", pady=(SPACE_1, 0))

        row3 = tb.Frame(detail)
        row3.grid(row=2, column=0, sticky="ew", pady=(SPACE_1, SPACE_1))
        tb.Button(row3, text="Uložit projekt", bootstyle=PRIMARY, command=self.save_project).pack(side=LEFT)

        sub = tb.Labelframe(detail, text="Podúkoly (postup)", style="UiCard.TLabelframe")
        sub.grid(row=3, column=0, sticky="nsew")
        detail.grid_rowconfigure(3, weight=1)
        sub.grid_columnconfigure(0, weight=1)
        sub.grid_rowconfigure(1, weight=1)

        sub_top = tb.Frame(sub)
        sub_top.grid(row=0, column=0, sticky="ew")
        sub_top.grid_columnconfigure(1, weight=1)

        tb.Label(sub_top, text="Podúkol:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        self.new_sub_var = tb.StringVar()
        self.new_sub_entry = tb.Entry(sub_top, textvariable=self.new_sub_var)
        self.new_sub_entry.grid(row=0, column=1, sticky="ew", padx=(SPACE_1, SPACE_3))
        self.new_sub_entry.bind("<Return>", lambda e: self.add_subtask())
        tb.Button(sub_top, text="Přidat", bootstyle=SUCCESS, command=self.add_subtask).grid(row=0, column=2, sticky="e")

        sub_mid = tb.Frame(sub)
        sub_mid.grid(row=1, column=0, sticky="nsew", pady=(SPACE_1, 0))
        sub_mid.grid_columnconfigure(0, weight=1)
        sub_mid.grid_rowconfigure(0, weight=1)

        st_columns = ("done", "title", "created")
        self.sub_tree = ttk.Treeview(sub_mid, columns=st_columns, show="headings", selectmode="browse")
        self.sub_tree.heading("done", text="✓")
        self.sub_tree.heading("title", text="Podúkol")
        self.sub_tree.heading("created", text="Datum")
        self.sub_tree.column("done", width=40, anchor="center")
        self.sub_tree.column("title", width=560, anchor="w")
        self.sub_tree.column("created", width=150, anchor="center")
        self.sub_tree.grid(row=0, column=0, sticky="nsew")

        sb2 = tb.Scrollbar(sub_mid, orient="vertical", command=self.sub_tree.yview)
        sb2.grid(row=0, column=1, sticky="ns")
        self.sub_tree.configure(yscrollcommand=sb2.set)

        self.sub_tree.bind("<<TreeviewSelect>>", lambda e: self._sub_selected())
        self.sub_tree.bind("<Double-1>", lambda e: self.toggle_subtask_done())

        sub_bottom = tb.Frame(sub)
        sub_bottom.grid(row=2, column=0, sticky="ew", pady=(SPACE_2, 0))
        tb.Button(sub_bottom, text="Hotovo", bootstyle=SUCCESS, command=self.toggle_subtask_done).pack(side=LEFT)
        tb.Button(sub_bottom, text="Smazat podúkol", bootstyle=DANGER, command=self.delete_subtask).pack(side=LEFT, padx=(10, 0))

        # Bottom bar (fixed)
        bottom = tb.Labelframe(self, text="Filtr a akce", style="UiCard.TLabelframe")
        bottom.grid(row=2, column=0, sticky="ew", padx=SPACE_2, pady=(0, SPACE_2))
        bottom.grid_columnconfigure(10, weight=1)

        tb.Label(bottom, text="Zobrazit:", style="UiLabel.TLabel").grid(row=0, column=0, sticky="w")
        tb.Radiobutton(bottom, text="Aktivní", value="active", variable=self.view_var, command=self.on_view_change).grid(
            row=0, column=1, sticky="w", padx=(8, 8)
        )
        tb.Radiobutton(bottom, text="Vyřešené", value="done", variable=self.view_var, command=self.on_view_change).grid(
            row=0, column=2, sticky="w", padx=(0, 18)
        )

        self.proj_toggle_btn = tb.Button(bottom, text="Hotovo", bootstyle=SUCCESS, command=self.toggle_project_done)
        self.proj_toggle_btn.grid(row=0, column=3, sticky="w")
        tb.Button(bottom, text="Smazat projekt", bootstyle=DANGER, command=self.delete_project).grid(row=0, column=4, sticky="w", padx=(10, 0))

        self.status_var = tb.StringVar(value="")
        tb.Label(bottom, textvariable=self.status_var, anchor="e", style="UiHint.TLabel").grid(row=0, column=10, sticky="e")

        self.after(50, lambda: self.new_entry.focus_set())

    # ---- Projects
    def on_view_change(self) -> None:
        self.refresh_projects()
        self._clear_project_detail()
        self.proj_toggle_btn.configure(text="Vrátit" if self.current_view_done() else "Hotovo",
                                       bootstyle=WARNING if self.current_view_done() else SUCCESS)

    def refresh_projects(self) -> None:
        for item in self.projects_tree.get_children():
            self.projects_tree.delete(item)

        show_done = self.current_view_done()
        visible_idx = 0
        for p in self.store.projects:
            if p.done != show_done:
                continue
            state = "Vyřešeno" if p.done else "Aktivní"
            tags = ["project_even" if visible_idx % 2 == 0 else "project_odd"]
            if p.done:
                tags.append("project_done")
            self.projects_tree.insert("", "end", iid=p.id, values=(p.title, p.created_at, state), tags=tuple(tags))
            visible_idx += 1

        total = len(self.store.projects)
        done = sum(1 for p in self.store.projects if p.done)
        active = total - done
        mode = "Vyřešené" if show_done else "Aktivní"
        self.status_var.set(f"{mode}: {visible_idx} | Aktivní: {active} | Vyřešené: {done} | Celkem: {total}")

    def add_project(self) -> None:
        title = self.new_title_var.get().strip()
        if not title:
            return
        self.store.projects.insert(0, Project(id=str(uuid.uuid4()), title=title))
        self.store.save()

        self.new_title_var.set("")
        if self.current_view_done():
            self.view_var.set("active")
            self.on_view_change()
        else:
            self.refresh_projects()
        self.after(20, lambda: self.new_entry.focus_set())

    def _get_selected_project_id(self) -> Optional[str]:
        sel = self.projects_tree.selection()
        return sel[0] if sel else None

    def load_selected_project(self) -> None:
        pid = self._get_selected_project_id()
        if not pid:
            self._clear_project_detail()
            return
        p = self.store.get_project(pid)
        if not p:
            self._clear_project_detail()
            return

        self.selected_project_id = p.id
        self.proj_created_var.set(p.created_at)
        self.proj_notes.delete("1.0", "end")
        self.proj_notes.insert("1.0", p.notes or "")

        self.refresh_subtasks()

    def save_project(self) -> None:
        if not self.selected_project_id:
            return
        p = self.store.get_project(self.selected_project_id)
        if not p:
            self._clear_project_detail()
            return

        p.notes = self.proj_notes.get("1.0", "end").rstrip()

        self.store.save()
        self.refresh_projects()
        try:
            self.projects_tree.selection_set(p.id)
        except Exception:
            pass

    def toggle_project_done(self) -> None:
        pid = self._get_selected_project_id()
        if not pid:
            return
        p = self.store.get_project(pid)
        if not p:
            return
        p.done = not p.done
        self.store.save()
        self.refresh_projects()
        self._clear_project_detail()

    def delete_project(self) -> None:
        pid = self._get_selected_project_id()
        if not pid:
            return
        p = self.store.get_project(pid)
        if not p:
            return
        if not messagebox.askyesno("Smazat", f"Opravdu smazat projekt?\n\n{p.title}"):
            return
        self.store.delete_project(pid)
        self.store.save()
        self.refresh_projects()
        self._clear_project_detail()

    # ---- Subtasks
    def refresh_subtasks(self) -> None:
        for item in self.sub_tree.get_children():
            self.sub_tree.delete(item)

        self.selected_subtask_id = None
        if not self.selected_project_id:
            return
        p = self.store.get_project(self.selected_project_id)
        if not p:
            return

        visible_idx = 0
        for st in p.subtasks:
            mark = "✓" if st.done else ""
            tags = ["even" if visible_idx % 2 == 0 else "odd"]
            if st.done:
                tags.append("done")
            self.sub_tree.insert("", "end", iid=st.id, values=(mark, st.title, st.created_at), tags=tuple(tags))
            visible_idx += 1

    def _sub_selected(self) -> None:
        sel = self.sub_tree.selection()
        self.selected_subtask_id = sel[0] if sel else None

    def add_subtask(self) -> None:
        if not self.selected_project_id:
            return
        p = self.store.get_project(self.selected_project_id)
        if not p:
            return
        title = self.new_sub_var.get().strip()
        if not title:
            return

        p.subtasks.insert(0, SubTask(id=str(uuid.uuid4()), title=title))
        self.store.save()
        self.new_sub_var.set("")
        self.refresh_subtasks()
        self.after(20, lambda: self.new_sub_entry.focus_set())

    def _get_selected_subtask(self) -> Optional[SubTask]:
        if not self.selected_project_id or not self.selected_subtask_id:
            return None
        p = self.store.get_project(self.selected_project_id)
        if not p:
            return None
        for st in p.subtasks:
            if st.id == self.selected_subtask_id:
                return st
        return None

    def toggle_subtask_done(self) -> None:
        st = self._get_selected_subtask()
        if not st:
            return
        st.done = not st.done
        self.store.save()
        self.refresh_subtasks()

    def delete_subtask(self) -> None:
        if not self.selected_project_id or not self.selected_subtask_id:
            return
        p = self.store.get_project(self.selected_project_id)
        if not p:
            return
        st = self._get_selected_subtask()
        if not st:
            return
        if not messagebox.askyesno("Smazat", f"Opravdu smazat podúkol?\n\n{st.title}"):
            return
        p.subtasks = [x for x in p.subtasks if x.id != st.id]
        self.store.save()
        self.refresh_subtasks()

    def _clear_project_detail(self) -> None:
        self.selected_project_id = None
        self.selected_subtask_id = None
        self.proj_created_var.set("")
        self.proj_notes.delete("1.0", "end")
        for item in self.sub_tree.get_children():
            self.sub_tree.delete(item)
        self.new_sub_var.set("")


# ----------------------------
# App
# ----------------------------
class App(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title(APP_TITLE)
        self.geometry("1180x790")
        self.minsize(980, 700)

        setup_global_fonts_and_styles(self)

        self.store = Store(DATA_FILE)
        self.store.load()

        nb = tb.Notebook(self)
        nb.pack(fill=BOTH, expand=True)

        self.tasks_tab = TasksTab(nb, self.store)
        self.projects_tab = ProjectsTab(nb, self.store)

        nb.add(self.tasks_tab, text="Úkoly")
        nb.add(self.projects_tab, text="Projekty")

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self) -> None:
        self.store.save()
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
