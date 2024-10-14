import os
import json
import time
import textwrap


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

APP_INFO = ''' A command Line ready checklist tool for productivity when working in the terminal

Written with Python and JSON
'''

# Directory to store all checklists
CHECKLIST_DIR = "checklists"
os.makedirs(CHECKLIST_DIR, exist_ok=True)  # Create directory if it doesn't exist

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
MENU_VISIBLE = True  
ONE_LINE_DISPLAY = False
# Flag to control menu visibility

# Variable to store the last action for undo functionality
last_action = None

# Current checklist and its name
current_checklist = []
current_checklist_name = "default"

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

# Display the menu options
def display_menu():
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
    print("19. Exit")

# Main menu
def main():
    print(ASCII_ART1)
    load_checklist(current_checklist_name)  # Load the default checklist at startup
    while True:
        if MENU_VISIBLE:
            display_menu()
        choice = input("Choose an option: ")

        if choice == '1':
            display_checklist()
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
        elif choice == '16':
            toggle_menu_visibility()
        elif choice == '17':
            toggle_one_line_display()
        elif choice == '18':
            load_external_checklist()
        elif choice == '19':
            print("Exiting Checklist Tool.")
            save_checklist(current_checklist_name)
            break
        else:
            print("Invalid option. Please choose again.")

if __name__ == "__main__":
    main()


