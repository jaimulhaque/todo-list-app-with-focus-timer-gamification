import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
from tkcalendar import Calendar
import mysql.connector
from datetime import datetime, timedelta
import threading
import time
from plyer import notification
from zoneinfo import ZoneInfo
import random

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class ToDoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do List")
        self.root.geometry("1000x700")
        self.root.minsize(800, 500)

        self.bangladesh_tz = ZoneInfo("Asia/Dhaka")
        self.db_config = {"host": "localhost", "user": "todo_user", "password": "secure_password", "database": "todo_app"}
        self.db = None
        self.cursor = None

        if not self._connect_db():
            messagebox.showerror("Error", "Database connection failed.")
            self.root.destroy()
            return

        self._create_tables()

        self.is_dark_mode = True
        self.prayer_times = {"Fajr": "4:30 AM", "Dhuhr": "12:00 PM", "Asr": "3:30 PM", "Maghrib": "6:30 PM", "Isha": "8:00 PM"}
        self.hadiths = [
            "The best of you are those who are best to your families.",
            "Seek knowledge from cradle to grave.",
            "The merciful are shown mercy.",
            "Speak good or remain silent.",
            "Control anger to be strong."
        ]
        self.last_hadith_time = None
        self.selected_task_time = None
        self.selected_reminder_time = None
        self.note_ids = {}
        self.task_ids = {}
        self.reminder_ids = {}
        self.task_view = "current"
        self.pomodoro_running = False
        self.pomodoro_time = 25 * 60
        self.is_work_session = True
        self.pomodoro_last_time = None
        self.session_count = 0

        self._setup_ui()
        self._test_notification()
        threading.Thread(target=self._check_reminders, daemon=True).start()
        threading.Thread(target=self._check_hadith, daemon=True).start()
        self._update_prayer_marquee()

    def _connect_db(self):
        try:
            if self.db and self.db.is_connected():
                self.cursor.close()
                self.db.close()
            self.db = mysql.connector.connect(**self.db_config)
            self.cursor = self.db.cursor()
            return True
        except mysql.connector.Error:
            return False

    def _create_tables(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS notes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS schedule (
                id INT AUTO_INCREMENT PRIMARY KEY,
                task VARCHAR(255) NOT NULL,
                time_slot TIME NOT NULL,
                date DATE NOT NULL,
                completed BOOLEAN DEFAULT FALSE
            )
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INT AUTO_INCREMENT PRIMARY KEY,
                title VARCHAR(255) NOT NULL,
                reminder_time VARCHAR(50) NOT NULL,
                `repeat` BOOLEAN DEFAULT FALSE
            )
        """)
        self.db.commit()

    def _setup_ui(self):
        self.main_container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=15, pady=15)

        self.header_frame = ctk.CTkFrame(self.main_container, corner_radius=15, fg_color="#252545")
        self.header_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(self.header_frame, text="To-Do List", font=("Helvetica", 28, "bold"), text_color="#FFFFFF").pack(pady=10, padx=20, anchor="w")
        self.marquee_canvas = tk.Canvas(self.header_frame, height=30, bg="#252545", highlightthickness=0)
        self.marquee_canvas.pack(fill="x", padx=10, pady=5)
        self.marquee_text = self.marquee_canvas.create_text(0, 15, anchor="w", font=("Helvetica", 12), fill="#A3BFFA")

        self.content_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True)

        self.sidebar = ctk.CTkFrame(self.content_container, width=200, corner_radius=15, fg_color="#2D2D4A")
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        button_config = {"font": ("Helvetica", 14, "bold"), "corner_radius": 10, "fg_color": "#4F46E5", "hover_color": "#4338CA", "height": 45, "text_color": "#FFFFFF"}
        for text, cmd in [("Notes", self.show_notes), ("Tasks", self.show_task), ("Reminders", self.show_reminders), ("Pomodoro", self.show_pomodoro)]:
            ctk.CTkButton(self.sidebar, text=text, command=cmd, **button_config).pack(pady=5, padx=10, fill="x")

        self.theme_btn = ctk.CTkButton(self.sidebar, text="Light Mode", command=self.toggle_theme, font=("Helvetica", 14, "bold"), corner_radius=10, fg_color="#10B981", hover_color="#059669", height=45)
        self.theme_btn.pack(pady=(10, 20), padx=10, fill="x", side="bottom")

        self.content_frame = ctk.CTkFrame(self.content_container, corner_radius=15, fg_color="#2D2D4A")
        self.content_frame.pack(side="left", fill="both", expand=True)
        self.show_notes()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        ctk.set_appearance_mode("dark" if self.is_dark_mode else "light")
        self.theme_btn.configure(text="Light Mode" if self.is_dark_mode else "Dark Mode")
        marquee_bg, marquee_text_color = ("#252545", "#A3BFFA") if self.is_dark_mode else ("#E5E7EB", "#6B7280")
        self.header_frame.configure(fg_color=marquee_bg)
        self.marquee_canvas.configure(bg=marquee_bg)
        self.marquee_canvas.itemconfig(self.marquee_text, fill=marquee_text_color)
        self.sidebar.configure(fg_color="#2D2D4A" if self.is_dark_mode else "#F3F4F6")
        self.content_frame.configure(fg_color="#2D2D4A" if self.is_dark_mode else "#FFFFFF")

    def _clear_content_frame(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _create_tk_listbox(self, parent_frame, height=10):
        return tk.Listbox(parent_frame, height=height, font=("Helvetica", 12), borderwidth=0, highlightthickness=0, relief="flat",
                          bg="#2D2D4A" if self.is_dark_mode else "#FFFFFF", fg="#E5E7EB" if self.is_dark_mode else "#1F2937",
                          selectbackground="#4F46E5", selectforeground="#FFFFFF", activestyle="none")

    def _open_time_picker(self, title, callback_func):
        picker_window = ctk.CTkToplevel(self.root)
        picker_window.title(title)
        picker_window.geometry("400x450")
        picker_window.transient(self.root)
        picker_window.grab_set()

        ctk.CTkLabel(picker_window, text="Select Date", font=("Helvetica", 16, "bold")).pack(pady=(20, 5))
        today = datetime.now(self.bangladesh_tz).date()
        calendar = Calendar(picker_window, selectmode="day", date_pattern="yyyy-mm-dd", year=today.year, month=today.month, day=today.day)
        calendar.pack(padx=20, pady=10)

        ctk.CTkLabel(picker_window, text="Select Time", font=("Helvetica", 16, "bold")).pack(pady=(10, 5))
        time_frame = ctk.CTkFrame(picker_window, fg_color="transparent")
        time_frame.pack(pady=10)
        hour_entry = ctk.CTkEntry(time_frame, placeholder_text="HH", width=60, font=("Helvetica", 14))
        hour_entry.pack(side="left", padx=(0, 5))
        ctk.CTkLabel(time_frame, text=":", font=("Helvetica", 14)).pack(side="left")
        minute_entry = ctk.CTkEntry(time_frame, placeholder_text="MM", width=60, font=("Helvetica", 14))
        minute_entry.pack(side="left", padx=(5, 10))
        am_pm_var = tk.StringVar(value="AM")
        ctk.CTkOptionMenu(time_frame, values=["AM", "PM"], variable=am_pm_var, font=("Helvetica", 14), width=80, fg_color="#4F46E5", button_color="#4F46E5").pack(side="left")

        def save_and_close():
            try:
                date_str = calendar.get_date()
                hour, minute = int(hour_entry.get().strip()), int(minute_entry.get().strip())
                if not (1 <= hour <= 12) or not (0 <= minute <= 59):
                    raise ValueError
                combined_dt_str = f"{date_str} {hour:02d}:{minute:02d} {am_pm_var.get()}"
                datetime.strptime(combined_dt_str, "%Y-%m-%d %I:%M %p")
                callback_func(combined_dt_str)
                picker_window.destroy()
            except ValueError:
                messagebox.showwarning("Invalid Input", "Please enter a valid date and time.")

        ctk.CTkButton(picker_window, text="Confirm", command=save_and_close, font=("Helvetica", 14, "bold"), fg_color="#4F46E5", hover_color="#4338CA", height=40).pack(pady=20)

    def show_pomodoro(self):
        self._clear_content_frame()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content_wrapper, text="Pomodoro Timer", font=("Helvetica", 24, "bold"), text_color="#E5E7EB").pack(anchor="w", pady=(0, 15))
        timer_card = ctk.CTkFrame(content_wrapper, corner_radius=15, fg_color="#3A3A5A")
        timer_card.pack(fill="x", pady=10)
        self.pomodoro_status_label = ctk.CTkLabel(timer_card, text="Work Session", font=("Helvetica", 18), text_color="#34D399")
        self.pomodoro_status_label.pack(pady=10)
        self.pomodoro_label = ctk.CTkLabel(timer_card, text="25:00", font=("Helvetica", 48, "bold"), text_color="#E5E7EB")
        self.pomodoro_label.pack(pady=10)

        button_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        button_frame.pack(pady=15)
        ctk.CTkButton(button_frame, text="Start", command=self._start_pomodoro, font=("Helvetica", 14, "bold"), fg_color="#34D399", hover_color="#059669", width=100).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Pause", command=self._pause_pomodoro, font=("Helvetica", 14, "bold"), fg_color="#FBBF24", hover_color="#D97706", width=100).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Reset", command=self._reset_pomodoro, font=("Helvetica", 14, "bold"), fg_color="#EF4444", hover_color="#DC2626", width=100).pack(side="left", padx=5)

        self.session_label = ctk.CTkLabel(content_wrapper, text=f"Completed Sessions: {self.session_count}", font=("Helvetica", 14), text_color="#E5E7EB")
        self.session_label.pack(pady=10)
        self._update_pomodoro()

    def _start_pomodoro(self):
        if not self.pomodoro_running:
            self.pomodoro_running = True
            self.pomodoro_last_time = time.time()
            self._update_pomodoro()

    def _pause_pomodoro(self):
        if self.pomodoro_running:
            self.pomodoro_running = False
            self.pomodoro_time = max(0, self.pomodoro_time - (time.time() - self.pomodoro_last_time))

    def _reset_pomodoro(self):
        self.pomodoro_running = False
        self.is_work_session = True
        self.pomodoro_time = 25 * 60
        self.pomodoro_label.configure(text="25:00")
        self.pomodoro_status_label.configure(text="Work Session", text_color="#34D399")

    def _format_time(self, seconds):
        minutes, secs = divmod(int(seconds), 60)
        return f"{minutes:02d}:{secs:02d}"

    def _update_pomodoro(self):
        if self.pomodoro_running:
            elapsed = time.time() - self.pomodoro_last_time
            self.pomodoro_time = max(0, self.pomodoro_time - elapsed)
            self.pomodoro_last_time = time.time()
            self.pomodoro_label.configure(text=self._format_time(self.pomodoro_time))
            if self.pomodoro_time <= 0:
                self.pomodoro_running = False
                if self.is_work_session:
                    self.session_count += 1
                    self.session_label.configure(text=f"Completed Sessions: {self.session_count}")
                    self.pomodoro_time = 5 * 60
                    self.is_work_session = False
                    self.pomodoro_status_label.configure(text="Break", text_color="#FBBF24")
                    notification.notify(title="Pomodoro", message="Time for a 5-minute break!", timeout=10)
                else:
                    self.pomodoro_time = 25 * 60
                    self.is_work_session = True
                    self.pomodoro_status_label.configure(text="Work Session", text_color="#34D399")
                    notification.notify(title="Pomodoro", message="Start a new work session!", timeout=10)
                self.pomodoro_label.configure(text=self._format_time(self.pomodoro_time))
            self.root.after(100, self._update_pomodoro)

    def show_notes(self):
        self._clear_content_frame()
        self.note_ids.clear()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content_wrapper, text="Notes", font=("Helvetica", 24, "bold"), text_color="#E5E7EB").pack(anchor="w", pady=(0, 15))
        input_card = ctk.CTkFrame(content_wrapper, corner_radius=15, fg_color="#3A3A5A")
        input_card.pack(fill="x", pady=(0, 10))
        self.note_title_entry = ctk.CTkEntry(input_card, placeholder_text="Note Title", font=("Helvetica", 14), height=40, fg_color="#4B4B6A")
        self.note_title_entry.pack(fill="x", padx=15, pady=(15, 5))
        self.note_content_textbox = ctk.CTkTextbox(input_card, height=100, font=("Helvetica", 14), fg_color="#4B4B6A")
        self.note_content_textbox.pack(fill="x", padx=15, pady=5)
        ctk.CTkButton(input_card, text="Add Note", command=self._add_note, font=("Helvetica", 14, "bold"), fg_color="#4F46E5", hover_color="#4338CA", height=40).pack(pady=10, padx=15, anchor="e")

        list_card = ctk.CTkFrame(content_wrapper, corner_radius=15, fg_color="#3A3A5A")
        list_card.pack(fill="both", expand=True)
        self.notes_listbox = self._create_tk_listbox(list_card)
        self.notes_listbox.pack(fill="both", expand=True, padx=15, pady=15)
        self.notes_listbox.bind("<Double-1>", lambda event: self._edit_note())

        action_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        action_frame.pack(fill="x", pady=10)
        ctk.CTkButton(action_frame, text="Edit", command=self._edit_note, font=("Helvetica", 14), fg_color="#4F46E5", hover_color="#4338CA", width=100).pack(side="left", padx=5)
        ctk.CTkButton(action_frame, text="Delete", command=self._delete_note, font=("Helvetica", 14), fg_color="#FBBF24", hover_color="#D97706", width=100).pack(side="right", padx=5)
        self._load_notes()

    def _add_note(self):
        title = self.note_title_entry.get().strip()
        content = self.note_content_textbox.get("1.0", "end-1c").strip()
        if not title or not content:
            messagebox.showwarning("Input Error", "Please enter both a title and content.")
            return
        self._connect_db()
        self.cursor.execute("INSERT INTO notes (title, content) VALUES (%s, %s)", (title, content))
        self.db.commit()
        messagebox.showinfo("Success", "Note added!")
        self._load_notes()
        self.note_title_entry.delete(0, tk.END)
        self.note_content_textbox.delete("1.0", tk.END)

    def _load_notes(self):
        self.notes_listbox.delete(0, tk.END)
        self.note_ids.clear()
        self._connect_db()
        self.cursor.execute("SELECT id, title, content FROM notes ORDER BY created_at DESC")
        for index, (note_id, title, content) in enumerate(self.cursor.fetchall()):
            preview = content[:50] + "..." if len(content) > 50 else content
            self.notes_listbox.insert(tk.END, f"{title}: {preview}")
            self.note_ids[index] = note_id

    def _edit_note(self):
        if not (selected := self.notes_listbox.curselection()):
            messagebox.showwarning("Selection Error", "Please select a note.")
            return
        index = selected[0]
        note_id = self.note_ids.get(index)
        self._connect_db()
        self.cursor.execute("SELECT title, content FROM notes WHERE id = %s", (note_id,))
        title, content = self.cursor.fetchone()

        edit_window = ctk.CTkToplevel(self.root)
        edit_window.title("Edit Note")
        edit_window.geometry("500x400")
        edit_window.transient(self.root)
        edit_window.grab_set()

        ctk.CTkLabel(edit_window, text="Title", font=("Helvetica", 14)).pack(pady=(15, 5), padx=15, anchor="w")
        edit_title_entry = ctk.CTkEntry(edit_window, font=("Helvetica", 14), height=40, fg_color="#4B4B6A")
        edit_title_entry.insert(0, title)
        edit_title_entry.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(edit_window, text="Content", font=("Helvetica", 14)).pack(pady=(10, 5), padx=15, anchor="w")
        edit_content_textbox = ctk.CTkTextbox(edit_window, height=150, font=("Helvetica", 14), fg_color="#4B4B6A")
        edit_content_textbox.insert("1.0", content)
        edit_content_textbox.pack(fill="both", expand=True, padx=15, pady=5)

        def save_changes():
            new_title, new_content = edit_title_entry.get().strip(), edit_content_textbox.get("1.0", tk.END).strip()
            if not new_title or not new_content:
                messagebox.showwarning("Input Error", "Title and content cannot be empty.")
                return
            self._connect_db()
            self.cursor.execute("UPDATE notes SET title = %s, content = %s WHERE id = %s", (new_title, new_content, note_id))
            self.db.commit()
            messagebox.showinfo("Success", "Note updated!")
            self._load_notes()
            edit_window.destroy()

        ctk.CTkButton(edit_window, text="Save", command=save_changes, font=("Helvetica", 14, "bold"), fg_color="#4F46E5", hover_color="#4338CA", height=40).pack(pady=15)

    def _delete_note(self):
        if not (selected := self.notes_listbox.curselection()):
            messagebox.showwarning("Selection Error", "Please select a note.")
            return
        index = selected[0]
        note_id = self.note_ids.get(index)
        self._connect_db()
        self.cursor.execute("SELECT title FROM notes WHERE id = %s", (note_id,))
        if messagebox.askyesno("Confirm", f"Delete '{self.cursor.fetchone()[0]}'?"):
            self.cursor.execute("DELETE FROM notes WHERE id = %s", (note_id,))
            self.db.commit()
            messagebox.showinfo("Success", "Note deleted!")
            self._load_notes()

    def show_task(self):
        self._clear_content_frame()
        self.task_ids.clear()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content_wrapper, text="Tasks", font=("Helvetica", 24, "bold"), text_color="#E5E7EB").pack(anchor="w", pady=(0, 15))
        view_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        view_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(view_frame, text="View:", font=("Helvetica", 14), text_color="#E5E7EB").pack(side="left", padx=(0, 5))
        self.task_view_button = ctk.CTkSegmentedButton(view_frame, values=["Current", "Completed", "All"], command=self._change_task_view, font=("Helvetica", 14), fg_color="#4B4B6A", selected_color="#4F46E5")
        self.task_view_button.set("Current")
        self.task_view_button.pack(side="left")

        input_card = ctk.CTkFrame(content_wrapper, corner_radius=15, fg_color="#3A3A5A")
        input_card.pack(fill="x", pady=(0, 10))
        input_inner = ctk.CTkFrame(input_card, fg_color="transparent")
        input_inner.pack(fill="x", padx=15, pady=15)
        self.task_entry = ctk.CTkEntry(input_inner, placeholder_text="Enter Task", font=("Helvetica", 14), height=40, fg_color="#4B4B6A")
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.task_time_label = ctk.CTkLabel(input_inner, text="No Date/Time Selected", font=("Helvetica", 12), text_color="#A3BFFA")
        self.task_time_label.pack(side="left", padx=(5, 10))
        ctk.CTkButton(input_inner, text="Pick Time", command=lambda: self._open_time_picker("Pick Task Time", self._set_task_time), font=("Helvetica", 14), fg_color="#4F46E5", hover_color="#4338CA", width=120).pack(side="left", padx=(0, 5))
        ctk.CTkButton(input_inner, text="Add Task", command=self._add_task, font=("Helvetica", 14, "bold"), fg_color="#4F46E5", hover_color="#4338CA", width=120).pack(side="left")

        list_card = ctk.CTkFrame(content_wrapper, corner_radius=15, fg_color="#3A3A5A")
        list_card.pack(fill="both", expand=True)
        self.task_listbox = self._create_tk_listbox(list_card)
        self.task_listbox.pack(fill="both", expand=True, padx=15, pady=15)

        action_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        action_frame.pack(fill="x", pady=10)
        ctk.CTkButton(action_frame, text="Complete", command=self._complete_task, font=("Helvetica", 14), fg_color="#4F46E5", hover_color="#4338CA", width=120).pack(side="left", padx=5)
        ctk.CTkButton(action_frame, text="Delete", command=self._delete_task, font=("Helvetica", 14), fg_color="#FBBF24", hover_color="#D97706", width=120).pack(side="right", padx=5)
        self._load_task()

    def _change_task_view(self, value):
        self.task_view = value.lower()
        self._load_task()

    def _set_task_time(self, dt_string):
        self.selected_task_time = dt_string
        self.task_time_label.configure(text=dt_string)

    def _add_task(self):
        task = self.task_entry.get().strip()
        if not task or not self.selected_task_time:
            messagebox.showwarning("Input Error", "Please enter a task and pick a date/time.")
            return
        dt_object = datetime.strptime(self.selected_task_time, "%Y-%m-%d %I:%M %p")
        self._connect_db()
        self.cursor.execute("INSERT INTO schedule (task, time_slot, date) VALUES (%s, %s, %s)", (task, dt_object.strftime("%H:%M:%S"), dt_object.strftime("%Y-%m-%d")))
        self.db.commit()
        messagebox.showinfo("Success", "Task added!")
        self._load_task()
        self.task_entry.delete(0, tk.END)
        self.task_time_label.configure(text="No Date/Time Selected")
        self.selected_task_time = None

    def _load_task(self):
        self.task_listbox.delete(0, tk.END)
        self.task_ids.clear()
        self._connect_db()
        query = "SELECT id, task, time_slot, date, completed FROM schedule"
        if self.task_view == "current":
            query += " WHERE completed = FALSE"
        elif self.task_view == "completed":
            query += " WHERE completed = TRUE"
        query += " ORDER BY date ASC, time_slot ASC"
        self.cursor.execute(query)
        for index, (task_id, task, time_slot, date, completed) in enumerate(self.cursor.fetchall()):
            display_time = datetime.strptime(str(time_slot), "%H:%M:%S").strftime("%I:%M %p")
            status = "[Done]" if completed else ""
            self.task_listbox.insert(tk.END, f"{date} {display_time}: {task} {status}")
            self.task_ids[index] = task_id

    def _complete_task(self):
        if not (selected := self.task_listbox.curselection()):
            messagebox.showwarning("Selection Error", "Please select a task.")
            return
        index = selected[0]
        task_id = self.task_ids.get(index)
        self._connect_db()
        self.cursor.execute("SELECT task, completed FROM schedule WHERE id = %s", (task_id,))
        task, completed = self.cursor.fetchone()
        if completed:
            messagebox.showinfo("Info", f"Task '{task}' is already completed.")
            return
        if messagebox.askyesno("Confirm", f"Mark '{task}' as complete?"):
            self.cursor.execute("UPDATE schedule SET completed = TRUE WHERE id = %s", (task_id,))
            self.db.commit()
            messagebox.showinfo("Success", "Task completed!")
            self._load_task()

    def _delete_task(self):
        if not (selected := self.task_listbox.curselection()):
            messagebox.showwarning("Selection Error", "Please select a task.")
            return
        index = selected[0]
        task_id = self.task_ids.get(index)
        self._connect_db()
        self.cursor.execute("SELECT task FROM schedule WHERE id = %s", (task_id,))
        if messagebox.askyesno("Confirm", f"Delete '{self.cursor.fetchone()[0]}'?"):
            self.cursor.execute("DELETE FROM schedule WHERE id = %s", (task_id,))
            self.db.commit()
            messagebox.showinfo("Success", "Task deleted!")
            self._load_task()

    def show_reminders(self):
        self._clear_content_frame()
        self.reminder_ids.clear()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(content_wrapper, text="Reminders", font=("Helvetica", 24, "bold"), text_color="#E5E7EB").pack(anchor="w", pady=(0, 15))
        input_card = ctk.CTkFrame(content_wrapper, corner_radius=15, fg_color="#3A3A5A")
        input_card.pack(fill="x", pady=(0, 10))
        input_inner = ctk.CTkFrame(input_card, fg_color="transparent")
        input_inner.pack(fill="x", padx=15, pady=15)
        self.reminder_title_entry = ctk.CTkEntry(input_inner, placeholder_text="Title", font=("Helvetica", 14), height=40, fg_color="#4B4B6A")
        self.reminder_title_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.reminder_time_label = ctk.CTkLabel(input_inner, text="No Date/Time Selected", font=("Helvetica", 12), text_color="#A3BFFA")
        self.reminder_time_label.pack(side="left", padx=(5, 10))
        ctk.CTkButton(input_inner, text="Pick Time", command=lambda: self._open_time_picker("Pick Reminder Time", self._set_reminder_time), font=("Helvetica", 14), fg_color="#4F46E5", hover_color="#4338CA", width=120).pack(side="left", padx=(0, 5))
        self.repeat_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(input_inner, text="Repeat", variable=self.repeat_var, font=("Helvetica", 14), text_color="#E5E7EB").pack(side="left", padx=(10, 5))
        ctk.CTkButton(input_inner, text="Add Reminder", command=self._add_reminder, font=("Helvetica", 14, "bold"), fg_color="#4F46E5", hover_color="#4338CA", width=120).pack(side="left")

        list_card = ctk.CTkFrame(content_wrapper, corner_radius=15, fg_color="#3A3A5A")
        list_card.pack(fill="both", expand=True)
        self.reminders_listbox = self._create_tk_listbox(list_card)
        self.reminders_listbox.pack(fill="both", expand=True, padx=15, pady=15)

        ctk.CTkButton(content_wrapper, text="Delete", command=self._delete_reminder, font=("Helvetica", 14), fg_color="#FBBF24", hover_color="#D97706", width=120).pack(anchor="e", pady=10)
        self._load_reminders()

    def _set_reminder_time(self, dt_string):
        self.selected_reminder_time = dt_string
        self.reminder_time_label.configure(text=dt_string)

    def _add_reminder(self):
        title = self.reminder_title_entry.get().strip()
        time_str = self.selected_reminder_time
        if not title or not time_str:
            messagebox.showwarning("Input Error", "Please enter a title and pick a time.")
            return
        repeat = self.repeat_var.get()
        self._connect_db()
        self.cursor.execute("INSERT INTO reminders (title, reminder_time, `repeat`) VALUES (%s, %s, %s)", (title, time_str, repeat))
        self.db.commit()
        messagebox.showinfo("Success", "Reminder added!")
        self._load_reminders()
        self.reminder_title_entry.delete(0, tk.END)
        self.reminder_time_label.configure(text="No Date/Time Selected")
        self.selected_reminder_time = None
        self.repeat_var.set(False)

    def _load_reminders(self):
        self.reminders_listbox.delete(0, tk.END)
        self.reminder_ids.clear()
        self._connect_db()
        self.cursor.execute("SELECT id, title, reminder_time, `repeat` FROM reminders ORDER BY reminder_time ASC")
        for index, (reminder_id, title, time_str, repeat) in enumerate(self.cursor.fetchall()):
            repeat_display = " (Daily)" if repeat else ""
            self.reminders_listbox.insert(tk.END, f"{time_str}: {title}{repeat_display}")
            self.reminder_ids[index] = reminder_id

    def _delete_reminder(self):
        if not (selected := self.reminders_listbox.curselection()):
            messagebox.showwarning("Selection Error", "Please select a reminder.")
            return
        index = selected[0]
        reminder_id = self.reminder_ids.get(index)
        self._connect_db()
        self.cursor.execute("SELECT title FROM reminders WHERE id = %s", (reminder_id,))
        if messagebox.askyesno("Confirm", f"Delete '{self.cursor.fetchone()[0]}'?"):
            self.cursor.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
            self.db.commit()
            messagebox.showinfo("Success", "Reminder deleted!")
            self._load_reminders()

    def _test_notification(self):
        notification.notify(title="To-Do App", message="Your to-do list is ready!", timeout=5)

    def _get_prayer_text(self):
        now = datetime.now(self.bangladesh_tz)
        today = now.date()
        upcoming = []
        for prayer, time_str in self.prayer_times.items():
            prayer_time = datetime.strptime(f"{today} {time_str}", "%Y-%m-%d %I:%M %p").replace(tzinfo=self.bangladesh_tz)
            if now < prayer_time:
                upcoming.append(f"{prayer}: {time_str}")
        return " | ".join(upcoming) or "No upcoming prayers."

    def _scroll_marquee(self, text, x_pos):
        if not text:
            return
        canvas_width = self.marquee_canvas.winfo_width()
        text_bbox = self.marquee_canvas.bbox(self.marquee_text)
        text_width = (text_bbox[2] - text_bbox[0]) if text_bbox else 0
        if x_pos < -text_width:
            x_pos = canvas_width
        self.marquee_canvas.coords(self.marquee_text, x_pos, 15)
        self.root.after(50, lambda: self._scroll_marquee(text, x_pos - 5))

    def _update_prayer_marquee(self):
        text = self._get_prayer_text()
        self.marquee_canvas.itemconfig(self.marquee_text, text=text)
        self.marquee_canvas.update_idletasks()
        self._scroll_marquee(text, self.marquee_canvas.winfo_width())
        self.root.after(60000, self._update_prayer_marquee)

    def _show_hadith_popup(self, hadith):
        popup = ctk.CTkToplevel(self.root)
        popup.title("Daily Hadith")
        popup.geometry("300x150")
        popup.transient(self.root)
        popup.grab_set()
        frame = ctk.CTkFrame(popup, corner_radius=10, fg_color="#3A3A5A")
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(frame, text=hadith, font=("Helvetica", 12), wraplength=250, justify="center", text_color="#E5E7EB").pack(pady=10)
        ctk.CTkButton(frame, text="Close", command=popup.destroy, font=("Helvetica", 14), fg_color="#4F46E5", hover_color="#4338CA").pack(pady=5)

    def _check_hadith(self):
        while True:
            now = datetime.now()
            if self.last_hadith_time is None or (now - self.last_hadith_time).total_seconds() >= 6 * 3600:
                hadith = random.choice(self.hadiths)
                self.last_hadith_time = now
                self.root.after(0, lambda: self._show_hadith_popup(hadith))
            time.sleep(60)

    def _check_reminders(self):
        while True:
            self._connect_db()
            now = datetime.now(self.bangladesh_tz)
            self.cursor.execute("SELECT id, title, reminder_time, `repeat` FROM reminders")
            for reminder_id, title, reminder_time_str, repeat in self.cursor.fetchall():
                stored_dt = datetime.strptime(reminder_time_str, "%Y-%m-%d %I:%M %p").replace(tzinfo=self.bangladesh_tz)
                if repeat:
                    if stored_dt.date() < now.date():
                        new_dt = now.replace(hour=stored_dt.hour, minute=stored_dt.minute, second=stored_dt.second, microsecond=stored_dt.microsecond)
                        if new_dt <= now and (now - new_dt).total_seconds() > 60:
                            new_dt += timedelta(days=1)
                        new_time_str = new_dt.strftime("%Y-%m-%d %I:%M %p")
                        self.cursor.execute("UPDATE reminders SET reminder_time = %s WHERE id = %s", (new_time_str, reminder_id))
                        self.db.commit()
                        self.root.after(0, self._load_reminders)
                        continue
                    today_dt = now.replace(hour=stored_dt.hour, minute=stored_dt.minute, second=stored_dt.second, microsecond=stored_dt.microsecond)
                    if now >= today_dt and (now - today_dt).total_seconds() < 60:
                        notification.notify(title=f"Reminder: {title}", message=f"It's time for: {title}!", timeout=10)
                else:
                    time_diff = (now - stored_dt).total_seconds()
                    if -5 <= time_diff <= 30:
                        notification.notify(title=f"Reminder: {title}", message=f"It's time for: {title}!", timeout=10)
                        self.cursor.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
                        self.db.commit()
                        self.root.after(0, self._load_reminders)
            time.sleep(5)

if __name__ == "__main__":
    app_root = ctk.CTk()
    app = ToDoApp(app_root)
    app_root.mainloop()