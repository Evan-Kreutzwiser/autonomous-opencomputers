from textual.widgets import RichLog
from rich.traceback import Traceback
import traceback

_log_widget: RichLog = None

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
        _log_widget.write(message)

def error(message: str, component: str):
    global _log_widget
    
    message = f"[{component}] Error: {message}"
    _log_file.write(message + "\n")
    _log_file.flush()
    print(message)
    
    if _log_widget is not None:
        _log_widget.write(message)

def exception(message: str, exception: Exception, component: str):
    global _log_widget
    
    trace = "".join(traceback.format_exception(exception))
    message = f"[{component}] {exception.__class__.__name__}: {message}"
    _log_file.write(message + "\n" + trace)
    _log_file.flush()
    print(message + "\n" + trace)
    
    if _log_widget is not None:
        _log_widget.write(message)
        _log_widget.write(Traceback.from_exception(exc_type=exception.__class__, exc_value=exception, traceback=exception.__traceback__, show_locals=True))


def set_log_widget(widget: RichLog):
    global _log_widget
    _log_widget = widget