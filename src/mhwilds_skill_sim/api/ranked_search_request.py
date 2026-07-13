"""Ranked CP-SAT search request decoding."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.api.search_request import (
    SearchRequest,
    decode_search_request_payload,
)
from mhwilds_skill_sim.domain.equipment import WeaponKind
from mhwilds_skill_sim.solver.preferences import SkillPreference
from mhwilds_skill_sim.solver.requirements import SkillRequirement


@dataclass(frozen=True, slots=True)
class RankedSearchRequest:
    requirements: tuple[SkillRequirement, ...]
    preferences: tuple[SkillPreference, ...]
    max_results: int
    weapon_kind: WeaponKind | None = None

    def __post_init__(self) -> None:
        SearchRequest(
            requirements=self.requirements,
            max_results=self.max_results,
            weapon_kind=self.weapon_kind,
        )
        _validate_preferences(value=self.preferences)


def decode_ranked_search_request_payload(
    *,
    payload: object,
) -> RankedSearchRequest:
    _validate_payload_shape(payload=payload)

    base_payload = {
        "requirements": payload["requirements"],
        "max_results": payload["max_results"],
    }
    if "weapon_kind" in payload:
        base_payload["weapon_kind"] = payload["weapon_kind"]

    base_request = decode_search_request_payload(payload=base_payload)
    preferences: list[SkillPreference] = []
    seen_preference_skill_ids: set[str] = set()
    for index, value in enumerate(payload["preferences"]):
        preference = _decode_preference_payload(value=value, index=index)
        if preference.skill_id in seen_preference_skill_ids:
            raise ValueError(
                f"preferences[{index}] must not duplicate skill_id",
            )

        preferences.append(preference)
        seen_preference_skill_ids.add(preference.skill_id)

    return RankedSearchRequest(
        requirements=base_request.requirements,
        preferences=tuple(preferences),
        max_results=base_request.max_results,
        weapon_kind=base_request.weapon_kind,
    )


def _validate_preferences(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("preferences must be tuple")

    seen_skill_ids: set[str] = set()
    for preference in value:
        if not isinstance(preference, SkillPreference):
            raise TypeError("preferences must contain only SkillPreference")

        if preference.skill_id in seen_skill_ids:
            raise ValueError("preferences must not contain duplicate skill_id")

        seen_skill_ids.add(preference.skill_id)


def _validate_payload_shape(*, payload: object) -> None:
    if type(payload) is not dict:
        raise TypeError("payload must be object")

    _validate_exact_keys(
        value=payload,
        required_keys=("requirements", "preferences", "max_results"),
        optional_keys=("weapon_kind",),
        location="payload",
    )

    if type(payload["preferences"]) is not list:
        raise TypeError("preferences must be list")


def _decode_preference_payload(
    *,
    value: object,
    index: int,
) -> SkillPreference:
    location = f"preferences[{index}]"
    if type(value) is not dict:
        raise TypeError(f"{location} must be object")

    _validate_exact_keys(
        value=value,
        required_keys=("skill_id", "target_level"),
        optional_keys=(),
        location=location,
    )

    try:
        return SkillPreference(
            skill_id=value["skill_id"],
            target_level=value["target_level"],
        )
    except (TypeError, ValueError) as error:
        raise type(error)(f"{location}: {error}") from error


def _validate_exact_keys(
    *,
    value: dict[object, object],
    required_keys: tuple[str, ...],
    optional_keys: tuple[str, ...],
    location: str,
) -> None:
    keys = set(value)
    required_key_set = set(required_keys)
    allowed_key_set = required_key_set | set(optional_keys)
    missing_keys = tuple(key for key in required_keys if key not in keys)
    extra_keys = tuple(
        sorted(
            (key for key in keys if key not in allowed_key_set),
            key=_key_sort_value,
        ),
    )

    if not missing_keys and not extra_keys:
        return

    details: list[str] = []
    if missing_keys:
        details.append(f"missing keys: {_format_keys(keys=missing_keys)}")

    if extra_keys:
        details.append(f"unexpected keys: {_format_keys(keys=extra_keys)}")

    raise ValueError(f"{location} {'; '.join(details)}")


def _key_sort_value(key: object) -> tuple[str, str]:
    return (type(key).__name__, repr(key))


def _format_keys(*, keys: tuple[object, ...]) -> str:
    return ", ".join(key if type(key) is str else repr(key) for key in keys)
