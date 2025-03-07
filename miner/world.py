"""
Generate a very rough approximation of underground terrain from a minecraft world
to provide a dynamic training environment for the agent which can run faster than real-time.
"""

import numpy as np
import matplotlib.pyplot as plt
import random

# In-game block hardness values detected by geolyzer
block_density = {
    "air": 0.0,
    "coal_ore": 3.0,
    "iron_ore": 3.0,
    "gold_ore": 3.0,
    "diamond_ore": 3.0,
    "redstone_ore": 3.0,
    "lapis_ore": 3.0,
    "emerald_ore": 3.0,

    "stone": 1.5,
    "dirt": 0.5,

    "gravel": 0.6,  

    "bedrock": float('inf')
}

class World:

    def __init__(self, x,y,z):
        self.blocks = [[[ "stone" for _ in range(z)] for _ in range(y)] for _ in range(x)]
        self.x_size = x
        self.y_size = y
        self.z_size = z

        for ore, attempts in [("coal_ore", 10), ("iron_ore", 5), ("gold_ore", 3), ("diamond_ore", 1), ("redstone_ore", 2)]:
            for _ in range(attempts):
                for chunk_x in range((x // 16)):
                    for chunk_z in range((z // 16)):
                        vein_position = (random.randint(0, 15), random.randint(0, y - 1), random.randint(0, 15))
                        vein_size = random.randint(1, 4)
                        create_sphere(self.blocks, vein_size, ore, chunk_x * 16 + vein_position[0], vein_position[1], chunk_z * 16 + vein_position[2])
        
        for chunk_x in range((x // 16)):
            for chunk_z in range((z // 16)):
                vein_position = (random.randint(0, 15), random.randint(0, y - 1), random.randint(0, 15))
                vein_size = random.randint(3, 5)
                create_sphere(self.blocks, vein_size, "dirt", chunk_x * 16 + vein_position[0], vein_position[1], chunk_z * 16 + vein_position[2])

        # Generate some caves (number based on world size)
        for chunk_x in range((x // 16) + (z // 16)):
            carver_position = (random.randint(0, x), random.randint(0, y), random.randint(0, z))
            carver_radius = random.randint(2, 5)
            for i in range(random.randint(15, 50)):
                carver_position = (carver_position[0] + random.randint(-2, 2),
                                carver_position[1] + random.randint(-2, 2),
                                carver_position[2] + random.randint(-2, 2))
                
                carver_radius += random.randint(-1, 1)
                carver_radius = min(5, max(2, carver_radius))
                
                create_sphere(self.blocks, 2, "air", *carver_position)

    def noisy_data_around(self, radius, x, y, z) -> list[list[list[float]]]:
        """Emulate in-game Geolyzer readings for a section of the world. Noise increases with distance from the robot's position"""
        world_slice = []
        for i in range(x - radius, x + radius + 1):
            world_slice.append([])
            for j in range(y - radius, y + radius + 1):
                world_slice[-1].append([])
                for k in range(z - radius, z + radius + 1):
                    x, y, z = i + radius, j + radius, k + radius
                    distance = ((x - radius) ** 2 + (y - radius) ** 2 + (z - radius) ** 2) ** 0.5
                    if 0 <= x < self.x_size and 0 <= y < self.y_size and 0 <= z < self.z_size:
                        noise = (distance / 33) * 2
                        density = block_density[self.blocks[x][y][z]]
                        world_slice[-1][-1].append(density + noise)
                    else:
                        world_slice[-1][-1].append(block_density["bedrock"])
        return world_slice
    
    def sample_block(self, x, y, z):
        """String name of a block at a given position"""
        if 0 <= x < self.x_size and 0 <= y < self.y_size and 0 <= z < self.z_size:
            return self.blocks[x][y][z]
        return "bedrock"
    
    def sample_density(self, x, y, z):
        """Get the (not noisy) block hardness from a given position"""
        return block_density.get(self.sample_block(x, y, z), float('inf'))
    

def create_sphere(world, radius, block, center_x, center_y, center_z):
    x, y, z = len(world), len(world[0]), len(world[0][0])

    for i in range(-radius, radius + 1):
        for j in range(-radius, radius + 1):
            for k in range(-radius, radius + 1):
                if (i**2 + j**2 + k**2) < radius**2:
                    block_x = center_x + i
                    block_y = center_y + j
                    block_z = center_z + k
                    if 0 <= block_x < x and 0 <= block_y < y and 0 <= block_z < z:
                        world[block_x][block_y][block_z] = block


def render_density(world: World):
    """Render a generated world for visual debugging"""
    data = np.zeros((world.x_size, world.y_size, world.z_size))
    for i in range(world.x_size):
        for j in range(world.y_size):
            for k in range(world.z_size):
                data[i][j][k] = block_density.get(world.blocks[i][j][k], 0.0)

    fig = plt.figure(figsize=(6, 6))
    ax = fig.add_subplot(projection="3d")
    ax.xaxis.pane.fill = False
    ax.yaxis.pane.fill = False
    ax.zaxis.pane.fill = False
    # Make regular stone invisible in render, to allow caves and ores to be seen
    mask = abs(data - 1.5) > 0.1
    x, y, z = np.indices(data.shape)

    ax.scatter(x, z, y, c=data, s=30.0 * mask, edgecolor="face", alpha=0.2, marker="o", cmap="magma", linewidth=0)
    max_axis = max(world.x_size, world.y_size, world.z_size)
    ax.set_xlim(0, max_axis)
    ax.set_ylim(0, max_axis)
    ax.set_zlim(0, max_axis)
    plt.show()


if __name__ == "__main__":
    world = World(64, 64, 64)
    render_density(world)
