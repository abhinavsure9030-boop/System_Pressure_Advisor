# Mnemo — Predictive Memory Pressure Engine
# Part of: System Pressure Advisor
# Author: Abhinav
# Stack: Python 3 + /proc/meminfo (no permissions required)
import time
from collections import deque

# --- MEMORY READER ---
def get_memory():
    data = {}
    with open('/proc/meminfo', 'r') as f:
        for line in f:
            parts = line.split()
            key = parts[0].rstrip(':')
            val = int(parts[1])
            data[key] = val
    return data

def analyze(mem):
    total        = mem['MemTotal']
    available    = mem['MemAvailable']
    swap_used    = mem['SwapTotal'] - mem['SwapFree']
    gpu_used     = mem.get('GPUTotalUsed', 0)
    ion_used     = mem.get('IonTotalUsed', 0)
    committed_as = mem.get('Committed_AS', 0)
    commit_limit = mem.get('CommitLimit', 1)

    return {
        'ram_%'        : round((total - available) / total * 100, 2),
        'swap_%'       : round(swap_used / mem['SwapTotal'] * 100, 2),
        'gpu_mb'       : round(gpu_used / 1024, 1),
        'ion_mb'       : round(ion_used / 1024, 1),
        'committed_kb' : committed_as,
        'commit_ratio' : round(committed_as / commit_limit, 2),
    }

# --- CALIBRATION ---
def calibrate(duration_secs=60, interval=3):
    samples = []
    total   = duration_secs // interval

    print("=" * 50)
    print("  SYSTEM PRESSURE ADVISOR — CALIBRATION")
    print("=" * 50)
    print(f"\n  Leave phone IDLE for {duration_secs} seconds.")
    print("  Don't open any apps. Just let it sit.\n")

    for i in range(total):
        mem = get_memory()
        d   = analyze(mem)
        samples.append(d)

        done    = int((i + 1) / total * 30)
        bar     = '█' * done + '░' * (30 - done)
        percent = int((i + 1) / total * 100)
        print(f"\r  [{bar}] {percent}%  "
              f"RAM:{d['ram_%']}%  "
              f"SWAP:{d['swap_%']}%  "
              f"VAS:{d['commit_ratio']}x",
              end='', flush=True)

        time.sleep(interval)

    print("\n\n  Calibration complete.\n")
    return build_profile(samples)

def build_profile(samples):
    signals = ['ram_%', 'swap_%', 'gpu_mb',
               'ion_mb', 'committed_kb']
    profile = {'baseline': {}, 'thresholds': {}}

    for sig in signals:
        vals = [s[sig] for s in samples]
        avg  = round(sum(vals) / len(vals), 2)
        std  = round((sum((v - avg) ** 2
               for v in vals) / len(vals)) ** 0.5, 2)
        bmax = round(max(vals), 2)
        s    = std if std > 0 else avg * 0.05

        profile['baseline'][sig] = {
            'min' : round(min(vals), 2),
            'max' : bmax,
            'avg' : avg,
            'std' : std,
        }
        profile['thresholds'][sig] = {
            'moderate' : round(bmax + (1 * s), 2),
            'high'     : round(bmax + (3 * s), 2),
            'critical' : round(bmax + (5 * s), 2),
        }

    return profile

def print_profile(profile):
    labels = {
        'ram_%'        : 'RAM Usage',
        'swap_%'       : 'Swap Usage',
        'gpu_mb'       : 'GPU Memory',
        'ion_mb'       : 'ION Memory',
        'committed_kb' : 'VAS Committed',
    }
    print("  YOUR DEVICE BASELINE")
    print("  " + "-" * 40)
    for sig, label in labels.items():
        b = profile['baseline'][sig]
        t = profile['thresholds'][sig]
        print(f"\n  {label}")
        print(f"    avg={b['avg']}  std={b['std']}")
        print(f"    Moderate : > {t['moderate']}")
        print(f"    High     : > {t['high']}")
        print(f"    Critical : > {t['critical']}")
    print()

