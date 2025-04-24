#!/add/your/pythonexec/path/here
"""Checklist++: cross-platform terminal checklist tool.

Minor high-impact update:
1. Use Colorama for ANSI color compatibility on Windows.
2. Store checklist JSON files in a user-specific data directory (~/.checklists) for macOS/Linux and %APPDATA%\ChecklistPP on Windows.
"""

import os
import json
import time
import textwrap
import sys
import platform
import shutil
import argparse
import yaml
import subprocess
import requests
from pathlib import Path
from datetime import datetime, timedelta

# Optional imports for smart grouping
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    import numpy as np
    SMART_GROUPING_AVAILABLE = True
except ImportError:
    SMART_GROUPING_AVAILABLE = False

# --- Cross-platform ANSI color support -------------------------------------
try:
    import colorama  # type: ignore
    colorama.just_fix_windows_console()
except ModuleNotFoundError:
    # Colorama not installed; ANSI colors work on most Unix terminals by default.
    colorama = None

# ---------------------------------------------------------------------------

ASCII_ART1 = ''' --  .+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+. 
-- (      ____ _               _    _ _     _                    )
--  )    / ___| |__   ___  ___| | _| (_)___| |_  _     _        ( 
-- (    | |   | '_ \ / _ \/ __| |/ / | / __| __|| |_ _| |_       )
--  )   | |___| | | |  __/ (__|   <| | \__ \ ||_   _|_   _|     ( 
-- (     \____|_| |_|\___|\___|_|\_\_|_|___/\__||_|   |_|        )
--  )                                                           ( 
-- (                                                             )
--  "+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+"+.+" 
'''

APP_INFO = ''' A command Line ready checklist and kanban tool for productivity

Written with Python and JSON/YAML
'''

# Directory to store all checklists (platform-specific user data dir)
def _default_data_dir() -> str:
    """Return a writable per-user directory for storing checklist JSON files."""
    if os.name == "nt":  # Windows
        base = os.getenv("APPDATA", os.path.expanduser("~"))
        return os.path.join(base, "ChecklistPP")
    # macOS/Linux – use ~/.checklists
    return os.path.join(os.path.expanduser("~"), ".checklists")


CHECKLIST_DIR = _default_data_dir()
# Ensure directory exists
os.makedirs(CHECKLIST_DIR, exist_ok=True)

# YAML configuration path
CONFIG_FILE = os.path.join(os.path.expanduser("~"), ".checklistpp.yaml")

# Default configuration
DEFAULT_CONFIG = {
    "data_dir": CHECKLIST_DIR,
    "limits": {
        "todo": 10,
        "progress": 3,
        "done": 10,
        "taskname": 40
    },
    "repaint": True,
    "default_view": "checklist"  # or "kanban"
}

# Load configuration from YAML
def load_config():
    """Load configuration from YAML file, create if doesn't exist"""
    global CHECKLIST_DIR, DEFAULT_CONFIG
    
    if not os.path.exists(CONFIG_FILE):
        # Create default config
        with open(CONFIG_FILE, 'w') as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False)
        return DEFAULT_CONFIG
    
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = yaml.safe_load(f)
            
        # Ensure all keys exist (backward compatibility)
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
                
        if "limits" not in config:
            config["limits"] = DEFAULT_CONFIG["limits"]
        else:
            for limit_key, limit_val in DEFAULT_CONFIG["limits"].items():
                if limit_key not in config["limits"]:
                    config["limits"][limit_key] = limit_val
                    
        # Update directory
        if config["data_dir"]:
            CHECKLIST_DIR = config["data_dir"]
            os.makedirs(CHECKLIST_DIR, exist_ok=True)
            
        return config
    except Exception as e:
        print(f"Error loading config: {e}. Using defaults.")
        return DEFAULT_CONFIG

# Load configuration
CONFIG = load_config()

EXPORT_DIR = os.path.join(os.path.expanduser("~"), ".checklists", "exports")
os.makedirs(EXPORT_DIR, exist_ok=True)

# ANSI escape codes for colors
COLOR_RED = '\033[91m'
COLOR_ORANGE = '\033[93m'
COLOR_GREEN = '\033[92m'
COLOR_RESET = '\033[0m'  
COLOR_BRIGHT_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'
# Reset to default color

# Flags to control visual enhancements
COLOR_CODING_ENABLED = True
SIMPLE_VIEW_ENABLED = False
MENU_VISIBLE = False  
# Kanban support
ONE_LINE_DISPLAY = False
KANBAN_VIEW_ENABLED = False  # Toggle between checklist and kanban views

# Default Kanban columns
KANBAN_COLUMNS = ["Todo", "Progress", "Done"]

# Use config to set default view
if CONFIG.get("default_view") == "kanban":
    KANBAN_VIEW_ENABLED = True

# Responsive alignment: horizontal table (default) or vertical stacked lists
KANBAN_ALIGNMENT_HORIZONTAL = True  # True=horizontal, False=vertical

# Variable to store the last action for undo functionality
last_action = None

# Current checklist and its name
current_checklist = []
current_checklist_name = "default"

def configure():
    """Interactive configuration setup"""
    global CONFIG, CHECKLIST_DIR
    
    print("\nChecklist++ Configuration")
    print("------------------------")
    
    data_dir = input(f"Data directory [{CONFIG['data_dir']}]: ").strip() or CONFIG['data_dir']
    todo_limit = input(f"Todo column limit [{CONFIG['limits']['todo']}]: ").strip() or CONFIG['limits']['todo']
    progress_limit = input(f"Progress column limit [{CONFIG['limits']['progress']}]: ").strip() or CONFIG['limits']['progress']
    done_limit = input(f"Done column limit [{CONFIG['limits']['done']}]: ").strip() or CONFIG['limits']['done']
    taskname_limit = input(f"Task name length limit [{CONFIG['limits']['taskname']}]: ").strip() or CONFIG['limits']['taskname']
    repaint = input(f"Auto-repaint after commands (y/n) [{CONFIG['repaint']}]: ").strip().lower()
    default_view = input(f"Default view (checklist/kanban) [{CONFIG['default_view']}]: ").strip() or CONFIG['default_view']
    
    # Update config
    CONFIG['data_dir'] = data_dir
    CONFIG['limits']['todo'] = int(todo_limit)
    CONFIG['limits']['progress'] = int(progress_limit)
    CONFIG['limits']['done'] = int(done_limit)
    CONFIG['limits']['taskname'] = int(taskname_limit)
    CONFIG['repaint'] = True if repaint in ('y', 'yes', 'true') else False
    CONFIG['default_view'] = default_view if default_view in ('checklist', 'kanban') else 'checklist'
    
    # Update directory
    CHECKLIST_DIR = CONFIG['data_dir']
    os.makedirs(CHECKLIST_DIR, exist_ok=True)
    
    # Save configuration
    with open(CONFIG_FILE, 'w') as f:
        yaml.dump(CONFIG, f, default_flow_style=False)
        
    print(f"Configuration saved to {CONFIG_FILE}")

