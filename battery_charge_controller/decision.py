from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from .calendar import ChargeWindow, Segment
from .config import ChargeModel


class DecisionAction(str, Enum):
	DISABLED="disabled"
	INVALID_DATA="invalid_data"
	INVALID_SETTINGS="invalid_settings"
	OUTSIDE_WINDOW="outside_window"
	OBSERVE="observe"
	WAIT="wait"
	START="start"
	CONTINUE="continue"
	RESET="reset"


@dataclass(frozen=True)
class Decision:
	action: DecisionAction
	reason: str
	segment: Segment
	estimated_minutes: float | None=None
	start_at: datetime | None=None
	end_at: datetime | None=None


def taper_extra_minutes(soc: float) -> float:
	if soc <= 98:
		return 0.0
	if soc <= 99:
		return (soc-98)*0.8
	return 0.8+(min(soc, 100)-99)*5.7


def estimate_night_minutes(from_soc: float, to_soc: float, model: ChargeModel) -> float:
	return max(0.0, to_soc-from_soc)*model.full_charge_minutes/model.reference_soc_range


def estimate_day_minutes(from_soc: float, to_soc: float, model: ChargeModel) -> float:
	linear=max(0.0, to_soc-from_soc)*model.full_charge_minutes/model.reference_soc_range
	taper=max(0.0, taper_extra_minutes(to_soc)-taper_extra_minutes(from_soc))
	return linear+taper


def evaluate_segment(*, segment: Segment, now: datetime, window: ChargeWindow, soc: float | None, threshold: float, target: float, enabled: bool, active: bool, model: ChargeModel) -> Decision:
	if active and now.astimezone(timezone.utc) >= window.end.astimezone(timezone.utc):
		return Decision(DecisionAction.RESET, "hard_stop", segment, end_at=window.end)
	if soc is None or not 0 <= soc <= 100:
		return Decision(DecisionAction.INVALID_DATA, "invalid_soc", segment, end_at=window.end)
	if active and soc >= target:
		return Decision(DecisionAction.RESET, "target_reached", segment, end_at=window.end)
	if active:
		return Decision(DecisionAction.CONTINUE, "charging", segment, end_at=window.end)
	if not enabled:
		return Decision(DecisionAction.DISABLED, "segment_disabled", segment)
	if not 20 <= threshold <= 100 or not 20 <= target <= 100 or target < threshold:
		return Decision(DecisionAction.INVALID_SETTINGS, "invalid_threshold_target", segment)
	if not window.contains(now):
		return Decision(DecisionAction.OUTSIDE_WINDOW, "outside_window", segment)
	if soc >= threshold:
		return Decision(DecisionAction.OBSERVE, "soc_above_threshold", segment, end_at=window.end)
	estimated=estimate_night_minutes(soc, target, model) if segment is Segment.NIGHT else estimate_day_minutes(soc, target, model)
	start_utc=window.end.astimezone(timezone.utc)-timedelta(minutes=estimated+model.safety_minutes)
	start_at=start_utc.astimezone(window.end.tzinfo)
	action=DecisionAction.START if now.astimezone(timezone.utc) >= start_utc else DecisionAction.WAIT
	reason="latest_safe_start" if action is DecisionAction.START else "waiting_for_latest_start"
	return Decision(action, reason, segment, estimated, start_at, window.end)