# --- VAS PRE-SIGNAL (LAYER 0) ---
class VASPreSignal:
    def __init__(self, window=5):
        self.history = deque(maxlen=window)

    def update(self, committed_kb, profile):
        self.history.append(committed_kb)

        if len(self.history) < 3:
            return None

        deltas = [
            self.history[i+1] - self.history[i]
            for i in range(len(self.history) - 1)
        ]
        avg_delta   = sum(deltas) / len(deltas)
        std         = profile['baseline']['committed_kb']['std']
        noise_floor = max(std * 3, 50000)

        if avg_delta > noise_floor * 4:
            return ("🔴 VAS SURGE — RAM explosion imminent",
                    avg_delta)
        elif avg_delta > noise_floor * 2:
            return ("🟠 VAS RISING FAST — RAM pressure incoming",
                    avg_delta)
        elif avg_delta > noise_floor:
            return ("🟡 VAS CLIMBING — watch RAM",
                    avg_delta)
        return None

# --- ADAPTIVE CLASSIFIER ---
def classify_adaptive(d, profile, prev_swap):
    t           = profile['thresholds']
    swap_delta  = d['swap_%'] - prev_swap if prev_swap else 0
    swap_rising = swap_delta > 0.3
    score       = 0

    if d['ram_%'] > t['ram_%']['critical']:      score += 4
    elif d['ram_%'] > t['ram_%']['high']:        score += 3
    elif d['ram_%'] > t['ram_%']['moderate']:    score += 1

    if d['swap_%'] > t['swap_%']['critical']:    score += 4
    elif d['swap_%'] > t['swap_%']['high']:      score += 3
    elif d['swap_%'] > t['swap_%']['moderate']:  score += 2

    if d['gpu_mb'] > t['gpu_mb']['critical']:    score += 4
    elif d['gpu_mb'] > t['gpu_mb']['high']:      score += 3
    elif d['gpu_mb'] > t['gpu_mb']['moderate']:  score += 1

    if d['ion_mb'] > t['ion_mb']['critical']:    score += 3
    elif d['ion_mb'] > t['ion_mb']['high']:      score += 2
    elif d['ion_mb'] > t['ion_mb']['moderate']:  score += 1

    if swap_rising: score += 2

    if score >= 9:   state = "CRITICAL"
    elif score >= 6: state = "HIGH"
    elif score >= 3: state = "MODERATE"
    else:            state = "IDLE"

    return state, score, swap_delta

# --- TRAJECTORY FORECASTER ---
class TrajectoryForecaster:
    def __init__(self):
        self.current_state = None
        self.state_start   = None
        self.duration_secs = 0

    def update(self, state):
        if state != self.current_state:
            self.current_state = state
            self.state_start   = time.time()
            self.duration_secs = 0
        else:
            self.duration_secs = int(
                time.time() - self.state_start)

    def forecast(self):
        d     = self.duration_secs
        state = self.current_state
        mins  = d // 60
        secs  = d % 60
        dur   = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        if state == "CRITICAL":
            if d > 300:  msg = "🚨 CRASH/FREEZE LIKELY"
            elif d > 120: msg = "🔴 HIGH RISK — 2+ mins critical"
            elif d > 30:  msg = "🟠 BUILDING — monitor closely"
            else:         msg = "⚡ SPIKE — may recover"
        elif state == "HIGH":
            if d > 600:   msg = "🟠 SUSTAINED — lag expected"
            elif d > 180: msg = "🟡 EXTENDED — fatiguing"
            else:         msg = "🟡 HIGH — normal active use"
        elif state == "MODERATE":
            msg = "🟢 STABLE — no concern"
        else:
            msg = "🟢 IDLE — recovering"

        return dur, msg

