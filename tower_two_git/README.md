# Scenario C — 12 Virtual UEs / 4 ZMQ DUs / 1 RIC / 1 CU — Full Reproduction Guide

Private 5G SA testbed for FRMCS railway slice management. 12 virtual srsUEs over ZeroMQ,
split across 4 ZMQ DUs (3 UEs each), one shared OSC Near-RT RIC, one CU, Open5GS core.
A CQI injector overwrites virtual-UE CQI with real SNCF railway traces. One xApp performs
SLA-driven downlink PRB allocation across all 12 UEs treated as one shared 52-PRB pool.

This guide reproduces the dataset from nothing. Two backup dirs:
- tower_one_git  : RAN side (CU, 4 DUs, UEs, brokers, injector, xApps, traffic gens, RIC, SNCF traces)
- tower_two_git  : Core side (Open5GS configs, subscriber DB, traffic_server, NAT state)

On ONE PC (single-machine simulation) put both on the same host; everything runs on localhost.
On TWO machines, keep the tower split (Tower-1 = RAN, Tower-2 = core).

================================================================================
## 0. HARDWARE / OS
================================================================================
- Ubuntu 22.04
- >= 12 CPU cores strongly recommended. 4 concurrent ZMQ pipelines drive load avg ~48
  on a 12-core box; it holds but is near the edge. Fewer cores = pipelines starve.
- No SDR/radio needed: 100% ZMQ simulation.

================================================================================
## 1. SOFTWARE TO BUILD / INSTALL  (EXACT versions used for this dataset)
================================================================================
### srsRAN Project (CU + DU)
  git clone https://github.com/srsran/srsRAN_Project
  git checkout 4bf1543936
  build with ZMQ enabled (needs libzmq3-dev):
    mkdir build && cd build && cmake .. -DENABLE_ZMQ=ON && make -j
  binaries used: build/apps/cu/srscu , build/apps/du/srsdu

### srsRAN 4G (srsUE — the virtual UEs)
  git clone https://github.com/srsran/srsRAN_4G
  git checkout release_25_10   (commit 6bcbd9e5b)
  build with ZMQ, then: sudo make install && sudo ldconfig
  /etc/ld.so.conf.d/srsran.conf must contain /usr/local/lib
  binary: /usr/local/bin/srsue

### Open5GS (5G core) + MongoDB
  install per https://open5gs.org/open5gs/docs/  (apt method ok)
  MongoDB for subscriber DB.

### OSC Near-RT RIC
  git clone https://github.com/srsran/oran-sc-ric
  SC_RIC_VERSION=i-release  (set in ric/.env, included)
  runs via docker compose.

### GNU Radio 3.10.1.1   (apt: gnuradio python3-zmq) — for the ZMQ brokers
### Docker 29.x + docker compose v2  (this box: compose v5.x)
### Python pkgs:
  host:      pip3 install websocket-client websocket-server
  container: pip3 install websocket-client   (NOT persistent across container recreate — redo each `up`)

