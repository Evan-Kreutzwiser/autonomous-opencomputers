"""

"""

import logger


items_list = [
    # Vanilla items
    "cobblestone",
    "stone",
    "coal",
    "iron_ore",
    "gold_ore",
    "iron",
    "gold",
    "diamond",
    "redstone",
    "iron_nugget",
    "gold_nugget",
    "log",
    "plank",
    "stick",
    "compass",
    "clock",
    "piston",
    "redstone_torch",
    "lever",
    "chest",
    "crafting_table",
    "furnace",
    "hopper",
    "dropper",
    "iron_bars",

    # OpenComputers Components
    "analyzer",
    "assembler",
    "cpu_tier_1",
    "cpu_tier_2",
    "cpu_tier_3",
    "ram_tier_1",
    "ram_tier_1_5",
    "ram_tier_2",
    "ram_tier_2_5",
    "ram_tier_3",
    "ram_tier_3_5",
    "card_base",
    "internet_card",
    "geolyzer",
    "crafting_upgrade",
    "inventory_upgrade",
    "inventory_controller",
    "cutting_wire",
    "raw_circuit",
    "circuit",
    "transistor",
    "microchip_tier_1",
    "microchip_tier_2",
    "microchip_tier_3",
    "alu",
    "control_unit",
    "disk_platter",
    "diamond_chip",
    "hard_drive_tier_1",
    "hard_drive_tier_2",
    "hard_drive_tier_3",
    "floppy_disk_drive",
    "floppy_disk",
    "eeprom",
    "case_tier_1",
    "case_tier_2",
    "case_tier_3",
    "robot",

    # Tools
    "wooden_pickaxe",
    "stone_pickaxe",
    "iron_pickaxe",
    "diamond_pickaxe",
]