# --- SLIDING WINDOW DETECTOR ---
class SlidingWindowDetector:
    def __init__(self, window=10):
        self.window = deque(maxlen=window)
        self.size   = window

    def update(self, state):
        self.window.append(state)

    def analyze(self):
        if len(self.window) < self.size:
            return None
        critical = self.window.count("CRITICAL")
        high     = self.window.count("HIGH")
        bad      = critical + high

        if critical >= 9:
            return "🚨 CRASH PRECURSOR — 9/10 CRITICAL"
        elif bad >= 9:
            return "🔴 DENSITY ALERT — 9/10 elevated"
        elif bad >= 7:
            return "🟠 PRESSURE DENSE — 7/10 elevated"
        elif bad >= 5:
            return "🟡 ELEVATED — 5/10 above normal"
        return None

# --- MAIN ADVISOR LOOP ---
def run_advisor(profile):
    trajectory = TrajectoryForecaster()
    window_det = SlidingWindowDetector(window=10)
    vas        = VASPreSignal(window=5)
    swap_hist  = deque(maxlen=5)
    prev_swap  = None
    sample_n   = 0

    # hysteresis
    last_state    = "IDLE"
    pending_state = "IDLE"
    state_confirm = 0

    print("=== LIVE MONITORING ===")
    print("Disclaimer: excludes screen, radio, thermal\n")

    while True:
        sample_n += 1
        mem   = get_memory()
        d     = analyze(mem)

        # layer 0 — vas pre-signal
        vas_alert = vas.update(d['committed_kb'], profile)

        # layer 1-3 — adaptive classifier
        state, score, swap_delta = classify_adaptive(
            d, profile, prev_swap)

        # hysteresis
        if state == pending_state:
            state_confirm += 1
        else:
            pending_state = state
            state_confirm = 1
        if state_confirm >= 2:
            last_state = state

        display = last_state
        emoji   = {
            "IDLE"    : "🟢",
            "MODERATE": "🟡",
            "HIGH"    : "🟠",
            "CRITICAL": "🔴"
        }[display]

        # layer 4 — trajectory + window
        trajectory.update(display)
        window_det.update(display)
        dur, traj_msg = trajectory.forecast()
        window_alert  = window_det.analyze()

        # swap warning — overrides hysteresis display
        swap_hist.append(d['swap_%'])
        swap_warn = None
        if len(swap_hist) >= 3:
            trend = all(
                swap_hist[i] < swap_hist[i+1]
                for i in range(len(swap_hist) - 1))
            if d['swap_%'] > profile['thresholds']\
                    ['swap_%']['critical']:
                swap_warn = "⚠️  SWAP CRITICAL"
            elif d['swap_%'] > profile['thresholds']\
                    ['swap_%']['high'] and trend:
                swap_warn = "⚠️  SWAP RISING FAST"

        # output
        print(f"\n[{sample_n}] {emoji} {display}  "
              f"score={score}  in-state:{dur}")
        print(f"  RAM:{d['ram_%']}%  "
              f"SWAP:{d['swap_%']}%  "
              f"(Δ{swap_delta:+.2f}%)")
        print(f"  GPU:{d['gpu_mb']}MB  "
              f"ION:{d['ion_mb']}MB  "
              f"VAS:{round(d['committed_kb']/1024/1024,1)}GB")
        print(f"  Trajectory: {traj_msg}")

        if vas_alert:
            msg, delta = vas_alert
            print(f"  ⚡ PRE-SIGNAL: {msg}  "
                  f"VAS Δ:+{round(delta/1024,1)}MB/sample")
        if window_alert:
            print(f"  {window_alert}")
        if swap_warn:
            print(f"  {swap_warn}")

        print(f"  [Confidence: medium — "
              f"radio/screen excluded]")
        print("─" * 45)

        prev_swap = d['swap_%']
        time.sleep(3)

# --- ENTRY POINT ---
def main():
    print("\n=== SYSTEM PRESSURE ADVISOR ===\n")
    profile = calibrate(duration_secs=60, interval=3)
    print_profile(profile)
    run_advisor(profile)

main()
