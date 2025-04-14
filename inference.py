from math import log10
from pgmpy.models import DiscreteBayesianNetwork
from pgmpy.factors.discrete.CPD import TabularCPD
from itertools import product
from pgmpy.inference import VariableElimination

# All of the y coordinates taken into account by the bayes net.
# No point in accounting for below y=4, since bedrock gets in the way
y_levels = [f"{i}" for i in range(4, 51)]


def _normalize_weights(array: list) -> list:
    total = sum(array)
    return [item / total for item in array]


def _build_ore_probability_table(needs_coal: bool, needs_iron: bool, needs_gold: bool, 
                                needs_redstone: bool, needs_diamond: bool) -> DiscreteBayesianNetwork:

    net = DiscreteBayesianNetwork()

    # Every possible y value will be tested
    net.add_edge("target_y", "robot_y")
    net.add_edge("robot_y", "block_is_replaceable")
    for ore in ["coal", "iron", "gold", "redstone", "lapis", "diamond"]:
        net.add_edge("robot_y", ore)
        net.add_edge("block_is_replaceable", ore)
        net.add_edge(ore, "ore_is_useful")


    y_level_cpd = TabularCPD(variable="target_y",
                             state_names={"target_y": y_levels},
                             values=[[1/len(y_levels)]] * len(y_levels),
                             variable_card=len(y_levels))

    # Robot can deviate from optimal y level, but should spend more time near that value if trained correctly
    y_level_deviation_cpd = TabularCPD(variable="robot_y",
                state_names={"robot_y": y_levels, "target_y": y_levels},
                evidence=["target_y"],
                # Each column must add up to one.
                # Generate a pointed curve that distributes the probability of the robot being at a particular height around the target.
                # This will allow the bayes net to consider the entire vertical range the robot may travel within at once. 
                values=[
                    list(row)
                    for row in   
                    zip(*[ _normalize_weights([2**(-1 * abs(y - other_y) / 4) for other_y in range(4,51)]) for y in range(4, 51)])
                ],
                variable_card=len(y_levels),
                evidence_card=[len(y_levels)]
                )

    # Distribution data obtained by scanning a 190x190 chunk area of the world 
    # (2.36 billion blocks!) using Just Enough Resources' /jer_profile command

    # Data covers y [4, 50]
    stone_distribution = [0.6077037, 0.7576785, 0.75672805, 0.75576496, 0.7545372, 0.75285023, 0.75158334, 0.75071996, 0.749829, 0.7495794, 0.7512247, 0.7533533, 0.7529744, 0.7523656, 0.7512067, 0.75028884, 0.7503957, 0.750659, 0.7504439, 0.7498299, 0.7492808, 0.74931055, 0.7497154, 0.74971235, 0.7490319, 0.7431343, 0.7295102, 0.70669425, 0.6987211, 0.68921417, 0.6791663, 0.66926473, 0.6586811, 0.64749664, 0.63739234, 0.62882334, 0.62529266, 0.6226649, 0.6197728, 0.6151598, 0.6078381, 0.59609854, 0.58099514, 0.56244713, 0.5008914, 0.50078267, 0.5002934]
    
    coal_distribution = [0.010294597, 0.012933377, 0.01276096, 0.012797417, 0.012949327, 0.013002495, 0.012830838, 0.012874349, 0.012944336, 0.012968425, 0.013009114, 0.01282194, 0.01279872, 0.012808268, 0.012635525, 0.012638563, 0.01265918, 0.0124768885, 0.012380534, 0.012479275, 0.012664388, 0.0126976995, 0.012662326, 0.012603516, 0.01258724, 0.012515951, 0.0124018015, 0.0119019095, 0.011763454, 0.011582465, 0.01137793, 0.011219727, 0.011121419, 0.010969726, 0.010809896, 0.010479167, 0.010457139, 0.010566515, 0.010409071, 0.010378798, 0.010336697, 0.01009809, 0.009709202, 0.009449652, 0.008504123, 0.008467882, 0.008406467]        
    iron_distribution = [0.0065503474, 0.008143663, 0.008125434, 0.008115235, 0.008093099, 0.008087131, 0.007998806, 0.008023546, 0.008024957, 0.007940972, 0.007948459, 0.008082357, 0.008070638, 0.007932942, 0.008031901, 0.0079934895, 0.008037435, 0.007999023, 0.007858398, 0.00790408, 0.007975261, 0.007938802, 0.007894531, 0.007944444, 0.007936306, 0.007823025, 0.00767079, 0.007390625, 0.0073261717, 0.007191623, 0.007183702, 0.0070706382, 0.0069932723, 0.0068565537, 0.006869683, 0.0066986764, 0.006562283, 0.0064863283, 0.0065120445, 0.0063182507, 0.006342882, 0.0061929254, 0.006088108, 0.0058511286, 0.005171007, 0.0051611327, 0.005294922]
    gold_distribution = [0.0013436415, 0.0016307508, 0.0016289062, 0.0016026476, 0.001571072, 0.0015585937, 0.001584961, 0.0016157769, 0.0016050347, 0.0015330946, 0.0016294487, 0.0016286892, 0.001571506, 0.0015211588, 0.001538303, 0.0015467665, 0.001585395, 0.0016103516, 0.0015882162, 0.0015813803, 0.0015775824, 0.0015491536, 0.0015571831, 0.0015669488, 0.0015240886, 0.0014356554, 0.0008158637, 0.00022612847, 8.9735244e-05, 7.671441e-05, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    diamond_distribution = [0.0009611545, 0.0012084418, 0.0011835938, 0.0011832683, 0.0011921658, 0.0011842448, 0.0012052951, 0.0012259114, 0.0011788195, 0.0010817057, 0.00059082033, 9.7873264e-05, 0.0]
    redstone_distribution = [0.0076826173, 0.009551215, 0.009431641, 0.009467773, 0.009530599, 0.009521375, 0.009644315, 0.009630642, 0.009543511, 0.0087910155, 0.004772461, 0.0007238498, 0.0]
    lapis_distribution = [0.00029144966, 0.00044574653, 0.0005157335, 0.00054144964, 0.0006308594, 0.00069173175, 0.0007355686, 0.0008128255, 0.00086317275, 0.0009120009, 0.0009561632, 0.00088986545, 0.00080707466, 0.00075531687, 0.00071614585, 0.00065570744, 0.00059461803, 0.0005249566, 0.00046961807, 0.0004097222, 0.0003343099, 0.0002873264, 0.00022265625, 0.00014811198, 8.344184e-05, 3.4613717e-05, 4.4487847e-06, 0.0]
    for distribution in [coal_distribution, iron_distribution, gold_distribution, diamond_distribution, redstone_distribution, lapis_distribution]:
        if len(distribution) < len(y_levels):
            distribution += [0] * (len(y_levels) - len(distribution))

    block_is_repalceable_cpd = TabularCPD(variable="block_is_replaceable",
                                          variable_card=2,
                                          state_names={"block_is_replaceable": ["True", "False"], "robot_y": y_levels},
                                          evidence=["robot_y"],
                                          evidence_card=[len(y_levels)],
                                          values=[stone_distribution, [1 - p for p in stone_distribution]])


    ore_cpds = []
    for ore, distribution in [("coal", coal_distribution), ("iron", iron_distribution), ("gold", gold_distribution), 
                              ("redstone", redstone_distribution), ("diamond", diamond_distribution), ("lapis", lapis_distribution)]:
        ore_cpds.append(TabularCPD(
            variable=ore,
            variable_card=2,
            state_names={ore: ["True", "False"], "block_is_replaceable": ["True", "False"], "robot_y": y_levels},
            evidence=["block_is_replaceable", "robot_y"],
            evidence_card=[2, len(y_levels)],
            values=[
                # Distribution represents chances per-block, but only for replaceable stone blocks. Chunks with less stone / more air will have fewer ores overall
                #   block is replaceable      | not replaceable
                distribution                  + [0]*len(y_levels),
                [1 - p for p in distribution] + [1]*len(y_levels)
            ]
        ))

    # If the block could be ANY of the undesirable ore types, the ore isn't useful, even if the probability says it may be one of the useful types
    # To be useful there must be a chance for it to be all of the requested ore types at that level
    is_useful = [1 if ((needs_coal and coal) or (not needs_coal and not coal)) and
                      ((needs_iron and iron) or (not needs_iron and not iron)) and
                      ((needs_gold and gold) or (not needs_gold and not gold)) and
                      ((needs_redstone and redstone) or (not needs_redstone and not redstone)) and
                      ((needs_diamond and diamond) or (not needs_diamond and not diamond)) and
                      not lapis # Never useful, but appears often enough at specific y levels to factor into probabilities
                 else 0
                 for coal, iron, gold, redstone, diamond, lapis in product([True, False], repeat=6)]
    
    ore_is_useful_cpd = TabularCPD(
        variable="ore_is_useful",
        variable_card=2,
        state_names={
            "ore_is_useful": ["True", "False"],
            "coal": ["True", "False"],
            "iron": ["True", "False"],
            "gold": ["True", "False"],
            "redstone": ["True", "False"],
            "diamond": ["True", "False"],
            "lapis": ["True", "False"]
        },
        evidence=["coal", "iron", "gold", "redstone", "diamond", "lapis"],
        evidence_card=[2, 2, 2, 2, 2, 2],
        values=[
            is_useful,
            [1 - p for p in is_useful]
        ]
    )

    net.add_cpds(y_level_cpd, y_level_deviation_cpd, block_is_repalceable_cpd, *ore_cpds, ore_is_useful_cpd)

    return net


def determine_optimal_depth(needs_coal: bool, needs_iron: bool, needs_gold: bool, 
                            needs_redstone: bool, needs_diamond: bool) -> int:
    net = _build_ore_probability_table(needs_coal, needs_iron, needs_gold, needs_redstone, needs_diamond)
    inference = VariableElimination(net)

    highest_probability = 0
    best_y_level = 4

    for y in y_levels:
        query_result = inference.query(variables=["ore_is_useful"], evidence={"target_y": y})
        useful_prob = query_result.values[0]  # Probability of ore_is_useful being True
        if useful_prob > highest_probability:
            highest_probability = useful_prob
            best_y_level = y

    return best_y_level
