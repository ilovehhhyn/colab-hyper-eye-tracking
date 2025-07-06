{
 "cells": [
  {
   "cell_type": "code",
   "execution_count": 1,
   "id": "6c4c1e3d",
   "metadata": {},
   "outputs": [],
   "source": [
    "from scipy.stats import entropy as calculate_entropy\n",
    "import numpy as np\n",
    "import json\n",
    "items = [0, 1, 2, 3]  # The four kinds of items\n",
    "n_layouts = 100000 #simulate this many layouts and choose highest entropy\n",
    "\n",
    "def generate_layout(item_count, row_size, col_size):\n",
    "\n",
    "    grid = np.random.choice(sum([[item] * count for item, count in item_count.items()], []), \n",
    "                            size=(row_size, col_size), replace=False)\n",
    "    return grid\n",
    "\n",
    "# Update the function to use the correctly aliased entropy function\n",
    "def calculate_spatial_entropy_fixed(grid, row_size, col_size):\n",
    "    diversity_scores = []\n",
    "    for i in range(grid.shape[0]):\n",
    "        for j in range(grid.shape[1]):\n",
    "            local_items = grid[max(0, i-1):min(row_size, i+2), max(0, j-1):min(col_size, j+2)].flatten()\n",
    "            _, counts = np.unique(local_items, return_counts=True)\n",
    "            diversity_scores.append(calculate_entropy(counts, base=len(items)))\n",
    "    return np.mean(diversity_scores)"
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 2,
   "id": "6b7a23b1",
   "metadata": {},
   "outputs": [
    {
     "name": "stdout",
     "output_type": "stream",
     "text": [
      "(2, 2)\n",
      "(2, 4)\n",
      "(4, 4)\n",
      "(4, 6)\n",
      "(6, 6)\n"
     ]
    }
   ],
   "source": [
    "n_trials, n_catch = 60, 6 # 60 actual trials and 6 catch trials\n",
    "grid_size_conditions = [(2,2),(2,4),(4,4),(4,6),(6,6)] # 3 possible grid sizes\n",
    "# grid_sizes = grid_size_conditions * n_trials//len(grid_size_conditions)\n",
    "# np.random.shuffle(grid_sizes)\n",
    "\n",
    "np.random.seed(n_layouts)\n",
    "\n",
    "top_layouts_fixed = {g[0]*g[1]: [] for g in grid_size_conditions} \n",
    "for gs in grid_size_conditions:\n",
    "    print(gs)\n",
    "    grid_size = gs[0]*gs[1]\n",
    "    # Re-generate a set of random layouts and compute their entropies with the fixed function\n",
    "    layouts_entropy_fixed = []\n",
    "    for _ in range(n_layouts):\n",
    "        item_count = {item: grid_size//len(items) for item in items} # first make sure all 4 stimuli show up as equal amount as possible\n",
    "        additional_item = np.random.choice(items, grid_size%len(items), replace=False) # randomly pick some addition stimuli if grid size is not divisible\n",
    "        for _ in additional_item: # add count to the additional stimuli\n",
    "            item_count[np.random.choice(items)]+=1\n",
    "        layout = generate_layout(item_count, gs[0], gs[1])\n",
    "        entropy_value = calculate_spatial_entropy_fixed(layout, gs[0], gs[1])\n",
    "        layouts_entropy_fixed.append((layout, entropy_value))\n",
    "    # Sort layouts by their entropy to identify the ones with higher spatial entropy\n",
    "    layouts_entropy_fixed.sort(key=lambda x: x[1], reverse=True)\n",
    "    # Retrieve the top layouts as examples of high spatial entropy\n",
    "    top_layouts_fixed[grid_size] += layouts_entropy_fixed[:n_trials]\n",
    "\n",
    "# Display the entropy values for the top layouts\n",
    "# top_layouts_entropy_fixed = [layout[1] for layout in top_layouts_fixed]\n",
    "top_layouts_array_fixed = {gs: [[int(e) for e in layout[0].flatten()] for layout in top_layouts_fixed] for gs,top_layouts_fixed in top_layouts_fixed.items()}\n",
    "catch_trials ={gs[0]*gs[1]: [[int(e) for e in np.repeat(items[i%len(items)], \\\n",
    "                                           gs[0]*gs[1])]\\\n",
    "                                            for i in range(n_catch)] for gs in grid_size_conditions} # catch trials only contrain one kind of image so super easy."
   ]
  },
  {
   "cell_type": "code",
   "execution_count": 3,
   "id": "2ec0ab59",
   "metadata": {},
   "outputs": [],
   "source": [
    "solo_conditions = {}# to use for the task save the consistency table into a json\n",
    "dyad_conditions = { }# to use for the task save the consistency table into a json\n",
    "for gs in grid_size_conditions:\n",
    "    grid_size = gs[0]*gs[1]\n",
    "    top_layouts_gs = top_layouts_array_fixed[grid_size]\n",
    "    catch_trials_gs = catch_trials[grid_size]\n",
    "    assert n_trials+n_catch == len(catch_trials_gs) + len(top_layouts_gs)\n",
    "    np.random.shuffle(top_layouts_gs) \n",
    "    np.random.shuffle(catch_trials_gs) \n",
    "\n",
    "    solo_conditions[\"nrows_\"+str(grid_size)] = gs[0]\n",
    "    solo_conditions[\"ncols_\"+str(grid_size)] = gs[1]\n",
    "    solo_conditions[\"catch_trials_\"+str(grid_size)] = catch_trials_gs[:n_catch//3]\n",
    "    solo_conditions[\"top_layouts_array_fixed_\"+str(grid_size)] = top_layouts_gs[:n_trials//3]# to use for the task save the consistency table into a json\n",
    "\n",
    "    dyad_conditions[\"nrows_\"+str(grid_size)] = gs[0]\n",
    "    dyad_conditions[\"ncols_\"+str(grid_size)] = gs[1]\n",
    "    dyad_conditions[\"catch_trials_\"+str(grid_size)] = catch_trials_gs[n_catch//3:]\n",
    "    dyad_conditions[\"top_layouts_array_fixed_\"+str(grid_size)] = top_layouts_gs[n_trials//3:]# to use for the task save the consistency table into a json\n",
    "\n",
    "# The string to prepend\n",
    "# prepend_str = 'var conditions = '\n",
    "\n",
    "# Writing the combined data to a file\n",
    "'''\n",
    "uncommment below to save json file to local\n",
    "'''\n",
    "with open(\"solo_conditions.json\", 'w') as file:\n",
    "    file.write(json.dumps(solo_conditions, indent=4))\n",
    "with open(\"dyad_conditions.json\", 'w') as file:\n",
    "    file.write(json.dumps(dyad_conditions, indent=4))"
   ]
  }
 ],
 "metadata": {
  "kernelspec": {
   "display_name": "dyat",
   "language": "python",
   "name": "python3"
  },
  "language_info": {
   "codemirror_mode": {
    "name": "ipython",
    "version": 3
   },
   "file_extension": ".py",
   "mimetype": "text/x-python",
   "name": "python",
   "nbconvert_exporter": "python",
   "pygments_lexer": "ipython3",
   "version": "3.12.2"
  }
 },
 "nbformat": 4,
 "nbformat_minor": 5
}
