from collections import Counter, defaultdict
import numpy as np
import pandas as pd

DIGITS = list(range(10))

def _smooth(counts, alpha=1.0):
    arr = np.asarray([counts.get(d, 0) for d in DIGITS], dtype=float) + alpha
    return arr / arr.sum()

def run_agents(ticks: list[dict], min_sample: int):
    digits = [int(t["digit"]) for t in ticks]
    if not digits:
        raise ValueError("No ticks available")
    results = {}
    windows = {"fast": min(100, len(digits)), "intermediate": min(500, len(digits)),
               "primary": min(5000, len(digits)), "stability": min(20000, len(digits))}
    # Distribution: smoothed empirical distribution, full 10-class vector.
    for name, size in windows.items():
        sample = digits[-size:]
        counts = Counter(sample)
        probs = _smooth(counts)
        results[f"distribution_{name}"] = {
            "probabilities": probs.tolist(), "sample_size": len(sample),
            "candidate": int(np.argmax(probs)), "method": "Dirichlet(1) smoothed frequency",
            "warning": "Historical frequency is descriptive, not proof of next-tick edge."
        }

    # First-order transition agent: condition on last observed digit.
    trans = defaultdict(Counter)
    for a,b in zip(digits[:-1], digits[1:]):
        trans[a][b] += 1
    prev = digits[-1]
    transition_counts = trans[prev]
    transition_probs = _smooth(transition_counts)
    results["transition"] = {
        "probabilities": transition_probs.tolist(), "sample_size": int(sum(transition_counts.values())),
        "candidate": int(np.argmax(transition_probs)), "condition": f"previous digit={prev}",
        "method": "First-order transition with Laplace smoothing",
        "warning": "Conditional counts may be sparse; state-specific inference is noisy."
    }

    # Bayesian categorical predictive distribution on primary window.
    primary = digits[-windows["primary"]:]
    bayes = _smooth(Counter(primary), alpha=0.5)
    results["bayesian"] = {
        "probabilities": bayes.tolist(), "sample_size": len(primary),
        "candidate": int(np.argmax(bayes)), "method": "Dirichlet-multinomial predictive",
        "warning": "Posterior predictive inherits the stationarity assumption."
    }

    # Adversarial checks: compare recent and longer window, calculate entropy.
    recent = _smooth(Counter(digits[-min(250,len(digits)):]))
    longp = _smooth(Counter(digits[-min(5000,len(digits)):]))
    entropy = float(-(longp * np.log(longp)).sum() / np.log(10))
    drift = float(np.abs(recent-longp).sum()/2)
    results["adversarial"] = {
        "probabilities": longp.tolist(), "sample_size": len(digits),
        "candidate": int(np.argmax(longp)), "normalized_entropy": entropy,
        "recent_long_total_variation": drift,
        "warning": "Drift/entropy are diagnostics, not predictive signals."
    }

    # Ensemble is deliberately conservative: equal average of primary, transition, Bayesian.
    vectors = [results["distribution_primary"]["probabilities"],
               results["transition"]["probabilities"], results["bayesian"]["probabilities"]]
    ensemble = np.mean(np.asarray(vectors), axis=0)
    ensemble = ensemble / ensemble.sum()
    candidate = int(np.argmax(ensemble))
    # Evidence is not considered validated merely because a model outputs >10%.
    edge = float(ensemble[candidate] - 0.10)
    mandatory_n = len(digits) >= min_sample
    # Compare the chosen digit's recent and longer probability as a basic stability guard.
    stable = abs(float(recent[candidate] - longp[candidate])) <= 0.12
    # Do not assert a signal absent walk-forward evidence and calibrated EV.
    approved = mandatory_n and edge >= 0.015 and stable and False
    reason = ("No actionable signal: predictive edge has not yet been validated on untouched "
              "walk-forward data with calibration and payout inputs.")
    results["ensemble"] = {
        "probabilities": ensemble.tolist(), "candidate": candidate, "estimated_probability": float(ensemble[candidate]),
        "nominal_baseline": 0.10, "apparent_edge": edge, "sample_size": len(digits),
        "status": "APPROVED" if approved else "ABSTAIN",
        "reason": reason, "agents_used": ["distribution_primary","transition","bayesian"]
    }
    return results
