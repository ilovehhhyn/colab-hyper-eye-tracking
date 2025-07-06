from scipy.stats import entropy as calculate_entropy
import numpy as np
import json

items = [0, 1, 2, 3]  # The four kinds of items
n_layouts = 100000 #simulate this many layouts and choose highest entropy

def generate_layout(item_count, row_size, col_size):
    grid = np.random.choice(sum([[item] * count for item, count in item_count.items()], []), 
                            size=(row_size, col_size), replace=False)
    return grid

# Update the function to use the correctly aliased entropy function
def calculate_spatial_entropy_fixed(grid, row_size, col_size):
    diversity_scores = []
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            local_items = grid[max(0, i-1):min(row_size, i+2), max(0, j-1):min(col_size, j+2)].flatten()
            _, counts = np.unique(local_items, return_counts=True)
            diversity_scores.append(calculate_entropy(counts, base=len(items)))
    return np.mean(diversity_scores)

n_trials, n_catch = 60, 6 # 60 actual trials and 6 catch trials
grid_size_conditions = [(2,2),(2,4),(4,4),(4,8),(8,8)] # 3 possible grid sizes

np.random.seed(n_layouts)

top_layouts_fixed = {g[0]*g[1]: [] for g in grid_size_conditions} 
for gs in grid_size_conditions:
    print(gs)
    grid_size = gs[0]*gs[1]
    # Re-generate a set of random layouts and compute their entropies with the fixed function
    layouts_entropy_fixed = []
    for _ in range(n_layouts):
        item_count = {item: grid_size//len(items) for item in items} # first make sure all 4 stimuli show up as equal amount as possible
        additional_item = np.random.choice(items, grid_size%len(items), replace=False) # randomly pick some addition stimuli if grid size is not divisible
        for _ in additional_item: # add count to the additional stimuli
            item_count[np.random.choice(items)]+=1
        layout = generate_layout(item_count, gs[0], gs[1])
        entropy_value = calculate_spatial_entropy_fixed(layout, gs[0], gs[1])
        layouts_entropy_fixed.append((layout, entropy_value))
    # Sort layouts by their entropy to identify the ones with higher spatial entropy
    layouts_entropy_fixed.sort(key=lambda x: x[1], reverse=True)
    # Retrieve the top layouts as examples of high spatial entropy
    top_layouts_fixed[grid_size] += layouts_entropy_fixed[:n_trials]

# Display the entropy values for the top layouts
top_layouts_array_fixed = {gs: [[int(e) for e in layout[0].flatten()] for layout in top_layouts_fixed] for gs,top_layouts_fixed in top_layouts_fixed.items()}
catch_trials ={gs[0]*gs[1]: [[int(e) for e in np.repeat(items[i%len(items)], 
                                           gs[0]*gs[1])]\
                                            for i in range(n_catch)] for gs in grid_size_conditions} # catch trials only contrain one kind of image so super easy.

solo_conditions = {}# to use for the task save the consistency table into a json
dyad_conditions = { }# to use for the task save the consistency table into a json
for gs in grid_size_conditions:
    grid_size = gs[0]*gs[1]
    top_layouts_gs = top_layouts_array_fixed[grid_size]
    catch_trials_gs = catch_trials[grid_size]
    assert n_trials+n_catch == len(catch_trials_gs) + len(top_layouts_gs)
    np.random.shuffle(top_layouts_gs) 
    np.random.shuffle(catch_trials_gs) 

    solo_conditions["nrows_"+str(grid_size)] = gs[0]
    solo_conditions["ncols_"+str(grid_size)] = gs[1]
    solo_conditions["catch_trials_"+str(grid_size)] = catch_trials_gs[:n_catch//3]
    solo_conditions["top_layouts_array_fixed_"+str(grid_size)] = top_layouts_gs[:n_trials//3]# to use for the task save the consistency table into a json

    dyad_conditions["nrows_"+str(grid_size)] = gs[0]
    dyad_conditions["ncols_"+str(grid_size)] = gs[1]
    dyad_conditions["catch_trials_"+str(grid_size)] = catch_trials_gs[n_catch//3:]
    dyad_conditions["top_layouts_array_fixed_"+str(grid_size)] = top_layouts_gs[n_trials//3:]# to use for the task save the consistency table into a json

# Writing the combined data to a file
with open("solo_conditions.json", 'w') as file:
    file.write(json.dumps(solo_conditions, indent=4))
with open("dyad_conditions.json", 'w') as file:
    file.write(json.dumps(dyad_conditions, indent=4))
