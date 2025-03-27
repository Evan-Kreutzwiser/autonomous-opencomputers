import asyncio
import json
import re

from rich import highlighter
from textual import log
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Button, Header, Input, RichLog

import logger
import planner
import webserver
from robot import Robot

# Allow the planner loop to be paused so that commands can manually be run
pause_event = asyncio.Event()
pause_completed_event = asyncio.Event()

class LogHighlighter(highlighter.Highlighter):
    def highlight(self, text):
        plain_text = text.plain
        for match in re.finditer(r'\[.*?\]', plain_text):
            text.stylize("dim", match.start(), match.start() + 1)
            text.stylize("dim", match.end() - 1, match.end())
        
        if "Warning:" in plain_text:
            start = plain_text.index("Warning:") + len("Warning:")
            text.stylize("yellow", start)
        
        if "Error:" in plain_text:
            start = plain_text.index("Error:") + len("Error:")
            text.stylize("red", start)

class CommandInput(Input):
    def __init__(self, disabled=False) -> None:
        super().__init__(disabled=disabled)
        self.placeholder = "Pause planner to send manual commands"
        self.styles.width = "1fr"

    async def action_submit(self):
        super().action_submit()

        # Dev command to replace client.lua on all connected robots
        if self.value == "update":
            logger.info("Updating all robots", "User")
            failed = False
            for id in webserver.get_robots():
                response = await webserver.send_command(id, "update")
                data = json.loads(response)
                if not data['success']:
                    logger.error(data['error'], id)
                    failed = True
            if failed:
                logger.error("Not all robots updated successfully", "User")
            return
        
        split = self.value.split(" ", 1)
        if len(split) != 2 or not split[0].isdecimal():
            logger.error("Invalid command format. Must be in the format \"<robot_id> <command>\"", "User")
            return

        robot, command = int(split[0]), split[1]

        logger.info(f"Sending \"{command}\" to robot {robot}", "User")
        response = await webserver.send_command(robot, command)
        data = json.loads(response)
        if data['success']:
            logger.info(data, robot)
        else:
            logger.error(data['error'], robot)


class InputContainer(HorizontalGroup):
    BINDINGS = [
        ("p", "pause", "Pause")
    ]

    def __init__(self) -> None:
        super().__init__()
        self.styles.height = 3
        self.is_paused = reactive(False)

    def compose(self) -> ComposeResult:
        yield CommandInput(disabled=True)
        button = Button("Pause", action="pause")
        button.styles.width = 16
        button.variant = "primary"
        yield button

    def action_pause(self):
        if pause_event.is_set() and pause_completed_event.is_set():
            pause_event.clear()
            logger.info("Resuming planner", "User")
        elif not pause_event.is_set():
            pause_event.set()
            logger.info("Pausing planner - Please wait for currently running actions to complete", "User")

        self.update_pause_state()

    def update_pause_state(self):
        if pause_event.is_set() or pause_completed_event.is_set():
            self.query_one("Input").disabled = False
            self.query_one("Input").placeholder = "Send a command: <robot_id> <command>"
            self.query_one("Button").label = "Unpause"
            self.query_one("Button").variant = "primary"
            self.query_one("Button").disabled = False
        elif not pause_event.is_set():
            self.query_one("Input").disabled = True
            self.query_one("Input").placeholder = "Pause planner to send manual commands"
            self.query_one("Button").label = "Pause"
            self.query_one("Button").variant = "primary"
            self.query_one("Button").disabled = False

        if pause_event.is_set() != pause_completed_event.is_set():
            self.query_one("Button").variant = "default"
            self.query_one("Button").disabled = True

class MainScreen(Screen):
    AUTO_FOCUS = "Input"

    def __init__(self) -> None:
        super().__init__()
        self._log_widget = RichLog(highlight=True)
        self._log_widget.highlighter = LogHighlighter()
        logger.set_log_widget(self._log_widget)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield self._log_widget
        yield InputContainer()

    def on_mount(self) -> None:
        self.title = "Autonomous OpenComputers"
        self.sub_title = "Robot Control"


class TerminalUI(App):
    def __init__(self):
        super().__init__()
        self.title = "Autonomous OpenComputers"

    def on_ready(self):
        self.push_screen(MainScreen())

    def update_pause_state(self):
        """Alert the UI to changes in the pause event states for the planning loop"""
        self.query_one("InputContainer").update_pause_state()


def save_and_exit():
    # TODO: Save robot positions to disk before exiting
    exit(0)

