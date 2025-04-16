# Autonomous OpenComputers

Grant autonomy to your OpenComputers robots, driving them to explore your world in search of the materials to replicate themselves. This is achieved by communicating with an external python server that does the number-crunching and planning, with a thin wrapper over various component apis running on the robot.

## Project Description

This project is my submission for the CISC 352 course project, which involves applying 3 AI methodologies from the course material to a topic of choice. The 3 areas chosen for this project are automated planning, probabilistic inference, and deep learning.

### Automated Planning

In the context of the course, automated planning revolves around the use of PDDL: the Planning Domain Definition Language. High-level planning around what resources to collect and what to craft and modelled with PDDL, and an external planner provides a series of actions to reach a defined goal. The high-level planned actions are queued up for each connected robot, and the robot executes the low-level behavior of individual actions independently of the larger plan. This combined with limited inventory space and the non-observable nature of exploration an open world leaves room for unexpected issues to arise, at which point the plan will be regenerated. To help keep the size of the explored state space under control in the planner, the task of crafting robot parts is split up such that the robot's goal at any given point is crafting a single item.

### Probabilistic Inference

A bayes net has been constructed from scans of a minecraft world to determine the probability of finding different ores at specific y levels. The network models the vertical range the robot is expected to travel within as a probability distribution to calculate the odds of finding ores around the entire area the robot can view. Samples are taken across the entire y axis to test the probability of finding the specific ores the robot intends to mine, factoring in the possibility of the robot accidentally mining ores it doesn't require, and selects the most fruitful y level as a target for the deep learning model.

Originally the plan included a system for behavior modelling using a bayes net to determine whether it is efficient for robots to meet up and exchange resources instead of spending that time mining, but this was unfortunately cut from the project due to the difficulty of determining the weights for the network,

### Deep Learning

Robots can mine underground for resources using a sort of "x-ray" view made possible by a built-in geolyzer. The geolyzer can produce (noisy) block hardness maps of 3d areas surrounding the robot, used see ores and caves through walls. Mining behavior is guided by a deep Q learning network (DQN) built using pytorch, which controls the movement of the robot and when it uses its pickaxe. It takes a 3d volume of the area around the robot at input, as well as its distance from the desired y coordinate selected by the bayes net described above.

The model is trained using unsupervised reinforcement learning, which takes place in a python simulation of underground minecraft world generation. It loosely mimics placement of ores and caves as well as the geolyzer's sensor noise, and allows the model to train significantly faster than it could in-game.

The current utility function encourages taking direct paths, avoiding breaking blocks unessecarily, and sticking close to the optimal y-level chosen by the probabilistic inference implementation.

## Installation

This project requires a linux system or container. Visit the [planutils](https://github.com/AI-Planning/planutils/tree/main) repo for information on how to create an appropriate docker container.

1. Clone the repository
```sh
git clone https://github.com/Evan-Kreutzwiser/autonomous-opencomputers.git
cd autonomous-opencomputers
```

2. Install dependencies
```sh
pip install -r requirements.txt
planutils setup
planutils install enhsp
```

3. Configure Minecraft

Download OpenComputers into a forge 1.12 Minecraft installation, either manually or using your choice of [Curseforge](https://www.curseforge.com/minecraft/mc-mods/opencomputers) or [Modrinth](https://modrinth.com/mod/opencomputers). Then, copy the `user.recipes` and `settings.conf` files into the `config/opencomputers` folder of your modded minecraft installation. If the folder doesn't exist, launch the game at least once or create it manually.

> [!NOTE]   
> Using these configuration files disable electricity usage for the whole mod, modify some recipes, and remove all filters on the internet card 

4. Construct First Robot

Once in game, you will need to create the first robot yourself. Using an assembler, combine:
- a tier 3 case
- a tier 3 CPU
- RAM (Required amount untested, but don't cheap out on it)
- an internet card
- a graphics card, screen, and keyboard for setup and troubleshooting
- a Lua BIOS EEPROM (Combine with a cobblestone to flash, recipe was modified)
- 4 inventory upgrades
- an inventory controller
- a crafting upgrade
- a geolyzer
- 2 floppy disk drives
- a floppy disk with OpenOS installed on it

**It is important to use all of the required parts**, as you cannot modify the robot after assembling it!

5. Launch Server and Client

Start the python server by running the following line in a terminal:
```sh
python main.py
```

A text-based UI with a terminal will open, informing you that the program is listening for robot connections on port 3000. Now it is time to copy the the Lua client to the robot. In the robot's OpenOS shell, enter:

```sh
wget -f http://localhost:8080/client client.lua
echo "return 1" > id.lua
```

The robot is now ready to connect with the server as robot #1. Any new robots it goes on to create will have automatically assigned IDs. Start the robot client by running:

```sh
client.lua
```

If everything is working correctly, the message `[1] Bot connected` will appear in the server terminal and the planner will start automatically!

## Miner Neural Network Training

To train a new instance of the DQN for the mining action, run `python main.py train`. During training the weights are periodically saved in `miner/checkpoints`, and `miner/model.pt` can be manually replaced with one of the generated files to update the network. Either restart the program or enter the command `reloadnn` in the TUI to refresh the model.

## Limitations

Due to the nature of the robots' hardware and the timeframe of this project, some special considerations have to be made in the configuration. Namely, custom recipes are provided for items that require paper, clay, or mob drops, and electricity consumption must be disabled. Additionally, OpenComputers has not officially been released for versions newer than 1.12, so that is the target game version of the project. Give the robot some logs to start with, because the robot is not yet capable of choping trees on its own.

The PDDL planner is invoked using [planutils](https://github.com/AI-Planning/planutils/tree/main), which limits the project to running on linux systems only - although planutils does include instructions for building docker containers
