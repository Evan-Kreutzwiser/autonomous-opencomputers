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
    Plus,
    Minus,
)
from pddl.core import Domain, Problem, Metric
from pddl.action import Action
from pddl.requirements import Requirements
import asyncio
from datetime import datetime
import logger
from recipes import recipe_ingredients, recipes, items_list, stack_size
from robot import Robot

# Number of slots completely filled with a specific item.
full_stack_functions = {
    item: NumericFunction(f"robot_full_stacks_of_{item}")()
    for item in items_list
    if stack_size[item] > 1
}
# There will only ever be one partial stack of an item at a time.
# Partial stacks are automatically consolidated in-game by the robot after
# actions that may cause multiple to exist.
partial_stack_functions = {
    item: NumericFunction(f"robot_partial_stack_size_{item}")()
    for item in items_list
    if stack_size[item] > 1
}
non_stackable_items_functions = {
    item: NumericFunction(f"robot_single_stacks_{item}")()
    for item in items_list
    if stack_size[item] == 1
}

# Inventory size is impacted by the number of inventory upgrades installed (16 slots per upgrade)
inventory_size_function = NumericFunction("robot_inventory_size")()
inventory_slots_used_function = NumericFunction("robot_inventory_slots_used")()

should_update_item = {item: Predicate(f"should_update_{item}")() for item in full_stack_functions.keys()}
should_update_item_stacks = Predicate("should_update_item_stacks")()

cost_function = NumericFunction("cost")()

desired_ore_predicates = {ore: Predicate(f"needs_{ore}")() for ore in ["coal", "iron", "gold", "redstone", "diamond"] }

