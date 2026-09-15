from __future__ import annotations


def signature_trace_metrics(image_data):
    """Return simple geometry metrics for a drawable-canvas image.

    A signature must be more than a non-empty canvas: taps, dots and tiny strokes
    are rejected. The function intentionally checks gesture substance, not identity.
    """
    if image_data is None:
        return {"valid": False, "reason": "empty", "pixels": 0, "width": 0, "height": 0, "rows": 0, "cols": 0}
    try:
        rgb=image_data[:,:,:3]
        # Canvas background is very light; count clearly non-background pixels.
        mask=(rgb < 220).any(axis=2)
        ys,xs=mask.nonzero()
        pixels=int(mask.sum())
        if pixels == 0:
            return {"valid": False, "reason": "empty", "pixels": 0, "width": 0, "height": 0, "rows": 0, "cols": 0}
        width=int(xs.max()-xs.min()+1); height=int(ys.max()-ys.min()+1)
        rows=int(len(set(ys.tolist()))); cols=int(len(set(xs.tolist())))
        # Conservative thresholds: reject taps/dots and micro-strokes while allowing
        # short genuine signatures/initials on phone, tablet or mouse.
        valid=(pixels >= 180 and width >= 45 and height >= 12 and rows >= 10 and cols >= 35)
        reason='ok' if valid else 'too_small'
        return {"valid": valid, "reason": reason, "pixels": pixels, "width": width, "height": height, "rows": rows, "cols": cols}
    except Exception:
        return {"valid": False, "reason": "invalid", "pixels": 0, "width": 0, "height": 0, "rows": 0, "cols": 0}


def signature_trace_is_valid(image_data):
    return bool(signature_trace_metrics(image_data).get("valid"))
