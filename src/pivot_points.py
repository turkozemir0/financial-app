"""Pivot point calculations: Classic, Fibonacci, Camarilla, Woodie, DeMark."""

from __future__ import annotations


def calculate_pivots(high: float, low: float, close: float, open_: float) -> dict:
    """Return all 5 pivot systems with S1-S3 and R1-R3 levels."""
    return {
        "classic": _classic(high, low, close),
        "fibonacci": _fibonacci(high, low, close),
        "camarilla": _camarilla(high, low, close),
        "woodie": _woodie(high, low, close),
        "demark": _demark(high, low, close, open_),
    }


def _round4(v: float) -> float:
    return round(v, 4)


def _classic(h: float, l: float, c: float) -> dict:
    pp = (h + l + c) / 3
    r1 = 2 * pp - l
    s1 = 2 * pp - h
    r2 = pp + (h - l)
    s2 = pp - (h - l)
    r3 = h + 2 * (pp - l)
    s3 = l - 2 * (h - pp)
    return {k: _round4(v) for k, v in
            {"pp": pp, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}.items()}


def _fibonacci(h: float, l: float, c: float) -> dict:
    pp = (h + l + c) / 3
    diff = h - l
    r1 = pp + 0.382 * diff
    r2 = pp + 0.618 * diff
    r3 = pp + 1.0 * diff
    s1 = pp - 0.382 * diff
    s2 = pp - 0.618 * diff
    s3 = pp - 1.0 * diff
    return {k: _round4(v) for k, v in
            {"pp": pp, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}.items()}


def _camarilla(h: float, l: float, c: float) -> dict:
    diff = h - l
    r1 = c + 1.1 * diff / 12
    r2 = c + 1.1 * diff / 6
    r3 = c + 1.1 * diff / 4
    s1 = c - 1.1 * diff / 12
    s2 = c - 1.1 * diff / 6
    s3 = c - 1.1 * diff / 4
    pp = (h + l + c) / 3
    return {k: _round4(v) for k, v in
            {"pp": pp, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}.items()}


def _woodie(h: float, l: float, c: float) -> dict:
    pp = (h + l + 2 * c) / 4
    r1 = 2 * pp - l
    r2 = pp + (h - l)
    r3 = r1 + (h - l)
    s1 = 2 * pp - h
    s2 = pp - (h - l)
    s3 = s1 - (h - l)
    return {k: _round4(v) for k, v in
            {"pp": pp, "r1": r1, "r2": r2, "r3": r3, "s1": s1, "s2": s2, "s3": s3}.items()}


def _demark(h: float, l: float, c: float, o: float) -> dict:
    if c < o:
        x = h + 2 * l + c
    elif c > o:
        x = 2 * h + l + c
    else:
        x = h + l + 2 * c
    pp = x / 4
    r1 = x / 2 - l
    s1 = x / 2 - h
    return {k: _round4(v) for k, v in
            {"pp": pp, "r1": r1, "s1": s1}.items()}
