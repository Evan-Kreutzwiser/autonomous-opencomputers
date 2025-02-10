import asyncio
import json
from typing import Literal
import logger
from recipes import convert_item_name
import webserver


class Robot:
    """
    Abstraction around robot commands.

    Represents a robot in the minecraft world and tracks its long term state.
    """

    id: int
    inventory: list[tuple[str, int] | None]
    position: tuple[int, int, int]
    direction: Literal["north", "east", "south", "west"]

    def __init__(self, id, position=None, direction=None):
        self.id = id
        self.inventory = []
        self.position = position or (0, 0, 0)
        self.direction = direction or "north"
        
        self.action_queue = asyncio.Queue()
        self.current_action = None
        # Indicates to the planner that the robot has completed its actions
        self.ready_event = asyncio.Event()
        self.ready_event.set()

    async def run(self, stop_event: asyncio.Event):
        """Execute the event queue until completion, manually stopped, or an action fails."""
        self.ready_event.clear()
        while not stop_event.is_set() and not self.action_queue.empty():
            # Actions queued are in the form of a list of strings,
            # where the first entry is the pddl function name and any further entries are arguments.
            action_name, *args = self.action_queue.get()
            self.current_action = _action_from_name(action_name, *args, robot=self)
            success = await self.current_action.run(self)
            self.current_action = None
            if not success:
                break
        self.ready_event.set()

    def add_action(self, action):
        self.action_queue.put_nowait(action)

    def clear_queue(self):
        self.action_queue = asyncio.Queue()

    async def _move(self, side: Literal["front", "left", "right", "back", "up", "down"]) -> bool:
        if side not in ["front", "left", "right", "back", "up", "down"]:
            logger.error(f"Invalid side for movement: {side}", self.id)
            return False
        
        response = await webserver.send_command(self.id, f"move {side}")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Move: {data['error']}", self.id)
            return False
        
        # Update recorded position
        if side == "up":
            self.position[1] += 1
        elif side == "down":
            self.position[1] -= 1
        else:
            moved_direction = ""
            if side == "front":
                moved_direction = self.direction
            elif side == "back":
                moved_direction = left_of(left_of(self.direction))
            elif side == "left":
                moved_direction = left_of(self.direction)
            elif side == "right":
                moved_direction = right_of(self.direction)
            
            if moved_direction == "north":
                self.position[2] -= 1
            elif moved_direction == "south":
                self.position[2] += 1
            elif moved_direction == "west":
                self.position[0] -= 1
            elif moved_direction == "east":
                self.position[0] += 1

        return True

    async def _turn_to_face(self, direction: str) -> bool:
        """Turn to face one of the caridinal directions."""
        if direction not in ["north", "east", "south", "west"]:
            logger.error(f"Invalid direction: {direction}", self.id)
            return False

        if direction == self.direction:
            return True
        elif direction == left_of(self.direction):
            return await self.turn_left()
        elif direction == right_of(self.direction):
            return await self.turn_right()
        else:
            return await self.turn_left() and await self.turn_left()

    async def _turn_left(self) -> bool:
        response = await webserver.send_command(self.id, f"turn left")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Turn Left: {data['error']}", self.id)
            return False

        self.direction = left_of(self.direction)
        return True

    async def _turn_right(self) -> bool:
        response = await webserver.send_command(self.id, f"turn right")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Turn Right: {data['error']}", self.id)
            return False

        self.direction = right_of(self.direction)
        return True

    async def update_inventory(self) -> bool:
        """
        Update the robot's inventory to reflect the in-world state.
        This is polled rather than automatic, scanning the entire inventory
        takes a relatively long time compared to other operations.
        """
        response = await webserver.send_command(self.id, "inventory")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Update Inventory: {data['error']}", self.id)
            return False

        inv = [None] * data["size"]

        for slot, item in data["inventory"].items():
            # Lua is 1-indexed, Python is 0-indexed
            slot = int(slot) - 1
            # Many modded items in-game share the same ID due to a hard cap 
            # on the number of valid IDs in old Minecraft versions.
            # These items are differentiated by their data value.
            item_name = convert_item_name(item["name"], item["dataValue"])
            inv[slot] = (item_name, item["count"])

        return True

    def __str__(self) -> str:
        return f"Robot {self.id} at {self.position} facing {self.direction}"


class Action:
    """
    Base class for robot actions. This action does nothing, 
    and subclasses should override run to add functionality.
    """
    cancel_event: asyncio.Event
    robot: Robot

    def __init__(self, robot):
        self.cancel_event = asyncio.Event()
        self.robot = robot

    async def run(self) -> bool:
        """
        Returns whether the action was successful.
        If not, the planner should sync inventories and replan.
        """
        return True

    async def cancel(self):
        self.cancel_event.set()


class PingAction(Action):
    """Ping the robot to check if it is still connected."""
    
    async def run(self) -> bool:
        response = await webserver.send_command(self.robot.id, "ping")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Ping: {data['error']}", self.robot.id)
            return False

        return True


class SmeltAction(Action):
    """Cook either 8 items or however many of the item are in the robot's inventory."""
    def __init__(self, robot: Robot, item: str, smelt_8: bool):
        super().__init__(robot)
        self.item = item
        self.smelt_8 = smelt_8

    async def run(self) -> bool:
        # Check if the item is in the robot's inventory
        # TODO: Make a generic function to search and combine item stacks
        slot_number = None
        for index, slot in enumerate(self.robot.inventory):
            if slot and slot[0] == self.item and slot[1] >= self.quantity:
                slot_number = index
        if not slot_number:
            logger.info(f"Smelt: Not enough of {self.item} found in inventory", self.robot.id)
            return False

        # TODO: Implmenent action

        return True


def _action_from_name(action_name: str, args: list[str], robot: Robot) -> Action:
    if action_name.startswith("smelt_8_"):
        item = action_name.split("_", 2)[-1]
        return SmeltAction(robot, *args, item, True)
    elif action_name.startswith("smelt_partial_"):
        item = action_name.split("_", 2)[-1]
        return SmeltAction(robot, *args, item, False)
    else:
        # No-Op
        return Action(robot)


def left_of(direction: str) -> Literal["north", "east", "south", "west"]:
    """Return the cardinal direction 90 degrees counterclockwise."""
    return {
        "north": "west",
        "west": "south",
        "south": "east",
        "east": "north",
    }[direction]

def right_of(direction: str) -> Literal["north", "east", "south", "west"]:
    """Return the cardinal direction 90 degrees clockwise."""
    return {
        "north": "east",
        "east": "south",
        "south": "west",
        "west": "north",
    }[direction]
