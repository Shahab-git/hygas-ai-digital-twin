"""
Time-series simulation v1 — a synthetic plant operating trajectory, built
by repeatedly evaluating the existing STEADY-STATE physics at evolving
operating conditions, one timestep at a time.

HONEST SCOPING, stated here and in the app.py UI: this is NOT a dynamic
process model. Real time-domain plant dynamics (thermal mass, transport
delay, control-loop response, actual startup/upset trajectories) are
explicitly out of scope for this repo — this is exactly the "zero
Dynamics coverage" gap novelty_audit.py's own 8-lens framework already
flags, and this module does not quietly try to close that gap. What it
DOES do: call kinetics.py's/psa.py's real, already-validated steady-state
functions at a SEQUENCE of evolving (T, GHSV, catalyst activity, feed
composition) operating points, producing a plausible-shaped multi-sensor
trajectory for time_series_sim's actual purpose — giving tda_analysis.py
something to run on — not a claim that this reproduces real transient
plant behavior. Each individual point on the trajectory is exactly as
physically real as any other steady-state calculation elsewhere in this
repo; what's synthetic is the SEQUENCE/SCHEDULE of operating conditions
connecting them, and the sensor noise added on top.

SCENARIO: a startup ramp into steady operation, a slow background
catalyst-activity drift (normal wear), then a COORDINATED ANOMALY window
where several operating parameters shift together by amounts individually
too small to trip any one sensor's own threshold — the actual test case
multi-sensor topological analysis is supposed to catch and simple
per-sensor thresholds are supposed to miss (see NAIVE_THRESHOLDS and
naive_threshold_flags() below, used as the comparison baseline in
tda_analysis.py) — then a recovery back toward the background trend.

Multi-sensor dataset, all evolving together over the same timeline:
  - HTS conversion (from kinetics.hts_conversion)
  - LTS conversion (from kinetics.lts_conversion, fed the HTS-stage
    outlet CO fraction, same chaining pattern as uncertainty.py)
  - PSA recovery (from psa.psa_recovery)
  - Catalyst activity factor — NOT a separate model: back-calculated from
    the noisy observed HTS conversion via predictive_maintenance.py's
    real inverse-kinetics root-finder, exactly as a live sensor reading
    would be diagnosed in that section of the app. This means the
    activity-factor column already carries realistic diagnostic noise on
    top of the raw sensor noise, not a clean synthetic curve.

Independent Gaussian sensor noise is added to each of HTS/LTS/PSA before
the activity factor is back-calculated — magnitude is an explicit assumed
default (see SENSOR_NOISE_STD), same honesty pattern as sim_to_real.py's
noise assumptions, not a real instrument spec.
"""
import numpy as np

from . import kinetics, psa, predictive_maintenance

# --- Illustrative assumed defaults — NOT real plant timing/instrument specs ---
SENSOR_NOISE_STD = 0.004  # Gaussian std on each conversion/recovery reading (fraction), per timestep
N_RAMP = 20           # startup ramp duration (timesteps)
N_NORMAL_1 = 45        # steady operation before the anomaly
N_ANOMALY = 20         # coordinated-anomaly window duration
N_RECOVERY = 13        # transition back toward the background trend
N_NORMAL_2 = 32        # steady operation after recovery
N_TOTAL = N_RAMP + N_NORMAL_1 + N_ANOMALY + N_RECOVERY + N_NORMAL_2
# Kept deliberately short: predictive_maintenance.py's real root-finding
# back-calculation (~110ms/call, called once per timestep below) dominates
# runtime -- this length keeps a full run well under Streamlit Cloud's
# free-tier patience for a button click, without touching that validated
# module just to make this feature faster.

# Design-point operating targets (matches this repo's own default slider positions)
HTS_T_TARGET_C, HTS_GHSV_TARGET = 350.0, 2000.0
LTS_T_TARGET_C, LTS_GHSV_TARGET = 220.0, 2000.0
HTS_T_START_C, LTS_T_START_C = 250.0, 160.0
GHSV_START = 500.0
Y_CO2_NOMINAL = 0.35

