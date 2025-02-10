import asyncio
from textual.app import App, ComposeResult
from textual.containers import HorizontalGroup
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Header, Footer, Log, Button, Input
from textual import log 
import logger
import json
import planner
from robot import Robot
import webserver

# Allow the planner loop to be paused so that commands can manually be run
pause_event = asyncio.Event()
pause_completed_event = asyncio.Event()

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
                print("Not all robots updated successfully")
            return
        
        split = self.value.split(" ", 1)
        if len(split) != 2 or not split[0].isdecimal():
            logger.error("Invalid command format. Must be in the format \"<robot_id> <command>\"", "User")
            return

        robot, command = int(split[0]), split[1]

        logger.info(f"Sending \"{command}\" to robot {robot}", "User")
        response = await webserver.send_command(robot, command)
        data = json.loads(response)
        if not data['success']:
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
        yield button

    def action_pause(self):
        if pause_event.is_set() and pause_completed_event.is_set():
            pause_event.clear()
            self.query_one("Input").disabled = True
            self.query_one("Input").placeholder = "Pause planner to send manual commands"
            self.query_one("Button").label = "Pause"
            logger.info("Resuming planner", "User")
        elif not pause_event.is_set():
            pause_event.set()
            self.query_one("Input").disabled = False
            self.query_one("Input").placeholder = "Send a command: <robot_id> <command>"

            self.query_one("Button").label = "Unpause"
            logger.info("Pausing planner - Please wait for currently running actions to complete", "User")


class MainScreen(Screen):
    AUTO_FOCUS = "Input"

    def __init__(self) -> None:
        super().__init__()
        self._log_widget = Log()
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


def save_and_exit():
    # TODO: Save robot positions to disk before exiting
    exit(0)

async def plan_actions(agents: dict[Robot]):
    """
    Plan the next set of actions for all robots, and add them to the agent's action queues.
    """
    # Ensure inventory contents are up to date
    await asyncio.wait([asyncio.create_task(agent.update_inventory()) for agent in agents.values()])
    
    actions = planner.replan(agents)
    if len(actions) == 0:
        return
    
    for robot_id, action in actions:
        agents[robot_id].add_action(action)

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

            # Check for connections / disconnections
            if webserver.connections_updated_event.is_set():
                while webserver.removed_connections:
                    removed_id = webserver.removed_connections.pop()
                    robots.pop(removed_id)
                while webserver.new_connections:
                    new_id = webserver.new_connections.pop()
                    robots[new_id] = Robot(new_id)

            if pause_event.is_set() and not pause_completed_event.is_set():
                # Manual command mode
                # Indicates to the UI that the planner is compltely paused now, and commands can be entered
                logger.info("Planner is now paused", "Server")
                pause_completed_event.set()

            elif not pause_event.is_set() and pause_completed_event.is_set():
                # Transition from manual command mode to autonomous planner mode

                # Wait for robots to finish commands initiated during manual mode
                if len(robots.keys()) > 0: # wait fails if no robots are connected
                    for agent in robots.values():
                        agent.clear_queue()
                        if agent.current_action:
                            agent.current_action.cancel()

                    await asyncio.wait([agent.ready_event.wait() for agent in robots.values()])
                pause_completed_event.clear()
                logger.info("Planner resumed", "Server")

            elif not pause_event.is_set() and not pause_completed_event.is_set():
                # Autonomous planner mode
                if len(robots.keys()) == 0:
                    # Planning and waiting fails if no robots are connected, so just wait for a connection
                    await asyncio.sleep(0.5)
                    continue
                logger.info(f"Replanning with {len(robots.keys())} connected robots", "Server")
                
                await plan_actions(robots)

                stop_robots_event = asyncio.Event()
                agent_tasks = [asyncio.create_task(agent.run(stop_robots_event)) for agent in robots.values()]
                # If agents are added or removed, stop right away and replan
                agent_tasks.append(webserver.connections_updated_event.wait())
                # Let the agents run until one of them completes or requires a replan
                asyncio.wait(agent_tasks, return_when=asyncio.FIRST_COMPLETED)

                stop_robots_event.set()
                for agent in robots.values():
                    agent.clear_queue()

            else:
                await asyncio.sleep(0.1)

    main_task = asyncio.create_task(event_loop())

    await ui_task
    # Try to prevent a bug where logging after the UI is closed causes an error
    logger.set_log_widget(None)

    exit_event.set()
    await main_task


if __name__ == "__main__":
    asyncio.run(main())
