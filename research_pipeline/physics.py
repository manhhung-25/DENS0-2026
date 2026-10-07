"""Lumped surrogate physics. Parameters are illustrative, not OEM calibrated."""
import numpy as np

FAULTS = ("normal", "bearing", "friction", "thermal", "backlash", "slow", "sensor_drift", "encoder_error")
JOINT_IDS = tuple(f"J{i}" for i in range(1, 8))
PROFILES = ("transient", "progressive", "intermittent")


def envelope(t, start, duration, profile="transient"):
    """Causal fault excitation; ramp down represents a virtual repair intervention."""
    age = np.asarray(t, dtype=float) - start
    on = (age >= 0) & (age < duration)
    fade = np.clip(np.minimum(age / .45, (duration - age) / .45), 0, 1)
    if profile == "progressive":
        fade *= np.clip(age / max(duration * .7, .1), 0, 1)
    elif profile == "intermittent":
        fade *= (.5 + .5 * np.sin(2 * np.pi * age / 1.6) > .45)
    elif profile != "transient":
        raise ValueError("Unknown fault profile")
    value = np.where(on, fade, 0.)
    return float(value) if value.ndim == 0 else value


def derivatives(x, dt, causal=False):
    """Velocity, acceleration and THIRD derivative jerk, with explicit seconds."""
    if not np.isfinite(dt) or dt <= 0:
        raise ValueError("dt must be positive seconds")
    x = np.asarray(x, dtype=float)
    if len(x) < 4:
        raise ValueError("At least four samples required")
    result = []
    for _ in range(3):
        if causal:
            # Least-squares backward polynomial, only past/current observations.
            out = np.full_like(x, np.nan)
            for i in range(4, len(x)):
                n = min(9, i + 1)
                ts = np.arange(-n + 1, 1) * dt
                weights = np.linalg.pinv(np.vander(ts, 4))[-2]
                out[i] = weights @ x[i - n + 1:i + 1]
            x = out
        else:
            x = np.gradient(x, dt, axis=0, edge_order=2)
        result.append(x.copy())
    return tuple(result)


def thermal_step(temperature, ambient, power, cooling, dt, capacity=9.):
    return temperature + dt * (power - cooling * (temperature - ambient)) / capacity


def sensor_sample(speed, torque, temperature, ambient, load, level, reversal, phase, noise):
    """Shared causal sensor surrogate for the dataset and video what-if engine.

    Vibration/acoustic values are aggregate envelopes, NOT high-rate waveforms.
    The same bearing impulses and friction power affect multiple channels.
    """
    friction = level.get("friction", 0.)
    bearing = level.get("bearing", 0.)
    backlash = level.get("backlash", 0.)
    impact = (.5 + .5 * np.sin(phase * 11)) ** 10
    vib = .8 + .12 * load + .18 * abs(speed)
    vib += bearing * (.6 + abs(speed)) * (.55 + 1.8 * impact)
    vib += .3 * friction * abs(speed) + .65 * backlash * reversal
    vib += 1.3 * level.get("sensor_drift", 0.) + noise[0]
    sound = 54 + 1.4 * load + 1.7 * abs(speed)
    sound += 5 * bearing * (.3 + abs(speed)) * (.7 + impact)
    sound += 2.5 * friction * abs(speed) + 2 * backlash * reversal + noise[1]
    current = .65 + abs(torque) / 2.4 + noise[2]
    return max(.01, vib), sound, max(.01, current), temperature + noise[3]