================================================================================
## 2. WHERE EACH FILE GOES
================================================================================
FROM tower_one_git/:
  cu_du/cu.yml                  -> srsRAN_Project configs (CU)
  cu_du/du_zmq1..4.yml          -> srsRAN_Project configs (4 DUs)
  scen_c/ue1..12.conf           -> 12 virtual UE configs
  scen_c/zmq_broker_du1..4.py   -> 4 GNU Radio ZMQ brokers
  scen_c/cqi_injector_4du.py    -> CQI injector (merges 4 DU streams -> port 8002)
  scen_c/virtual_ue_traffic_12.py -> launches per-UE traffic in 12 netns
  scen_c/ue_slice_map.txt       -> UE -> slice -> IMSI reference
  xapps/cqi_driven_xapp_12_shared.py -> docker cp into python_xapp_runner:/opt/xApps/
  xapps/metrics_logger_v4.py    -> docker cp into python_xapp_runner:/opt/xApps/
  traffic/critical_traffic.py   -> ~ (NOTE: ato carries video_surv stress profile, see sec 6)
  traffic/performance_traffic.py-> ~
  traffic/business_traffic.py   -> ~
  ric/docker-compose.yml + .env -> oran-sc-ric/
  sncf_traces/*.csv             -> injector --dataset_dir points here (183 files, ~324M)

FROM tower_two_git/:
  core/*.yaml                   -> /etc/open5gs/
  subscribers/mongodump         -> restore: mongorestore subscribers/mongodump
  subscribers/subscribers_dump.json -> human-readable IMSI/slice reference
  traffic_generation/traffic_server.py -> core side (responds to UL/DL_REQ/PING)
  system/tower2_state.txt       -> NAT/forward rules to reapply
  system/connect-5g.sh          -> (physical-UE helper; not needed for all-virtual scen_c)

================================================================================
## 3. NETWORK / SLICE PARAMETERS (must match for attach to succeed)
================================================================================
PLMN 00101 (MCC=001 MNC=01) | Band 3 FDD | DL ARFCN 368500 | SCS 15 kHz
Bandwidth 10 MHz -> 52 PRBs | TAC 7 | DNN srsapn | UE pool 10.45.0.0/16
SIM (all UEs): K=0c0a34601d4f07677303652c0462535b  OPc=63bfa50ee6523365ff14c1f45f88737d  AMF=8000

Slices: CRITICAL SD=000003 (sd:3) | PERFORMANCE SD=000001 (sd:1) | BUSINESS SD=000002 (sd:2)

12 UEs (IMSI -> slice; attach in config order per DU):
  DU1: vue1=IMSI006 CRIT, vue2=IMSI007 PERF, vue3=IMSI008 BUS
  DU2: vue4=IMSI009 CRIT, vue5=IMSI010 PERF, vue6=IMSI011 BUS
  DU3: vue7=IMSI012 CRIT, vue8=IMSI013 PERF, vue9=IMSI014 BUS
  DU4: vue10=IMSI015 CRIT, vue11=IMSI016 PERF, vue12=IMSI017 CRIT
ALL 12 IMSIs (006..017) MUST be provisioned in MongoDB or attach -> Registration reject [7].

E2 nodes (after all 4 DUs up, `docker exec ric_dbaas redis-cli KEYS '*RAN*'`):
  gnbd_001_001_00000213_1 .._2 .._3 .._4   (same gnb_id 531, differ by gnb_du_id 1..4)

================================================================================
## 4. BOOT ORDER (strict — wait at each gate)
================================================================================
CORE (Tower-2 / core side):
  1. ip_forward=1 ; apply NAT (see system/tower2_state.txt):
       MASQUERADE for 10.45.0.0/16 ; FORWARD ACCEPT ogstun<->uplink iface
  2. start Open5GS (nrf first, then the rest) ; mongorestore subscribers if DB empty
  3. start traffic_server.py  (binds UDP 6001-6005, 7001-7005, 9001)

RAN (Tower-1 / RAN side):
  4. CPU tuning (srsran_performance script), set uplink iface MTU 9000
  5. create netns: for i in 1..12: sudo ip netns add vue$i
  6. RIC: cd oran-sc-ric && docker compose up -d ; wait ~20s
     add secondary IP to RIC docker bridge (changes name each up):
       BRIDGE=$(ip link | grep br- | head -1 | awk '{print $2}' | tr -d ':')
       sudo ip addr add 10.0.2.2/24 dev $BRIDGE
  7. container: docker compose exec python_xapp_runner pip3 install websocket-client
  8. CU: sudo srscu -c cu_du/cu.yml   (wait "N2: Connection to AMF ... completed")
  9. PER DU (do 1, then 2, then 3, then 4 — DO NOT batch):
       start its 3 UEs:   sudo -b srsue scen_c/ueX.conf  (in config order)
       start its broker:  python3 scen_c/zmq_broker_duN.py &
       start the DU:      sudo srsdu -c cu_du/du_zmqN.yml
       GATE: wait for "E2AP ... completed" + DU started, then verify all 3 netns have 10.45.x.x:
         for ns in vueA vueB vueC; do sudo ip netns exec $ns ip -4 addr show | grep -oP 'inet \K10\.45\.\d+\.\d+' || echo NO IP; done
       Only proceed to next DU once all 3 have IPs. redis should grow _1 -> _2 -> _3 -> _4.
 10. injector: python3 scen_c/cqi_injector_4du.py --dataset_dir <path>/sncf_traces/
       wait for 4x "[INJ] connected ... -> gnbd_..._N"
 11. deploy + run xApp:
       docker cp xapps/cqi_driven_xapp_12_shared.py python_xapp_runner:/opt/xApps/
       docker cp xapps/metrics_logger_v4.py        python_xapp_runner:/opt/xApps/
       docker compose exec python_xapp_runner python3 /opt/xApps/cqi_driven_xapp_12_shared.py
       (prints "=== shared-pool alloc (12 UEs) ===" every 5s)
 12. traffic: sudo python3 scen_c/virtual_ue_traffic_12.py
 13. logger:  docker exec python_xapp_runner bash -c 'rm -f /tmp/ue_metrics_log.csv /tmp/prb_decisions.json'
              docker compose exec python_xapp_runner python3 /opt/xApps/metrics_logger_v4.py
       -> writes /tmp/ue_metrics_log.csv (24 cols, ~12 rows/sec)
 14. collect after 30-45 min:
       docker cp python_xapp_runner:/tmp/ue_metrics_log.csv ~/scen_c_$(date +%Y%m%d_%H%M).csv
       cp /tmp/offered_vue*.csv <somewhere>   (per-UE offered vs achieved)

================================================================================
## 5. DATASET SCHEMA (metrics_logger_v4 -> ue_metrics_log.csv, 24 columns)
================================================================================
timestamp, rnti, e2_node, f1ap, slice_sd, slice_name, cqi, ri, dl_mcs, ul_mcs,
pusch_snr_db, pusch_rsrp_db, phr, dl_brate_bps, ul_brate_bps, dl_nof_ok, dl_nof_nok,
dl_latency_us, ul_latency_us, prb_min, prb_max, alloc_req_bps, sla_dl_target_bps

Per-UE offered CSV (offered_vueN.csv): timestamp, ue, off_ul_bps, off_dl_bps, ach_ul_bps, ach_dl_bps
Preprocessing: drop first ~30s rows where prb_max is empty (xApp not yet allocating).

================================================================================
## 6. DESIGN NOTES & KNOWN LIMITATIONS (state these in any writeup)
================================================================================
- WHY 4 DUs not 1: srsRAN+ZMQ saturates above 3 simultaneous UEs per pipeline (GNU Radio
  REQ/REP synchronous combiner + srsUE hardcoded PRACH preamble). Documented in Barker et al.,
  arXiv:2502.00715 (Clemson 2025), same stack, same ceiling. 4 DUs x 3 UEs = 12.
- SHARED POOL: each ZMQ DU is its own 52-PRB cell, so physically each cell only carries 3 UEs.
  The xApp imposes ONE logical 52-PRB budget across all 12 to emulate a single congested cell,
  then maps each UE's share back to its own DU via E2SM-RC. This is a modeling choice — state it.
- DOWNLINK ONLY: E2SM-RC slice PRB control in srsRAN applies to PDSCH (downlink) only.
  Uplink is logged (ul_brate_bps) but NOT controlled. Confirmed: srsRAN discussion #904,
  and Barker et al. ("stable srsRAN supports only down-link slicing"). Violation metric is DL.
- ato STRESS PROFILE: critical's 'ato' app was changed from nominal 1/0.25 kbps to the
  video_surv profile (300 kbps DL / 3000 kbps UL + 9000 UL burst) to stress the slice.
  Name kept 'ato'. The 3 Mbps is UL (uncontrolled); the 300 kbps DL is what the allocator sees.
- SLICE LABELS by attach order: f1ap=0/1/2 per DU mapped to slice by attach order in the injector
  (slice_order [3,1,2] for DU1-3, [3,1,3] for DU4). Start UEs in config order or labels shift.
  Verify post-hoc against AMF attach log + subscriber DB if rigor needed.
- CONTENTION FLATTENS SIGNATURES: under full load all UEs ration to similar UL; slices are not
  cleanly separable by traffic signature alone — rely on the IMSI->slice mapping, not behavior.

================================================================================
## 7. GOTCHAS THAT COST HOURS
================================================================================
- du_zmq1.yml cu_cp_addr MUST be 127.0.10.1 (was once wrongly 10.0.2.2 -> F1 "Network unreachable").
- 10.0.2.2/24 must be re-added to the RIC bridge after EVERY docker compose up (bridge name changes).
- websocket-client pip install in the container does NOT survive container recreation — reinstall.
- All 12 IMSIs (006..017) must be in MongoDB first, or those UEs get Registration reject [7].
- Start DUs one at a time with the IP gate; batching all 4 at once starves the later pipelines.
- srsUE must be started before its broker, broker before its DU (ZMQ pipeline ordering).
