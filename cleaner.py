"""Well log cleaning logic.

Rule of the whole tool: MASK, DON'T DELETE. Bad readings become blanks (NaN)
in a copy of the data. The original is never changed, and every decision is
written into the report so a geologist can review it.
"""

import numpy as np
import pandas as pd

# Default thresholds. They are plain numbers so you can explain and change them.
DEFAULTS = {
    "res_ceiling": 5000.0,   # resistivity stuck at this value is not a real reading
    "drho_limit": 0.1,       # |DRHO| beyond this = density tool unreliable
    "pef_limit": 10.0,       # PEF above this is implausible for most rocks
    "cali_tolerance": 1.0,   # caliper this many inches below bit size is suspicious
}

KEY_CURVES = ["GR", "RESD", "RHO", "NPHI"]


def _runs(mask: pd.Series) -> pd.DataFrame:
    """Group consecutive True readings into depth ranges (gaps / bad stretches)."""
    if not mask.any():
        return pd.DataFrame(columns=["from_depth", "to_depth", "readings"])
    run_id = (mask != mask.shift()).cumsum()
    out = (
        mask.index.to_series()[mask]
        .groupby(run_id[mask])
        .agg(["min", "max", "count"])
        .reset_index(drop=True)
    )
    out.columns = ["from_depth", "to_depth", "readings"]
    return out


def clean_well_log(las, **overrides):
    """Clean a lasio LASFile.

    Returns a dict with:
      clean    - cleaned DataFrame (depth is the index)
      original - original DataFrame
      missing  - DataFrame: missing readings per curve (count and percent)
      gaps     - dict curve -> DataFrame of gap depth ranges
      counts   - dict of how many readings each rule blanked
      usable   - (top, bottom, n_readings) or None
      bit_size_changes - list of depths where bit size changes
      report   - plain-text report
    """
    p = {**DEFAULTS, **overrides}

    original = las.df()
    clean = original.copy()
    cols = set(original.columns)
    counts = {}
    notes = []

    # 1. Resistivity at the ceiling
    if "RESD" in cols:
        bad = clean["RESD"] >= p["res_ceiling"]
        clean.loc[bad, "RESD"] = np.nan
        counts["RESD stuck at ceiling (>= %g)" % p["res_ceiling"]] = int(bad.sum())

    # 2. Density tool unreliable where DRHO is large
    if "DRHO" in cols:
        bad = clean["DRHO"].abs() > p["drho_limit"]
        targets = [c for c in ["RHO", "DRHO", "PEF"] if c in cols]
        clean.loc[bad, targets] = np.nan
        counts["Density/DRHO/PEF blanked where |DRHO| > %g" % p["drho_limit"]] = int(bad.sum())

    # 3. Impossible PEF
    if "PEF" in cols:
        bad = clean["PEF"] > p["pef_limit"]
        clean.loc[bad, "PEF"] = np.nan
        counts["PEF above %g" % p["pef_limit"]] = int(bad.sum())

    # 4. Caliper far below bit size
    if "CALI" in cols and "BS" in cols:
        bad = original["CALI"] < original["BS"] - p["cali_tolerance"]
        clean.loc[bad, "CALI"] = np.nan
        counts["CALI more than %g in below bit size" % p["cali_tolerance"]] = int(bad.sum())

    # Missing data summary and where the gaps are
    n = len(original)
    missing = pd.DataFrame(
        {
            "missing": original.isna().sum(),
            "percent": (original.isna().sum() / n * 100).round(1),
        }
    )
    gaps = {c: _runs(original[c].isna()) for c in original.columns if original[c].isna().any()}

    # Usable interval = where the key curves all exist in the ORIGINAL data
    present_keys = [c for c in KEY_CURVES if c in cols]
    usable = None
    if present_keys:
        ok = original[present_keys].notna().all(axis=1)
        clean["usable_interval"] = ok
        if ok.any():
            d = original.index[ok]
            usable = (float(d.min()), float(d.max()), int(ok.sum()))

    # Bit size changes
    bit_changes = []
    if "BS" in cols:
        change = original["BS"] != original["BS"].shift()
        bit_changes = [float(x) for x in original.index[change][1:]]

    # Plain-text report
    try:
        well = str(las.well["WELL"].value)
    except Exception:
        well = "unknown"
    top, bottom = float(original.index.min()), float(original.index.max())
    lines = [
        "WELL LOG CLEANING REPORT - Well %s" % well,
        "Depth range: %g to %g | Total readings: %d" % (top, bottom, n),
        "",
        "Readings blanked (original data is NOT changed):",
    ]
    for name, c in counts.items():
        lines.append("  - %s: %d" % (name, c))
    lines.append("")
    if usable:
        lines.append(
            "Usable interval (all of %s present): %g to %g ft (%d readings)"
            % (", ".join(present_keys), usable[0], usable[1], usable[2])
        )
    if bit_changes:
        lines.append("Bit size changes at: %s" % ", ".join("%g ft" % b for b in bit_changes))
    lines.append("")
    lines.append("Curves with missing readings:")
    for c, row in missing[missing["missing"] > 0].iterrows():
        lines.append("  - %s: %d (%.1f%%)" % (c, row["missing"], row["percent"]))
    lines.append("")
    lines.append("Method: bad readings are masked (set blank), never deleted or invented.")
    lines.append("Gaps are not filled; review thresholds with a geologist before relying on them.")

    return {
        "clean": clean,
        "original": original,
        "missing": missing,
        "gaps": gaps,
        "counts": counts,
        "usable": usable,
        "bit_size_changes": bit_changes,
        "report": "\n".join(lines),
    }
