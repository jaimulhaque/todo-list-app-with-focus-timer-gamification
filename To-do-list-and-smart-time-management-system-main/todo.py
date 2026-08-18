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
import logging
import sys
import uuid


logging.basicConfig(
    filename="todo_app.log",
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

class ToDoApp:
    def __init__(self, root):
        self.root = root
        self.root.title("To-Do List")
        self.root.geometry("1000x700")
        self.root.minsize(800, 500)

        self.bangladesh_tz = ZoneInfo("Asia/Dhaka")
        self.db_config = {
            "host": "localhost",
            "user": "todo_user",
            "password": "secure_password",
            "database": "todo_app"
        }
        self.db = None
        self.cursor = None

        if not self._connect_db():
            messagebox.showerror("Error", "Failed to connect to the database. Exiting.")
            self.root.destroy()
            return

        self._create_tables()

        self.is_dark_mode = True
        self.prayer_times = {
            "Fajr": "4:30 AM", "Dhuhr": "12:00 PM", "Asr": "3:30 PM",
            "Maghrib": "6:30 PM", "Isha": "8:00 PM"
        }
        self.hadiths = [
            "The best of you are those who are best to your families. (Tirmidhi)",
            "Seek knowledge from cradle to grave. (Ibn Majah)",
            "The merciful are shown mercy. (Tirmidhi)",
            "Speak good or remain silent. (Bukhari)",
            "Control anger to be strong. (Bukhari)"
        ]
        self.last_hadith_time = None
        self.selected_task_time = None
        self.selected_reminder_time = None
        self.note_ids = {}
        self.task_ids = {}
        self.reminder_ids = {}
        self.task_view = "current"  # Default view: current (incomplete) tasks
        # Pomodoro variables
        self.pomodoro_running = False
        self.pomodoro_time = 25 * 60  # 25 minutes in seconds
        self.is_work_session = True
        self.pomodoro_last_time = None
        self.session_count = 0

        self._setup_ui()
        self._test_notification()

        threading.Thread(target=self._check_reminders, daemon=True).start()
        threading.Thread(target=self._check_hadith, daemon=True).start()
        self._update_prayer_marquee()

    # --- Database Operations ---
    def _connect_db(self):
        try:
            if self.db and self.db.is_connected():
                self.cursor.close()
                self.db.close()
            self.db = mysql.connector.connect(**self.db_config)
            self.cursor = self.db.cursor()
            logging.info("Database connection established.")
            return True
        except mysql.connector.Error as err:
            logging.error(f"Database connection failed: {err}")
            return False

    def _create_tables(self):
        try:
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
            logging.info("Database tables checked/created successfully.")
        except mysql.connector.Error as err:
            logging.error(f"Error creating tables: {err}")
            messagebox.showerror("Database Error", f"Failed to create tables: {err}")

    # --- UI Setup ---
    def _setup_ui(self):
        self.main_container = ctk.CTkFrame(self.root, fg_color="#1E1E2E")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=20)

        self.header_frame = ctk.CTkFrame(self.main_container, corner_radius=12, fg_color="#2A2A3C")
        self.header_frame.pack(fill="x", pady=(0, 10))
        self.header_label = ctk.CTkLabel(
            self.header_frame, text="To-Do List", font=ctk.CTkFont("Roboto", 32, "bold"),
            text_color="#E0E0E0"
        )
        self.header_label.pack(pady=(15, 5), padx=20, anchor="w")
        self.marquee_canvas = tk.Canvas(
            self.header_frame, height=40, bg="#2A2A3C", highlightthickness=0
        )
        self.marquee_canvas.pack(fill="x", padx=10, pady=5)
        self.marquee_text = self.marquee_canvas.create_text(
            0, 20, anchor="w", font=("Roboto", 14), fill="#A5B4FC"
        )

        self.content_container = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.content_container.pack(fill="both", expand=True)

        self.sidebar = ctk.CTkFrame(
            self.content_container, width=220, corner_radius=12, fg_color="#2C2C3E"
        )
        self.sidebar.pack(side="left", fill="y", padx=(0, 10))
        self.sidebar.pack_propagate(False)

        button_config = {
            "font": ctk.CTkFont("Roboto", 16, "bold"),
            "corner_radius": 8,
            "fg_color": "#6366F1",
            "hover_color": "#4F46E5",
            "height": 50,
            "anchor": "w",
            "text_color": "#FFFFFF"
        }
        ctk.CTkButton(
            self.sidebar, text="  Notes", command=self.show_notes, compound="left", **button_config
        ).pack(pady=(20, 5), padx=10, fill="x")
        ctk.CTkButton(
            self.sidebar, text="  Task", command=self.show_task, compound="left", **button_config
        ).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(
            self.sidebar, text="  Reminders", command=self.show_reminders, compound="left", **button_config
        ).pack(pady=5, padx=10, fill="x")
        ctk.CTkButton(
            self.sidebar, text="  Pomodoro", command=self.show_pomodoro, compound="left", **button_config
        ).pack(pady=5, padx=10, fill="x")

        self.theme_btn = ctk.CTkButton(
            self.sidebar, text="Light Mode", command=self.toggle_theme,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#10B981", hover_color="#059669", height=40
        )
        self.theme_btn.pack(pady=(10, 20), padx=10, fill="x", side="bottom")

        self.content_frame = ctk.CTkFrame(
            self.content_container, corner_radius=12, fg_color="#2C2C3E"
        )
        self.content_frame.pack(side="left", fill="both", expand=True)

        self.show_notes()

    def toggle_theme(self):
        self.is_dark_mode = not self.is_dark_mode
        ctk.set_appearance_mode("dark" if self.is_dark_mode else "light")
        self.theme_btn.configure(text="Light Mode" if self.is_dark_mode else "Dark Mode")
        marquee_bg = "#2A2A3C" if self.is_dark_mode else "#F5F5F5"
        marquee_text_color = "#A5B4FC" if self.is_dark_mode else "#4B5563"
        self.main_container.configure(fg_color="#1E1E2E" if self.is_dark_mode else "#F3F4F6")
        self.header_frame.configure(fg_color=marquee_bg)
        self.marquee_canvas.configure(bg=marquee_bg)
        self.marquee_canvas.itemconfig(self.marquee_text, fill=marquee_text_color)
        self.sidebar.configure(fg_color="#2C2C3E" if self.is_dark_mode else "#E5E7EB")
        self.content_frame.configure(fg_color="#2C2C3E" if self.is_dark_mode else "#FFFFFF")

    def _clear_content_frame(self):
        for widget in self.content_frame.winfo_children():
            widget.destroy()

    def _create_tk_listbox(self, parent_frame, height=10):
        return tk.Listbox(
            parent_frame, height=height, font=("Roboto", 12), borderwidth=0,
            highlightthickness=0, relief="flat",
            bg="#2C2C3E" if self.is_dark_mode else "#FFFFFF",
            fg="#E0E0E0" if self.is_dark_mode else "#1F2937",
            selectbackground="#6366F1",
            selectforeground="#FFFFFF",
            activestyle="none"
        )

    def _open_time_picker(self, title, callback_func):
        picker_window = ctk.CTkToplevel(self.root)
        picker_window.title(title)
        picker_window.geometry("450x500")
        picker_window.transient(self.root)
        picker_window.grab_set()

        ctk.CTkLabel(picker_window, text="Select Date:", font=("Roboto", 14, "bold")).pack(pady=(15, 5))
        today = datetime.now(self.bangladesh_tz).date()
        calendar = Calendar(
            picker_window, selectmode="day", date_pattern="yyyy-mm-dd",
            year=today.year, month=today.month, day=today.day
        )
        calendar.pack(padx=15, pady=5)

        ctk.CTkLabel(picker_window, text="Select Time:", font=("Roboto", 14, "bold")).pack(pady=(15, 5))
        time_frame = ctk.CTkFrame(picker_window, fg_color="transparent")
        time_frame.pack(pady=5)
        hour_entry = ctk.CTkEntry(time_frame, placeholder_text="HH", width=60, font=("Roboto", 14))
        hour_entry.pack(side="left", padx=(0, 2))
        ctk.CTkLabel(time_frame, text=":", font=("Roboto", 14, "bold")).pack(side="left")
        minute_entry = ctk.CTkEntry(time_frame, placeholder_text="MM", width=60, font=("Roboto", 14))
        minute_entry.pack(side="left", padx=(2, 5))
        am_pm_var = tk.StringVar(value="AM")
        ctk.CTkOptionMenu(
            time_frame, values=["AM", "PM"], variable=am_pm_var, font=("Roboto", 14),
            width=80, corner_radius=8, fg_color="#6366F1", button_color="#6366F1"
        ).pack(side="left")

        def save_and_close():
            try:
                date_str = calendar.get_date()
                hour, minute = int(hour_entry.get().strip()), int(minute_entry.get().strip())
                if not (1 <= hour <= 12) or not (0 <= minute <= 59):
                    raise ValueError("Invalid hour (1-12) or minute (00-59).")
                combined_dt_str = f"{date_str} {hour:02d}:{minute:02d} {am_pm_var.get()}"
                datetime.strptime(combined_dt_str, "%Y-%m-%d %I:%M %p")
                callback_func(combined_dt_str)
                picker_window.destroy()
            except ValueError as e:
                messagebox.showwarning("Invalid Input", f"Please enter a valid date and time: {e}")
                logging.warning(f"Invalid time input: {e}")

        ctk.CTkButton(
            picker_window, text="Confirm", command=save_and_close,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40
        ).pack(pady=20)
        picker_window.protocol("WM_DELETE_WINDOW", picker_window.destroy)

    # --- Pomodoro Section ---
    def show_pomodoro(self):
        self._clear_content_frame()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content_wrapper, text="Pomodoro Timer", font=ctk.CTkFont("Roboto", 28, "bold"),
            text_color="#E0E0E0"
        ).pack(anchor="w", pady=(0, 15))

        # Timer display
        self.pomodoro_status_label = ctk.CTkLabel(
            content_wrapper, text="Work Session", font=ctk.CTkFont("Roboto", 20),
            text_color="#10B981"
        )
        self.pomodoro_status_label.pack(pady=5)
        self.pomodoro_label = ctk.CTkLabel(
            content_wrapper, text="25:00", font=ctk.CTkFont("Roboto", 48),
            text_color="#E0E0E0"
        )
        self.pomodoro_label.pack(pady=20)

        # Control buttons
        button_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        button_frame.pack(pady=10)
        ctk.CTkButton(
            button_frame, text="Start", command=self._start_pomodoro,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#10B981", hover_color="#059669", height=40, width=100
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            button_frame, text="Pause", command=self._pause_pomodoro,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#F59E0B", hover_color="#D97706", height=40, width=100
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            button_frame, text="Reset", command=self._reset_pomodoro,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#EF4444", hover_color="#DC2626", height=40, width=100
        ).pack(side="left", padx=5)

        # Session counter
        self.session_label = ctk.CTkLabel(
            content_wrapper, text=f"Completed Sessions: {self.session_count}",
            font=ctk.CTkFont("Roboto", 16), text_color="#E0E0E0"
        )
        self.session_label.pack(pady=10)

        self._update_pomodoro()

    def _start_pomodoro(self):
        if not self.pomodoro_running:
            self.pomodoro_running = True
            self.pomodoro_last_time = time.time()
            self._update_pomodoro()
            logging.info("Pomodoro timer started")

    def _pause_pomodoro(self):
        if self.pomodoro_running:
            self.pomodoro_running = False
            self.pomodoro_time = max(0, self.pomodoro_time - (time.time() - self.pomodoro_last_time))
            logging.info("Pomodoro timer paused")

    def _reset_pomodoro(self):
        self.pomodoro_running = False
        self.is_work_session = True
        self.pomodoro_time = 25 * 60  # Reset to 25 minutes
        self.pomodoro_label.configure(text="25:00")
        self.pomodoro_status_label.configure(text="Work Session", text_color="#10B981")
        logging.info("Pomodoro timer reset")

    def _format_time(self, seconds):
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
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
                    self.pomodoro_time = 5 * 60  # 5-minute break
                    self.is_work_session = False
                    self.pomodoro_status_label.configure(text="Break", text_color="#F59E0B")
                    try:
                        notification.notify(
                            title="Pomodoro Work Session Complete",
                            message="Time for a 5-minute break!",
                            app_name="To-Do App",
                            timeout=10
                        )
                    except Exception as e:
                        logging.error(f"Notification failed: {e}")
                        self.root.after(0, lambda: messagebox.showinfo("Pomodoro", "Work session complete! Take a 5-minute break."))
                else:
                    self.pomodoro_time = 25 * 60  # 25-minute work session
                    self.is_work_session = True
                    self.pomodoro_status_label.configure(text="Work Session", text_color="#10B981")
                    try:
                        notification.notify(
                            title="Pomodoro Break Complete",
                            message="Time to start a new work session!",
                            app_name="To-Do App",
                            timeout=10
                        )
                    except Exception as e:
                        logging.error(f"Notification failed: {e}")
                        self.root.after(0, lambda: messagebox.showinfo("Pomodoro", "Break complete! Start a new work session."))
                self.pomodoro_label.configure(text=self._format_time(self.pomodoro_time))

            self.root.after(100, self._update_pomodoro)

    # --- Notes Section ---
    def show_notes(self):
        self._clear_content_frame()
        self.note_ids.clear()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content_wrapper, text="Notes", font=ctk.CTkFont("Roboto", 28, "bold"),
            text_color="#E0E0E0"
        ).pack(anchor="w", pady=(0, 15))

        input_card = ctk.CTkFrame(content_wrapper, corner_radius=12, fg_color="#3A3A4E")
        input_card.pack(fill="x", pady=(0, 10))
        self.note_title_entry = ctk.CTkEntry(
            input_card, placeholder_text="Note Title", font=ctk.CTkFont("Roboto", 14),
            height=40, corner_radius=8, border_width=0, fg_color="#4B4B5F"
        )
        self.note_title_entry.pack(fill="x", padx=15, pady=(15, 5))
        self.note_content_textbox = ctk.CTkTextbox(
            input_card, height=120, font=ctk.CTkFont("Roboto", 14),
            corner_radius=8, border_width=0, fg_color="#4B4B5F"
        )
        self.note_content_textbox.pack(fill="x", padx=15, pady=5)
        button_frame = ctk.CTkFrame(input_card, fg_color="transparent")
        button_frame.pack(fill="x", padx=15, pady=10)
        ctk.CTkButton(
            button_frame, text="Add Note", command=self._add_note,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40
        ).pack(side="right")

        list_card = ctk.CTkFrame(content_wrapper, corner_radius=12, fg_color="#3A3A4E")
        list_card.pack(fill="both", expand=True, pady=5)
        self.notes_listbox = self._create_tk_listbox(list_card)
        self.notes_listbox.pack(fill="both", expand=True, padx=15, pady=15)
        self.notes_listbox.bind("<Double-1>", lambda event: self._edit_note())

        action_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        action_frame.pack(fill="x", pady=10)
        ctk.CTkButton(
            action_frame, text="Edit Selected", command=self._edit_note,
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40
        ).pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            action_frame, text="Delete Selected", command=self._delete_note,
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#F59E0B", hover_color="#D97706", height=40
        ).pack(side="right")

        self._load_notes()

    def _add_note(self):
        title = self.note_title_entry.get().strip()
        content = self.note_content_textbox.get("1.0", "end-1c").strip()
        if not title or not content:
            messagebox.showwarning("Input Error", "Please enter both a title and content.")
            return
        try:
            self._connect_db()
            self.cursor.execute("INSERT INTO notes (title, content) VALUES (%s, %s)", (title, content))
            self.db.commit()
            logging.info(f"Note added: '{title}'")
            messagebox.showinfo("Success", "Note added successfully!")
            self._load_notes()
            self.note_title_entry.delete(0, tk.END)
            self.note_content_textbox.delete("1.0", tk.END)
        except mysql.connector.Error as err:
            logging.error(f"Failed to add note: {err}")
            messagebox.showerror("Database Error", f"Failed to add note: {err}")

    def _load_notes(self):
        self.notes_listbox.delete(0, tk.END)
        self.note_ids.clear()
        try:
            self._connect_db()
            self.cursor.execute("SELECT id, title, content FROM notes ORDER BY created_at DESC")
            for index, (note_id, title, content) in enumerate(self.cursor.fetchall()):
                preview = content[:50] + "..." if len(content) > 50 else content
                display_text = f"{title}: {preview}"
                self.notes_listbox.insert(tk.END, display_text)
                self.note_ids[index] = note_id
            logging.debug("Notes loaded successfully.")
        except mysql.connector.Error as err:
            logging.error(f"Failed to load notes: {err}")
            messagebox.showerror("Database Error", f"Failed to load notes: {err}")

    def _edit_note(self):
        selected = self.notes_listbox.curselection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a note to edit.")
            return
        try:
            index = selected[0]
            note_id = self.note_ids.get(index)
            if note_id is None:
                raise ValueError("Note ID not found for selected index.")
            self._connect_db()
            self.cursor.execute("SELECT title, content FROM notes WHERE id = %s", (note_id,))
            title, content = self.cursor.fetchone()

            edit_window = ctk.CTkToplevel(self.root)
            edit_window.title(f"Edit Note [ID: {note_id}]")
            edit_window.geometry("600x450")
            edit_window.transient(self.root)
            edit_window.grab_set()

            ctk.CTkLabel(edit_window, text="Edit Title:", font=("Roboto", 14)).pack(pady=(20, 5), padx=20, anchor="w")
            edit_title_entry = ctk.CTkEntry(edit_window, font=("Roboto", 14), height=40, fg_color="#4B4B5F")
            edit_title_entry.insert(0, title)
            edit_title_entry.pack(fill="x", padx=20, pady=5)
            ctk.CTkLabel(edit_window, text="Edit Content:", font=("Roboto", 14)).pack(pady=(10, 5), padx=20, anchor="w")
            edit_content_textbox = ctk.CTkTextbox(edit_window, height=150, font=ctk.CTkFont("Roboto", 14), fg_color="#4B4B5F")
            edit_content_textbox.insert("1.0", content)
            edit_content_textbox.pack(fill="both", expand=True, padx=20, pady=10)

            def save_changes():
                new_title = edit_title_entry.get().strip()
                new_content = edit_content_textbox.get("1.0", tk.END).strip()
                if not new_title or not new_content:
                    messagebox.showwarning("Input Error", "Title and content cannot be empty.")
                    return
                try:
                    self._connect_db()
                    self.cursor.execute(
                        "UPDATE notes SET title = %s, content = %s WHERE id = %s",
                        (new_title, new_content, note_id)
                    )
                    self.db.commit()
                    logging.info(f"Note ID {note_id} updated successfully.")
                    messagebox.showinfo("Success", "Note updated successfully!")
                    self._load_notes()
                    edit_window.destroy()
                except mysql.connector.Error as err:
                    logging.error(f"Failed to update note ID {note_id}: {err}")
                    messagebox.showerror("Database Error", f"Failed to update note: {err}")

            ctk.CTkButton(
                edit_window, text="Save Changes", command=save_changes,
                font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
                fg_color="#6366F1", hover_color="#4F46E5", height=40
            ).pack(pady=20)
            edit_window.protocol("WM_DELETE_WINDOW", edit_window.destroy)
        except Exception as e:
            logging.error(f"Error editing note: {e}")
            messagebox.showerror("Error", f"Failed to edit note: {e}")

    def _delete_note(self):
        selected = self.notes_listbox.curselection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a note to delete.")
            return
        try:
            index = selected[0]
            note_id = self.note_ids.get(index)
            if note_id is None:
                raise ValueError("Note ID not found for selected index.")
            self._connect_db()
            self.cursor.execute("SELECT title FROM notes WHERE id = %s", (note_id,))
            title = self.cursor.fetchone()[0]
            if messagebox.askyesno("Confirm Deletion", f"Delete the note titled '{title}'?"):
                self.cursor.execute("DELETE FROM notes WHERE id = %s", (note_id,))
                self.db.commit()
                logging.info(f"Note ID {note_id} deleted.")
                messagebox.showinfo("Success", "Note deleted successfully!")
                self._load_notes()
        except Exception as e:
            logging.error(f"Error deleting note: {e}")
            messagebox.showerror("Error", f"Failed to delete note: {e}")

    # --- Task Section ---
    def show_task(self):
        self._clear_content_frame()
        self.task_ids.clear()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content_wrapper, text="Task", font=ctk.CTkFont("Roboto", 28, "bold"),
            text_color="#E0E0E0"
        ).pack(anchor="w", pady=(0, 10))

        # View selection
        view_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        view_frame.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(
            view_frame, text="View:", font=ctk.CTkFont("Roboto", 14),
            text_color="#E0E0E0"
        ).pack(side="left", padx=(0, 5))
        self.task_view_button = ctk.CTkSegmentedButton(
            view_frame, values=["Current", "Completed", "All"],
            command=self._change_task_view,
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#4B4B5F", selected_color="#6366F1",
            selected_hover_color="#4F46E5", height=40
        )
        self.task_view_button.set("Current")
        self.task_view_button.pack(side="left")

        input_card = ctk.CTkFrame(content_wrapper, corner_radius=10, fg_color="#3A3A4E")
        input_card.pack(fill="x", pady=(0, 10))
        input_inner = ctk.CTkFrame(input_card, fg_color="transparent")
        input_inner.pack(fill="x", padx=15, pady=15)
        self.task_entry = ctk.CTkEntry(
            input_inner, placeholder_text="Enter Task", font=ctk.CTkFont("Roboto", 14),
            height=40, corner_radius=8, text_color="#E0E0E0", fg_color="#4B4B5F"
        )
        self.task_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.task_time_label = ctk.CTkLabel(
            input_inner, text="No Date/Time Selected", font=ctk.CTkFont("Roboto", 12),
            text_color="#A5B4FC"
        )
        self.task_time_label.pack(side="left", padx=(5, 10))
        ctk.CTkButton(
            input_inner, text="Pick Date/Time",
            command=lambda: self._open_time_picker("Pick Task Date & Time", self._set_task_time),
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40, width=120
        ).pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            input_inner, text="Add Task", command=self._add_task,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40, width=120
        ).pack(side="left")

        list_card = ctk.CTkFrame(content_wrapper, corner_radius=10, fg_color="#3A3A4E")
        list_card.pack(fill="both", expand=True, pady=10)
        self.task_listbox = self._create_tk_listbox(list_card)
        self.task_listbox.pack(fill="both", expand=True, padx=15, pady=15)

        action_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        action_frame.pack(fill="x", pady=10)
        ctk.CTkButton(
            action_frame, text="Mark Completed", command=self._complete_task,
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40
        ).pack(side="left", padx=(0, 5))
        ctk.CTkButton(
            action_frame, text="Delete Task", command=self._delete_task,
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#F59E0B", hover_color="#D97706", height=40
        ).pack(side="right")

        self.selected_task_time = None
        self._load_task()

    def _change_task_view(self, value):
        self.task_view = value.lower()
        self._load_task()
        logging.info(f"Task view changed to: {self.task_view}")

    def _set_task_time(self, dt_string):
        self.selected_task_time = dt_string
        self.task_time_label.configure(text=dt_string)
        logging.info(f"Task time selected: {dt_string}")

    def _add_task(self):
        task = self.task_entry.get().strip()
        if not task or not self.selected_task_time:
            messagebox.showwarning("Input Error", "Please enter a task and pick a date/time.")
            return
        try:
            dt_object = datetime.strptime(self.selected_task_time, "%Y-%m-%d %I:%M %p")
            self._connect_db()
            self.cursor.execute(
                "INSERT INTO schedule (task, time_slot, date) VALUES (%s, %s, %s)",
                (task, dt_object.strftime("%H:%M:%S"), dt_object.strftime("%Y-%m-%d"))
            )
            self.db.commit()
            logging.info(f"Task added: '{task}' at {self.selected_task_time}")
            messagebox.showinfo("Success", "Task added successfully!")
            self._load_task()
            self.task_entry.delete(0, tk.END)
            self.task_time_label.configure(text="No Date/Time Selected")
            self.selected_task_time = None
        except Exception as e:
            logging.error(f"Error adding task: {e}")
            messagebox.showerror("Error", f"Error adding task: {e}")

    def _load_task(self):
        self.task_listbox.delete(0, tk.END)
        self.task_ids.clear()
        try:
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
                status = "[Completed]" if completed else ""
                display_text = f"{date} {display_time}: {task} {status}"
                self.task_listbox.insert(tk.END, display_text)
                self.task_ids[index] = task_id
            logging.debug(f"Tasks loaded for view: {self.task_view}")
        except Exception as e:
            logging.error(f"Error loading tasks: {e}")
            messagebox.showerror("Error", f"Error loading tasks: {e}")

    def _complete_task(self):
        selected = self.task_listbox.curselection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a task to mark as completed.")
            return
        try:
            index = selected[0]
            task_id = self.task_ids.get(index)
            if task_id is None:
                raise ValueError("Task ID not found for selected index.")
            self._connect_db()
            self.cursor.execute("SELECT task, completed FROM schedule WHERE id = %s", (task_id,))
            task, completed = self.cursor.fetchone()
            if completed:
                messagebox.showinfo("Info", f"Task '{task}' is already marked as completed.")
                return
            if messagebox.askyesno("Confirm Completion", f"Mark the task '{task}' as complete?"):
                self.cursor.execute("UPDATE schedule SET completed = TRUE WHERE id = %s", (task_id,))
                self.db.commit()
                logging.info(f"Task ID {task_id} marked as completed.")
                messagebox.showinfo("Success", "Task marked as completed!")
                self._load_task()
        except Exception as e:
            logging.error(f"Error completing task: {e}")
            messagebox.showerror("Error", f"Failed to mark task as completed: {e}")

    def _delete_task(self):
        selected = self.task_listbox.curselection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a task to delete.")
            return
        try:
            index = selected[0]
            task_id = self.task_ids.get(index)
            if task_id is None:
                raise ValueError("Task ID not found for selected index.")
            self._connect_db()
            self.cursor.execute("SELECT task FROM schedule WHERE id = %s", (task_id,))
            task = self.cursor.fetchone()[0]
            if messagebox.askyesno("Confirm Deletion", f"Delete the task '{task}'?"):
                self.cursor.execute("DELETE FROM schedule WHERE id = %s", (task_id,))
                self.db.commit()
                logging.info(f"Task ID {task_id} deleted.")
                messagebox.showinfo("Success", "Task deleted successfully!")
                self._load_task()
        except Exception as e:
            logging.error(f"Error deleting task: {e}")
            messagebox.showerror("Error", f"Failed to delete task: {e}")

    # --- Reminders Section ---
    def show_reminders(self):
        self._clear_content_frame()
        self.reminder_ids.clear()
        content_wrapper = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        content_wrapper.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            content_wrapper, text="Reminders", font=ctk.CTkFont("Roboto", 28, "bold"),
            text_color="#E0E0E0"
        ).pack(anchor="w", pady=(0, 15))

        input_card = ctk.CTkFrame(content_wrapper, corner_radius=10, fg_color="#3A3A4E")
        input_card.pack(fill="x", pady=(0, 10))
        input_inner = ctk.CTkFrame(input_card, fg_color="transparent")
        input_inner.pack(fill="x", padx=15, pady=10)
        self.reminder_title_entry = ctk.CTkEntry(
            input_inner, placeholder_text="Reminder Title", font=ctk.CTkFont("Roboto", 14),
            height=40, corner_radius=8, text_color="#E0E0E0", fg_color="#4B4B5F"
        )
        self.reminder_title_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.reminder_time_label = ctk.CTkLabel(
            input_inner, text="No Date/Time Selected", font=ctk.CTkFont("Roboto", 12),
            text_color="#A5B4FC"
        )
        self.reminder_time_label.pack(side="left", padx=(5, 10))
        ctk.CTkButton(
            input_inner, text="Pick Date/Time",
            command=lambda: self._open_time_picker("Pick Reminder Date/Time", self._set_reminder_time),
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40, width=120
        ).pack(side="left", padx=(0, 5))
        self.repeat_var = tk.BooleanVar(value=False)
        ctk.CTkCheckBox(
            input_inner, text="Repeat Daily", variable=self.repeat_var,
            font=ctk.CTkFont("Roboto", 14), text_color="#E0E0E0"
        ).pack(side="left", padx=(10, 10))
        ctk.CTkButton(
            input_inner, text="Add Reminder", command=self._add_reminder,
            font=ctk.CTkFont("Roboto", 14, "bold"), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5", height=40, width=120
        ).pack(side="left")

        list_card = ctk.CTkFrame(content_wrapper, corner_radius=10, fg_color="#3A3A4E")
        list_card.pack(fill="both", expand=True, pady=10)
        self.reminders_listbox = self._create_tk_listbox(list_card)
        self.reminders_listbox.pack(fill="both", expand=True, padx=15, pady=15)

        action_frame = ctk.CTkFrame(content_wrapper, fg_color="transparent")
        action_frame.pack(fill="x", pady=10)
        ctk.CTkButton(
            action_frame, text="Delete Selected Reminder", command=self._delete_reminder,
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#F59E0B", hover_color="#D97706", height=40
        ).pack(side="right")

        self.selected_reminder_time = None
        self._load_reminders()

    def _set_reminder_time(self, dt_string):
        self.selected_reminder_time = dt_string
        self.reminder_time_label.configure(text=dt_string)
        logging.info(f"Reminder time selected: {dt_string}")

    def _add_reminder(self):
        title = self.reminder_title_entry.get().strip()
        time_str = self.selected_reminder_time
        repeat = self.repeat_var.get()
        if not title or not time_str:
            messagebox.showwarning("Input Error", "Please enter a title and pick a date/time.")
            return
        try:
            self._connect_db()
            self.cursor.execute(
                "INSERT INTO reminders (title, reminder_time, `repeat`) VALUES (%s, %s, %s)",
                (title, time_str, repeat)
            )
            self.db.commit()
            logging.info(f"Reminder added: '{title}' at {time_str}, Repeat: {repeat}")
            messagebox.showinfo("Success", "Reminder added successfully!")
            self._load_reminders()
            self.reminder_title_entry.delete(0, tk.END)
            self.reminder_time_label.configure(text="No Date/Time Selected")
            self.selected_reminder_time = None
            self.repeat_var.set(False)
        except Exception as e:
            logging.error(f"Error adding reminder: {e}")
            messagebox.showerror("Error", f"Failed to add reminder: {e}")

    def _load_reminders(self):
        self.reminders_listbox.delete(0, tk.END)
        self.reminder_ids.clear()
        try:
            self._connect_db()
            self.cursor.execute("SELECT id, title, reminder_time, `repeat` FROM reminders ORDER BY reminder_time ASC")
            for index, (reminder_id, title, time_str, repeat) in enumerate(self.cursor.fetchall()):
                repeat_display = " (Daily)" if repeat else ""
                display_text = f"{title} at {time_str}{repeat_display}"
                self.reminders_listbox.insert(tk.END, display_text)
                self.reminder_ids[index] = reminder_id
            logging.debug("Reminders loaded successfully.")
        except Exception as e:
            logging.error(f"Error loading reminders: {e}")
            messagebox.showerror("Error", f"Failed to load reminders: {e}")

    def _delete_reminder(self):
        selected = self.reminders_listbox.curselection()
        if not selected:
            messagebox.showwarning("Selection Error", "Please select a reminder to delete.")
            return
        try:
            index = selected[0]
            reminder_id = self.reminder_ids.get(index)
            if reminder_id is None:
                raise ValueError("Reminder ID not found for selected index.")
            self._connect_db()
            self.cursor.execute("SELECT title FROM reminders WHERE id = %s", (reminder_id,))
            title = self.cursor.fetchone()[0]
            if messagebox.askyesno("Confirm Deletion", f"Delete the reminder titled '{title}'?"):
                self.cursor.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
                self.db.commit()
                logging.info(f"Reminder ID {reminder_id} deleted.")
                messagebox.showinfo("Success", "Reminder deleted successfully!")
                self._load_reminders()
        except Exception as e:
            logging.error(f"Error deleting reminder: {e}")
            messagebox.showerror("Error", f"Failed to delete reminder: {e}")

    # --- Background Tasks and Notifications ---
    def _test_notification(self):
        try:
            notification.notify(
                title="To-Do App Started",
                message="Your To-Do List application is now running.",
                timeout=5
            )
            logging.info("Startup notification sent successfully.")
        except Exception as e:
            logging.warning(f"Failed to send startup notification: {e}")
            messagebox.showwarning("Notification Warning", "Notifications might not work.")

    def _get_prayer_text(self):
        now = datetime.now(self.bangladesh_tz)
        today = now.date()
        upcoming = []
        for prayer, time_str in self.prayer_times.items():
            try:
                prayer_time = datetime.strptime(
                    f"{today} {time_str}", "%Y-%m-%d %I:%M %p"
                ).replace(tzinfo=self.bangladesh_tz)
                if now < prayer_time:
                    upcoming.append(f"{prayer}: {time_str}")
            except ValueError as e:
                logging.error(f"Error parsing prayer time for '{prayer}': {e}")
        return "  |  ".join(upcoming) or "No upcoming prayers currently."

    def _scroll_marquee(self, text, x_pos):
        if not text:
            return
        canvas_width = self.marquee_canvas.winfo_width()
        text_bbox = self.marquee_canvas.bbox(self.marquee_text)
        text_width = (text_bbox[2] - text_bbox[0]) if text_bbox else 0
        if x_pos < -text_width:
            x_pos = canvas_width
        self.marquee_canvas.coords(self.marquee_text, x_pos, 20)
        self.root.after(50, lambda: self._scroll_marquee(text, x_pos - 1))

    def _update_prayer_marquee(self):
        text = self._get_prayer_text()
        self.marquee_canvas.itemconfig(self.marquee_text, text=text)
        self.marquee_canvas.update_idletasks()
        self._scroll_marquee(text, self.marquee_canvas.winfo_width())
        self.root.after(60000, self._update_prayer_marquee)

    def _show_hadith_popup(self, hadith):
        popup = ctk.CTkToplevel(self.root)
        popup.title("Daily Hadith")
        popup.geometry("350x180")
        popup.transient(self.root)
        popup.grab_set()
        frame = ctk.CTkFrame(popup, corner_radius=10, fg_color="#3A3A4E")
        frame.pack(fill="both", expand=True, padx=15, pady=15)
        ctk.CTkLabel(
            frame, text="Hadith of the Day:", font=ctk.CTkFont("Roboto", 16, "bold"),
            text_color="#E0E0E0"
        ).pack(pady=(5, 10))
        ctk.CTkLabel(
            frame, text=hadith, font=ctk.CTkFont("Roboto", 12), wraplength=300, justify="center",
            text_color="#E0E0E0"
        ).pack(pady=5)
        ctk.CTkButton(
            frame, text="Close", command=popup.destroy,
            font=ctk.CTkFont("Roboto", 14), corner_radius=8,
            fg_color="#6366F1", hover_color="#4F46E5"
        ).pack(pady=(10, 5))
        popup.protocol("WM_DELETE_WINDOW", popup.destroy)

    def _check_hadith(self):
        while True:
            now = datetime.now()
            if self.last_hadith_time is None or (now - self.last_hadith_time).total_seconds() >= 6 * 3600:
                hadith = random.choice(self.hadiths)
                self.last_hadith_time = now
                logging.info(f"Displaying new Hadith: {hadith[:50]}...")
                self.root.after(0, lambda: self._show_hadith_popup(hadith))
            time.sleep(60)

    def _check_reminders(self):
        while True:
            try:
                self._connect_db()
                now = datetime.now(self.bangladesh_tz)
                logging.debug(f"Checking reminders at {now}")

                self.cursor.execute("SELECT id, title, reminder_time, `repeat` FROM reminders")
                for reminder_id, title, reminder_time_str, repeat in self.cursor.fetchall():
                    try:
                        stored_dt = datetime.strptime(
                            reminder_time_str, "%Y-%m-%d %I:%M %p"
                        ).replace(tzinfo=self.bangladesh_tz)
                        trigger = False

                        if repeat:
                            if stored_dt.date() < now.date():
                                new_dt = now.replace(
                                    hour=stored_dt.hour, minute=stored_dt.minute,
                                    second=stored_dt.second, microsecond=stored_dt.microsecond
                                )
                                if new_dt <= now and (now - new_dt).total_seconds() > 60:
                                    new_dt += timedelta(days=1)
                                new_time_str = new_dt.strftime("%Y-%m-%d %I:%M %p")
                                self.cursor.execute(
                                    "UPDATE reminders SET reminder_time = %s WHERE id = %s",
                                    (new_time_str, reminder_id)
                                )
                                self.db.commit()
                                self.root.after(0, self._load_reminders)
                                continue
                            today_dt = now.replace(
                                hour=stored_dt.hour, minute=stored_dt.minute,
                                second=stored_dt.second, microsecond=stored_dt.microsecond
                            )
                            if now >= today_dt and (now - today_dt).total_seconds() < 60:
                                trigger = True
                        else:
                            time_diff = (now - stored_dt).total_seconds()
                            if -5 <= time_diff <= 30:
                                trigger = True
                            elif time_diff > 30:
                                self.cursor.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
                                self.db.commit()
                                self.root.after(0, self._load_reminders)
                                continue

                        if trigger:
                            logging.info(f"Triggering reminder ID {reminder_id}: '{title}'")
                            try:
                                notification.notify(
                                    title=f"Reminder: {title}",
                                    message=f"It's time for: {title}!",
                                    app_name="To-Do App",
                                    timeout=10
                                )
                            except Exception as e:
                                logging.error(f"Notification failed for ID {reminder_id}: {e}")
                                self.root.after(0, lambda t=title: messagebox.showinfo(f"Reminder: {t}", f"It's time for: {t}!"))

                            if repeat:
                                new_dt = stored_dt + timedelta(days=1)
                                new_time_str = new_dt.strftime("%Y-%m-%d %I:%M %p")
                                self.cursor.execute(
                                    "UPDATE reminders SET reminder_time = %s WHERE id = %s",
                                    (new_time_str, reminder_id)
                                )
                            else:
                                self.cursor.execute("DELETE FROM reminders WHERE id = %s", (reminder_id,))
                            self.db.commit()
                            self.root.after(0, self._load_reminders)

                    except ValueError as e:
                        logging.error(f"Error parsing reminder ID {reminder_id}: {e}")
                    except Exception as e:
                        logging.error(f"Error processing reminder ID {reminder_id}: {e}")

                time.sleep(5)
            except Exception as e:
                logging.error(f"Error in reminder thread: {e}")
                time.sleep(10)

if __name__ == "__main__":
    app_root = ctk.CTk()
    app = ToDoApp(app_root)
    app_root.mainloop()
