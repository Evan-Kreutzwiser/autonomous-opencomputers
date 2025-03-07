from pddl.logic import Predicate, constants, Variable, functions, effects, Constant, predicates
from pddl.logic.base import And, Or, Not
from pddl.logic.functions import (
    NumericFunction,
    NumericValue,
    GreaterEqualThan,
    GreaterThan,
    LesserEqualThan,
    LesserThan,
    Assign,
    EqualTo,
    Increase,
    Decrease,
    Divide,
    Plus,
    Minus,
)
from pddl.core import Domain, Problem, Formula
from pddl.action import Action
from pddl.requirements import Requirements
import logger
from recipes import recipe_ingredients, recipes, items_list, stack_size
from robot import Robot
import subprocess

types = {"robot": "object"}
robot_variable = Variable("r", ("robot",))

# Number of slots completely filled with a specific item.
full_stack_functions = {
    item: NumericFunction(f"robot_full_stacks_of_{item}", robot_variable)
    for item in items_list
    if stack_size[item] > 1
}
# There will only ever be one partial stack of an item at a time.
# Partial stacks are automatically consolidated in-game by the robot after
# actions that may cause multiple to exist.
partial_stack_functions = {
    item: NumericFunction(f"robot_partial_stack_size_{item}", robot_variable)
    for item in items_list
    if stack_size[item] > 1
}
# Whether partial_stack_functions are nonzero, for inventory usage calculations
has_partial_stack_functions = {
    item: NumericFunction(f"robot_has_partial_stack_{item}", robot_variable)
    for item in items_list
    if stack_size[item] > 1
}
non_stackable_items_functions = {
    item: NumericFunction(f"robot_single_stacks_{item}", robot_variable)
    for item in items_list
    if stack_size[item] == 1
}

# Inventory size is impacted by the number of inventory upgrades installed (16 slots per upgrade)
inventory_size_function = NumericFunction("robot_inventory_size", robot_variable)
inventory_slots_used_function = NumericFunction("robot_inventory_slots_used", robot_variable)

should_update_item = {item: Predicate(f"should_update_{item}", robot_variable) for item in full_stack_functions.keys()}
should_update_item_stacks = Predicate("should_update_item_stacks", robot_variable)


