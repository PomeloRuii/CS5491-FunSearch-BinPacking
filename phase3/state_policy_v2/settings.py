"""Frozen factors and three order-controlled blocks, no execution at import."""
import numpy as np
from .states import SEEDS

SETTINGS = (
    dict(name='exact_c1', bank=None, size=0, cache='C1', fallback='F0'),
    *[dict(name=f's0_n{n}_c1_f1', bank='S0', size=n, cache='C1', fallback='F1') for n in (16,64,128)],
    *[dict(name=f's2_n{n}_c1_f1', bank='S2', size=n, cache='C1', fallback='F1') for n in (16,64,128)],
    dict(name='bridge_s0_n16_c0_f0', bank='S0', size=16, cache='C0', fallback='F0'),
)


def orders():
    first = [SETTINGS[int(i)]['name'] for i in np.random.default_rng(SEEDS['timing_order']).permutation(8)]
    return [first, list(reversed(first)), first[4:]+first[:4]]