def simulate_cycle(label="normal", faulty_joint=None, *, seed=0, steps=280,
                   dt=.04, domain="train", profile=None, severity=None):
    """Seven independent joint servos with friction, deadband and thermal state.

    This is NOT Panda FK/full rigid-body dynamics. Mechanical state, encoder
    measurement and camera measurement are separate, especially for sensor faults.
    """
    if label not in FAULTS or domain not in ("train", "validation", "test"):
        raise ValueError("Invalid label/domain")
    if steps < 80 or not np.isfinite(dt) or dt <= 0:
        raise ValueError("Need at least 80 samples and positive dt")
    rng = np.random.default_rng(seed)
    j = -1 if label == "normal" else int(rng.integers(7) if faulty_joint is None else faulty_joint)
    if label != "normal" and not 0 <= j < 7:
        raise ValueError("Joint must be zero-based 0..6")
    profile = profile or str(rng.choice(PROFILES))
    if profile not in PROFILES:
        raise ValueError("Invalid profile")
    sev = float(rng.uniform(.35, 1.5) if severity is None else severity)
    if not np.isfinite(sev) or not 0 <= sev <= 2.5:
        raise ValueError("Severity outside 0..2.5")
    # Test domain changes load/speed/noise and harmonics, not just RNG seed.
    shifted = domain == "test"
    load = float(rng.uniform(1.15, 1.65) if shifted else rng.uniform(.6, 1.2))
    frequency = float(rng.uniform(.22, .32) if shifted else rng.uniform(.13, .22))
    ambient = float(rng.uniform(28, 35))
    t = np.arange(steps) * dt
    phases = rng.uniform(-np.pi, np.pi, 7)
    amplitude = rng.uniform(.18, .5, 7)
    target = amplitude * np.sin(2 * np.pi * frequency * t[:, None] + phases)
    target += (.05 if shifted else .025) * np.sin(4 * np.pi * frequency * t[:, None] + phases)
    start = float(rng.uniform(1.8, 3.1))
    duration = float(rng.uniform(4.5, 6.5))
    duration = min(duration, t[-1] - start - 1.)
    excitation = envelope(t, start, duration, profile) * (0 if label == "normal" else sev)
    q = np.zeros_like(target)
    q[0] = target[0]
    vel = np.zeros(7)
    temperature = np.full(7, ambient + 4.)
    signal = {name: np.empty_like(target) for name in ("vibration", "acoustic", "current", "temperature")}
    torques = np.zeros_like(target)
    mechanical_q = np.zeros_like(target)
    encoder = np.zeros_like(target)
    camera = np.zeros_like(target)
    truth = np.zeros((steps, 7), dtype=np.int8)
    noise_scale = 1.6 if shifted else 1.
    ext_sound = rng.normal(0, .7, steps) + .5 * np.sin(.8 * t)
    for i in range(steps):
        for k in range(7):
            level = {label: float(excitation[i])} if k == j else {}
            f = level.get("friction", 0.)
            limit = 7. / (1 + 2 * level.get("slow", 0.))
            requested = 24 * (target[i, k] - q[max(0, i - 1), k]) - 3.2 * vel[k]
            torque = np.clip(requested, -limit, limit)
            if i:
                resisting = (.10 + .8 * f) * np.tanh(vel[k] * 30) + (.25 + .5 * f) * vel[k]
                acc = (torque - resisting) / (.65 * load)
                vel[k] = np.clip(vel[k] + acc * dt, -4, 4)
                q[i, k] = q[i - 1, k] + vel[k] * dt
            torques[i, k] = torque
            # Compliance/deadband is applied to output, not to the encoder.
            deadband = .04 * level.get("backlash", 0.) * np.tanh(vel[k] * 20)
            mechanical_q[i, k] = q[i, k] - deadband
            # Measurement faults must not alter true mechanical motion.
            encoder[i, k] = q[i, k] + .045 * level.get("encoder_error", 0.)
            encoder[i, k] += rng.normal(0, .0015 * noise_scale)
            camera[i, k] = mechanical_q[i, k] + rng.normal(0, .003 * noise_scale)
            # I^2R and friction work heat the same state that feeds temperature.
            current = .65 + abs(torque) / 2.4
            power = .25 * current ** 2 + (.1 + .8 * f) * abs(vel[k])
            power += .7 * level.get("bearing", 0.) * abs(vel[k])
            cooling = .25 / (1 + 2 * level.get("thermal", 0.))
            temperature[k] = thermal_step(temperature[k], ambient, power, cooling, dt)
            previous_vel = (q[i - 1, k] - q[max(0, i - 2), k]) / dt if i else vel[k]
            reversal = float(vel[k] * previous_vel < 0)
            noise = rng.normal(0, [.055, .45, .05, .10]) * noise_scale
            noise[1] += ext_sound[i]
            values = sensor_sample(vel[k], torque, temperature[k], ambient, load,
                                   level, reversal, 2 * np.pi * frequency * t[i], noise)
            for name, value in zip(("vibration", "acoustic", "current", "temperature"), values):
                signal[name][i, k] = value
            truth[i, k] = int(excitation[i] > .015 and k == j)
    vel, acc, jerk = derivatives(mechanical_q, dt)
    return dict(signal, t=t, dt=dt, target=target, actual=mechanical_q,
                encoder=encoder, camera=camera, torque=torques,
                velocity=vel, acceleration=acc, jerk=jerk, truth=truth,
                label=label, faulty_joint=j, joint_ids=JOINT_IDS, domain=domain,
                seed=seed, load=load, ambient=ambient, speed_hz=frequency,
                profile=profile, severity=sev, fault_start_s=start,
                fault_end_s=start + duration, generator_version="3.0.0",
                units={"target": "rad", "camera": "rad (virtual camera)",
                       "current": "A", "temperature": "degC", "vibration": "mm/s envelope",
                       "acoustic": "dB envelope", "jerk": "rad/s^3"})


def quality_check(cycle):
    fields = ("target", "actual", "camera", "encoder", "temperature", "current", "vibration", "acoustic")
    failures = [f"nonfinite:{name}" for name in fields if not np.isfinite(cycle[name]).all()]
    if not np.all(np.diff(cycle["t"]) > 0):
        failures.append("timestamp_order")
    if any(cycle[name].shape != (len(cycle["t"]), 7) for name in fields):
        failures.append("seven_joint_shape")
    if np.max(np.abs(cycle["actual"])) > 3.2:
        failures.append("surrogate_position_range")
    if np.min(cycle["current"]) < 0 or np.min(cycle["vibration"]) < 0:
        failures.append("negative_envelope")
    return {"accepted": not failures, "failures": failures,
            "scope": "numerical and surrogate bounds, not OEM/field validation"}