# Background catalyst wear: a slow, honest, individually-unremarkable drift
# (stays well within predictive_maintenance.py's own 0.95 "healthy" band)
K0_END_OF_RUN = 0.975

# The coordinated anomaly: each shift alone is individually subtle --
# k0_scale dips to 0.965 (activity factor ~0.965, still > the 0.95 healthy
# threshold), k1_scale rises to 1.025 (a few points of PSA recovery, on its
# own comfortably under any reasonable single-sensor alarm band), and feed
# CO2 rises slightly (0.35 -> 0.36) -- individually unremarkable, but all
# three moving the "wrong" way at once is a real coordinated signature a
# naive per-sensor monitor has no way to notice.
ANOMALY_K0_SCALE = 0.965
ANOMALY_K1_SCALE = 1.025
ANOMALY_Y_CO2 = 0.36

# Naive baseline for comparison in tda_analysis.py: flag a timestep if any
# ONE sensor's reading deviates from its own trailing local average by more
# than this, or if the back-calculated activity factor drops below
# predictive_maintenance.py's own real "healthy" threshold. This is a
# reasonable, not a strawman, per-sensor monitor -- it already compares
# against a local rolling baseline, not just a fixed setpoint.
NAIVE_THRESHOLDS = {
    "hts": 0.02, "lts": 0.02, "psa_recovery": 0.02,
    "activity_factor": predictive_maintenance.HEALTHY_THRESHOLD,
}
NAIVE_ROLLING_WINDOW = 20


def _phase_labels():
    labels = (
        ["ramp"] * N_RAMP + ["normal"] * N_NORMAL_1 + ["anomaly"] * N_ANOMALY
        + ["recovery"] * N_RECOVERY + ["normal"] * N_NORMAL_2
    )
    assert len(labels) == N_TOTAL
    return labels


