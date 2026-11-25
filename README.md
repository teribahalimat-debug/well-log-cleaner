# Well Log Cleaner

Upload a well log (`.las`) and get a cleaned file plus a plain-text report.

**Rule of the tool: mask, don't delete.** Bad readings are blanked in a copy of the
data. The original is never changed, nothing is invented, and every decision is
written into the report for a geologist to review.

## What it checks
- **Missing readings** per curve, and the depth ranges of the gaps
- **Resistivity stuck at a ceiling value** (default 5000 ohm-m) - likely a placeholder, not a reading
- **Density tool reliability** - density, DRHO and PEF are blanked where |DRHO| exceeds 0.1
- **Impossible PEF** (default above 10)
- **Caliper far below bit size** (default more than 1 inch) - likely a tool problem
- **Usable interval** - the depth range where GR, RESD, RHO and NPHI all exist
- **Bit size changes** (hole section changes)

Thresholds are rules of thumb and can be changed in the sidebar. Different wells and
mud systems may need different values - review with a geologist.

## Run it
```
pip install -r requirements.txt
streamlit run app.py
```
Try it with `demo_synthetic_well.las` (synthetic data with planted problems, not a real well).

## Files
- `app.py` - the Streamlit web page
- `cleaner.py` - the cleaning logic (works without the web page)

## Limits
- Tested on one LAS 2.0 layout and synthetic data; other formats may need adjustments.
- It flags and masks. It does not interpret geology.

*Built by [your name] - geology graduate learning AI and automation.*