recipes = {
    # Vanilla items
    "plank": {
        "recipe": [
            ["log", None, None],
            [None, None, None],
            [None, None, None]
        ],
        "output": 4
    },
    "stick": {
        "recipe": [
            ["plank", None, None],
            ["plank", None, None],
            [None, None, None]
        ],
        "output": 4
    },
    "compass": {
        "recipe": [
            [None, "iron", None],
            ["iron", "redstone", "iron"],
            [None, "iron", None]
        ],
        "output": 1
    },
    "clock": {
        "recipe": [
            [None, "gold", None],
            ["gold", "redstone", "gold"],
            [None, "gold", None]
        ],
        "output": 1
    },
    "iron_nugget": {
        "recipe": [
            ["iron", None, None],
            [None, None, None],
            [None, None, None]
        ],
        "output": 9
    },
    "gold_nugget": {
        "recipe": [
            ["gold", None, None],
            [None, None, None],
            [None, None, None]
        ],
        "output": 9
    },
    "piston": {
        "recipe": [
            ["plank", "plank", "plank"],
            ["cobblestone", "iron", "cobblestone"],
            ["cobblestone", "redstone", "cobblestone"]
        ],
        "output": 1
    },
    "redstone_torch": {
        "recipe": [
            [None, "redstone", None],
            [None, "stick", None],
            [None, None, None]
        ],
        "output": 1
    },
    "lever": {
        "recipe": [
            [None, "stick", None],
            [None, "cobblestone", None],
            [None, None, None]
        ],
        "output": 1
    },
    "chest": {
        "recipe": [
            ["plank", "plank", "plank"],
            ["plank", None, "plank"],
            ["plank", "plank", "plank"]
        ],
        "output": 1
    },
    "crafting_table": {
        "recipe": [
            ["plank", "plank", None],
            ["plank", "plank", None],
            [None, None, None]
        ],
        "output": 1
    },
    "furnace": {
        "recipe": [
            ["cobblestone", "cobblestone", "cobblestone"],
            ["cobblestone", None, "cobblestone"],
            ["cobblestone", "cobblestone", "cobblestone"]
        ],
        "output": 1
    },
    "hopper": {
        "recipe": [
            ["iron", None, "iron"],
            ["iron", "chest", "iron"],
            [None, "iron", None]
        ],
        "output": 1
    },
    "dropper": {
        "recipe": [
            ["cobblestone", "cobblestone", "cobblestone"],
            ["cobblestone", None, "cobblestone"],
            ["cobblestone", "redstone", "cobblestone"]
        ],
        "output": 1
    },
    "iron_bars": {
        "recipe": [
            ["iron", "iron", "iron"],
            ["iron", "iron", "iron"],
            [None, None, None]
        ],
        "output": 16
    },

    # Tools
    "wooden_pickaxe": {
        "recipe": [
            ["plank", "plank", "plank"],
            [None, "stick", None],
            [None, "stick", None]
        ],
        "output": 1
    },
    "stone_pickaxe": {
        "recipe": [
            ["cobblestone", "cobblestone", "cobblestone"],
            [None, "stick", None],
            [None, "stick", None]
        ],
        "output": 1
    },
    "iron_pickaxe": {
        "recipe": [
            ["iron", "iron", "iron"],
            [None, "stick", None],
            [None, "stick", None]
        ],
        "output": 1
    },
    "diamond_pickaxe": {
        "recipe": [
            ["diamond", "diamond", "diamond"],
            [None, "stick", None],
            [None, "stick", None]
        ],
        "output": 1
    },

    # OpenComputers Components
    "analyzer": {
        "recipe": [
            ["redstone_torch", None, None],
            ["transistor", "gold_nugget", None],
            ["circuit", "gold_nugget", None]
        ],
        "output": 1
    },
    "assembler": {
        "recipe": [
            ["iron", "crafting_table", "iron"],
            ["piston", "microchip_tier_2", "piston"],
            ["iron", "circuit", "iron"]
        ],
        "output": 1
    },
    "cpu_tier_1": {
        "recipe": [
            ["iron_nugget", "redstone", "iron_nugget"],
            ["microchip_tier_1", "control_unit", "microchip_tier_1"],
            ["iron_nugget", "alu", "iron_nugget"]
        ],
        "output": 1
    },
    "cpu_tier_2": {
        "recipe": [
            ["gold_nugget", "redstone", "gold_nugget"],
            ["microchip_tier_2", "control_unit", "microchip_tier_2"],
            ["gold_nugget", "alu", "gold_nugget"]
        ],
        "output": 1
    },
    "cpu_tier_3": {
        "recipe": [
            ["diamond_chip", "redstone", "diamond_chip"],
            ["microchip_tier_3", "control_unit", "microchip_tier_3"],
            ["diamond_chip", "alu", "diamond_chip"]
        ],
        "output": 1
    },
    "ram_tier_1": {
        "recipe": [
            [None, None, None],
            ["microchip_tier_1", "iron_nugget", "microchip_tier_1"],
            [None, "circuit", None]
        ],
        "output": 1
    },
    "ram_tier_1_5": {
        "recipe": [
            [None, None, None],
            ["microchip_tier_1", "microchip_tier_2", "microchip_tier_1"],
            [None, "circuit", None]
        ],
        "output": 1
    },
    "ram_tier_2": {
        "recipe": [
            [None, None, None],
            ["microchip_tier_2", "iron_nugget", "microchip_tier_2"],
            [None, "circuit", None]
        ],
        "output": 1
    },
    "ram_tier_2_5": {
        "recipe": [
            [None, None, None],
            ["microchip_tier_2", "microchip_tier_3", "microchip_tier_2"],
            [None, "circuit", None]
        ],
        "output": 1
    },
    "ram_tier_3": {
        "recipe": [
            [None, None, None],
            ["microchip_tier_3", "iron_nugget", "microchip_tier_3"],
            [None, "circuit", None]
        ],
        "output": 1
    },
    "ram_tier_3_5": {
        "recipe": [
            [None, None, None],
            ["microchip_tier_3", "microchip_tier_3", "microchip_tier_3"],
            ["microchip_tier_2", "circuit", "microchip_tier_2"]
        ],
        "output": 1
    },
    "card_base": {
        "recipe": [
            ["iron_nugget", None, None],
            ["iron_nugget", "circuit", None],
            ["iron_nugget", "gold_nugget", None]
        ],
        "output": 1
    },
    "internet_card": {
        "recipe": [
            [None, None, None],
            ["diamond", "microchip_tier_2", "redstone_torch"],
            [None, "card_base", "redstone"]
        ],
        "output": 1
    },
    "geolyzer": {
        "recipe": [
            ["gold", "compass", "gold"],
            ["diamond", "microchip_tier_2", "diamond"],
            ["gold", "circuit", "gold"]
        ],
        "output": 1
    },
    "crafting_upgrade": {
        "recipe": [
            ["iron", None, "iron"],
            ["microchip_tier_1", "crafting_table", "microchip_tier_1"],
            ["iron", "circuit", "iron"]
        ],
        "output": 1
    },
    "inventory_upgrade": {
        "recipe": [
            ["plank", "hopper", "plank"],
            ["dropper", "chest", "piston"],
            ["plank", "microchip_tier_1", "plank"]
        ],
        "output": 1
    },
    "inventory_controller": {
        "recipe": [
            ["gold", "analyzer", "gold"],
            ["dropper", "microchip_tier_2", "piston"],
            ["gold", "circuit", "gold"]
        ],
        "output": 1
    },
    "cutting_wire": {
        "recipe": [
            [None, None, None],
            ["stick", "iron_nugget", "stick"],
            [None, None, None]
        ],
        "output": 1
    },
    "transistor": {
        "recipe": [
            ["iron", "iron", "iron"],
            ["gold_nugget", "redstone", "gold_nugget"],
            [None, "redstone", None]
        ],
        "output": 8
    },
    "microchip_tier_1": {
        "recipe": [
            ["iron_nugget", "iron_nugget", "iron_nugget"],
            ["redstone", "transistor", "redstone"],
            ["iron_nugget", "iron_nugget", "iron_nugget"]
        ],
        "output": 8
    },
    "microchip_tier_2": {
        "recipe": [
            ["gold_nugget", "gold_nugget", "gold_nugget"],
            ["redstone", "transistor", "redstone"],
            ["gold_nugget", "gold_nugget", "gold_nugget"]
        ],
        "output": 4
    },
    "microchip_tier_3": {
        "recipe": [
            ["diamond_chip", "diamond_chip", "diamond_chip"],
            ["redstone", "transistor", "redstone"],
            ["diamond_chip", "diamond_chip", "diamond_chip"]
        ],
        "output": 2
    },
    "alu": {
        "recipe": [
            ["iron_nugget", "redstone", "iron_nugget"],
            ["transistor", "microchip_tier_1", "transistor"],
            ["iron_nugget", "transistor", "iron_nugget"]
        ],
        "output": 1
    },
    "control_unit": {
        "recipe": [
            ["gold_nugget", "redstone", "gold_nugget"],
            ["transistor", "clock", "transistor"],
            ["gold_nugget", "transistor", "gold_nugget"]
        ],
        "output": 1
    },
    "disk_platter": {
        "recipe": [
            [None, "iron_nugget", None],
            ["iron_nugget", None, "iron_nugget"],
            [None, "iron_nugget", None]
        ],
        "output": 1
    },
    "diamond_chip": {
        "recipe": [
            ["cutting_wire", "diamond", None],
            [None, None, None],
            [None, None, None]
        ],
        "output": 6
    },
    "raw_circuit": {
        "recipe": [
            [None, None, None],
            ["gold_nugget", "gold_nugget", "gold_nugget"],
            ["iron_nugget", "iron_nugget", "iron_nugget"]
        ],
        "output": 4
    },
    "hard_drive_tier_1": {
        "recipe": [
            ["microchip_tier_1", "disk_platter", "iron"],
            ["circuit", "disk_platter", "piston"],
            ["microchip_tier_1", "disk_platter", "iron"]
        ],
        "output": 1
    },
    "hard_drive_tier_2": {
        "recipe": [
            ["microchip_tier_2", "disk_platter", "gold"],
            ["circuit", "disk_platter", "piston"],
            ["microchip_tier_2", "disk_platter", "gold"]
        ],
        "output": 1
    },
    "hard_drive_tier_3": {
        "recipe": [
            ["microchip_tier_3", "disk_platter", "diamond"],
            ["circuit", "disk_platter", "piston"],
            ["microchip_tier_3", "disk_platter", "diamond"]
        ],
        "output": 1
    },
    "floppy_disk_drive": {
        "recipe": [
            ["iron", "microchip_tier_1", "iron"],
            ["piston", "stick", None],
            ["iron", "circuit", "iron"]
        ],
        "output": 1
    },
    "floppy_disk": {
        "recipe": [
            ["iron", "lever", "iron"],
            ["gold_nugget", "disk_platter", "gold_nugget"],
            ["iron", "redstone", "iron"]
        ],
        "output": 1
    },
    "eeprom": {
        "recipe": [
            ["gold_nugget", "transistor", "gold_nugget"],
            ["microchip_tier_1", "redstone", "microchip_tier_1"],
            ["gold_nugget", "redstone_torch", "gold_nugget"]
        ],
        "output": 1
    },
    "case_tier_1": {
        "recipe": [
            ["iron", "microchip_tier_1", "iron"],
            ["iron_bars", "chest", "iron_bars"],
            ["iron", "circuit", "iron"]
        ],
        "output": 1
    },
    "case_tier_2": {
        "recipe": [
            ["gold", "microchip_tier_2", "gold"],
            ["iron_bars", "chest", "iron_bars"],
            ["gold", "circuit", "gold"]
        ],
        "output": 1
    },
    "case_tier_3": {
        "recipe": [
            ["diamond", "microchip_tier_3", "diamond"],
            ["iron_bars", "chest", "iron_bars"],
            ["diamond", "circuit", "diamond"]
        ],
        "output": 1
    }
}