def _schedule():
    """Builds the per-timestep TRUE (noise-free) operating-condition and
    catalyst/PSA-calibration schedule. Returns a dict of arrays, length
    N_TOTAL each."""
    t = np.arange(N_TOTAL)
    phases = _phase_labels()

    hts_T_C = np.full(N_TOTAL, HTS_T_TARGET_C)
    lts_T_C = np.full(N_TOTAL, LTS_T_TARGET_C)
    ghsv = np.full(N_TOTAL, HTS_GHSV_TARGET)

    ramp_frac = np.linspace(0.0, 1.0, N_RAMP)
    hts_T_C[:N_RAMP] = HTS_T_START_C + ramp_frac * (HTS_T_TARGET_C - HTS_T_START_C)
    lts_T_C[:N_RAMP] = LTS_T_START_C + ramp_frac * (LTS_T_TARGET_C - LTS_T_START_C)
    ghsv[:N_RAMP] = GHSV_START + ramp_frac * (HTS_GHSV_TARGET - GHSV_START)

    # Background catalyst wear: linear drift from 1.0 (end of ramp) to
    # K0_END_OF_RUN (end of run), independent of the anomaly overlay below.
    post_ramp_frac = np.clip((t - N_RAMP) / max(N_TOTAL - N_RAMP - 1, 1), 0.0, 1.0)
    k0_background = 1.0 - post_ramp_frac * (1.0 - K0_END_OF_RUN)
    k1_background = np.ones(N_TOTAL)
    y_co2_background = np.full(N_TOTAL, Y_CO2_NOMINAL)

    k0_scale = k0_background.copy()
    k1_scale = k1_background.copy()
    y_co2 = y_co2_background.copy()

    anomaly_start = N_RAMP + N_NORMAL_1
    anomaly_end = anomaly_start + N_ANOMALY
    recovery_end = anomaly_end + N_RECOVERY

    # Smooth (half-cosine) transitions in and out of the anomaly, rather
    # than an instantaneous jump -- a smidge more realistic, and it gives
    # tda_analysis.py's transition-sensitive behavior something honest to
    # respond to at the edges as well as the plateau.
    ramp_in = np.linspace(0, 1, max(N_ANOMALY // 4, 1))
    ramp_out = ramp_in[::-1]
    plateau = np.ones(N_ANOMALY - 2 * len(ramp_in))
    shape = np.concatenate([ramp_in, plateau, ramp_out])
    shape = shape[:N_ANOMALY]

    k0_scale[anomaly_start:anomaly_end] = (
        k0_background[anomaly_start:anomaly_end] - shape * (k0_background[anomaly_start:anomaly_end] - ANOMALY_K0_SCALE)
    )
    k1_scale[anomaly_start:anomaly_end] = 1.0 + shape * (ANOMALY_K1_SCALE - 1.0)
    y_co2[anomaly_start:anomaly_end] = Y_CO2_NOMINAL + shape * (ANOMALY_Y_CO2 - Y_CO2_NOMINAL)

    # Recovery: back toward the (still-drifting) background trend.
    rec_frac = np.linspace(0, 1, N_RECOVERY)
    k0_scale[anomaly_end:recovery_end] = (
        ANOMALY_K0_SCALE + rec_frac * (k0_background[anomaly_end:recovery_end] - ANOMALY_K0_SCALE)
    )
    k1_scale[anomaly_end:recovery_end] = ANOMALY_K1_SCALE + rec_frac * (1.0 - ANOMALY_K1_SCALE)
    y_co2[anomaly_end:recovery_end] = ANOMALY_Y_CO2 + rec_frac * (Y_CO2_NOMINAL - ANOMALY_Y_CO2)

    is_anomaly = np.array([p == "anomaly" for p in phases])

    return {
        "t": t, "phase": np.array(phases), "is_anomaly": is_anomaly,
        "hts_T_C": hts_T_C, "hts_GHSV": ghsv, "lts_T_C": lts_T_C, "lts_GHSV": ghsv.copy(),
        "k0_scale": k0_scale, "k1_scale": k1_scale, "y_co2": y_co2,
    }


def simulate(seed=42, noise_std=SENSOR_NOISE_STD):
    """Runs the full simulated trajectory: real kinetics.py/psa.py steady-
    state physics at every evolving operating point, plus independent
    Gaussian sensor noise, plus a real predictive_maintenance.py inverse-
    kinetics back-calculation of the activity factor from the noisy
    observed HTS reading (reused, not reimplemented).

    Returns a dict of length-N_TOTAL arrays, keyed: t, phase, is_anomaly,
    plus true/observed hts, lts, psa_recovery, and activity_factor.
    """
    sched = _schedule()
    rng = np.random.default_rng(seed)
    n = N_TOTAL

    hts_true = np.empty(n)
    lts_true = np.empty(n)
    psa_true = np.empty(n)

    for i in range(n):
        X_hts = kinetics.hts_conversion(
            T_K=sched["hts_T_C"][i] + 273.15, GHSV=sched["hts_GHSV"][i], k0_scale=sched["k0_scale"][i],
        )
        y_co_after_hts = 0.28 * (1 - X_hts)
        X_lts = kinetics.lts_conversion(
            T_K=sched["lts_T_C"][i] + 273.15, GHSV=sched["lts_GHSV"][i],
            y_CO_in=y_co_after_hts, k0_scale=sched["k0_scale"][i],
        )
        recovery = psa.psa_recovery(y_CO2=sched["y_co2"][i], k1_scale=sched["k1_scale"][i])

        hts_true[i] = X_hts
        lts_true[i] = X_lts
        psa_true[i] = recovery

    hts_obs = np.clip(hts_true + rng.normal(0, noise_std, n), 0.0, 1.0)
    lts_obs = np.clip(lts_true + rng.normal(0, noise_std, n), 0.0, 1.0)
    psa_obs = np.clip(psa_true + rng.normal(0, noise_std, n), 0.0, 1.0)

    activity_factor = np.empty(n)
    for i in range(n):
        result = predictive_maintenance.back_calculate_activity_hts(
            observed_X=hts_obs[i], T_C=sched["hts_T_C"][i], GHSV=sched["hts_GHSV"][i],
        )
        activity_factor[i] = result.get("activity_factor", np.nan)

    out = dict(sched)
    out.update({
        "hts_true": hts_true, "lts_true": lts_true, "psa_recovery_true": psa_true,
        "hts": hts_obs, "lts": lts_obs, "psa_recovery": psa_obs,
        "activity_factor": activity_factor,
    })
    return out


def naive_threshold_flags(data, window=NAIVE_ROLLING_WINDOW, thresholds=None):
    """The per-sensor comparison baseline: flags a timestep if any ONE
    sensor deviates from its own trailing rolling average by more than
    its threshold, or if the activity factor drops below
    predictive_maintenance.py's real 'healthy' threshold. A reasonable
    per-sensor monitor, not a strawman -- exists so tda_analysis.py can
    honestly report whether multi-sensor topology catches anything this
    doesn't."""
    thresholds = thresholds or NAIVE_THRESHOLDS
    n = len(data["t"])

    def _rolling_mean(arr):
        out = np.full(n, np.nan)
        for i in range(n):
            lo = max(0, i - window)
            out[i] = np.mean(arr[lo:i]) if i > lo else arr[i]
        return out

    flags = np.zeros(n, dtype=bool)
    per_sensor = {}
    for key in ("hts", "lts", "psa_recovery"):
        roll = _rolling_mean(data[key])
        dev = np.abs(data[key] - roll)
        sensor_flag = dev > thresholds[key]
        per_sensor[key] = sensor_flag
        flags |= sensor_flag

    activity_flag = data["activity_factor"] < thresholds["activity_factor"]
    per_sensor["activity_factor"] = activity_flag
    flags |= activity_flag

    return flags, per_sensor


if __name__ == "__main__":
    data = simulate()
    flags, per_sensor = naive_threshold_flags(data)

    anomaly_idx = np.where(data["is_anomaly"])[0]
    print(f"Simulated {N_TOTAL} timesteps: ramp[0:{N_RAMP}) normal anomaly[{anomaly_idx[0]}:{anomaly_idx[-1] + 1}) "
          f"recovery normal\n")

    print("Per-sensor deltas during the anomaly plateau (vs. immediately-preceding normal period):")
    pre_window = slice(N_RAMP + N_NORMAL_1 - 20, N_RAMP + N_NORMAL_1)
    plateau = slice(anomaly_idx[len(anomaly_idx) // 3], anomaly_idx[-len(anomaly_idx) // 3])
    for key in ("hts", "lts", "psa_recovery"):
        pre_mean = np.mean(data[key][pre_window])
        plateau_mean = np.mean(data[key][plateau])
        print(f"  {key}: pre-anomaly mean={pre_mean:.4f}  anomaly-plateau mean={plateau_mean:.4f}  "
              f"delta={plateau_mean - pre_mean:+.4f}  (naive threshold: {NAIVE_THRESHOLDS[key]:.3f})")
    act_pre = np.mean(data["activity_factor"][pre_window])
    act_plateau = np.mean(data["activity_factor"][plateau])
    print(f"  activity_factor: pre-anomaly mean={act_pre:.4f}  anomaly-plateau mean={act_plateau:.4f}  "
          f"(healthy threshold: {NAIVE_THRESHOLDS['activity_factor']:.3f})")

    print(f"\nNaive per-sensor flags raised during the anomaly plateau: "
          f"{int(flags[plateau].sum())} / {plateau.stop - plateau.start} timesteps")
    print(f"Naive per-sensor flags raised elsewhere (false-positive check): "
          f"{int(flags[~data['is_anomaly']].sum())} / {int((~data['is_anomaly']).sum())} timesteps")
