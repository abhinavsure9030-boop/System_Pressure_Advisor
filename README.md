# System Pressure Advisor

> A five-layer predictive memory pressure classifier for Android.
> Built entirely from `/proc/meminfo` — no root, no special permissions.

---

## What it is

System Pressure Advisor is a real-time system health monitor that 
predicts memory pressure and potential lag/crash events before they 
happen. Unlike every existing battery and memory tool that tells you 
what already occurred, this tool tells you what is about to occur.

It classifies your Android device into four pressure states — IDLE, 
MODERATE, HIGH, CRITICAL — and fires predictive warnings using a 
five-layer signal stack derived entirely from readable system files.

---

## The problem it solves

Every memory and battery monitor on Android shows you history.
- "You used 4GB of RAM"
- "Battery dropped 20% in the last hour"

None of them answer the question that actually matters:

**What is about to happen to my system right now?**

A developer wants to know if their device is about to lag before it does.
A user wants a warning before the freeze, not a report after it.

---

## Why existing tools don't solve it

Most tools rely on restricted Android APIs:
- `BatteryStatsManager` — requires system-level permission
- `NetworkStatsManager` — requires privileged access
- Hardware battery registers — blocked without root

This project takes a different approach entirely. Instead of asking 
Android for permission to read hardware, it reads the mathematical 
relationships between signals that are always readable:

```

/proc/meminfo  →  RAM, swap, virtual address space,
                  GPU memory, ION allocator usage
```

No permissions. No root. No hardware APIs. Pure signal derivation.

---

## Architecture — The Five Layer Stack

```
LAYER 0  →  VAS Pre-Signal
            Tracks Committed_AS delta across samples
            Fires BEFORE RAM moves
            Catches OS-level memory intent

LAYER 1  →  RAM Pressure
            Adaptive threshold derived from calibration
            Relative to YOUR device baseline, not hardcoded

LAYER 2  →  Swap Pressure  
            Trend detection across 5-sample window
            Rising swap = RAM exhausted, kernel spilling

LAYER 3  →  Subsystem Stress
            GPU memory (GPUTotalUsed)
            ION allocator (IonTotalUsed)
            Camera, video decoder, display activity

LAYER 4  →  Temporal Analysis
            Trajectory forecaster — time-in-state escalation
            Sliding window detector — density of bad samples
            10-sample window, fires at 5/7/9 elevated threshold
```

### Self-Calibrating Thresholds

On first run the system samples your device at idle for 60 seconds.
Every threshold — RAM, swap, GPU, ION, VAS — is derived from YOUR 
baseline using standard deviation bands:

```
moderate  =  baseline_max + (1 × std)
high      =  baseline_max + (3 × std)
critical  =  baseline_max + (5 × std)
```

No hardcoded values. The same code runs correctly on a budget phone 
with 2GB RAM and a flagship with 12GB — because it calibrates to 
whatever it finds.

---

## Validated Results

Three controlled test runs were conducted on a real Android device.

### Run 1 — Idle Baseline
70+ consecutive samples. Score=0 throughout.
Zero false positives on a genuinely idle system.
Proves calibration accuracy and threshold correctness.

```

[1]  🟢 IDLE  score=0   RAM:64.63%  SWAP:23.84%
[10] 🟢 IDLE  score=0   RAM:63.69%  SWAP:23.84%
[50] 🟢 IDLE  score=0   RAM:64.24%  SWAP:23.95%
[70] 🟢 IDLE  score=0   RAM:64.32%  SWAP:23.95%
```




### Run 2— App Download + Installation (Subway Surfers, 158MB)
Full prediction chain fired in correct layer order.
VAS delta peaked at +14,553MB/sample during APK unpacking.
Layer 0 detected Play Store speculative memory prefetch
before download was initiated.

```

[5]  VAS SURGE fires          ← before download started
[17] CRITICAL confirmed        ← 36 seconds later
[34] VAS Δ: +2715MB/sample    ← install begins
[36] VAS Δ: +14553MB/sample   ← APK unpacking peak
```

---

## Honest Limitations

This tool deliberately admits what it cannot see.

**Excluded signals:**
- Screen brightness — significant drain factor, not in /proc/meminfo
- Cellular/WiFi radio transmit power — largest drain on active 4G/5G
- Thermal state — chip temperature affects power draw significantly
- Per-process attribution — we see system totals, not which app

**What this means for forecasts:**
Drain estimates are probabilistic ranges, not precise numbers.
The tool says "15-22% per hour" not "18.3% per hour."
Honest uncertainty over fabricated confidence.

**Observer effect:**
The monitoring program itself contributes to RAM usage over extended 
runs. Short observation windows recommended for cleanest baseline.

**VAS pre-signal sensitivity:**
Layer 0 will fire during autonomous OS background activity even on 
idle systems. This is correct behavior — the OS is never truly idle —
but users should interpret VAS alerts as "something is claiming memory" 
not necessarily "user-initiated pressure incoming."

---

## How to Run

**Requirements:** Python 3, Android device, Pydroid 3 or Termux

```bash
python advisor.py
```

On first launch: leave phone idle for 60 seconds during calibration.
Calibration runs once per session and stores thresholds in memory.
After calibration, monitoring begins automatically.

**Controls:** Ctrl+C to stop

---

## Design Philosophy

Every architectural decision in this project follows one principle:

**Honest uncertainty over fabricated confidence.**

- Probabilistic drain ranges instead of false precision
- Explicit disclaimer on every sample output
- Calibration derived from real device behavior, not manufacturer specs
- VAS pre-signal reports what it sees, not what it assumes
- Limitations documented in the tool output itself, not hidden in docs

This is the same principle that separates a useful instrument 
from a convincing lie.

---

## What I'd Build Next

**Universal input model** — let users declare available signals.
Missing signals widen the uncertainty band explicitly rather than 
breaking the classifier. Same engine, any platform.

**Exam integrity layer** — the same VAS + ION spike detection 
that catches app installations can detect background AI tools 
opening during proctored exams. Calibrate baseline at exam start, 
flag anomalous process signatures mid-exam.

**Drain correlation training** — accumulate timestamped pressure 
state logs alongside manual battery readings to build a 
device-specific drain curve over time. The model improves 
with every session.

---

## Built With

- Python 3 — signal processing and classification engine
- `/proc/meminfo` — sole data source, no permissions required
- Pydroid 3 on Android — entire project built on a phone

---

*Confidence: medium — radio, screen brightness, and thermal 
signals excluded from all estimates.*
```
