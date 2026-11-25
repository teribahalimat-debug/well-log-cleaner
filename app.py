import io

import lasio
import matplotlib.pyplot as plt
import numpy as np
import streamlit as st

from cleaner import DEFAULTS, clean_well_log

st.set_page_config(page_title="Well Log Cleaner", layout="wide")

st.title("Well Log Cleaner")
st.write(
    "Upload a well log (.las file). The app finds missing data, impossible values and "
    "rough-hole readings, blanks the bad ones (it never deletes or invents data), and "
    "gives you a cleaned file and a report."
)

# ---- Sidebar: thresholds you can explain and change -------------------------
st.sidebar.header("Settings")
res_ceiling = st.sidebar.number_input("Resistivity ceiling (ohm-m)", value=DEFAULTS["res_ceiling"])
drho_limit = st.sidebar.number_input("DRHO limit (+/-)", value=DEFAULTS["drho_limit"], step=0.01)
pef_limit = st.sidebar.number_input("PEF upper limit", value=DEFAULTS["pef_limit"])
cali_tol = st.sidebar.number_input(
    "Caliper tolerance below bit size (in)", value=DEFAULTS["cali_tolerance"], step=0.25
)
st.sidebar.caption(
    "These are rules of thumb. Different wells and mud systems may need different values."
)

uploaded = st.file_uploader("Choose a LAS file", type=["las", "LAS"])

if uploaded is None:
    st.info("Upload a LAS file to begin.")
    st.stop()

try:
    text = uploaded.getvalue().decode("utf-8", errors="ignore")
    las = lasio.read(io.StringIO(text))
except Exception as e:  # noqa: BLE001
    st.error("Could not read this file as LAS: %s" % e)
    st.stop()

res = clean_well_log(
    las,
    res_ceiling=res_ceiling,
    drho_limit=drho_limit,
    pef_limit=pef_limit,
    cali_tolerance=cali_tol,
)
orig, clean = res["original"], res["clean"]

# ---- Summary -----------------------------------------------------------------
try:
    well = str(las.well["WELL"].value)
except Exception:  # noqa: BLE001
    well = "unknown"

c1, c2, c3, c4 = st.columns(4)
c1.metric("Well", well)
c2.metric("Depth range", "%g - %g" % (orig.index.min(), orig.index.max()))
c3.metric("Readings per curve", len(orig))
if res["usable"]:
    c4.metric(
        "Usable interval",
        "%g - %g" % (res["usable"][0], res["usable"][1]),
        "%d readings" % res["usable"][2],
        delta_color="off",
    )

st.subheader("What was found")
left, right = st.columns(2)
with left:
    st.markdown("**Readings blanked by each rule**")
    for name, count in res["counts"].items():
        st.write("- %s: **%d**" % (name, count))
    if res["bit_size_changes"]:
        st.write("- Bit size changes at: %s ft" % ", ".join("%g" % b for b in res["bit_size_changes"]))
with right:
    st.markdown("**Missing readings per curve**")
    miss = res["missing"]
    st.dataframe(miss[miss["missing"] > 0], width="stretch")

if res["gaps"]:
    with st.expander("Where the gaps are (depth ranges)"):
        for curve, g in res["gaps"].items():
            st.markdown("**%s**" % curve)
            st.dataframe(g, width="stretch", hide_index=True)

# ---- Chart -------------------------------------------------------------------
st.subheader("Before and after")
tracks = [c for c in ["GR", "CALI", "RESD", "RHO", "DRHO", "NPHI", "PEF"] if c in orig.columns]
if tracks:
    fig, axes = plt.subplots(1, len(tracks), figsize=(2.2 * len(tracks), 9), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, curve in zip(axes, tracks):
        ax.plot(orig[curve], orig.index, color="lightgrey", lw=1.4, label="original")
        ax.plot(clean[curve], clean.index, color="#1f6feb", lw=0.8, label="cleaned")
        removed = orig[curve].notna() & clean[curve].isna()
        ax.plot(orig[curve][removed], orig.index[removed], ".", color="red", ms=2, label="blanked")
        if curve == "RESD":
            ax.set_xscale("log")
        ax.set_title(curve, fontsize=10)
        ax.grid(alpha=0.25)
    axes[0].invert_yaxis()
    axes[0].set_ylabel("Depth")
    axes[0].legend(loc="lower left", fontsize=7)
    fig.tight_layout()
    st.pyplot(fig)

# ---- Downloads ---------------------------------------------------------------
st.subheader("Download")
d1, d2 = st.columns(2)
d1.download_button(
    "Cleaned data (CSV)", clean.to_csv().encode("utf-8"), file_name="%s_cleaned.csv" % well, mime="text/csv"
)
d2.download_button(
    "Report (TXT)", res["report"].encode("utf-8"), file_name="%s_cleaning_report.txt" % well, mime="text/plain"
)
with st.expander("Preview the report"):
    st.text(res["report"])
