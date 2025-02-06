from pddl.logic import Predicate, constants, Variable, functions, effects, Constant
from pddl.logic.functions import NumericFunction, NumericValue, GreaterEqualThan, LesserEqualThan, EqualTo, Increase, Decrease
from pddl.core import Domain, Problem, Formula
from pddl.action import Action
from pddl.requirements import Requirements

types = {"robot": None}

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
    "logs",
    "planks",
    "sticks",
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
    "planks": {
        "logs": 1,
        "output": 4
    },
    "sticks": {
        "planks": 2,
        "output": 4
    },
    "compass": {
        "iron": 4,
        "redstone": 1,
        "output": 1
    },
    "clock": {
        "gold": 4,
        "redstone": 1,
        "output": 1
    },
    "iron_nugget": {
        "iron": 1,
        "output": 9
    },
    "gold_nugget": {
        "gold": 1,
        "output": 9
    },

    # Tools
    "wooden_pickaxe": {
        "planks": 3,
        "sticks": 2,
        "output": 1
    },
    "stone_pickaxe": {
        "cobblestone": 3,
        "sticks": 2,
        "output": 1
    },
    "iron_pickaxe": {
        "iron": 3,
        "sticks": 2,
        "output": 1
    },
    "diamond_pickaxe": {
        "diamond": 3,
        "sticks": 2,
        "output": 1
    }
}

inventory_functions = {}
for item in items_list:
    inventory_functions[item] = NumericFunction(f"robot_inventory_{item}", Variable("r", ("robot",)))

def create_domain() -> Domain:
    robot = Variable("r", ("robot", ))
    robot_inventory_functions = {inventory_functions[item]: None for item in items_list}

    actions = []


    for item, recipe in recipes.items():
        crafting_preconditions = []
        for ingredient, amount in recipe.items():
            if ingredient != "output":
                crafting_preconditions.append(GreaterEqualThan(inventory_functions[ingredient], NumericValue(amount)))

        crafting_effects = [
            # Add the output item to this robot's inventory
            Increase(inventory_functions[item], NumericValue(recipe["output"]))
        ]

        for ingredient, amount in recipe.items():
            if ingredient != "output":
                crafting_effects.append(Decrease(inventory_functions[ingredient](robot), NumericValue(amount)))

        actions.append(Action(
            f"craft_{item}",
            parameters=[robot],
            precondition=effects.And(*crafting_preconditions),
            effect=effects.And(*crafting_effects)
        ))

    domain = Domain(
        "OpenComputersPlanner",
        requirements=[Requirements.TYPING, Requirements.NUMERIC_FLUENTS],
        actions=actions,
        functions=robot_inventory_functions,
        types=types,
    )

    return domain


if __name__ == "__main__":
    domain = create_domain()
    print(domain)