async def plan_actions(agents: dict[int, Robot]) -> bool:
    """
    Plan the next set of actions for all robots, and add them to the agent's action queues.

    :return: Whether the planner found a valid plan
    """
    # Ensure inventory contents are up to date and that items are optimally stacked.
    # Additionally, discard any items not recognized by the planner.
    await asyncio.wait([asyncio.create_task(agent.update_inventory()) for agent in agents.values()])
    await asyncio.wait([asyncio.create_task(agent.drop_unrecognized_items()) for agent in agents.values()])
    results = await asyncio.gather(*[agent.consolidate_stacks() for agent in agents.values()])
    if not all(results):
        # This shouldn't happen unless one of the robots disconnects partway through or runs into an error.
        # Additionally, any failures updating the inventory should also cause an error here
        return False

    actions = await planner.replan(agents)
    if len(actions) == 0:
        return False
    
    for robot_id, action in actions:
        agents[robot_id].add_action(action)
    return True

async def main():
    """
    Spawn the UI and planner event loop, and allow the event 
    loop to exit gracefully when the UI is closed.
    """

    # Create the domain which defines all of the actions the planner can take
    # Unlike the problem file, this doesn't change based on the number of connected robots
    problem = planner.create_domain()
    open("domain.pddl", "w").write(str(problem))

    app = TerminalUI()
    ui_task = asyncio.create_task(app.run_async())
    
    await webserver.start_server()

    robots = {}

    exit_event = asyncio.Event()
    async def event_loop():
        while not exit_event.is_set():
            try:
                # Check for connections / disconnections
                if webserver.connections_updated_event.is_set():
                    while webserver.removed_connections:
                        removed_id = webserver.removed_connections.pop()
                        robots.pop(removed_id)
                    while webserver.new_connections:
                        new_id = webserver.new_connections.pop()
                        robots[new_id] = Robot(new_id)
                    webserver.connections_updated_event.clear()

                if pause_event.is_set() and not pause_completed_event.is_set():
                    # Manual command mode
                    # Indicates to the UI that the planner is compltely paused now, and commands can be entered
                    logger.info("Planner is now paused", "Server")
                    pause_completed_event.set()
                    app.update_pause_state()

                elif not pause_event.is_set() and pause_completed_event.is_set():
                    # Transition from manual command mode to autonomous planner mode

                    # Wait for robots to finish commands initiated during manual mode
                    for agent in robots.values():
                        agent.stop_actions()

                    if len(robots.keys()) > 0: # wait fails if no robots are connected
                        await asyncio.wait([agent.ready_event.wait() for agent in robots.values()])
                    
                    pause_completed_event.clear()
                    app.update_pause_state()
                    logger.info("Planner resumed", "Server")

                elif not pause_event.is_set() and not pause_completed_event.is_set():
                    # Autonomous planner mode

                    if len(robots.keys()) == 0:
                        # Planning and waiting fails if no robots are connected, so just wait for a connection
                        await asyncio.wait([pause_event.wait(), webserver.connections_updated_event.wait(), exit_event.wait()], return_when=asyncio.FIRST_COMPLETED)
                        continue
                    logger.info(f"Replanning with {len(robots.keys())} connected robots", "Server")
                    
                    # Populate the action queues for each robot
                    found_plan = await plan_actions(robots)
                    if not found_plan:
                        # If planning failed there is no way it will success again without new robots or manual intervention.
                        # Only relavent during development and testing
                        await asyncio.wait([pause_event.wait(), webserver.connections_updated_event.wait(), exit_event.wait()], return_when=asyncio.FIRST_COMPLETED)
                        continue 

                    agent_tasks = [asyncio.create_task(agent.run()) for agent in robots.values()]
                    # If agents are added or removed, stop right away and replan
                    agent_tasks.append(webserver.connections_updated_event.wait())
                    agent_tasks.append(pause_event.wait())
                    agent_tasks.append(exit_event.wait())
                    # Let the agents run until one of them completes or requires a replan
                    await asyncio.wait(agent_tasks, return_when=asyncio.FIRST_COMPLETED)

                    for agent in robots.values():
                        agent.stop_actions()

                    await asyncio.gather(*[agent.ready_event.wait() for agent in robots.values()])

                else:
                    await asyncio.sleep(1)
            
            except Exception as exception:
                logger.exception(f"Error in main loop", exception, "Server")
                pause_event.set()
                app.update_pause_state()

    main_task = asyncio.create_task(event_loop())

    await ui_task
    # Try to prevent a bug where logging after the UI is closed causes an error
    logger.set_log_widget(None)

    logger.info("Exiting - Please wait for current tasks for finish", "Server")
    exit_event.set()
    await main_task


if __name__ == "__main__":
    asyncio.run(main())