# (item, quantity) pairs for ingredients of each recipe
recipe_ingredients: dict[str, dict[str, int]] = {}

for item, data in recipes.items():
    recipe_ingredients[item] = {}
    for ingredient in [item for row in data["recipe"] for item in row if item is not None]:
        if ingredient not in recipe_ingredients[item]:
            recipe_ingredients[item][ingredient] = 1
        else:
            recipe_ingredients[item][ingredient] += 1

        if ingredient not in items_list:
            logger.info(f"Warning: Ingredient {ingredient} not in items_list", "Server")


def convert_item_name(name: str, data_value: int) -> str:
    """
    The robot can only see the item id and data value, not the
    human readable name. Modded items are often grouped together to
    conserve item IDs, this determines which item matches the pair.
    """

    # Some items' names will match directly, minus the namespace
    split = name.split(":")
    if len(split) == 2 and split[1] in items_list:
        return split[1]

    if name == "minecraft:planks":
        return "plank"
    if name == "minecraft:iron_ingot":
        return "iron"
    if name == "minecraft:gold_ingot":
        return "gold"

    if name == "opencomputers:geolyzer":
        return "geolyzer"
    if name == "opencomputers:diskdrive":
        return "floppy_disk_drive"
    if name == "opencomputers:case1":
        return "case_tier_1"
    if name == "opencomputers:case2":
        return "case_tier_2"
    if name == "opencomputers:case3":
        return "case_tier_3"

    if name == "opencomputers:component":
        if data_value == 0:
            return "cpu_tier_1"
        if data_value == 1:
            return "cpu_tier_2"
        if data_value == 2:
            return "cpu_tier_3"
        if data_value == 6:
            return "ram_tier_1"
        if data_value == 7:
            return "ram_tier_1_5"
        if data_value == 8:
            return "ram_tier_2"
        if data_value == 9:
            return "ram_tier_2_5"
        if data_value == 10:
            return "ram_tier_3"
        if data_value == 11:
            return "ram_tier_3_5"

    if name == "opencomputers:card":
        if data_value == 8:
            return "internet_card"

    if name == "opencomputers:upgrade":
        if data_value == 11:
            return "crafting_upgrade"
        elif data_value == 17:
            return "inventory_upgrade"
        elif data_value == 18:
            return "inventory_controller"

    if name == "opencomputers:material":
        if data_value == 0:
            return "cutting_wire"
        if data_value == 2:
            return "raw_circuit"
        if data_value == 4:
            return "circuit"
        if data_value == 5:
            return "card_base"
        if data_value == 6:
            return "transistor"
        if data_value == 7:
            return "microchip_tier_1"
        if data_value == 8:
            return "microchip_tier_2"
        if data_value == 9:
            return "microchip_tier_3"
        if data_value == 10:
            return "alu"
        if data_value == 11:
            return "control_unit"
        if data_value == 12:
            return "disk_platter"
        if data_value == 29:
            return "diamond_chip"

    if name == "opencomputers:storage":
        if data_value == 0:
            return "eeprom"
        if data_value == 1:
            return "floppy_disk"
        if data_value == 2:
            return "hard_drive_tier_1"
        if data_value == 3:
            return "hard_drive_tier_2"
        if data_value == 4:
            return "hard_drive_tier_3"

    if name == "opencomputers:tool" and data_value == 0:
        return "analyzer"

    logger.info(f"Warning: Unrecognized item in robot inventory: {name}", "Server")
    return name
