"""

"""

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

    # OpenComputers Components
    "analyzer",
    "cpu_tier_1",
    "cpu_tier_2",
    "cpu_tier_3",
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
            print(f"Warmomg: Ingredient {ingredient} not in items_list")


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

    if name == "opencomputers:component":
        if data_value == 0:
            return "cpu_tier_1"
        if data_value == 1:
            return "cpu_tier_2"
        if data_value == 2:
            return "cpu_tier_3"

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

    if name == "opencomputers:tool" and data_value == 0:
        return "analyzer"

    print(f"Warning: Unrecognized item name: {name}")
    return name
