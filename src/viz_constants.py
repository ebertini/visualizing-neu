"""
viz_constants.py — the 9-agency bucket order + color palette shared by
src/build_viz_data.py and src/build_viz_aggregates.py.

Split out so build_viz_aggregates.py's "runnable with json alone" degraded
path (see its module docstring) is actually true: before this split, its
lazy `from src.build_viz_data import COLORS, ORDER` transitively pulled in
numpy/pandas (build_viz_data.py imports them at module level), even on the
code path that otherwise touches nothing but stdlib json. This module has
no dependencies at all.

Agency short-code buckets + colors (EnricoVis decision #2: NIH-SUB kept
separate from NIH). Values are unchanged from where they previously lived
in build_viz_data.py — this is a pure move, not a data change.
"""
from __future__ import annotations

COLORS = {
    "NSF": "#0072B2", "NIH": "#E69F00", "NIH-SUB": "#56B4E9", "Navy": "#009E73",
    "NASA": "#9467BD", "Army": "#E7298A", "DOE": "#66A61E", "AFRO": "#A6761D", "Other": "#B0B4BB",
}
ORDER = ["NSF", "NIH", "NIH-SUB", "Navy", "NASA", "Army", "DOE", "AFRO", "Other"]