def create_domain() -> Domain:
    robot = robot_variable
    actions = []

    # Derived predicates and functions
    #
    # Derived values are calculated manually after every action rather
    # than making use of the derived-predicates feature, because no planner
    # seems to support the full scope of features I need.
    ####################

    for item in full_stack_functions.keys():
        actions.append(Action(
            f"compress_{item}_stack_no_remainder",
            parameters=[robot],
            precondition=And(should_update_item[item](robot), EqualTo(partial_stack_functions[item](robot), NumericValue(stack_size[item]))),
            effect=And(
                Increase(full_stack_functions[item](robot), NumericValue(1)),
                Decrease(partial_stack_functions[item](robot), NumericValue(stack_size[item])),
                Not(should_update_item[item](robot)),
            )
        ))
        
        actions.append(Action(
            f"compress_{item}_stack_with_remainder",
            parameters=[robot],
            precondition=And(should_update_item[item](robot), GreaterThan(partial_stack_functions[item](robot), NumericValue(stack_size[item]))),
            effect=And(
                Increase(full_stack_functions[item](robot), NumericValue(1)),
                Decrease(partial_stack_functions[item](robot), NumericValue(stack_size[item])),
                Increase(inventory_slots_used_function(robot), NumericValue(1)), 
                Not(should_update_item[item](robot)),
            )
        ))

        actions.append(Action(
            f"unpack_{item}_stack",
            parameters=[robot],
            precondition=And(should_update_item[item](robot), LesserThan(partial_stack_functions[item](robot), NumericValue(0))),
            effect=And(
                Decrease(full_stack_functions[item](robot), NumericValue(1)),
                Increase(partial_stack_functions[item](robot), NumericValue(stack_size[item])),
                Decrease(inventory_slots_used_function(robot), NumericValue(1)),
                Not(should_update_item[item](robot)),
            )
        ))

        # Assuming that should_update_item will only be invoked if items were added or removed,
        # If there isn't any of the item it is safe to assume there was a partial stack which is not gone.
        actions.append(Action(
            f"ran_out_of_{item}",
            parameters=[robot],
            precondition=And(
                should_update_item[item](robot),
                And(
                    EqualTo(partial_stack_functions[item](robot), NumericValue(0)),
                    EqualTo(full_stack_functions[item](robot), NumericValue(0))
                )),
            effect=And(
                Decrease(inventory_slots_used_function(robot), NumericValue(1)),
                Not(should_update_item[item](robot)),
            )
        ))

        # No change in the number of stacks
        actions.append(Action(
            f"acknowledge_{item}_update",
            parameters=[robot],
            precondition=And(
                should_update_item[item](robot),
                And(
                    GreaterThan(partial_stack_functions[item](robot), NumericValue(0)),
                    LesserThan(partial_stack_functions[item](robot), NumericValue(stack_size[item]))
                )
            ),
            effect=Not(should_update_item[item](robot))
        ))

    actions.append(Action(
        "finish_updating_items",
        parameters=[robot],
        precondition=And(should_update_item_stacks(robot), *[Not(pred(robot)) for pred in should_update_item.values()]),
        effect=And(
            Not(should_update_item_stacks(robot)),
        )))

    # Crafting
    #
    # Auto generate actions from recipe data
    ####################

    has_9_free_slots = lambda r: GreaterEqualThan(Minus(inventory_size_function(r), inventory_slots_used_function(r)), NumericValue(9))

    for item, current_recipe in recipe_ingredients.items():
        recipe_preconditions = []
        for ingredient, amount in current_recipe.items():
            ingredient_can_stack = stack_size[ingredient] > 1
            # If a full stack of the ingredient is present, the partial stack is allowed to momentarily go negative.
            # It will be replenished by the update_derived_values action from a full stack.
            if ingredient_can_stack:
                recipe_preconditions.append(Or(
                        GreaterEqualThan(partial_stack_functions[ingredient](robot), NumericValue(amount)),
                        GreaterEqualThan(full_stack_functions[ingredient](robot), NumericValue(1))
                    ))
            else:
                recipe_preconditions.append(
                    GreaterEqualThan(non_stackable_items_functions[ingredient](robot), NumericValue(amount))
                )

        crafting_effects = []
        # Add the output item to this robot's inventory
        if stack_size[item] > 1:
            crafting_effects.append(Increase(partial_stack_functions[item](robot), NumericValue(recipes[item]["output"])))
        else:
            crafting_effects.append(Increase(non_stackable_items_functions[item](robot), NumericValue(1)))
            crafting_effects.append(Decrease(inventory_slots_used_function(robot), NumericValue(1)))

        # Consume crafting ingredients
        for ingredient, amount in current_recipe.items():
            ingredient_can_stack = stack_size[ingredient] > 1
            if ingredient_can_stack:
                crafting_effects.append(should_update_item[ingredient](robot))
                crafting_effects.append(Decrease(partial_stack_functions[ingredient](robot), NumericValue(amount)))
            else:
                crafting_effects.append(Decrease(non_stackable_items_functions[ingredient](robot), NumericValue(amount))) 
                crafting_effects.append(Decrease(inventory_slots_used_function(robot), NumericValue(amount)))

        actions.append(
            Action(
                f"craft_{item}",
                parameters=[robot],
                precondition=And(
                    Not(should_update_item_stacks(robot)),
                    has_9_free_slots(robot),
                    *recipe_preconditions,
                ),
                effect=And(should_update_item_stacks, *crafting_effects),
            )
        )

    # for ore, cooked in [("iron_ore", "iron"), ("gold_ore", "gold"), ("raw_circuit", "circuit")]:
    #     actions.append(Action(
    #         f"smelt_8_{ore}",
    #         parameters=[robot],
    #         precondition=And(
    #             GreaterEqualThan(inventory_functions[ore](robot), NumericValue(8)),
    #             GreaterEqualThan(inventory_functions["coal"](robot), NumericValue(1))
    #         ),
    #         effect=And(
    #             Decrease(inventory_functions[ore](robot), NumericValue(8)),
    #             Increase(inventory_functions[cooked](robot), NumericValue(8)),
    #             Decrease(inventory_functions["coal"](robot), NumericValue(1))
    #         )
    #     ))

    #     actions.append(Action(
    #         f"smelt_partial_{ore}",
    #         parameters=[robot],
    #         precondition=And(
    #             GreaterEqualThan(inventory_functions["coal"](robot), NumericValue(1)),
    #             GreaterEqualThan(inventory_functions[ore](robot), NumericValue(1)),
    #             LesserEqualThan(inventory_functions[ore](robot), NumericValue(8))
    #         ),
    #         effect=And(
    #             Decrease(inventory_functions["coal"](robot), NumericValue(1)),
    #             Increase(inventory_functions[cooked](robot), inventory_functions[ore](robot)),
    #             Assign(inventory_functions[ore](robot), NumericValue(0)),
    #             # effects.When(
    #             #     EqualTo(inventory_functions["coal"](robot), NumericValue(0)),
    #             # ),

    #         )
    #     ))

    domain = Domain(
        "OpenComputersDomain",
        requirements=[Requirements.TYPING, Requirements.NUMERIC_FLUENTS, Requirements.NEG_PRECONDITION, Requirements.DIS_PRECONDITION],
        actions=actions,
        functions={function: None for function_list in [
            full_stack_functions.values(),
            partial_stack_functions.values(),
            has_partial_stack_functions.values(),
            non_stackable_items_functions.values(),
            [inventory_size_function, inventory_slots_used_function]
        ] for function in function_list},
        types=types,
        predicates=[should_update_item_stacks] + list(should_update_item.values())
    )

    return domain


