import math
import statistics


def _round(value, digits=4):
    if value is None:
        return None
    return round(float(value), digits)


def _bin_score(value, bin_size=0.5):
    return round(value / bin_size) * bin_size


def _mode_binned(scores, bin_size=0.5):
    bins = [_bin_score(score, bin_size) for score in scores]
    modes = statistics.multimode(bins)
    return min(modes)


def _median_range(scores):
    if len(scores) < 2:
        return 0.0
    quartiles = statistics.quantiles(scores, n=4, method="inclusive")
    return quartiles[2] - quartiles[0]


def _percentile(scores, percentile):
    ordered = sorted(scores)
    count = len(ordered)
    if count == 1:
        return ordered[0]
    rank = (count - 1) * (percentile / 100)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def compute_score_stats(scores):
    if not scores:
        return None
    values = [float(score) for score in scores]
    std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
    return {
        "count": len(values),
        "mean": _round(statistics.mean(values)),
        "median": _round(statistics.median(values)),
        "mode": _round(_mode_binned(values)),
        "max": _round(max(values)),
        "median_range": _round(_median_range(values)),
        "p95": _round(_percentile(values, 95)),
        "std_dev": _round(std_dev),
    }