def create_domain() -> Domain:
    actions = []

    # Inventory slot usage
    ####################

    slots_used_non_stackable = None
    for item in non_stackable_items_functions.keys():
        slots_used_non_stackable = Plus(Minus(slots_used_non_stackable, NumericValue(0)), non_stackable_items_functions[item]) \
            if slots_used_non_stackable is not None else non_stackable_items_functions[item]
        
    slots_used_full = None
    for item in full_stack_functions.keys():
        slots_used_full = Plus(Minus(slots_used_full, NumericValue(0)), full_stack_functions[item]) \
            if slots_used_full is not None else full_stack_functions[item]

    actions.append(Action(
        "update_stack_usage",
        parameters=[],
        precondition=And(should_update_item_stacks),
        effect=And(
            Not(should_update_item_stacks),

            Increase(inventory_slots_used_function, Plus(Minus(slots_used_non_stackable, NumericValue(0)), Minus(slots_used_full, NumericValue(0)))),

            And(
                # Unpack full stacks
                *[effects.When(And(
                    LesserThan(partial_stack_functions[item], NumericValue(0)),
                    GreaterThan(full_stack_functions[item], NumericValue(0)),
                ), And(
                    Decrease(full_stack_functions[item], NumericValue(1)),
                    Increase(partial_stack_functions[item], NumericValue(stack_size[item])),
                    # Stack usage not changed in this case
                )) for item in full_stack_functions.keys()],

                # Condense full stacks
                *[effects.When(And(
                    GreaterThan(partial_stack_functions[item], NumericValue(stack_size[item])),
                ), And(
                    Increase(full_stack_functions[item], NumericValue(1)),
                    Increase(partial_stack_functions[item], NumericValue(stack_size[item])),
                    # Handle the event where the partial stack contained exactly the stack size in the next group
                )) for item in full_stack_functions.keys()],

                # Detect and count partial stacks
                *[effects.When(And(
                    GreaterThan(partial_stack_functions[item], NumericValue(0)),
                    LesserThan(partial_stack_functions[item], NumericValue(stack_size[item])),
                ), And(
                    Increase(inventory_slots_used_function, NumericValue(1)),
                )) for item in full_stack_functions.keys()],
            )
        )))

    # Crafting
    #
    # Auto generate actions from recipe data
    ####################

    has_9_free_slots = GreaterEqualThan(Minus(inventory_size_function, inventory_slots_used_function), NumericValue(9))

    for item, current_recipe in recipe_ingredients.items():
        recipe_preconditions = []
        for ingredient, amount in current_recipe.items():
            ingredient_can_stack = stack_size[ingredient] > 1
            # If a full stack of the ingredient is present, the partial stack is allowed to momentarily go negative.
            # It will be replenished by the update_derived_values action from a full stack.
            if ingredient_can_stack:
                recipe_preconditions.append(Or(
                        GreaterEqualThan(partial_stack_functions[ingredient], NumericValue(amount)),
                        GreaterEqualThan(full_stack_functions[ingredient], NumericValue(1))
                    ))
            else:
                recipe_preconditions.append(
                    GreaterEqualThan(non_stackable_items_functions[ingredient], NumericValue(amount))
                )

        crafting_effects = []
        # Add the output item to this robot's inventory
        if stack_size[item] > 1:
            crafting_effects.append(Increase(partial_stack_functions[item], NumericValue(recipes[item]["output"])))
        else:
            crafting_effects.append(Increase(non_stackable_items_functions[item], NumericValue(1)))
            crafting_effects.append(Increase(inventory_slots_used_function, NumericValue(1)))

        # Consume crafting ingredients
        for ingredient, amount in current_recipe.items():
            ingredient_can_stack = stack_size[ingredient] > 1
            if ingredient_can_stack:
                crafting_effects.append(Decrease(partial_stack_functions[ingredient], NumericValue(amount)))
            else:
                crafting_effects.append(Decrease(non_stackable_items_functions[ingredient], NumericValue(amount))) 
                crafting_effects.append(Decrease(inventory_slots_used_function, NumericValue(amount)))

        actions.append(
            Action(
                f"craft_{item}",
                parameters=[],
                precondition=And(
                    Not(should_update_item_stacks),
                    has_9_free_slots,
                    *recipe_preconditions,
                ),
                effect=And(
                    should_update_item_stacks,
                    Assign(inventory_slots_used_function, NumericValue(0)),
                    *crafting_effects,
                    Increase(cost_function, NumericValue(1))
                ),
            )
        )

    for ore, cooked in [("iron_ore", "iron"), ("gold_ore", "gold"), ("raw_circuit", "circuit")]:
        # Smelting 8 items at a time makes efficient use of fuel
        actions.append(Action(
            f"smelt_8_{ore}",
            parameters=[],
            precondition=And(
                Or(
                    GreaterEqualThan(partial_stack_functions["coal"], NumericValue(1)),
                    GreaterEqualThan(full_stack_functions["coal"], NumericValue(1))
                ),
                Or(
                    GreaterEqualThan(partial_stack_functions[ore], NumericValue(8)),
                    GreaterEqualThan(full_stack_functions[ore], NumericValue(1))
                ),
                GreaterEqualThan(partial_stack_functions["furnace"], NumericValue(1)),
                # Require a free slot for result
                GreaterEqualThan(Minus(inventory_size_function, inventory_slots_used_function), NumericValue(1))
                ),
            effect=And(
                Decrease(partial_stack_functions[ore], NumericValue(8)),
                Increase(partial_stack_functions[cooked], NumericValue(8)),
                Decrease(partial_stack_functions["coal"], NumericValue(1)),
                Increase(cost_function, NumericValue(1)),
                Assign(inventory_slots_used_function, NumericValue(0)),
                should_update_item_stacks
            )
        ))

        # In the event that we don't have enough unprocessed items, allow the fuel ticks to be wasted
        actions.append(Action(
            f"smelt_partial_{ore}",
            parameters=[],
            precondition=And(
                Or(
                    GreaterEqualThan(partial_stack_functions["coal"], NumericValue(1)),
                    GreaterEqualThan(full_stack_functions["coal"], NumericValue(1))
                ),
                GreaterThan(partial_stack_functions[ore], NumericValue(0)),
                LesserThan(partial_stack_functions[ore], NumericValue(8)),
                EqualTo(full_stack_functions[ore], NumericValue(0)),
                GreaterEqualThan(partial_stack_functions["furnace"], NumericValue(1))
                # Does not require a free slot because the action already empties one, which it will reuse
            ),
            effect=And(
                Decrease(partial_stack_functions["coal"], NumericValue(1)),
                Increase(partial_stack_functions[cooked], partial_stack_functions[ore]),
                Assign(partial_stack_functions[ore], NumericValue(0)),
                should_update_item_stacks,
                Increase(cost_function, NumericValue(2))
            )
        ))

    # Drop items on the ground to open up inventory space
    # Components used to build robots are not allowed to be dropped
    dropable_items = [i for i in items_list if i not in [
        "assembler", "cpu_tier_1", "cpu_tier_3", "ram_tier_1", "ram_tier_2", "ram_tier_3",
        "geolyzer", "internet_card", "crafting_upgrade", "inventory_upgrade", "inventory_controller",
        "floppy_disk_drive", "floppy_disk", "eeprom", "robot", "case_tier_1", "case_tier_3"
        ]]
    for item in dropable_items:
        if stack_size[item] > 1:
            # Stackable items (Can discard either a full stack or the partial stack)
            actions.append(Action(
                f"discard_partial_{item}",
                parameters=[],
                precondition=And(
                    Not(should_update_item_stacks),
                    GreaterThan(partial_stack_functions[item], NumericValue(0)),
                ),
                effect=And(
                    Assign(partial_stack_functions[item], NumericValue(0)),
                    Decrease(inventory_slots_used_function, NumericValue(1)),
                    Increase(cost_function, NumericValue(3))
                ),
            ))
            actions.append(Action(
                f"discard_stack_{item}",
                parameters=[],
                precondition=And(
                    Not(should_update_item_stacks),
                    EqualTo(partial_stack_functions[item], NumericValue(0)),
                    GreaterThan(full_stack_functions[item], NumericValue(0)),
                ),
                effect=And(
                    Decrease(full_stack_functions[item], NumericValue(1)),
                    Decrease(inventory_slots_used_function, NumericValue(1)),
                    Increase(cost_function, NumericValue(10))
                ),
            ))
        else:
            # Non stackable items
            actions.append(Action(
                f"discard_one_{item}",
                parameters=[],
                precondition=And(
                    Not(should_update_item_stacks),
                    GreaterThan(non_stackable_items_functions[item], NumericValue(0)),
                ),
                effect=And(
                    Decrease(non_stackable_items_functions[item], NumericValue(1)),
                    Decrease(inventory_slots_used_function, NumericValue(1)),
                    Increase(cost_function, NumericValue(5))
                )
            ))


    # Select which resources the mine action should prioritize
    # Not used when mining with stone pickaxes
    for ore in ["coal", "iron", "gold", "redstone", "diamond"]:
        actions.append(Action(
            f"should_mine_{ore}",
            parameters=[],
            precondition=And(
                Not(should_update_item_stacks),
                Not(desired_ore_predicates[ore]),
                Or(
                    GreaterThan(non_stackable_items_functions["iron_pickaxe"], NumericValue(0)),
                    GreaterThan(non_stackable_items_functions["diamond_pickaxe"], NumericValue(0))
                )
            ),
            effect=And(desired_ore_predicates[ore])
        ))

    actions.append(Action(
        "mine",
        parameters=[],
        precondition=And(
            Not(should_update_item_stacks),
            # Require free inventory space for collected resources
            GreaterEqualThan(Minus(inventory_size_function, inventory_slots_used_function), NumericValue(7)),
            GreaterThan(non_stackable_items_functions["stone_pickaxe"], NumericValue(0)),
            Or(
                GreaterThan(non_stackable_items_functions["iron_pickaxe"], NumericValue(0)),
                GreaterThan(non_stackable_items_functions["diamond_pickaxe"], NumericValue(0))
            ),
            Or(*[desired_ore_predicates[ore] for ore in desired_ore_predicates.keys()]),
            
        ),
        effect=And(
            should_update_item_stacks,
            Increase(cost_function, NumericValue(15)),
            # Remove the 2 pickaxes used to mine. Diamond pickaxes have priority over iron.
            Decrease(non_stackable_items_functions["stone_pickaxe"], NumericValue(1)),
            effects.When(
                EqualTo(non_stackable_items_functions["diamond_pickaxe"], NumericValue(0)),
                Decrease(non_stackable_items_functions["iron_pickaxe"], NumericValue(1))
            ),
            effects.When(
                GreaterThan(non_stackable_items_functions["diamond_pickaxe"], NumericValue(0)),
                Decrease(non_stackable_items_functions["diamond_pickaxe"], NumericValue(1))
            ),
            *[
                effects.When(
                    desired_ore_predicates[ore],
                    And(
                        Increase(full_stack_functions[ore], NumericValue(1)),
                        Not(desired_ore_predicates[ore])
                    )
                )
                for ore in desired_ore_predicates.keys()
            ]
        )
    ))

    # Variant of mining action which limits the robot to the area where ores requiring an iron pickaxe don't generate
    actions.append(Action(
        "mine_near_surface",
        parameters=[],
        precondition=And(
            Not(should_update_item_stacks),
            # Require free inventory space for collected resources
            GreaterEqualThan(Minus(inventory_size_function, inventory_slots_used_function), NumericValue(4)),
            GreaterEqualThan(non_stackable_items_functions["stone_pickaxe"], NumericValue(2)),
        ),
        effect=And(
            should_update_item_stacks,
            Increase(cost_function, NumericValue(10)),
            # Remove the 2 pickaxes used to mine. Diamond pickaxes have priority over iron.
            Decrease(non_stackable_items_functions["stone_pickaxe"], NumericValue(2)),
            Increase(full_stack_functions["cobblestone"], NumericValue(2)),
            # I don't expect a stone pickaxe to gather nearly this much, but it'll trigger a replan anyway
            Increase(full_stack_functions["coal"], NumericValue(1)),
            Increase(full_stack_functions["iron"], NumericValue(1)),
        )
    ))

    # 
    actions.append(Action(
        "collect_cobblestone",
        parameters=[],
        precondition=And(
            Not(should_update_item_stacks),
            # Require free inventory space for collected resources
            GreaterEqualThan(Minus(inventory_size_function, inventory_slots_used_function), NumericValue(1)),
            GreaterEqualThan(non_stackable_items_functions["wooden_pickaxe"], NumericValue(2)),
            # Limit when this can be called to reduce branching factor
            EqualTo(full_stack_functions["cobblestone"], NumericValue(0)),
            LesserThan(partial_stack_functions["cobblestone"], NumericValue(6)) # Only do this if other mining tasks are impossible
        ),
        effect=And(
            should_update_item_stacks,
            Increase(cost_function, NumericValue(10)),
            # Remove the 2 pickaxes used to mine. Diamond pickaxes have priority over iron.
            Decrease(non_stackable_items_functions["stone_pickaxe"], NumericValue(2)),
            Increase(full_stack_functions["cobblestone"], NumericValue(1)),
        )
    ))
    
    domain = Domain(
        "OpenComputersDomain",
        requirements=[Requirements.CONDITIONAL_EFFECTS, Requirements.ACTION_COSTS, Requirements.NUMERIC_FLUENTS, Requirements.NEG_PRECONDITION, Requirements.DIS_PRECONDITION],
        actions=actions,
        functions={function: None for function_list in [
            full_stack_functions.values(),
            partial_stack_functions.values(),
            non_stackable_items_functions.values(),
            [inventory_size_function, inventory_slots_used_function, cost_function]
        ] for function in function_list},
        predicates=[should_update_item_stacks, *desired_ore_predicates.values()]
    )

    return domain