def create_problem(robots: dict[int, Robot]) -> Problem:
    """
    Create a PDDL problem from a dictionary of robots and their inventories.
    
    :param robots: A dictionary of robot ids and their inventories, 
                   represented as a dictionary of item names and quantities.
    :return: A PDDL Problem with the goal of creating a new robot.
    """
    initial_state = []
    robot_objects = {id: Constant(f"robot_{id}", "robot") for id in robots.keys()}

    for robot in robots.values():
        inventory = robot.count_items()
        for item, quantity in inventory.items():
            if item not in items_list:
                logger.info(f"Warning: Robot has item \"{item}\" (x{quantity}), which is not recognized by the planner!", robot.id)
            elif stack_size[item] > 1:
                initial_state.append(EqualTo(full_stack_functions[item](robot_objects[robot.id]), NumericValue(quantity // stack_size[item])))
                initial_state.append(EqualTo(partial_stack_functions[item](robot_objects[robot.id]), NumericValue(quantity % stack_size[item])))
            else:
                initial_state.append(EqualTo(non_stackable_items_functions[item](robot_objects[robot.id]), NumericValue(quantity)))

        # All items not listed in the inventory are assumed to be 0
        for absent_item in [item for item in items_list if item not in inventory.keys()]:
            if stack_size[absent_item] > 1:
                initial_state.append(EqualTo(full_stack_functions[absent_item](robot_objects[robot.id]), NumericValue(0)))
                initial_state.append(EqualTo(partial_stack_functions[absent_item](robot_objects[robot.id]), NumericValue(0)))
            else:
                initial_state.append(EqualTo(non_stackable_items_functions[absent_item](robot_objects[robot.id]), NumericValue(0)))

        print(f"Inventory Size: {len(robot.inventory)-1}")
        initial_state.append(EqualTo(inventory_size_function(robot_objects[robot.id]), NumericValue(len(robot.inventory) - 1)))

        slots_used = len([1 for item in robot.inventory if item is not None])
        initial_state.append(EqualTo(inventory_slots_used_function(robot_objects[robot.id]), NumericValue(slots_used)))
        initial_state.append(Not(should_update_item_stacks(robot_objects[robot.id])))


    first_robot_id = max(robots.keys())
    problem = Problem(
        "OpenComputersProblem",
        domain=create_domain(),
        objects=robot_objects.values(),
        requirements=[Requirements.TYPING, Requirements.NUMERIC_FLUENTS, Requirements.NEG_PRECONDITION, Requirements.DIS_PRECONDITION],
        init=initial_state,
        # Placeholder goal for testing output files
        goal=And(
                GreaterEqualThan(non_stackable_items_functions["diamond_pickaxe"](robot_objects[first_robot_id]), NumericValue(1)),
                # GreaterEqualThan(inventory_functions["cpu_tier_3"](robot_objects[3]), NumericValue(1)),
                # GreaterEqualThan(inventory_functions["case_tier_3"](robot_objects[3]), NumericValue(1)),
            )
    )

    return problem


def replan(robots: dict[int, Robot]) -> list[tuple[int, list[str]]]:
    """
    Determine which actions each robot should taek to contrstruct a new robot.

    :param robots: All connected robots, with up to date inventories and empty action queues.
    """
    problem = create_problem(robots)
    open("problem.pddl", "w").write(str(problem))

    output = subprocess.run("planutils run enhsp \"-o domain.pddl\" \"-f problem.pddl\"", capture_output=True, text=True, shell=True).stdout


    if "Found Plan" in output:
        solution = output.split("Found Plan")[1]

        lines = solution.split("\n")
        actions = []
        has_tasks_for = set()

        # Interpretes enhsp output to obtain the plan
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

                logger.info(action_string, "Planner")
                has_tasks_for.add(robot)

        # Make robots without instructions wait for other robots to finish
        # Mostly just required for the simple testing goals
        for id in robots.keys():
            if not id in has_tasks_for:
                logger.info(f"Robot {id} not assigned tasks", "Planner")
                actions.append((id, ["wait"]))

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
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ]
    problem = create_problem({1: robot})

    open("domain.pddl", "w").write(str(domain))
    # I'd prefer to keep this in-memory because of the frequent replanning,
    # but would need a way to get it through to the planner's container
    open("problem.pddl", "w").write(str(problem))

    plan = replan({1: robot})
    print("\n".join([action[0] for action in plan]))
