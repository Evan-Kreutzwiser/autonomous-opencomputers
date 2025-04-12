"""
Testing ability to train / run model using PyTorch sample code.

Model's input space is a 25x25x25 view of the hardness of surrounding blocks,
and the action space is move or mine in any of the 4 cardinal directions, or up and down.
"""

from collections import deque, namedtuple
import random
import math
import matplotlib
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F
import os
from miner import world

is_ipython = 'inline' in matplotlib.get_backend()
if is_ipython:
    from IPython import display

plt.ion()

device = torch.device(
    "cuda" if torch.cuda.is_available() else
    "mps" if torch.backends.mps.is_available() else
    "cpu"
)

class DQN(nn.Module):
    def __init__(self, n_actions):
        super(DQN, self).__init__()
        self.conv1 = nn.Conv3d(1, 32, kernel_size=3, stride=1, padding=1)
        self.conv2 = nn.Conv3d(32, 64, kernel_size=3, stride=1, padding=1)
        self.conv3 = nn.Conv3d(64, 64, kernel_size=3, stride=1, padding=1)
        self.fc1 = nn.Linear(25 * 25 * 25, 512)
        self.fc2 = nn.Linear(512, 256)
        self.fc3 = nn.Linear(256, n_actions)

    def forward(self, x):
        x = F.relu(self.conv1(x))
        x = F.relu(self.conv2(x))
        x = F.relu(self.conv3(x))
        x = x.view(x.size(0), -1)
        x = F.relu(self.fc1(x))
        x = F.relu(self.fc2(x))
        x = self.fc3(x)
        x = x.mean(dim=0, keepdim=True)  # Average the 64 channels down to 1
        return x

Transition = namedtuple('Transition',
                        ('state', 'action', 'next_state', 'reward'))

class ReplayMemory():

    def __init__(self, capacity):
        self.memory = deque([], maxlen=capacity)

    def push(self, *args):
        """Save a transition"""
        self.memory.append(Transition(*args))

    def sample(self, batch_size):
        return random.sample(self.memory, batch_size)

    def __len__(self):
        return len(self.memory)


# Robot faces a direction and either mines or moves
n_actions = 6 + 6

# Instance utilized by the robot's mining action
robot_nn = DQN(n_actions).to(device)
has_loaded_weights = False

def load_model():
    """
    Load model.pt for use in the robot's mining action. 
    May be called multiple times to reload the model from disk.
    """
    # TODO: Error handling 
    global has_loaded_weights
    model_state = torch.load("miner/model.pt")
    robot_nn.load_state_dict(model_state)
    has_loaded_weights = True

def run_model_one_step(geolyzer_view: list[list[list[int]]], distance_from_target_y: int) -> tuple[str, bool]:
    """
    Use the DQN Model to select the next action a mining robot should take.

    Returns a string containing a direction (cardinal, up, or down), and bool 
    indicating whether the robot should mine. When the value is true the robot 
    should mine in the chosen direction, otherwise it should attempt to move in 
    that direction. The direction is absolute - the model does not know its local 
    heading, and the caller is responsible for conversion and rotation the robot.
    """

    if not has_loaded_weights:
        raise RuntimeError("No model loaded for NN")

    view_tensor = torch.tensor(geolyzer_view, dtype=torch.float32, device=device).unsqueeze(0)
    action = robot_nn(view_tensor).max(1).indices.view(1, 1)

    mapping = [
        "east", # +X
        "west", # -X
        "up", # +Y
        "down", # -Y
        "south", # +Z
        "north", # -Z
    ]

    # Actions 0-5 are navigation, 6-11 are mining
    return (mapping[action % 6], action >= 6)
    

# Model Training
################


