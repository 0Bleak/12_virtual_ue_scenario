#!/usr/bin/env python3
import pandas as pd, glob, os, matplotlib.pyplot as plt, numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.join(BASE, "scen_c_full12_20260603_1445.csv")
OFF  = os.path.join(BASE, "offered")

# vue -> slice (design: 1,4,7,10,12=CRIT 2,5,8,11=PERF 3,6,9=BUS)
SLICE = {1:"CRITICAL",2:"PERFORMANCE",3:"BUSINESS",4:"CRITICAL",5:"PERFORMANCE",
         6:"BUSINESS",7:"CRITICAL",8:"PERFORMANCE",9:"BUSINESS",
         10:"CRITICAL",11:"PERFORMANCE",12:"CRITICAL"}
COL = {"CRITICAL":"#e8552d","PERFORMANCE":"#2d7fe8","BUSINESS":"#2da84f"}
ORDER = ["CRITICAL","PERFORMANCE","BUSINESS"]

# ---------- OFFERED + UL DELIVERED (from offered CSVs) ----------
rows=[]
for f in glob.glob(os.path.join(OFF,"offered_vue*.csv")):
    vue=int(''.join(filter(str.isdigit,os.path.basename(f))))
    d=pd.read_csv(f)
    rows.append({"vue":vue,"slice":SLICE[vue],
                 "off_dl":d["off_dl_bps"].mean(),
                 "off_ul":d["off_ul_bps"].mean(),
                 "ach_ul":d["ach_ul_bps"].mean()})
off=pd.DataFrame(rows)

# ---------- DL DELIVERED (from main CSV, RAN scheduler dl_brate) ----------
m=pd.read_csv(MAIN)
m=m[m["prb_max"].notna()]                      # drop ~30s startup
# mean dl_brate per UE (rnti), then attach slice via slice_name already in main
dl_per_rnti=m.groupby("rnti").agg(dl=("dl_brate_bps","mean"),
                                  slice=("slice_name","first")).reset_index()

# slice-level aggregates
off_slice = off.groupby("slice").agg(off_dl=("off_dl","sum"),
                                     off_ul=("off_ul","sum"),
                                     ach_ul=("ach_ul","sum")).reindex(ORDER)
dl_slice  = dl_per_rnti.groupby("slice")["dl"].sum().reindex(ORDER).fillna(0)

# ===== PLOT 1: DL offered vs delivered per slice (log) =====
fig,ax=plt.subplots(figsize=(8,5))
x=np.arange(3); w=0.35
ax.bar(x-w/2, off_slice["off_dl"]/1e6, w, label="Offered", color="#999")
ax.bar(x+w/2, dl_slice.values/1e6, w, label="Delivered (RAN dl_brate)",
       color=[COL[s] for s in ORDER])
ax.set_xticks(x); ax.set_xticklabels(ORDER); ax.set_ylabel("DL throughput (Mbps)")
ax.set_yscale("log"); ax.set_title("Scenario C: DL Offered vs Delivered per Slice")
ax.legend(); plt.tight_layout()
plt.savefig(os.path.join(BASE,"plot1_dl_offered_vs_delivered.png"),dpi=150)

# ===== PLOT 2: DL satisfaction % per slice =====
fig,ax=plt.subplots(figsize=(8,5))
sat=(dl_slice.values/off_slice["off_dl"].values)*100
ax.bar(ORDER, sat, color=[COL[s] for s in ORDER])
for i,v in enumerate(sat): ax.text(i,v+max(sat)*0.02,f"{v:.1f}%",ha="center",fontweight="bold")
ax.set_ylabel("DL SLA satisfaction (%)")
ax.set_title("Scenario C: DL Satisfaction per Slice (delivered/offered)")
plt.tight_layout(); plt.savefig(os.path.join(BASE,"plot2_dl_satisfaction.png"),dpi=150)

# ===== PLOT 3: UL offered vs delivered per slice (clean ~100%) =====
fig,ax=plt.subplots(figsize=(8,5))
ax.bar(x-w/2, off_slice["off_ul"]/1e6, w, label="Offered", color="#999")
ax.bar(x+w/2, off_slice["ach_ul"]/1e6, w, label="Delivered",
       color=[COL[s] for s in ORDER])
ax.set_xticks(x); ax.set_xticklabels(ORDER); ax.set_ylabel("UL throughput (Mbps)")
ax.set_title("Scenario C: UL Offered vs Delivered per Slice (uncontrolled, unsaturated)")
ax.legend(); plt.tight_layout()
plt.savefig(os.path.join(BASE,"plot3_ul_offered_vs_delivered.png"),dpi=150)

# ---------- print the numbers too ----------
print("\n=== DL per slice ===")
for s in ORDER:
    o=off_slice.loc[s,"off_dl"]; d=dl_slice[s]
    print(f"{s:12s} offered={o/1e6:6.2f} Mbps  delivered={d/1e6:6.3f} Mbps  sat={100*d/o:5.1f}%")
print("\n=== UL per slice ===")
for s in ORDER:
    o=off_slice.loc[s,"off_ul"]; a=off_slice.loc[s,"ach_ul"]
    print(f"{s:12s} offered={o/1e6:6.2f} Mbps  delivered={a/1e6:6.2f} Mbps  sat={100*a/o:5.1f}%")
print("\nwrote plot1_dl_offered_vs_delivered.png, plot2_dl_satisfaction.png, plot3_ul_offered_vs_delivered.png")