# Load checklist data from file
def load_checklist(name):
    global current_checklist, current_checklist_name

    filename = os.path.join(CHECKLIST_DIR, f"{name}.json")
    if os.path.exists(filename):
        with open(filename, 'r') as file:
            current_checklist = json.load(file)
        current_checklist_name = name
        print(f"Loaded checklist: {name}")
    else:
        print(f"Checklist '{name}' does not exist. Starting a new checklist.")
        current_checklist = []
        current_checklist_name = name
        save_checklist(current_checklist_name)

# Save checklist data to file
def save_checklist(name):
    global current_checklist
    filename = os.path.join(CHECKLIST_DIR, f"{name}.json")
    with open(filename, 'w') as file:
        json.dump(current_checklist, file, indent=4)
    print(f"Checklist saved as '{name}'.")

def toggle_one_line_display():
    global ONE_LINE_DISPLAY
    ONE_LINE_DISPLAY = not ONE_LINE_DISPLAY
    status = "enabled" if ONE_LINE_DISPLAY else "disabled"
    print(f"One-line display has been {status}.")

# Display checklist items with optional visual enhancements
def display_checklist():
    print(f"\nChecklist: {current_checklist_name}")
    if not current_checklist:
        print("No tasks yet. Add a task to get started!")
    else:
        # Sort checklist by priority level (High -> Medium -> Low)
        sorted_checklist = sorted(current_checklist, key=lambda x: x.get('priority', 'Medium'), reverse=True)
        for index, item in enumerate(sorted_checklist, start=1):
            status = f"{COLOR_BRIGHT_GREEN}✓{COLOR_RESET}" if item["completed"] else f"{COLOR_RED}✗{COLOR_RESET}"
            task_name = item['task']
            if SIMPLE_VIEW_ENABLED:
                # Simplified view: only show task name and status
                print(f"{index}. [{status}] {task_name}")
            else:
                # Detailed view with priority, time spent, and progress
                duration = item.get("time_spent", 0)
                priority = item.get('priority', 'Medium')
                progress = f"{item.get('progress', 0)}%"  # Progress tracking

                # Determine color coding based on priority and flag
                if COLOR_CODING_ENABLED:
                    if priority == 'High':
                        color = COLOR_RED
                    elif priority == 'Medium':
                        color = COLOR_ORANGE
                    else:
                        color = COLOR_GREEN
                else:
                    color = COLOR_RESET  # No color if color coding is disabled

                if SIMPLE_VIEW_ENABLED:
                    print(f"{index}. [{status}] {task_name}")

                else:
                    if ONE_LINE_DISPLAY:
                    # Truncate task name if it's too long
                        max_task_length = 30
                        if len(task_name) > max_task_length:
                            task_name = task_name[:max_task_length-3] + "..."
                    
                        line = f"{index}. [{status}] {task_name} - {color}Pri: {priority[:1]}{COLOR_RESET} - Time: {duration:.0f}s - Prog: {progress}"
                        print(line)
                    else:
                        print(f"{index}. [{status}] {task_name}")
                        print(f"   {color}Priority: {priority}{COLOR_RESET} - Time Spent: {duration:.2f} seconds - Progress: {progress}")
        return sorted_checklist
        # Add a task with priority
def add_task():
    global last_action
    task = input("Enter the task: ")
    priority = input("Enter priority (High, Medium, Low): ").capitalize()
    if priority not in ['High', 'Medium', 'Low']:
        print("Invalid priority. Defaulting to Medium.")
        priority = 'Medium'
    new_task = {"task": task, "completed": False, "start_time": 0, "time_spent": 0, "priority": priority, "progress": 0}
    current_checklist.append(new_task)
    save_checklist(current_checklist_name)
    last_action = ('add', new_task)
    print(f"Task '{task}' added with priority '{priority}'.")

# Undo the last action
def undo_action():
    global last_action
    if not last_action:
        print("No actions to undo.")
        return

    action, task = last_action
    if action == 'add':
        current_checklist.remove(task)
        print(f"Task '{task['task']}' removed.")
    elif action == 'complete':
        task["completed"] = False
        print(f"Task '{task['task']}' marked as incomplete.")
    save_checklist(current_checklist_name)
    last_action = None

# Edit a task
def edit_task():
    sorted_checklist = display_checklist()
    try:
        task_num = int(input("Enter the number of the task to edit: ")) - 1
        if 0 <= task_num < len(sorted_checklist):
            task = sorted_checklist[task_num]
            task['task'] = input(f"Edit task name (current: {task['task']}): ") or task['task']
            task['priority'] = input(f"Edit priority (current: {task['priority']} - High, Medium, Low): ").capitalize() or task['priority']
            progress = input(f"Edit progress percentage (current: {task['progress']}%): ")
            if progress.isdigit():
                task['progress'] = int(progress)
            save_checklist(current_checklist_name)
            print(f"Task '{task['task']}' has been updated.")
        else:
            print("Invalid task number.")
    except ValueError:
        print("Please enter a valid number.")

# Mark a task as completed
def mark_task():
    global last_action
    sorted_checklist =display_checklist()
    try:
        task_num = int(input("Enter the number of the task to mark as completed: ")) - 1
        if 0 <= task_num < len(sorted_checklist):
            task = sorted_checklist[task_num]
            task["completed"] = True
            save_checklist(current_checklist_name)
            last_action = ('complete', task)
            print(f"Task '{task['task']}' marked as completed.")
        else:
            print("Invalid task number.")
    except ValueError:
        print("Please enter a valid number.")