def step_environment(world: world.World, robot_position: tuple, action: int):
    reward = 0.0
    mined_ore = False

    distance_to_ore = world.distance_to_nearest_ore(*robot_position)

    target_position = robot_position
    if action == 0 or action == 6:
        # positive X
        target_position = (robot_position[0] + 1, robot_position[1], robot_position[2])
    elif action == 1 or action == 7:
        # negative X
        target_position = (robot_position[0] - 1, robot_position[1], robot_position[2])
    elif action == 2 or action == 8:
        # positive Y
        target_position = (robot_position[0], robot_position[1] + 1, robot_position[2])
    elif action == 3 or action == 9:
        # negative Y
        target_position = (robot_position[0], robot_position[1] - 1, robot_position[2])
    elif action == 4 or action == 10:
        # positive Z
        target_position = (robot_position[0], robot_position[1], robot_position[2] + 1)
    elif action == 5 or action == 11:
        # negative Z
        target_position = (robot_position[0], robot_position[1], robot_position[2] - 1)


    new_position = robot_position

    if action >= 6:
        # Mine target
        target_block = world.sample_density(*target_position)
        world.dig(*target_position)
        if target_block == 3.0:
            reward = 1.0
            mined_ore = True
        elif target_block > 9999:
            reward = -0.5
        else:
            # Discourage swining pickaxe at air
            reward = -0.05
    else:
        # Move to target
        if world.sample_density(*target_position) > 0.0:
            # Discourage running into walls.
            reward = -0.5
        else:
            new_position = target_position

    observation = world.noisy_data_around(12, *new_position)

    new_distance_to_ore = world.distance_to_nearest_ore(*new_position)

    if new_distance_to_ore < distance_to_ore:
        reward += 0.5
    else:
        reward -= 0.1

    return new_position, observation, reward, mined_ore

# BATCH_SIZE is the number of transitions sampled from the replay buffer
# GAMMA is the discount factor as mentioned in the previous section
# EPS_START is the starting value of epsilon
# EPS_END is the final value of epsilon
# EPS_DECAY controls the rate of exponential decay of epsilon, higher means a slower decay
# TAU is the update rate of the target network
# LR is the learning rate of the ``AdamW`` optimizer
BATCH_SIZE = 1
GAMMA = 0.99
EPS_START = 0.9
EPS_END = 0.05
EPS_DECAY = 1000
TAU = 0.005
LR = 1e-4

policy_net = DQN(n_actions).to(device)
target_net = DQN(n_actions).to(device)
target_net.load_state_dict(policy_net.state_dict())

optimizer = optim.AdamW(policy_net.parameters(), lr=LR, amsgrad=True)
memory = ReplayMemory(10000)


steps_done = 0


def select_action(state):
    global steps_done
    sample = random.random()
    eps_threshold = EPS_END + (EPS_START - EPS_END) * \
        math.exp(-1. * steps_done / EPS_DECAY)
    steps_done += 1
    if sample > eps_threshold:
        with torch.no_grad():
            # t.max(1) will return the largest column value of each row.
            # second column on max result is index of where max element was
            # found, so we pick action with the larger expected reward.
            return policy_net(state).max(1).indices.view(1, 1)
    else:
        return torch.tensor([[random.randint(0, 8)]], device=device, dtype=torch.long)


episode_utility = []


def plot_durations(show_result=False):
    plt.figure(1)
    durations_t = torch.tensor(episode_utility, dtype=torch.float)
    if show_result:
        plt.title('Result')
    else:
        plt.clf()
        plt.title('Training...')
    plt.xlabel('Episode')
    plt.ylabel('Ores Mined')
    plt.plot(durations_t.numpy())
    # Take 100 episode averages and plot them too
    if len(durations_t) >= 100:
        means = durations_t.unfold(0, 100, 1).mean(1).view(-1)
        means = torch.cat((torch.zeros(99), means))
        plt.plot(means.numpy())

    plt.pause(0.001)  # pause a bit so that plots are updated
    if is_ipython:
        if not show_result:
            display.display(plt.gcf())
            display.clear_output(wait=True)
        else:
            display.display(plt.gcf())




