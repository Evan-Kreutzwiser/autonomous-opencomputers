import asyncio
import json
from typing import Literal
import logger
from recipes import convert_item_name
import recipes
import webserver


class Robot:
    """
    Represents a robot in the minecraft world and tracks its long term state.

    Attributes:
    id: int
        The robot's unique identifier, stored on the robot itself to aid in restoring state.
    inventory: list
        A list of item name and quantity pairs, representing the robot's inventory.
        The list is 1-indexed, with an extra unusable None in position 0.
    position: tuple
        The in-world position of the robot. It has no native coordinate access, so this is tracked manually.
    direction: str
        The cardinal direction the robot is facing. Not natively readable, so this is tracked manually.
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

    async def run(self):
        """Execute the event queue until completion, manually stopped, or an action fails."""
        self.ready_event.clear()
        try:
            while not self.action_queue.empty():
                # Actions queued are in the form of a list of strings,
                # where the first entry is the pddl function name and any further entries are arguments.
                action_name, *args = self.action_queue.get_nowait()
                logger.info(f"Executing action {action_name} {args or ''}", self.id)
                self.current_action = _action_from_name(action_name, args, robot=self)
                success = await self.current_action.run()

                self.current_action = None
                if not success:
                    logger.error(f"Action {action_name} failed", self.id)
                    break
        except Exception as e:
            logger.exception(f"Error in robot action queue", e, self.id)
        self.ready_event.set()

    def add_action(self, action):
        self.action_queue.put_nowait(action)

    def stop_actions(self):
        """
        Cause the robot to stop as soon as possible. Current action will either finish
        or exit at its earliest convience, and all further actions are cancelled.
        """
        self.action_queue = asyncio.Queue()
        if self.current_action:
            self.current_action.cancel()

    async def move(self, side: Literal["front", "left", "right", "back", "up", "down"]) -> bool:
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

    async def turn_to_face(self, direction: str) -> bool:
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

    async def turn_left(self) -> bool:
        response = await webserver.send_command(self.id, f"turn left")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Turn Left: {data['error']}", self.id)
            return False

        self.direction = left_of(self.direction)
        return True

    async def turn_right(self) -> bool:
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

        # Inventory is 1-indexed in Lua
        inv = [None] * (data["size"] + 1)

        for slot, item in data["inventory"].items():
            slot = int(slot)
            # Many modded items in-game share the same ID due to a hard cap 
            # on the number of valid IDs in old Minecraft versions.
            # These items are differentiated by their data value.
            item_name = convert_item_name(item["name"], item["dataValue"])
            inv[slot] = (item_name, item["count"])

        self.inventory = inv
        return True

    def count_items(self) -> dict[str, int]:
        """
        Robot inventory tracks individual slot contents, 
        the planner just needs to know total quantities.
        """
        counts = {}
        for item, quantity in [slot for slot in self.inventory if slot is not None]:
            if item in counts:
                counts[item] += quantity
            else:
                counts[item] = quantity
        return counts

    def first_empty_slot(self, exclude_crafting_grid=False) -> int:
        """
        Return the index of the first empty slot in the robot's inventory.
        If exclude_crafting_grid is True, the 3x3 area in the top left of the inventory is ignored.
        """
        for i, slot in enumerate(self.inventory[1:]):
            # Inventory renders as 4 columns, and only the first 3 cells in each row are part of the crafting grid.
            if slot is None and not (exclude_crafting_grid and i < 12 and i%4 < 3):
                return i+1
        return -1

    def find_item(self, item: str, exclude_crafting_grid=False) -> int:
        """
        Return the index of the first slot containing the specified item.
        If exclude_crafting_grid is True, the 3x3 area in the top left of the inventory is ignored.
        """
        for i, slot in enumerate(self.inventory[1:]):
            if slot and slot[0] == item and not (exclude_crafting_grid and i < 12 and i%4 < 3):
                return i+1
        return -1

    async def consolidate_stacks(self) -> bool:
        """
        Combine stacks of the same item in the robot's inventory.
        The planner works under the assumption that inventory space is used efficiently
        by having no more than one stack of an item type that isn't full.
        Returns whether the operation was successful.
        """
        partial_stacks = {number: contents for number, contents in enumerate(self.inventory) if contents and contents[1] < recipes.stack_size.get(contents[0], 64)}

        while len(partial_stacks) > 0:
            slot, stack = partial_stacks.popitem()

            destination_slot = None
            for other_slot, other_stack in partial_stacks.items():
                if other_slot != slot and stack[0] == other_stack[0]:
                    destination_slot = other_slot
                    break
            
            if destination_slot is None:
                continue

            success = await self.transfer_items(slot, destination_slot)
            partial_stacks[destination_slot] = self.inventory[destination_slot]
            if not success:
                # Robot networking or client code failed, give up and the caller should return to the planner
                logger.error(f"Failed to consolidate stacks in slots {slot} and {destination_slot}", self.id)
                return False
            
            # If anything was left in the source stack, it means the destination was filled by the transfer.
            # Ignore the destination slot from now on, and find try to find somewhere else for the remainder.
            if self.inventory[slot] is not None:
                partial_stacks.pop(destination_slot)
                partial_stacks[slot] = self.inventory[slot]            

        return True
    
    async def transfer_items(self, source_slot: int, dest_slot: int, quantity: int = None) -> bool:
        """
        Transfer items from one inventory slot to another.
        Automatically updates tracked inventory state if successful.

        - If quantity is not specified, transfer all items in the stack if possible.
        - When the source slot is empty, nothing happens. 
        - When the destination is empty the operation succeeds
        - If both stacks are the same item type, attempt to move as many as possible
        - If the stacks are different and no quantity was given, swap them
        - If a quantity was given but both stacks are present and different, nothing happens
        """
        response = await webserver.send_command(self.id, f"transfer {source_slot} {dest_slot} {quantity or ''}")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Transfer: {data['error']}", self.id)
            return False

        source_stack = self.inventory[source_slot]
        dest_stack = self.inventory[dest_slot]
        # TODO: Thoroughly verify correctness
        # Simulate the action taken by the command on the robot to maintain consistent
        # inventory state without making the expensive call to update_inventory.
        if dest_stack is None:
            if quantity is None or quantity > source_stack[1]:
                self.inventory[dest_slot] = source_stack
                self.inventory[source_slot] = None
            else:
                self.inventory[source_slot] = (source_stack[0], source_stack[1] - quantity)
                self.inventory[dest_slot] = (source_stack[0], quantity)

        elif source_stack is not None:
            if quantity is None and source_stack[0] != dest_stack[0]:
                self.inventory[source_slot], self.inventory[dest_slot] = dest_stack, source_stack

            if source_stack[0] == dest_stack[0]:
                remaining_space = recipes.stack_size.get(dest_stack[0], 64) - dest_stack[1]
                amount_to_move = min(quantity or source_stack[1], source_stack[1])
                if remaining_space >= amount_to_move:
                    self.inventory[dest_slot] = (dest_stack[0], dest_stack[1] + amount_to_move)
                    self.inventory[source_slot] = None
                else:
                    self.inventory[dest_slot] = (dest_stack[0], dest_stack[1] + remaining_space)
                    self.inventory[source_slot] = (source_stack[0], source_stack[1] - remaining_space)
        # elif source_stack is None: no-op
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

    def cancel(self):
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


class WaitAction(Action):
    """For the cases when the planner did not assign a robot a task."""
    
    async def run(self) -> bool:
        """Continue until manually cancelled by the planning loop or user."""
        await self.cancel_event.wait()
        return True


class CraftAction(Action):
    """Craft an item using the robot's crafting upgrade."""

    def __init__(self, robot: Robot, item: str):
        super().__init__(robot)
        self.item = item

    async def run(self) -> bool:
        # TODO: Syncing inventories is slow, so we should only do it when necessary
        await self.robot.update_inventory()

        # Check if the robot has the required materials
        required_items = recipes.recipe_ingredients[self.item]
        items = self.robot.count_items()
        for ingredient, quantity in required_items.items():
            if ingredient not in items or items[ingredient] < quantity:
                logger.error(f"Missing {ingredient} required to craft {self.item}", self.robot.id)
                return False

        # Empty the crafting grid
        for i in range(1, 13):
            if (i-1) % 4 < 3 and (self.robot.inventory[i] is not None):
                dest_index = self.robot.first_empty_slot(exclude_crafting_grid=True)
                success = await self.robot.transfer_items(i, dest_index)
                if not success:
                    logger.error(f"Failed to clear crafting grid (moving slot {i} to {dest_index})", self.robot.id)
                    return False
        
        # Place the ingredients in the correct slots for crafting
        recipe_data = recipes.recipes[self.item]
        for row in range(3):
            for col in range(3):
                ingredient = recipe_data["recipe"][row][col]
                if ingredient:
                    source_index = self.robot.find_item(ingredient, exclude_crafting_grid=True)
                    dest_index = row*4 + (col+1) # Crafting grid uses 3 of the 4 columns in the inventory grid
                    success = await self.robot.transfer_items(source_index, dest_index, 1)
                    if not success:
                        logger.error(f"Failed to place {ingredient} in crafting grid", self.robot.id)
                        return False

        # Craft the item
        dest_slot = self.robot.find_item(self.item, exclude_crafting_grid=True)
        dest_slot = 1 if dest_slot == -1 else dest_slot
        await webserver.send_command(self.robot.id, f"select {dest_slot}")
        response = await webserver.send_command(self.robot.id, "craft")
        data = json.loads(response)
        if not data["success"]:
            logger.error(f"Failed to craft {self.item}: {data['error']}", self.robot.id)
            return False

        # TODO: Probably don't need this since anywhere that accesses it already refreshes first
        await self.robot.update_inventory()
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
        return SmeltAction(robot, item, True)
    elif action_name.startswith("smelt_partial_"):
        item = action_name.split("_", 2)[-1]
        return SmeltAction(robot, item, False)
    elif action_name.startswith("craft_"):
        item = action_name.split("_", 1)[-1]
        return CraftAction(robot, item)
    elif action_name == "wait":
        return WaitAction(robot)
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
