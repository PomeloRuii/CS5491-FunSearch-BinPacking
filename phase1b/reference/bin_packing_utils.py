# Publication-only data loader; original dataset literals withheld.
# Utility functions below retain RayZhhh/DeepMind upstream attribution (NOTICE).
from __future__ import annotations
from typing import Tuple
from pathlib import Path
import json
import numpy as np
_data = Path(__file__).resolve().parents[2]/'phase2/data/research_data.json'
datasets = json.loads(_data.read_text())['development'] if _data.exists() else {'OR3': {}, 'Weibull 5k': {}}
def l1_bound(items: Tuple[int, ...], capacity: int) -> float:
    """Computes L1 lower bound on OPT for bin packing.

    Args:
      items: Tuple of items to pack into bins.
      capacity: Capacity of bins.

    Returns:
      Lower bound on number of bins required to pack items.
    """
    return np.ceil(np.sum(items) / capacity)


def l1_bound_dataset(instances: dict) -> float:
    """Computes the mean L1 lower bound across a dataset of bin packing instances.

    Args:
      instances: Dictionary containing a set of bin packing instances.

    Returns:
      Average L1 lower bound on number of bins required to pack items.
    """
    l1_bounds = []
    for name in instances:
        instance = instances[name]
        l1_bounds.append(l1_bound(instance['items'], instance['capacity']))
    return np.mean(l1_bounds)


opt_num_bins = {name: l1_bound_dataset(data) for name, data in datasets.items() if data}
