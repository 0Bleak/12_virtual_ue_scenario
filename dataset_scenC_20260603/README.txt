Scenario C, 12 virtual UEs, 4 ZMQ DUs, ~47min, 34k rows. Main: ue_metrics 24-col schema. offered/: per-UE offered-vs-achieved.

SLICE LABEL VERIFICATION (verified, not assumed):
Per-DU attach order confirmed from srsRAN DU F1-UE-context logs matches config order on all 4 DUs.
f1ap 0/1/2 -> IMSI -> slice mapping is correct: CRITICAL(sd3)/PERFORMANCE(sd1)/BUSINESS(sd2).
Exception by design: DU4 f1ap2 = IMSI017 (vue12) = CRITICAL per ue_slice_map.txt (5 crit/4 perf/3 bus).