# Start task timer
def start_task():
    sorted_checklist = display_checklist()
    try:
        task_num = int(input("Enter the number of the task to start: ")) - 1
        if 0 <= task_num < len(sorted_checklist) and not current_checklist[task_num]["completed"]:
            task = sorted_checklist[task_num]
            task["start_time"] = time.time()
            save_checklist(current_checklist_name)
            print(f"Started tracking time for task: {task['task']}")
        else:
            print("Invalid task number or task already completed.")
    except ValueError:
        print("Please enter a valid number.")

# Stop task timer
def stop_task():
    sorted_checklist = display_checklist()
    try:
        task_num = int(input("Enter the number of the task to stop: ")) - 1
        if 0 <= task_num < len(sorted_checklist) and sorted_checklist[task_num]["start_time"] > 0:
            task = sorted_checklist[task_num]
            end_time = time.time()
            elapsed = end_time - task["start_time"]
            task["time_spent"] += elapsed
            task["start_time"] = 0
            save_checklist(current_checklist_name)
            print(f"Stopped tracking time for task: {task['task']}, Time Spent: {elapsed:.2f} seconds")
        else:
            print("Invalid task number or task timer not started.")
    except ValueError:
        print("Please enter a valid number.")

# Toggle color coding on and off
def toggle_color_coding():
    global COLOR_CODING_ENABLED
    COLOR_CODING_ENABLED = not COLOR_CODING_ENABLED
    status = "enabled" if COLOR_CODING_ENABLED else "disabled"
    print(f"Color coding has been {status}.")

# Toggle simplified view on and off
def toggle_simple_view():
    global SIMPLE_VIEW_ENABLED
    SIMPLE_VIEW_ENABLED = not SIMPLE_VIEW_ENABLED
    status = "enabled" if SIMPLE_VIEW_ENABLED else "disabled"
    print(f"Simplified view has been {status}.")

# Toggle menu visibility
def toggle_menu_visibility():
    global MENU_VISIBLE
    MENU_VISIBLE = not MENU_VISIBLE
    status = "shown" if MENU_VISIBLE else "hidden"
    print(f"Menu is now {status}.")

# Clear the checklist
def clear_checklist():
    confirm = input("Are you sure you want to clear the entire checklist? (yes/no): ").strip().lower()
    if confirm == "yes":
        current_checklist.clear()  # Clear the current checklist
        save_checklist(current_checklist_name)
        print("Checklist has been cleared.")
    else:
        print("Checklist not cleared.")

# List all saved checklists
def list_checklists():
    files = [f.replace('.json', '') for f in os.listdir(CHECKLIST_DIR) if f.endswith('.json')]
    if files:
        print("\nAvailable Checklists:")
        for i, filename in enumerate(files, start=1):
            print(f"{i}. {filename}")
    else:
        print("No saved checklists available.")

# Switch to another checklist
def switch_checklist():
    list_checklists()
    name = input("Enter the name of the checklist to load: ")
    if name:
        save_checklist(current_checklist_name)  # Save current checklist before switching
        load_checklist(name)

# Delete a saved checklist
def delete_checklist():
    list_checklists()
    name = input("Enter the name of the checklist to delete: ")
    filename = os.path.join(CHECKLIST_DIR, f"{name}.json")
    if os.path.exists(filename):
        confirm = input(f"Are you sure you want to delete '{name}'? (yes/no): ").strip().lower()
        if confirm == "yes":
            os.remove(filename)
            print(f"Checklist '{name}' has been deleted.")
        else:
            print("Deletion cancelled.")
    else:
        print(f"Checklist '{name}' does not exist.")

# Delete all saved checklists
def delete_all_checklists():
    files = [f for f in os.listdir(CHECKLIST_DIR) if f.endswith('.json')]
    if not files:
        print("No checklists available to delete.")
        return

    confirm = input("Are you sure you want to delete ALL checklists? (yes/no): ").strip().lower()
    if confirm == "yes":
        for file in files:
            os.remove(os.path.join(CHECKLIST_DIR, file))
        print("All checklists have been deleted.")
    else:
        print("Deletion cancelled.")

# Show all checklists without loading them
def show_checklists():
    files = [f.replace('.json', '') for f in os.listdir(CHECKLIST_DIR) if f.endswith('.json')]
    if files:
        print("\nAll Stored Checklists:")
        for filename in files:
            print(f"- {filename}")
    else:
        print("No checklists available.")


# Add this new function
def load_external_checklist():
    global current_checklist, current_checklist_name
    file_path = input("Enter the full path to the JSON file: ").strip()
    if os.path.exists(file_path) and file_path.endswith('.json'):
        try:
            with open(file_path, 'r') as file:
                loaded_checklist = json.load(file)
            
            # Validate the loaded data (optional, but recommended)
            if isinstance(loaded_checklist, list) and all(isinstance(item, dict) for item in loaded_checklist):
                current_checklist = loaded_checklist
                current_checklist_name = os.path.basename(file_path).replace('.json', '')
                print(f"Loaded external checklist: {current_checklist_name}")
                save_checklist(current_checklist_name)  # Save it in the current program's format
            else:
                print("The file does not contain a valid checklist format.")
        except json.JSONDecodeError:
            print("The file is not a valid JSON file.")
    else:
        print("Invalid file path or not a JSON file.")

def enforce_column_limits(sorted_tasks):
    """Enforce column limits based on configuration"""
    counts = {"Todo": 0, "Progress": 0, "Done": 0}
    warnings = []
    
    # Count tasks per column
    for item in sorted_tasks:
        status = _status_for_task(item)
        counts[status] = counts.get(status, 0) + 1
    
    # Check limits
    if counts["Todo"] > CONFIG['limits']['todo']:
        warnings.append(f"Todo column has {counts['Todo']} tasks, exceeding limit of {CONFIG['limits']['todo']}")
    
    if counts["Progress"] > CONFIG['limits']['progress']:
        warnings.append(f"Progress column has {counts['Progress']} tasks, exceeding limit of {CONFIG['limits']['progress']}")
        
    if counts["Done"] > CONFIG['limits']['done']:
        warnings.append(f"Done column has {counts['Done']} tasks, exceeding limit of {CONFIG['limits']['done']}")
        
    return warnings

