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
from pddl.core import Domain, Problem, Formula, Metric
from pddl.action import Action
from pddl.requirements import Requirements
import asyncio
from datetime import datetime
import logger
from recipes import recipe_ingredients, recipes, items_list, stack_size
from robot import Robot

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

cost_function = NumericFunction("cost", robot_variable)

def create_domain() -> Domain:
    robot = robot_variable
    actions = []

    # Inventory slot usage
    ####################

    slots_used_non_stackable = None
    for item in non_stackable_items_functions.keys():
        slots_used_non_stackable = Plus(Minus(slots_used_non_stackable, NumericValue(0)), non_stackable_items_functions[item](robot)) \
            if slots_used_non_stackable is not None else non_stackable_items_functions[item](robot)
        
    slots_used_full = None
    for item in full_stack_functions.keys():
        slots_used_full = Plus(Minus(slots_used_full, NumericValue(0)), full_stack_functions[item](robot)) \
            if slots_used_full is not None else full_stack_functions[item](robot)

    actions.append(Action(
        "update_stack_usage",
        parameters=[robot],
        precondition=And(should_update_item_stacks(robot)),
        effect=And(
            Not(should_update_item_stacks(robot)),

            Increase(inventory_slots_used_function(robot), Plus(Minus(slots_used_non_stackable, NumericValue(0)), Minus(slots_used_full, NumericValue(0)))),

            And(
                # Unpack full stacks
                *[effects.When(And(
                    LesserThan(partial_stack_functions[item](robot), NumericValue(0)),
                    GreaterThan(full_stack_functions[item](robot), NumericValue(0)),
                ), And(
                    Decrease(full_stack_functions[item](robot), NumericValue(1)),
                    Increase(partial_stack_functions[item](robot), NumericValue(stack_size[item])),
                    # Stack usage not changed in this case
                )) for item in full_stack_functions.keys()],

                # Condense full stacks
                *[effects.When(And(
                    GreaterThan(partial_stack_functions[item](robot), NumericValue(stack_size[item])),
                ), And(
                    Increase(full_stack_functions[item](robot), NumericValue(1)),
                    Increase(partial_stack_functions[item](robot), NumericValue(stack_size[item])),
                    # Handle the event where the partial stack contained exactly the stack size in the next group
                )) for item in full_stack_functions.keys()],

                # Detect and count partial stacks
                *[effects.When(And(
                    GreaterThan(partial_stack_functions[item](robot), NumericValue(0)),
                    LesserThan(partial_stack_functions[item](robot), NumericValue(stack_size[item])),
                ), And(
                    Increase(inventory_slots_used_function(robot), NumericValue(1)),
                )) for item in full_stack_functions.keys()],
            )
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
            crafting_effects.append(Increase(inventory_slots_used_function(robot), NumericValue(1)))

        # Consume crafting ingredients
        for ingredient, amount in current_recipe.items():
            ingredient_can_stack = stack_size[ingredient] > 1
            if ingredient_can_stack:
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
                effect=And(
                    should_update_item_stacks,
                    Assign(inventory_slots_used_function(robot), NumericValue(0)),
                    *crafting_effects,
                    Increase(cost_function(robot), NumericValue(1))
                ),
            )
        )

    for ore, cooked in [("iron_ore", "iron"), ("gold_ore", "gold"), ("raw_circuit", "circuit")]:
        # Smelting 8 items at a time makes efficient use of fuel
        actions.append(Action(
            f"smelt_8_{ore}",
            parameters=[robot],
            precondition=And(
                Or(
                    GreaterEqualThan(partial_stack_functions["coal"](robot), NumericValue(1)),
                    GreaterEqualThan(full_stack_functions["coal"](robot), NumericValue(1))
                ),
                Or(
                    GreaterEqualThan(partial_stack_functions[ore](robot), NumericValue(8)),
                    GreaterEqualThan(full_stack_functions[ore](robot), NumericValue(1))
                ),
                GreaterEqualThan(partial_stack_functions["furnace"](robot), NumericValue(1))
                ),
            effect=And(
                Decrease(partial_stack_functions[ore](robot), NumericValue(8)),
                Increase(partial_stack_functions[cooked](robot), NumericValue(8)),
                Decrease(partial_stack_functions["coal"](robot), NumericValue(1)),
                Increase(cost_function(robot), NumericValue(1)),
                Assign(inventory_slots_used_function(robot), NumericValue(0)),
                should_update_item_stacks
            )
        ))

        # In the event that we don't have enough unprocessed items, allow the fuel ticks to be wasted
        actions.append(Action(
            f"smelt_partial_{ore}",
            parameters=[robot],
            precondition=And(
                Or(
                    GreaterEqualThan(partial_stack_functions["coal"](robot), NumericValue(1)),
                    GreaterEqualThan(full_stack_functions["coal"](robot), NumericValue(1))
                ),
                GreaterThan(partial_stack_functions[ore](robot), NumericValue(0)),
                LesserThan(partial_stack_functions[ore](robot), NumericValue(8)),
                EqualTo(full_stack_functions[ore](robot), NumericValue(0)),
                GreaterEqualThan(partial_stack_functions["furnace"](robot), NumericValue(1))
            ),
            effect=And(
                Decrease(partial_stack_functions["coal"](robot), NumericValue(1)),
                Increase(partial_stack_functions[cooked](robot), partial_stack_functions[ore](robot)),
                Assign(partial_stack_functions[ore](robot), NumericValue(0)),
                Decrease(inventory_slots_used_function(robot), NumericValue(1)),
                Increase(cost_function(robot), NumericValue(2))
            )
        ))

    # Drop items on the ground to open up inventory space
    for item in items_list:
        if stack_size[item] > 1:
            # Stackable items (Can discard either a full stack or the partial stack)
            actions.append(Action(
                f"discard_partial_{item}",
                parameters=[robot],
                precondition=And(
                    Not(should_update_item_stacks(robot)),
                    GreaterThan(partial_stack_functions[item](robot), NumericValue(0)),
                ),
                effect=And(
                    Assign(partial_stack_functions[item](robot), NumericValue(0)),
                    Decrease(inventory_slots_used_function(robot), NumericValue(1)),
                    Increase(cost_function(robot), NumericValue(3))
                ),
            ))
            actions.append(Action(
                f"discard_stack_{item}",
                parameters=[robot],
                precondition=And(
                    Not(should_update_item_stacks(robot)),
                    EqualTo(partial_stack_functions[item](robot), NumericValue(0)),
                    GreaterThan(full_stack_functions[item](robot), NumericValue(0)),
                ),
                effect=And(
                    Decrease(full_stack_functions[item](robot), NumericValue(1)),
                    Decrease(inventory_slots_used_function(robot), NumericValue(1)),
                    Increase(cost_function(robot), NumericValue(10))
                ),
            ))
        else:
            # Non stackable items
            actions.append(Action(
                f"discard_one_{item}",
                parameters=[robot],
                precondition=And(
                    Not(should_update_item_stacks(robot)),
                    GreaterThan(non_stackable_items_functions[item](robot), NumericValue(0)),
                ),
                effect=And(
                    Decrease(non_stackable_items_functions[item](robot), NumericValue(1)),
                    Decrease(inventory_slots_used_function(robot), NumericValue(1)),
                    Increase(cost_function(robot), NumericValue(5))
                )
            ))


    domain = Domain(
        "OpenComputersDomain",
        requirements=[Requirements.TYPING, Requirements.ACTION_COSTS, Requirements.NUMERIC_FLUENTS, Requirements.NEG_PRECONDITION, Requirements.DIS_PRECONDITION],
        actions=actions,
        functions={function: None for function_list in [
            full_stack_functions.values(),
            partial_stack_functions.values(),
            non_stackable_items_functions.values(),
            [inventory_size_function, inventory_slots_used_function, cost_function]
        ] for function in function_list},
        types=types,
        predicates=[should_update_item_stacks] #+ list(should_update_item.values())
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


    total_cost = None
    for robot in robot_objects.values():
        total_cost = Plus(cost_function(robot), Minus(total_cost, NumericValue(0))) \
                     if total_cost is not None else \
                     cost_function(robot)

    max_robot_id = max(robots.keys())
    problem = Problem(
        "OpenComputersProblem",
        domain=create_domain(),
        objects=robot_objects.values(),
        requirements=[Requirements.TYPING, Requirements.ACTION_COSTS, Requirements.NUMERIC_FLUENTS, Requirements.NEG_PRECONDITION, Requirements.DIS_PRECONDITION],
        init=initial_state,
        # Placeholder goal for testing output files
        goal=And(
                GreaterEqualThan(non_stackable_items_functions["diamond_pickaxe"](robot_objects[max_robot_id]), NumericValue(1)),
                GreaterEqualThan(partial_stack_functions["cpu_tier_3"](robot_objects[max_robot_id]), NumericValue(1)),
                # GreaterEqualThan(partial_stack_functions["crafting_table"](robot_objects[max_robot_id]), NumericValue(1)),
                # GreaterEqualThan(inventory_functions["case_tier_3"](robot_objects[3]), NumericValue(1)),
            ),
        metric=Metric(total_cost, Metric.MINIMIZE)
    )

    return problem


async def replan(robots: dict[int, Robot]) -> list[tuple[int, list[str]]]:
    """
    Determine which actions each robot should taek to contrstruct a new robot.

    :param robots: All connected robots, with up to date inventories and empty action queues.
    """
    problem = create_problem(robots)
    open("problem.pddl", "w").write(str(problem))

    async def run_planner():
        process = await asyncio.create_subprocess_shell(
            "planutils run enhsp \"-o domain.pddl\" \"-f problem.pddl\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return stdout.decode()

    start_time = datetime.now()
    output = await run_planner()

    end_time = datetime.now()
    duration = end_time - start_time

    if "Found Plan" in output:
        logger.info(f"Found plan in {duration.total_seconds():.2f} seconds", "Planner")

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
        logger.error(f"No solution found (Processed for {duration.total_seconds():.2f} seconds).", "Planner")
        return []


if __name__ == "__main__":
    domain = create_domain()

    robot = Robot(1)
    # robot.inventory = [
    #     None,
    #     ("plank", 8),
    #     ("diamond", 3),
    #     None,
    #     None, 
    #     ("cpu_tier_3", 63),
    #     None,
    #     None,
    #     None,
    #     None,
    #     None,
    #     None,
    #     None,
    # ]

    robot.inventory = [
        None,
        ("plank", 43),
        ("diamond", 23),
        None,
        None, 
        ("iron", 50),
        ("redstone", 50),
        ("gold", 50),
        ("cobblestone", 50),
        ("alu", 4),
        ("control_unit", 4),
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

    
    plan = asyncio.run(replan({1: robot}))
    # replan function logs actions taken to terminal