import json
from typing import Literal
from recipes import convert_item_name
import webserver


class robot:
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

    def turn_to_face(self, direction: str) -> bool:
        """Turn to face one of the caridinal directions."""
        if direction not in ["north", "east", "south", "west"]:
            print(f"[{self.id}] Invalid direction: {direction}")
            return False

        if direction == self.direction:
            return True
        elif direction == left_of(self.direction):
            return self.turn_left()
        elif direction == right_of(self.direction):
            return self.turn_right()
        else:
            return self.turn_left() and self.turn_left()

    def turn_left(self) -> bool:
        response = webserver.send_command(self.id, f"turn left")
        data = json.loads(response)
        if not data["success"]:
            print(f"[{self.id}] Turn Left: Error: {data['error']}")
            return False

        self.direction = left_of(self.direction)
        return True

    def turn_right(self) -> bool:
        response = webserver.send_command(self.id, f"turn right")
        data = json.loads(response)
        if not data["success"]:
            print(f"[{self.id}] Turn Right: Error: {data['error']}")
            return False

        self.direction = right_of(self.direction)
        return True

    def update_inventory(self) -> bool:
        """
        Update the robot's inventory to reflect the in-world state.
        This is polled rather than automatic, scanning the entire inventory
        takes a relatively long time compared to other operations.
        """
        response = webserver.send_command(self.id, "inventory")
        data = json.loads(response)
        if not data["success"]:
            print(f"[{self.id}] Update Inventory: Error: {data['error']}")
            return False

        inv = [None] * data["size"]

        for slot, item in data["inventory"].items():
            slot = int(slot)
            # Many modded items in-game share the same ID due to a hard cap 
            # on the number of valid IDs in old Minecraft versions.
            # These items are differentiated by their data value.
            item_name = convert_item_name(item["name"], item["dataValue"])
            inv[slot] = (item_name, item["count"])

        return True

    def get_inventory(self):
        return self.inventory

    def get_position(self) -> tuple[int, int, int]:
        return self.position

    def get_direction(self) -> str:
        return self.direction

    def get_id(self) -> int:
        return self.id

    def __str__(self) -> str:
        return f"Robot {self.id} at {self.position} facing {self.direction}"


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
