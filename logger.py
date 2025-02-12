from textual.widgets import Log
import traceback

_log_widget: Log = None

try:
    _log_file = open("autonomous-opencomputers-log.txt", "w")
except PermissionError:
    print("Could not open log file (autonomous-opencomputers-log.txt): Permission Denied")
    exit(-1)

def info(message: str, component: str):
    global _log_widget
    
    message = f"[{component}] {message}"
    _log_file.write(message + "\n")
    _log_file.flush()
    print(message)

    if _log_widget is not None:
        _log_widget.write_line(message)

def error(message: str, component: str):
    global _log_widget
    
    message = f"[{component}] Error: {message}"
    _log_file.write(message + "\n")
    _log_file.flush()
    print(message)
    
    if _log_widget is not None:
        _log_widget.write_line(message)

def exception(message: str, exception: Exception, component: str):
    global _log_widget
    
    trace = "".join(traceback.format_exception(exception))
    message = f"[{component}] {exception.__class__.__name__}: {message}\n{trace}"
    _log_file.write(message + "\n")
    _log_file.flush()
    print(message)
    
    if _log_widget is not None:
        _log_widget.write_line(message)


def set_log_widget(widget: Log):
    global _log_widget
    _log_widget = widget