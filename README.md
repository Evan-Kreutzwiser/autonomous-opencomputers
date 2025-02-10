# Autonomous OpenComputers

Grant autonomy to your OpenComputers robots, driving them to explore your world in search of the materials to replicate themselves. This is achieved by communicating with an external python server that does the number-crunching and planning, and allows the robots to work cooperatively towards their goals.

## Project Description

This project is my submission for the CISC 352 course project, which involves applying 3 AI methodologies from the course material to a topic of choice. The 3 chosen for this project are automated planning, probabilistic inference, and deep learning

### Automated Planning

In the context of the course, automated planning revolves around the use of PDDL: the Planning Domain Definition Language. High-level planning around what resources to collect and what to craft and modelled with PDDL, and an external planner provides a series of actions to reach a defined goal. The high-level planned actions are queued up for each connected robot, and the robot executes the low-level behavior of individual actions independently of the larger plan. This combined with limited inventory space and the non-deterministic nature of exploration leaves room for unexpected issues to arise, at which point the plan will be regenerated. 

### Probabilistic Inference

Not yet started. Probabilistic inference will be used in a behavior-modelling context to influence sharing between robots, based on how effective it is deemed to share vs. collecting resources independently in an environment that can't be completely observed.

### Deep Learning

Not yet started. The goal is to train an AI model using PyTorch to control robots when mining using volumetric block hardness scans from the geolyzer to locate ores and pathfind through caves. 

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
planutils install popf
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
- a hard drive with a copy of OpenOS installed using another computer (or install using a floppy disk)
- a graphics card, screen, and keyboard for setup and troubleshooting
- a Lua BIOS EEPROM (Combine with a manual to flash)
- 2 inventory upgrades
- an inventory controller
- a crafting upgrade
- a geolyzer
- a floppy disk drive

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

## Limitations

Due to the nature of the robots' hardware and the timeframe of this project, some special considerations have to be made in the configuration. Namely, custom recipes are provided for items that require paper, clay, or mob drops, and electricity consumption must be disabled. Additionally, OpenComputers has not officially been released for versions newer than 1.12, so that is the target game version of the project

The PDDL planner is invoke using [planutils](https://github.com/AI-Planning/planutils/tree/main), which limits the project to running on linux systems only - although planutils does include instructions for building docker containers
