# 📋 To-Do List Application with Focus Timer & Gamification

> A powerful desktop productivity application combining task management, Pomodoro timer, gamification, and smart reminders - built with Python CustomTkinter and MySQL.

## 🌟 Overview

This comprehensive To-Do List application is designed to boost productivity through an integrated approach to task management. It combines traditional task tracking with a focus timer, gamification elements, and intelligent reminders to help users stay organized and motivated.

## ✨ Features

### 📝 Notes Management
- Create, edit, and delete notes
- Rich text editing capabilities
- Search and filter notes
- Timestamp tracking for each note
- Organized display with preview

### 📅 Task Schedule
- Add tasks with date and time
- Mark tasks as completed
- View tasks in current/completed/all views
- Task status tracking
- Sort by date and time

### 🔔 Smart Reminders
- Set reminders with date and time selection (AM/PM format)
- Daily repeat option for recurring reminders
- Desktop notifications for due reminders
- Automatic cleanup of completed reminders
- Real-time reminder checking

### ⏱️ Focus Timer (Pomodoro)
- **25-minute work sessions** with 5-minute breaks
- Visual timer display with progress tracking
- Session counter
- Start, Pause, and Reset controls
- Desktop notifications for session completion
- **Task Integration**: Select tasks from schedule to focus on

### 🎮 Gamification System
- **Points System**: Earn 10 points per completed work session
- **Level System**: Level up every 100 points
- **Achievement Badges**: Unlock themes as you progress
  - 🎯 **Focus Seeker** - 50 points (New theme)
  - 🌅 **Sunrise Master** - 100 points (New theme)
  - 🌙 **Twilight Sage** - 200 points (New theme)
  - 🏆 **Productivity Guru** - 500 points (New theme)
- **Theme Unlocks**: Earn new visual themes for the app

### 🌙 Additional Features
- **Dark/Light Theme Toggle**: Comfortable viewing in any environment
- **Prayer Time Marquee**: Displays upcoming prayer times (Bangladesh timezone)
- **Daily Hadith Popups**: Motivational Islamic reminders every 6 hours
- **Responsive UI**: Modern glassmorphism design
- **Database Persistence**: All data stored in MySQL

## 🛠️ Technology Stack

| Layer | Technology |
|-------|------------|
| GUI Framework | CustomTkinter |
| Database | MySQL 8 |
| Backend Language | Python 3.13+ |
| Notifications | Plyer |
| Date/Time | datetime, zoneinfo |
| UI Components | Tkinter, tkcalendar |

### Dependencies
```bash
customtkinter
mysql-connector-python
plyer
tkcalendar