def _status_for_task(item):
    """Determine which kanban column a task belongs to."""
    if 'status' in item:
        # If task already has an explicit status defined
        return item['status']
    # Otherwise, determine based on completion status
    if item.get('completed', False):
        return "Done"
    elif item.get('progress', 0) > 0:
        return "Progress"
    else:
        return "Todo"

def display_kanban():
    """Render tasks grouped by status in a minimalist board."""
    print("\nKanban Board")
    # Prepare grouped tasks
    grouped = {col: [] for col in KANBAN_COLUMNS}
    for idx, item in enumerate(current_checklist, start=1):
        col = _status_for_task(item)
        grouped.setdefault(col, []).append((idx, item))

    # Check if we should display in horizontal or vertical mode
    if KANBAN_ALIGNMENT_HORIZONTAL:
        # Determine terminal width for dynamic sizing
        term_width = shutil.get_terminal_size((80, 20)).columns
        # Reserve 3 spaces for separators between columns
        col_width = max(12, (term_width - (3 * (len(KANBAN_COLUMNS) - 1))) // len(KANBAN_COLUMNS))

        # Render header
        header = " | ".join(col.center(col_width) for col in KANBAN_COLUMNS)
        print(header)
        print("-" * len(header))

        # Determine the maximum tasks in any column
        max_tasks = max((len(lst) for lst in grouped.values()), default=0)

        # Render rows
        for row in range(max_tasks):
            row_cells = []
            for col in KANBAN_COLUMNS:
                if row < len(grouped[col]):
                    idx, item = grouped[col][row]
                    title = textwrap.shorten(item['task'], width=col_width-4, placeholder="...")
                    row_cells.append(f"{idx}. {title}".ljust(col_width))
                else:
                    row_cells.append("".ljust(col_width))
            print(" | ".join(row_cells))
    else:
        # Vertical stacked lists
        for col in KANBAN_COLUMNS:
            col_items = grouped.get(col, [])
            
            # Apply limit from config - only for display
            limit_key = col.lower()
            if limit_key == "progress": 
                limit_key = "progress"  # Map to config key
                
            limit = CONFIG['limits'].get(limit_key, 999)
            if len(col_items) > limit and col == "Done":
                col_items = col_items[:limit]  # For Done column, just show most recent
                overflow = len(grouped.get(col, [])) - limit
                if overflow > 0:
                    display_suffix = f" (+{overflow} more)"
                else:
                    display_suffix = ""
            else:
                display_suffix = ""
            
            print(f"\n{col}{display_suffix}:")
            if not col_items:
                print("  (empty)")
            for idx, item in col_items:
                title = textwrap.shorten(item['task'], width=CONFIG['limits']['taskname'], placeholder="...")
                priority_marker = ""
                if item.get('priority') == 'High':
                    priority_marker = f"{COLOR_RED}!{COLOR_RESET} "
                print(f"  {idx}. {priority_marker}{title}")

def promote_task():
    """Move a task to the next stage in the Kanban workflow."""
    sorted_checklist = display_checklist() if not KANBAN_VIEW_ENABLED else current_checklist
    try:
        task_num = int(input("Enter the task number to promote: ")) - 1
        if 0 <= task_num < len(sorted_checklist):
            task = current_checklist[task_num]
            status = _status_for_task(task)
            idx = KANBAN_COLUMNS.index(status)
            if idx < len(KANBAN_COLUMNS) - 1:
                task['status'] = KANBAN_COLUMNS[idx + 1]
                # If moving to Done, mark as completed
                if task['status'] == "Done":
                    task['completed'] = True
                print(f"Task promoted to {task['status']}")
            else:
                print("Task is already in the last column.")
            save_checklist(current_checklist_name)
        else:
            print("Invalid task number.")
    except ValueError:
        print("Please enter a valid number.")

def regress_task():
    """Move a task back to the previous stage in the Kanban workflow."""
    sorted_checklist = display_checklist() if not KANBAN_VIEW_ENABLED else current_checklist
    try:
        task_num = int(input("Enter the task number to regress: ")) - 1
        if 0 <= task_num < len(sorted_checklist):
            task = current_checklist[task_num]
            status = _status_for_task(task)
            idx = KANBAN_COLUMNS.index(status)
            if idx > 0:
                task['status'] = KANBAN_COLUMNS[idx - 1]
                # If moving back from Done, mark as incomplete
                if status == "Done":
                    task['completed'] = False
                print(f"Task regressed to {task['status']}")
            else:
                print("Task is already in the first column.")
            save_checklist(current_checklist_name)
        else:
            print("Invalid task number.")
    except ValueError:
        print("Please enter a valid number.")

def toggle_kanban_view():
    """Switch between list and kanban visualisations."""
    global KANBAN_VIEW_ENABLED
    KANBAN_VIEW_ENABLED = not KANBAN_VIEW_ENABLED
    status = "Kanban" if KANBAN_VIEW_ENABLED else "Checklist"
    print(f"Switched to {status} view.")

def toggle_kanban_alignment():
    """Toggle between horizontal and vertical Kanban layouts."""
    global KANBAN_ALIGNMENT_HORIZONTAL
    KANBAN_ALIGNMENT_HORIZONTAL = not KANBAN_ALIGNMENT_HORIZONTAL
    orient = "horizontal" if KANBAN_ALIGNMENT_HORIZONTAL else "vertical"
    print(f"Kanban orientation set to {orient}.")

def short_help():
    """Show brief command help for clikan-style usage"""
    print("\nChecklist++ Commands:")
    print("  s, show             - Show current view (checklist/kanban)")
    print("  a, add <text>       - Add a new task")
    print("  p, promote <id>     - Promote a task to the next column")
    print("  r, regress <id>     - Move a task back to previous column")
    print("  d, delete <id>      - Delete a task")
    print("  m, mark <id>        - Mark a task as completed")
    print("  c, configure        - Update configuration")
    print("  v, view <type>      - Switch view (checklist/kanban)")
    print("  e, export [format]  - Export tasks (md, cursor)")
    print("  i, import <file>    - Import tasks from file")
    print("  g, group            - Smart group tasks using NLP")
    print("  h, help             - Show this help")
    print("  q, quit             - Exit")

def add_task_with_args(args):
    """Add a task with arguments"""
    global last_action
    
    task = " ".join(args)
    if not task:
        print("Error: Task text required")
        return
        
    if len(task) > CONFIG['limits']['taskname']:
        task = task[:CONFIG['limits']['taskname']]
        print(f"Note: Task text truncated to {CONFIG['limits']['taskname']} characters")
    
    # Default to Medium priority
    new_task = {
        "task": task, 
        "completed": False, 
        "start_time": 0, 
        "time_spent": 0, 
        "priority": "Medium", 
        "progress": 0,
        "status": "Todo"
    }
    
    current_checklist.append(new_task)
    save_checklist(current_checklist_name)
    last_action = ('add', new_task)
    print(f"Added task: {task}")
    
    # Auto-repaint if enabled
    if CONFIG.get('repaint', True):
        if KANBAN_VIEW_ENABLED:
            display_kanban()
        else:
            display_checklist()

def process_simple_commands(command, args):
    """Process clikan-style simple commands"""
    global current_checklist, current_checklist_name, KANBAN_VIEW_ENABLED
    
    if command in ('s', 'show'):
        if KANBAN_VIEW_ENABLED:
            display_kanban()
        else:
            display_checklist()
    elif command in ('a', 'add') and args:
        add_task_with_args(args)
    elif command in ('p', 'promote') and args:
        try:
            task_id = int(args[0]) - 1
            if 0 <= task_id < len(current_checklist):
                task = current_checklist[task_id]
                status = _status_for_task(task)
                idx = KANBAN_COLUMNS.index(status)
                if idx < len(KANBAN_COLUMNS) - 1:
                    task['status'] = KANBAN_COLUMNS[idx + 1]
                    print(f"Task promoted to {task['status']}")
                else:
                    print("Task is already in the last column.")
                save_checklist(current_checklist_name)
                
                # Auto-repaint
                if CONFIG.get('repaint', True):
                    if KANBAN_VIEW_ENABLED:
                        display_kanban()
                    else:
                        display_checklist()
            else:
                print("Invalid task number.")
        except (ValueError, IndexError):
            print("Please provide a valid task number.")
    elif command in ('r', 'regress') and args:
        try:
            task_id = int(args[0]) - 1
            if 0 <= task_id < len(current_checklist):
                task = current_checklist[task_id]
                status = _status_for_task(task)
                idx = KANBAN_COLUMNS.index(status)
                if idx > 0:
                    task['status'] = KANBAN_COLUMNS[idx - 1]
                    # If moving back from Done, mark as incomplete
                    if status == "Done":
                        task['completed'] = False
                    print(f"Task regressed to {task['status']}")
                else:
                    print("Task is already in the first column.")
                save_checklist(current_checklist_name)
                
                # Auto-repaint
                if CONFIG.get('repaint', True):
                    if KANBAN_VIEW_ENABLED:
                        display_kanban()
                    else:
                        display_checklist()
            else:
                print("Invalid task number.")
        except (ValueError, IndexError):
            print("Please provide a valid task number.")
    elif command in ('d', 'delete') and args:
        try:
            task_id = int(args[0]) - 1
            if 0 <= task_id < len(current_checklist):
                task = current_checklist.pop(task_id)
                print(f"Deleted: {task['task']}")
                save_checklist(current_checklist_name)
                
                # Auto-repaint
                if CONFIG.get('repaint', True):
                    if KANBAN_VIEW_ENABLED:
                        display_kanban()
                    else:
                        display_checklist()
            else:
                print("Invalid task number.")
        except (ValueError, IndexError):
            print("Please provide a valid task number.")
    elif command in ('m', 'mark') and args:
        try:
            task_id = int(args[0]) - 1
            if 0 <= task_id < len(current_checklist):
                task = current_checklist[task_id]
                task["completed"] = True
                task["status"] = "Done"  # Also update status for kanban view
                save_checklist(current_checklist_name)
                print(f"Marked task '{task['task']}' as completed.")
                
                # Auto-repaint
                if CONFIG.get('repaint', True):
                    if KANBAN_VIEW_ENABLED:
                        display_kanban()
                    else:
                        display_checklist()
            else:
                print("Invalid task number.")
        except (ValueError, IndexError):
            print("Please provide a valid task number.")
    elif command in ('c', 'configure'):
        configure()
    elif command in ('v', 'view') and args:
        view_type = args[0].lower()
        if view_type in ('k', 'kanban'):
            KANBAN_VIEW_ENABLED = True
            display_kanban()
        elif view_type in ('c', 'checklist'):
            KANBAN_VIEW_ENABLED = False
            display_checklist()
        else:
            print("Unknown view type. Use 'checklist' or 'kanban'.")
    elif command in ('e', 'export') and args:
        format = args[0].lower()
        if format in ('md', 'markdown'):
            export_to_markdown()
        elif format in ('cursor', 'cursor_tasks'):
            _export_as_cursor_tasks()
        else:
            print("Unknown export format. Use 'md' or 'cursor'.")
    elif command in ('i', 'import') and args:
        import_from_markdown()
    elif command in ('g', 'group'):
        smart_group_tasks()
    elif command in ('h', 'help'):
        short_help()
    elif command in ('q', 'quit', 'exit'):
        print("Exiting Checklist++.")
        save_checklist(current_checklist_name)
        sys.exit(0)
    else:
        print("Unknown command. Type 'h' for help.")
        return False
    
    return True

def process_args():
    """Process command-line arguments for clikan-style commands"""
    if len(sys.argv) < 2:
        return False  # No args, go to interactive mode
        
    command = sys.argv[1].lower()
    args = sys.argv[2:]
    
    # Process the command
    return process_simple_commands(command, args)

# Main menu
def main():
    # First check for direct command-line arguments (clikan-style)
    if process_args():
        return
        
    # Interactive mode
    print(ASCII_ART1)
    load_checklist(current_checklist_name)  # Load the default checklist at startup
    
    # Show initial view based on config
    if KANBAN_VIEW_ENABLED:
        display_kanban()
    else:
        display_checklist()
    
    while True:
        if MENU_VISIBLE:
            display_menu()
            
        choice = input("Choose an option (or enter shortcut command): ")
        
        # Check for clikan-style shortcuts
        if ' ' in choice:
            parts = choice.split(' ', 1)
            cmd = parts[0].lower()
            args = parts[1].split() if len(parts) > 1 else []
            if process_simple_commands(cmd, args):
                continue
                
        # Legacy menu choices
        elif choice == '1':
            display_checklist()
        elif choice == '1k':
            display_kanban()
            display_checklist()
            print("powered by Ḱ64")
        elif choice == '2':
            add_task()
        elif choice == '3':
            mark_task()
        elif choice == '4':
            start_task()
        elif choice == '5':
            stop_task()
        elif choice == '6':
            clear_checklist()
        elif choice == '7':
            toggle_color_coding()
        elif choice == '8':
            edit_task()
        elif choice == '9':
            undo_action()
        elif choice == '10':
            toggle_simple_view()
        elif choice == '11':
            list_checklists()
        elif choice == '12':
            switch_checklist()
        elif choice == '13':
            delete_checklist()
        elif choice == '14':
            show_checklists()
        elif choice == '15':
            delete_all_checklists()
        elif choice == '16' or choice == 'v':
            toggle_menu_visibility()
        elif choice == '17':
            toggle_one_line_display()
        elif choice == '18':
            load_external_checklist()
        elif choice == '19':
            toggle_kanban_view()
        elif choice == '20' or choice == 'k':
            display_kanban()
        elif choice == '21':
            promote_task()
        elif choice == '22':
            regress_task()
        elif choice == '23':
            toggle_kanban_alignment()
        elif choice == '24':
            configure()
        elif choice == '25':
            export_to_markdown()
        elif choice == '26':
            schedule_task()
        elif choice == '27':
            export_to_system_tasks()
        elif choice == '28':
            import_from_markdown()
        elif choice == '29':
            smart_group_tasks()
        elif choice == '30' or choice == 'q':
            print("Exiting Checklist Tool.")
            save_checklist(current_checklist_name)
            break
        else:
            print("Invalid option. Please choose again.")

def display_menu():
    """Display the full menu options."""
    print("\nChecklist Menu:")
    print("1. View Checklist")
    print("2. Add Task")
    print("3. Mark Task as Completed")
    print("4. Start Task Timer")
    print("5. Stop Task Timer")
    print("6. Clear Checklist")
    print("7. Toggle Color Coding")
    print("8. Edit Task")
    print("9. Undo Last Action")
    print("10. Toggle Simplified View")
    print("11. List Checklists")
    print("12. Switch Checklist")
    print("13. Delete Checklist")
    print("14. Show All Checklists")
    print("15. Delete All Checklists")
    print("16. Toggle Menu Visibility")
    print("17. Toggle One-Line Display")
    print("18. Load External Checklist")
    print("19. Toggle Kanban View")
    print("20. Display Kanban")
    print("21. Promote Task")
    print("22. Regress Task")
    print("23. Toggle Kanban Alignment (horizontal/vertical)")
    print("24. Configure")
    print("25. Export to Markdown")
    print("26. Schedule Task")
    print("27. Export to System Tasks")
    print("28. Import from Markdown")
    print("29. Smart Group Tasks")
    print("30. Exit")

def export_to_markdown():
    """Export the current checklist to a markdown file."""
    # Ask if user wants to use default export directory or specify a custom one
    use_default = input(f"Use default export directory ({EXPORT_DIR})? (y/n): ").lower() == 'y'
    
    if use_default:
        output_dir = EXPORT_DIR
    else:
        output_dir = input("Enter full path to export directory: ").strip()
        if not output_dir:
            output_dir = EXPORT_DIR
        else:
            # Create directory if it doesn't exist
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                print(f"Error creating directory: {e}")
                print(f"Using default export directory: {EXPORT_DIR}")
                output_dir = EXPORT_DIR
    
    filename = os.path.join(output_dir, f"{current_checklist_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    
    with open(filename, 'w') as f:
        # Write header
        f.write(f"# Checklist: {current_checklist_name}\n\n")
        f.write(f"*Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n")
        
        # Group by status for better organization
        tasks_by_status = {"Todo": [], "Progress": [], "Done": []}
        
        for idx, task in enumerate(current_checklist, start=1):
            status = _status_for_task(task)
            tasks_by_status[status].append((idx, task))
        
        # Write each section
        for status, tasks in tasks_by_status.items():
            if tasks:
                f.write(f"## {status}\n\n")
                for idx, task in tasks:
                    checkbox = "- [x] " if task.get('completed', False) else "- [ ] "
                    priority = f"**Priority: {task.get('priority', 'Medium')}**"
                    progress = f"Progress: {task.get('progress', 0)}%"
                    time_spent = f"Time: {task.get('time_spent', 0):.2f}s"
                    
                    f.write(f"{checkbox}{task['task']} ({priority}, {progress}, {time_spent})\n")
                f.write("\n")
        
        # Add metadata section
        f.write("## Metadata\n\n")
        f.write("```yaml\n")
        f.write(f"checklist_name: {current_checklist_name}\n")
        f.write(f"date_exported: {datetime.now().isoformat()}\n")
        f.write(f"total_tasks: {len(current_checklist)}\n")
        f.write(f"completed_tasks: {sum(1 for t in current_checklist if t.get('completed', False))}\n")
        f.write("```\n")
    
    print(f"Checklist exported to: {filename}")
    return filename

def schedule_task():
    """Schedule a task with a due date and optional reminder"""
    sorted_checklist = display_checklist()
    
    try:
        task_num = int(input("Enter the number of the task to schedule: ")) - 1
        if 0 <= task_num < len(sorted_checklist):
            task = sorted_checklist[task_num]
            
            # Get due date
            days = input("Enter days from now for due date (or specific date YYYY-MM-DD): ")
            if days.isdigit():
                due_date = (datetime.now() + timedelta(days=int(days))).strftime('%Y-%m-%d')
            else:
                try:
                    # Validate the date format
                    datetime.strptime(days, '%Y-%m-%d')
                    due_date = days
                except ValueError:
                    print("Invalid date format. Using tomorrow's date.")
                    due_date = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Add due date to task
            task['due_date'] = due_date
            
            # Option to set reminder
            set_reminder = input("Set a system reminder? (y/n): ").lower() == 'y'
            if set_reminder:
                if platform.system() == 'Darwin':  # macOS
                    reminder_text = f"Reminder: Task '{task['task']}' is due"
                    cmd = f"osascript -e 'tell application \"Reminders\" to make new reminder with properties {{name:\"{reminder_text}\", due date:date \"{due_date}\"}}'"
                    try:
                        subprocess.run(cmd, shell=True, check=True)
                        print(f"Reminder set for {due_date}")
                    except subprocess.CalledProcessError as e:
                        print(f"Failed to create reminder: {e}")
                else:
                    print("System reminders only supported on macOS currently.")
            
            save_checklist(current_checklist_name)
            print(f"Task '{task['task']}' scheduled for {due_date}")
        else:
            print("Invalid task number.")
    except ValueError:
        print("Please enter a valid number.")

def export_to_system_tasks():
    """Export tasks to system task managers or cron jobs"""
    if platform.system() != 'Darwin' and platform.system() != 'Linux':
        print("This feature is currently only supported on macOS and Linux.")
        return
    
    print("\nExport options:")
    print("1. Export to Reminders app (macOS)")
    print("2. Create scheduled job for task (using cron)")
    print("3. Export as Cursor Tasks format")
    
    choice = input("Choose an option: ")
    
    if choice == '1' and platform.system() == 'Darwin':
        _export_to_reminders()
    elif choice == '2':
        _create_cron_job()
    elif choice == '3':
        _export_as_cursor_tasks()
    else:
        print("Invalid option or not supported on this platform.")

def _export_to_reminders():
    """Export tasks to macOS Reminders app"""
    list_name = input("Enter reminder list name (leave blank for default): ") or "Checklist++"
    
    for task in current_checklist:
        if not task.get('completed', False):  # Only export incomplete tasks
            title = task['task']
            priority_str = {"High": "high", "Medium": "normal", "Low": "low"}.get(task.get('priority', 'Medium'), "normal")
            due_date = task.get('due_date', '')
            
            # Create the AppleScript command
            cmd = f'''osascript -e 'tell application "Reminders"
                set mylist to (first list where name is "{list_name}")
                tell mylist
                    make new reminder with properties {{name:"{title}", priority:{priority_str}'''
            
            if due_date:
                cmd += f''', due date:date "{due_date}"'''
            
            cmd += '''}
                end tell
            end tell' '''
            
            try:
                subprocess.run(cmd, shell=True, check=True)
                print(f"Exported task: {title}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to export task '{title}': {e}")
    
    print(f"Tasks exported to Reminders list: {list_name}")

def _create_cron_job():
    """Create a cron job for a task"""
    sorted_checklist = display_checklist()
    
    try:
        task_num = int(input("Enter the number of the task to schedule: ")) - 1
        if 0 <= task_num < len(sorted_checklist):
            task = sorted_checklist[task_num]
            
            # Get schedule information
            print("\nCron Schedule Format: minute hour day month weekday")
            print("Examples: '0 9 * * 1-5' (weekdays at 9 AM), '30 18 * * *' (daily at 6:30 PM)")
            schedule = input("Enter cron schedule: ")
            
            # Create command to run
            cmd = input("Enter command to run (leave blank for notification): ")
            if not cmd:
                title = task['task']
                if platform.system() == 'Darwin':  # macOS
                    cmd = f"osascript -e 'display notification \"{title}\" with title \"Checklist++ Reminder\"'"
                else:  # Linux
                    cmd = f"notify-send 'Checklist++ Reminder' '{title}'"
            
            # Create temporary file with cron entry
            temp_cron = os.path.join("/tmp", "temp_cron")
            cron_entry = f"{schedule} {cmd} # Checklist++ task: {task['task']}\n"
            
            # Get existing crontab
            try:
                subprocess.run(f"crontab -l > {temp_cron}", shell=True, check=True)
            except subprocess.CalledProcessError:
                # No existing crontab
                with open(temp_cron, 'w') as f:
                    f.write("")
            
            # Append new job and update crontab
            with open(temp_cron, 'a') as f:
                f.write(cron_entry)
            
            try:
                subprocess.run(f"crontab {temp_cron}", shell=True, check=True)
                print(f"Cron job created for task: {task['task']}")
            except subprocess.CalledProcessError as e:
                print(f"Failed to create cron job: {e}")
            
            # Cleanup
            os.remove(temp_cron)
        else:
            print("Invalid task number.")
    except ValueError:
        print("Please enter a valid number.")

def _export_as_cursor_tasks():
    """Export tasks in a format compatible with Cursor tasks"""
    # Ask if user wants to use default export directory or specify a custom one
    use_default = input(f"Use default export directory ({EXPORT_DIR})? (y/n): ").lower() == 'y'
    
    if use_default:
        output_dir = EXPORT_DIR
    else:
        output_dir = input("Enter full path to export directory: ").strip()
        if not output_dir:
            output_dir = EXPORT_DIR
        else:
            # Create directory if it doesn't exist
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                print(f"Error creating directory: {e}")
                print(f"Using default export directory: {EXPORT_DIR}")
                output_dir = EXPORT_DIR
    
    filename = os.path.join(output_dir, f"cursor_tasks_{current_checklist_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
    
    with open(filename, 'w') as f:
        f.write("# Tasks\n\n")
        
        for task in current_checklist:
            status = "x" if task.get('completed', False) else " "
            priority = task.get('priority', 'Medium')
            priority_marker = "🔴" if priority == "High" else "🟡" if priority == "Medium" else "🟢"
            
            due_date = task.get('due_date', '')
            due_str = f" due:{due_date}" if due_date else ""
            
            tags = []
            if _status_for_task(task) == "Progress":
                tags.append("#in-progress")
            
            tags_str = " ".join(tags)
            
            f.write(f"- [{status}] {priority_marker} {task['task']}{due_str} {tags_str}\n")
    
    print(f"Tasks exported to: {filename}")
    return filename

def import_from_markdown():
    """Import tasks from a markdown file with GitHub-style task lists"""
    file_path = input("Enter path to markdown file: ").strip()
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return
        
    try:
        with open(file_path, 'r') as f:
            content = f.readlines()
            
        # Parse markdown task items (- [ ] Task or - [x] Task)
        task_count = 0
        section = "Todo"  # Default section
        
        for line in content:
            line = line.strip()
            
            # Check for section headers
            if line.startswith('## '):
                potential_section = line[3:].strip()
                if potential_section in KANBAN_COLUMNS:
                    section = potential_section
                continue
                
            # Check for task items with checkboxes
            if line.startswith('- ['):
                if len(line) < 6:  # Need at least "- [ ] x"
                    continue
                    
                checkbox = line[3:5]  # "[ ]" or "[x]"
                if checkbox not in ['[ ]', '[x]']:
                    continue
                    
                task_text = line[6:].strip()
                if not task_text:
                    continue
                    
                # Extract priority if specified in format like "🔴 Task text"
                priority = "Medium"  # Default
                if task_text.startswith('🔴'):
                    priority = "High"
                    task_text = task_text[1:].strip()
                elif task_text.startswith('🟡'):
                    priority = "Medium"
                    task_text = task_text[1:].strip()
                elif task_text.startswith('🟢'):
                    priority = "Low"
                    task_text = task_text[1:].strip()
                
                # Extract due date if in format like "task text due:2023-06-15"
                due_date = None
                if " due:" in task_text:
                    parts = task_text.split(" due:")
                    task_text = parts[0].strip()
                    try:
                        due_date = parts[1].strip()
                        # Validate date format
                        datetime.strptime(due_date, '%Y-%m-%d')
                    except (ValueError, IndexError):
                        due_date = None
                
                # Create the task
                new_task = {
                    "task": task_text,
                    "completed": checkbox == '[x]',
                    "start_time": 0,
                    "time_spent": 0,
                    "priority": priority,
                    "progress": 0 if section == "Todo" else (100 if section == "Done" else 50),
                    "status": section
                }
                
                if due_date:
                    new_task['due_date'] = due_date
                    
                current_checklist.append(new_task)
                task_count += 1
                
        if task_count > 0:
            save_checklist(current_checklist_name)
            print(f"Imported {task_count} tasks from {file_path}")
        else:
            print("No valid tasks found in the markdown file.")
            
    except Exception as e:
        print(f"Error importing markdown file: {e}")

def _extract_keywords(vectorizer, cluster_center, num_keywords=3):
    """Extract representative keywords for a cluster"""
    if not SMART_GROUPING_AVAILABLE:
        return ["Group"]
        
    # Get feature names from vectorizer
    feature_names = vectorizer.get_feature_names_out()
    
    # Get indices of top values in cluster center
    ordered_indices = np.argsort(cluster_center)[::-1]
    
    # Get top keywords
    top_indices = ordered_indices[:num_keywords]
    keywords = [feature_names[i] for i in top_indices if cluster_center[i] > 0]
    
    # If no meaningful keywords found, use a generic name
    if not keywords:
        return ["Group"]
        
    return keywords

def smart_group_tasks():
    """Group tasks using NLP techniques to identify natural clusters"""
    if not SMART_GROUPING_AVAILABLE:
        print("\nSmart grouping requires scikit-learn. Install it with:")
        print("pip install scikit-learn numpy")
        return
        
    if len(current_checklist) < 3:
        print("Need at least 3 tasks for meaningful grouping")
        return
        
    # Extract task texts, skipping completed tasks unless user wants to include them
    include_completed = input("Include completed tasks in grouping? (y/n): ").lower() == 'y'
    
    tasks_to_group = []
    task_indices = []
    
    for i, task in enumerate(current_checklist):
        if include_completed or not task.get('completed', False):
            tasks_to_group.append(task)
            task_indices.append(i)
    
    if len(tasks_to_group) < 3:
        print("Not enough active tasks for meaningful grouping. Need at least 3.")
        return
        
    task_texts = [task['task'] for task in tasks_to_group]
    
    try:
        # Vectorize tasks
        vectorizer = TfidfVectorizer(stop_words='english', min_df=1)
        X = vectorizer.fit_transform(task_texts)
        
        # Determine optimal number of clusters (between 2 and 5)
        num_clusters = min(5, max(2, len(tasks_to_group) // 3))
        
        # Cluster
        kmeans = KMeans(n_clusters=num_clusters, random_state=42, n_init=10)
        clusters = kmeans.fit_predict(X)
        
        # Extract keywords for each cluster
        groups = {}
        for i in range(num_clusters):
            # Get indices of tasks in this cluster
            cluster_task_indices = [idx for idx, cluster_id in enumerate(clusters) if cluster_id == i]
            
            # Map back to original indices
            original_indices = [task_indices[idx] for idx in cluster_task_indices]
            
            # Get keywords
            keywords = _extract_keywords(vectorizer, kmeans.cluster_centers_[i], 3)
            group_name = f"Group {i+1}: {', '.join(keywords).title()}"
            
            groups[group_name] = original_indices
        
        # Display groups
        print("\nSmart Task Groups:")
        for group_name, indices in groups.items():
            print(f"\n{COLOR_GREEN}{group_name}{COLOR_RESET}")
            for idx in indices:
                status = f"{COLOR_BRIGHT_GREEN}✓{COLOR_RESET}" if current_checklist[idx]["completed"] else f"{COLOR_RED}✗{COLOR_RESET}"
                print(f"  {idx+1}. [{status}] {current_checklist[idx]['task']}")
                
        # Option to save groups as tags
        save_as_tags = input("\nSave these groups as tags on tasks? (y/n): ").lower() == 'y'
        if save_as_tags:
            for group_name, indices in groups.items():
                tag = group_name.split(":")[0].strip()
                for idx in indices:
                    if 'tags' not in current_checklist[idx]:
                        current_checklist[idx]['tags'] = []
                    current_checklist[idx]['tags'].append(tag)
            save_checklist(current_checklist_name)
            print("Groups saved as tags on tasks.")
            
    except Exception as e:
        print(f"Error during task grouping: {e}")

if __name__ == "__main__":
    main()


