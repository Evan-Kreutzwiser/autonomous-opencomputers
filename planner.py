from pddl.logic import Predicate, constants, Variable, functions, effects, Constant
from pddl.logic.functions import (
    NumericFunction,
    NumericValue,
    GreaterEqualThan,
    LesserEqualThan,
    Assign,
    EqualTo,
    Increase,
    Decrease,
    Divide,
)
from pddl.core import Domain, Problem, Formula
from pddl.action import Action
from pddl.requirements import Requirements
import logger
from recipes import recipe_ingredients, recipes, items_list
from robot import Robot
import subprocess

types = {"robot": "object"}

inventory_functions = {}
for item in items_list:
    inventory_functions[item] = NumericFunction(
        f"robot_inventory_{item}", Variable("r", ("robot",))
    )


def _count_items(inventory: list[str, int]) -> dict[str, int]:
    """
    Robot inventory tracks individual slot contents, 
    the planner just needs to know total quantities.
    """
    counts = {}
    for item, quantity in inventory:
        if item in counts:
            counts[item] += quantity
        else:
            counts[item] = quantity

    return counts


def create_domain() -> Domain:
    robot = Variable("r", ("robot",))
    robot_inventory_functions = {inventory_functions[item]: None for item in items_list}

    actions = []

    for item, current_recipe in recipe_ingredients.items():
        crafting_preconditions = []
        for ingredient, amount in current_recipe.items():
            if ingredient != "output":
                crafting_preconditions.append(GreaterEqualThan(inventory_functions[ingredient], NumericValue(amount)))

        crafting_effects = [
            # Add the output item to this robot's inventory
            Increase(inventory_functions[item], NumericValue(recipes[item]["output"]))
        ]

        for ingredient, amount in current_recipe.items():
            if ingredient != "output":
                crafting_effects.append(Decrease(inventory_functions[ingredient](robot), NumericValue(amount)))

        actions.append(Action(
            f"craft_{item}",
            parameters=[robot],
            precondition=effects.And(*crafting_preconditions),
            effect=effects.And(*crafting_effects)
        ))

    for ore, cooked in [("iron_ore", "iron"), ("gold_ore", "gold"), ("raw_circuit", "circuit")]:
        actions.append(Action(
            f"smelt_8_{ore}",
            parameters=[robot],
            precondition=effects.And(
                GreaterEqualThan(inventory_functions[ore](robot), NumericValue(8)),
                GreaterEqualThan(inventory_functions["coal"](robot), NumericValue(1))
            ),
            effect=effects.And(
                Decrease(inventory_functions[ore](robot), NumericValue(8)),
                Increase(inventory_functions[cooked](robot), NumericValue(8)),
                Decrease(inventory_functions["coal"](robot), NumericValue(1))
            )
        ))

        actions.append(Action(
            f"smelt_partial_{ore}",
            parameters=[robot],
            precondition=effects.And(
                GreaterEqualThan(inventory_functions["coal"](robot), NumericValue(1)),
                GreaterEqualThan(inventory_functions[ore](robot), NumericValue(1)),
                LesserEqualThan(inventory_functions[ore](robot), NumericValue(8))
            ),
            effect=effects.And(
                Decrease(inventory_functions["coal"](robot), NumericValue(1)),
                Increase(inventory_functions[cooked](robot), inventory_functions[ore](robot)),
                Assign(inventory_functions[ore](robot), NumericValue(0))
            )
        ))

    domain = Domain(
        "OpenComputersPlanner",
        requirements=[Requirements.TYPING, Requirements.NUMERIC_FLUENTS],
        actions=actions,
        functions=robot_inventory_functions,
        types=types,
    )

    return domain


def create_problem(robots: dict[Robot]) -> Problem:
    """
    Create a PDDL problem from a dictionary of robots and their inventories.
    
    :param robots: A dictionary of robot ids and their inventories, 
                   represented as a dictionary of item names and quantities.
    :return: A PDDL Problem with the goal of creating a new robot.
    """
    initial_state = []
    robot_objects = {id: Constant(f"robot_{id}", "robot") for id in robots.keys()}

    for robot in robots.values():
        inventory = _count_items(robot.inventory)
        for item, quantity in inventory.items():
            if item not in items_list:
                print(f"WARNING: Robot {robot.id} has item \"{item}\" (x{quantity}), which is not recognized by the planner!")
            else:
                initial_state.append(EqualTo(inventory_functions[item](robot_objects[robot.id]), NumericValue(quantity)))
        
        # All items not listed in the inventory are assumed to be 0
        for missing_item in [item for item in items_list if item not in inventory.keys()]:
            initial_state.append(EqualTo(inventory_functions[missing_item](robot_objects[robot.id]), NumericValue(0)))


    first_robot_id = list(robots.keys())[0]
    problem = Problem(
        "OpenComputersPlanner",
        domain=create_domain(),
        objects=robot_objects.values(),
        requirements=[Requirements.TYPING, Requirements.NUMERIC_FLUENTS],
        init=initial_state,
        # Placeholder goal for testing output files
        goal=effects.And(
                GreaterEqualThan(inventory_functions["diamond_pickaxe"](robot_objects[first_robot_id]), NumericValue(1)),
            )
    )

    return problem


def replan(robots: dict[Robot]) -> list[tuple[int, list[str]]]:
    """
    Determine which actions each robot should taek to contrstruct a new robot.

    :param robots: All connected robots, with up to date inventories and empty action queues.
    """
    problem = create_problem(robots)
    open("problem.pddl", "w").write(str(problem))

    output = subprocess.run("planutils run popf domain.pddl problem.pddl", capture_output=True, text=True, shell=True).stdout

    # Even if no solution was found, this line should still print
    # This separates the solution output from debug messages about pruning and optimization
    solution = output.split("Initial heuristic")[1]


    if "Solution Found" in solution:
        lines = solution.split("\n")
        actions = []

        # Interpretes POPF output to obtain the plan
        # Extraction will need changes if a different planner is used
        # TODO: Surely somewhere theres a planner that can handle 
        # numeric fluents and output in a structure format?
        for line in lines:
            if ": (" in line:
                # Extract the action and argument from the line
                action_string = line.split(": (")[1].split(")")[0]
                # Robot constants are named robot_#
                terms = action_string.split(" ")
                # Extract the id of the robot performing the task
                robot = int(terms.pop(1).split("_")[1])
                # Other terms describe the action itself
                actions.append((robot, terms))

        return actions
    else:
        logger.error("No solution found.", "Planner")
        return []

if __name__ == "__main__":
    domain = create_domain()

    robot = Robot(1)
    robot.inventory = [
        ("plank", 2),
        ("diamond", 3),
    ]
    problem = create_problem([robot])

    open("domain.pddl", "w").write(str(domain))
    # I'd prefer to keep this in-memory because of the frequent replanning,
    # but would need a way to get it through to the planner's container
    open("problem.pddl", "w").write(str(problem))

    plan = replan({1: robot})
    print("\n".join([action[0] for action in plan]))
