from textual.widgets import Log

_log_widget: Log = None


def info(message: str, component: str = None):
    global _log_widget
    
    message = f"[{component}] {message}" if component else message
    print(message)

    if _log_widget is not None:
        _log_widget.write_line(message)

def error(message: str, component: str = None):
    global _log_widget
    
    message = f"[{component}] Error: {message}" if component else "Error: " + message
    print(message)
    
    if _log_widget is not None:
        _log_widget.write_line(message)



def set_log_widget(widget: Log):
    global _log_widget
    _log_widget = widget