def optimize_model():
    if len(memory) < BATCH_SIZE:
        return
    transitions = memory.sample(BATCH_SIZE)
    # Transpose the batch (see https://stackoverflow.com/a/19343/3343043 for
    # detailed explanation). This converts batch-array of Transitions
    # to Transition of batch-arrays.
    batch = Transition(*zip(*transitions))

    # Compute a mask of non-final states and concatenate the batch elements
    # (a final state would've been the one after which simulation ended)
    non_final_mask = torch.tensor(tuple(map(lambda s: s is not None,
                                          batch.next_state)), device=device, dtype=torch.bool)
    non_final_next_states = torch.cat([s for s in batch.next_state
                                                if s is not None])
    state_batch = torch.cat(batch.state)
    action_batch = torch.cat(batch.action)
    reward_batch = torch.cat(batch.reward)

    # Compute Q(s_t, a) - the model computes Q(s_t), then we select the
    # columns of actions taken. These are the actions which would've been taken
    # for each batch state according to policy_net
    state_action_values = policy_net(state_batch).gather(1, action_batch)

    # Compute V(s_{t+1}) for all next states.
    # Expected values of actions for non_final_next_states are computed based
    # on the "older" target_net; selecting their best reward with max(1).values
    # This is merged based on the mask, such that we'll have either the expected
    # state value or 0 in case the state was final.
    next_state_values = torch.zeros(BATCH_SIZE, device=device)
    with torch.no_grad():
        next_state_values[non_final_mask] = target_net(non_final_next_states).max(1).values
    # Compute the expected Q values
    expected_state_action_values = (next_state_values * GAMMA) + reward_batch

    # Compute Huber loss
    criterion = nn.SmoothL1Loss()
    loss = criterion(state_action_values, expected_state_action_values.unsqueeze(1))

    # Optimize the model
    optimizer.zero_grad()
    loss.backward()
    # In-place gradient clipping
    torch.nn.utils.clip_grad_value_(policy_net.parameters(), 100)
    optimizer.step()


def train():
    if not os.path.exists("miner/checkpoints"):
        os.mkdir("miner/checkpoints")

    if torch.cuda.is_available() or torch.backends.mps.is_available():
        num_episodes = 600
    else:
        print("Warning: Cuda device not available")
        num_episodes = 50

    for i_episode in range(num_episodes):
        # Initialize the environment and get its state
        env = world.World(128, 64, 128)
        robot_position = (64, 32, 64)
        print("Starting episode", i_episode)


        ore_mined = 0

        current_state = torch.tensor(env.noisy_data_around(12, *robot_position), dtype=torch.float32, device=device).unsqueeze(0)
        for t in range(384):
            action = select_action(current_state)
            new_position, observation, reward, did_mine_ore = step_environment(env, robot_position, action.item())
            reward = torch.tensor([reward], device=device)

            if did_mine_ore:
                ore_mined += 1

            next_state = torch.tensor(observation, dtype=torch.float32, device=device).unsqueeze(0)

            # Store the transition in memory
            memory.push(current_state, action, next_state, reward)

            current_state = next_state

            # Perform one step of the optimization
            optimize_model()

            # Soft update of the target network's weights
            # θ′ ← τ θ + (1 −τ )θ′
            target_net_state_dict = target_net.state_dict()
            policy_net_state_dict = policy_net.state_dict()
            for key in policy_net_state_dict:
                target_net_state_dict[key] = policy_net_state_dict[key]*TAU + target_net_state_dict[key]*(1-TAU)
            target_net.load_state_dict(target_net_state_dict)

        episode_utility.append(ore_mined)
        print(f"Mined {ore_mined} ores")
        plot_durations()

        if (i_episode) % 25 == 0 and i_episode > 0:
            print("Saving checkpoint")
            torch.save(policy_net_state_dict, f"miner/checkpoints/miner-{i_episode}.pt")

    print('Complete')
    plot_durations(show_result=True)
    plt.ioff()
    plt.show()


if __name__ == "__main__":
    train()