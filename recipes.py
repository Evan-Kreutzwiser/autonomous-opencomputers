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
    "cpu_tier_1",
    "cpu_tier_2",
    "cpu_tier_3",
    "internet_card",
    "geolyzer",
    "inventory_controller",
    "diamond_nugget",

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
