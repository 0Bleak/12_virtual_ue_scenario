#!/usr/bin/env python3
import subprocess, threading, time
SERVER="10.45.0.1"
MAP={"vue1":"critical","vue2":"performance","vue3":"business",
     "vue4":"critical","vue5":"performance","vue6":"business",
     "vue7":"critical","vue8":"performance","vue9":"business",
     "vue10":"critical","vue11":"performance","vue12":"critical"}
SCRIPT={"critical":"/home/ligm/critical_traffic.py",
        "performance":"/home/ligm/performance_traffic.py",
        "business":"/home/ligm/business_traffic.py"}
def run(ns,kind):
    cmd=["sudo","ip","netns","exec",ns,"python3",SCRIPT[kind],
         "--server",SERVER,"--duration","999999","--ue",ns,
         "--latency_log",f"/tmp/latency_{ns}.csv"]
    while True:
        try: subprocess.run(cmd)
        except Exception as e: print(f"[{ns}] {e}, restart 3s"); time.sleep(3)
for ns,kind in MAP.items():
    threading.Thread(target=run,args=(ns,kind),daemon=True).start()
print("[VT12] 12 UEs launched (5 critical / 4 perf / 3 business)")
while True: time.sleep(60); print("[VT12] running")
