"""Session analysis relative to each participant's baseline.

Documented rules
----------------
Data quality:  a reading with signal_quality < MIN_SIGNAL_QUALITY (0.5) is a
               data-quality issue. It is excluded from every statistic.
Sufficiency:   a session needs at least MIN_USABLE_READINGS (3) usable readings
               AND at least MIN_USABLE_FRACTION (60%) of its readings usable.
               Otherwise the result is "Insufficient data" - no claim is made
               about the participant.
Classification (based on peak heart rate above the personal baseline):
               < 25%            Normal (near baseline)
               25% to < 75%     Moderate exertion
               >= 75%           High exertion
               An elevation of 25% or more while mean activity_level is below
               0.30 is reported as "Unusual" (heart rate not explained by activity).
Recovery:      only judged when peak elevation is >= 25%. Recovery % is how much
               of the peak elevation is gone by the last usable reading;
               >= 50% is "recovering", otherwise "slow recovery".
"""
from dataclasses import dataclass, field
from statistics import mean

MIN_SIGNAL_QUALITY = 0.5
MIN_USABLE_READINGS = 3
MIN_USABLE_FRACTION = 0.6
MODERATE_PCT = 25.0
HIGH_PCT = 75.0
LOW_ACTIVITY = 0.30
RECOVERY_OK = 50.0
SKIN_RATIO_HIGH = 1.5
TEMP_RISE = 0.5


@dataclass
class FitnessSession:
    """A group of readings for one session plus the participant they belong to."""
    session_id: str
    participant: object
    readings: list = field(default_factory=list)

    def __post_init__(self):
        self.readings = sorted(self.readings, key=lambda r: r.timestamp)

    @property
    def usable(self):
        return [r for r in self.readings if r.signal_quality >= MIN_SIGNAL_QUALITY]

    @property
    def has_sufficient_data(self):
        n, total = len(self.usable), len(self.readings)
        return n >= MIN_USABLE_READINGS and n / total >= MIN_USABLE_FRACTION


class SessionAnalyzer:
    def analyse(self, session):
        """Return a result dictionary for one FitnessSession."""
        p = session.participant
        result = {
            "session_id": session.session_id,
            "participant_id": p.participant_id,
            "participant_name": p.name,
            "readings_total": len(session.readings),
            "readings_usable": len(session.usable),
            "classification": "",
            "recovery": "",
            "avg_heart_rate": "", "peak_heart_rate": "", "peak_elevation_pct": "",
            "recovery_pct": "", "skin_ratio": "", "temp_change": "",
            "mean_activity": "", "mean_signal_quality": "",
            "reasons": [],
        }
        if not session.has_sufficient_data:
            result["classification"] = "Insufficient data"
            result["recovery"] = "not assessed"
            result["reasons"].append(
                f"{result['readings_usable']} of {result['readings_total']} readings are usable "
                f"(signal quality >= {MIN_SIGNAL_QUALITY}); a result needs at least "
                f"{MIN_USABLE_READINGS} usable readings making up {MIN_USABLE_FRACTION:.0%} of the session.")
            return result

        use = session.usable
        base_hr = p.baseline_heart_rate
        peak = max(use, key=lambda r: r.heart_rate)
        peak_pct = (peak.heart_rate - base_hr) / base_hr * 100
        mean_act = mean(r.activity_level for r in use)
        skin_ratio = mean(r.skin_response for r in use) / p.baseline_skin_response \
            if p.baseline_skin_response else 0.0
        temp_change = mean(r.temperature for r in use) - p.baseline_temperature

        result.update(
            avg_heart_rate=round(mean(r.heart_rate for r in use), 1),
            peak_heart_rate=peak.heart_rate,
            peak_elevation_pct=round(peak_pct, 1),
            skin_ratio=round(skin_ratio, 2),
            temp_change=round(temp_change, 2),
            mean_activity=round(mean_act, 2),
            mean_signal_quality=round(mean(r.signal_quality for r in use), 2),
        )
        reasons = result["reasons"]
        reasons.append(f"Peak heart rate {peak.heart_rate:.0f} bpm is {peak_pct:+.1f}% versus "
                       f"baseline {base_hr:.0f} bpm (at timestamp {peak.timestamp}).")

        if peak_pct < MODERATE_PCT:
            label = "Normal (near baseline)"
        elif peak_pct < HIGH_PCT:
            label = "Moderate exertion"
        else:
            label = "High exertion"
        if peak_pct >= MODERATE_PCT and mean_act < LOW_ACTIVITY:
            label = "Unusual"
            reasons.append(f"Heart rate is elevated but mean activity is only {mean_act:.2f} "
                           f"(< {LOW_ACTIVITY}), so activity does not explain it.")
        else:
            reasons.append(f"Mean activity level {mean_act:.2f}.")
        result["classification"] = label

        if skin_ratio >= SKIN_RATIO_HIGH:
            reasons.append(f"Skin response averages {skin_ratio:.2f}x baseline (elevated).")
        else:
            reasons.append(f"Skin response averages {skin_ratio:.2f}x baseline (within normal range).")
        if temp_change >= TEMP_RISE:
            reasons.append(f"Skin temperature is {temp_change:+.2f} C above baseline.")
        else:
            reasons.append(f"Skin temperature change {temp_change:+.2f} C is small.")

        self._assess_recovery(result, use, peak, base_hr, peak_pct)
        return result

    @staticmethod
    def _assess_recovery(result, use, peak, base_hr, peak_pct):
        reasons = result["reasons"]
        if peak_pct < MODERATE_PCT:
            result["recovery"] = "not applicable"
            reasons.append("Recovery not assessed because heart rate never rose notably above baseline.")
            return
        last = use[-1]
        if last.timestamp == peak.timestamp:
            result["recovery"] = "not observed"
            reasons.append("The peak is the last usable reading, so recovery was not observed.")
            return
        pct = (peak.heart_rate - last.heart_rate) / (peak.heart_rate - base_hr) * 100
        result["recovery_pct"] = round(pct, 1)
        result["recovery"] = "recovering" if pct >= RECOVERY_OK else "slow recovery"
        reasons.append(f"By the last reading ({last.heart_rate:.0f} bpm) {pct:.0f}% of the peak "
                       f"elevation was gone: {result['recovery']}.")