def create_problem(robot: Robot) -> Problem:
    """
    Create a PDDL problem from a dictionary of robots and their inventories.
    
    :param robots: A dictionary of robot ids and their inventories, 
                   represented as a dictionary of item names and quantities.
    :return: A PDDL Problem with the goal of creating a new robot.
    """
    initial_state = []

    inventory = robot.count_items()
    for item, quantity in inventory.items():
        if item not in items_list:
            logger.info(f"Warning: Robot has item \"{item}\" (x{quantity}), which is not recognized by the planner!", robot.id)
        elif stack_size[item] > 1:
            initial_state.append(EqualTo(full_stack_functions[item], NumericValue(quantity // stack_size[item])))
            initial_state.append(EqualTo(partial_stack_functions[item], NumericValue(quantity % stack_size[item])))
        else:
            initial_state.append(EqualTo(non_stackable_items_functions[item], NumericValue(quantity)))

    # All items not listed in the inventory are assumed to be 0
    for absent_item in [item for item in items_list if item not in inventory.keys()]:
        if stack_size[absent_item] > 1:
            initial_state.append(EqualTo(full_stack_functions[absent_item], NumericValue(0)))
            initial_state.append(EqualTo(partial_stack_functions[absent_item], NumericValue(0)))
        else:
            initial_state.append(EqualTo(non_stackable_items_functions[absent_item], NumericValue(0)))

    print(f"Inventory Size: {len(robot.inventory)-1}")
    initial_state.append(EqualTo(inventory_size_function, NumericValue(len(robot.inventory) - 1)))

    slots_used = len([1 for item in robot.inventory if item is not None])
    initial_state.append(EqualTo(inventory_slots_used_function, NumericValue(slots_used)))
    initial_state.append(Not(should_update_item_stacks))

    for predicate in desired_ore_predicates.values():
        initial_state.append(Not(predicate))

    problem = Problem(
        "OpenComputersProblem",
        domain=create_domain(),
        requirements=[Requirements.CONDITIONAL_EFFECTS, Requirements.ACTION_COSTS, Requirements.NUMERIC_FLUENTS, Requirements.NEG_PRECONDITION, Requirements.DIS_PRECONDITION],
        init=initial_state,
        # Placeholder goal for testing output files
        goal=And(
                GreaterEqualThan(non_stackable_items_functions["diamond_pickaxe"], NumericValue(1)),
                GreaterEqualThan(partial_stack_functions["cpu_tier_3"], NumericValue(1)),
                # GreaterEqualThan(partial_stack_functions["crafting_table"](robot_objects[max_robot_id]), NumericValue(1)),
                # GreaterEqualThan(inventory_functions["case_tier_3"](robot_objects[3]), NumericValue(1)),
            ),
        metric=Metric(cost_function, Metric.MINIMIZE)
    )

    return problem


async def replan(robot: Robot) -> list[str]:
    """
    Determine which actions each robot should taek to contrstruct a new robot.

    :param robots: All connected robots, with up to date inventories and empty action queues.
    """
    problem = create_problem(robot)
    open("problem.pddl", "w").write(str(problem))

    start_time = datetime.now()
    process = await asyncio.create_subprocess_shell(
            "planutils run enhsp \"-o domain.pddl\" \"-f problem.pddl\"",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
    stdout, stderr = await process.communicate()
    output = stdout.decode()

    end_time = datetime.now()
    duration = end_time - start_time

    if "Found Plan" in output:
        logger.info(f"Found plan in {duration.total_seconds():.2f} seconds", "Planner")

        solution = output.split("Found Plan")[1]

        lines = solution.split("\n")
        actions = []

        # Interpretes ENHSP's output to obtain the plan
        # Extraction will need changes if a different planner is used
        for line in lines:
            if ": (" in line:
                # Extract the action from the surrounding text
                action_string = line.split(": (")[1].split(")")[0]
                actions.append(action_string)
                logger.info(action_string, "Planner")

        # Make robots without instructions wait for other robots to finish
        # Mostly just required for the simple testing goals
        if len(actions) == 0:
            logger.info(f"Robot {robot.id} not assigned tasks", "Planner")
            actions.append("wait")

        return actions
    else:
        logger.error(f"No solution found (Processed for {duration.total_seconds():.2f} seconds).", "Planner")
        logger.info(stderr.decode(), "Planner")
        return []


if __name__ == "__main__":
    """
    This block is intended for debugging pddl generation during development, by running this file directly instead of main.
    """
    domain = create_domain()

    robot = Robot(1)
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
    problem = create_problem(robot)

    open("domain.pddl", "w").write(str(domain))
    # I'd prefer to keep this in-memory because of the frequent replanning,
    # but would need a way to get it through to the planner's container
    open("problem.pddl", "w").write(str(problem))

    
    plan = asyncio.run(replan(robot))
    # replan function logs actions taken to terminal