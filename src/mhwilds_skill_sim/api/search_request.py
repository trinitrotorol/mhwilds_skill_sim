"""API search request decoding."""

from __future__ import annotations

from dataclasses import dataclass

from mhwilds_skill_sim.solver.requirements import SkillRequirement


@dataclass(frozen=True, slots=True)
class SearchRequest:
    requirements: tuple[SkillRequirement, ...]
    max_results: int

    def __post_init__(self) -> None:
        _validate_requirements(value=self.requirements)
        _validate_max_results(value=self.max_results)


def decode_search_request_payload(
    *,
    payload: object,
) -> SearchRequest:
    _validate_payload_shape(payload=payload)

    requirements = tuple(
        _decode_requirement_payload(value=value, index=index)
        for index, value in enumerate(payload["requirements"])
    )

    return SearchRequest(
        requirements=requirements,
        max_results=payload["max_results"],
    )


def _validate_requirements(*, value: object) -> None:
    if type(value) is not tuple:
        raise TypeError("requirements must be tuple")

    seen_skill_ids: set[str] = set()
    for requirement in value:
        if not isinstance(requirement, SkillRequirement):
            raise TypeError("requirements must contain only SkillRequirement")

        if requirement.skill_id in seen_skill_ids:
            raise ValueError("requirements must not contain duplicate skill_id")

        seen_skill_ids.add(requirement.skill_id)


def _validate_max_results(*, value: object) -> None:
    if type(value) is not int:
        raise TypeError("max_results must be int")

    if value < 0:
        raise ValueError("max_results must be at least 0")


def _validate_payload_shape(*, payload: object) -> None:
    if type(payload) is not dict:
        raise TypeError("payload must be object")

    _validate_exact_keys(
        value=payload,
        required_keys=("requirements", "max_results"),
        location="payload",
    )

    if type(payload["requirements"]) is not list:
        raise TypeError("requirements must be list")


def _decode_requirement_payload(
    *,
    value: object,
    index: int,
) -> SkillRequirement:
    location = f"requirements[{index}]"
    if type(value) is not dict:
        raise TypeError(f"{location} must be object")

    _validate_exact_keys(
        value=value,
        required_keys=("skill_id", "min_level"),
        location=location,
    )

    return SkillRequirement(
        skill_id=value["skill_id"],
        min_level=value["min_level"],
    )


def _validate_exact_keys(
    *,
    value: dict[object, object],
    required_keys: tuple[str, ...],
    location: str,
) -> None:
    keys = set(value)
    required_key_set = set(required_keys)
    missing_keys = tuple(key for key in required_keys if key not in keys)
    extra_keys = tuple(
        sorted(
            (key for key in keys if key not in required_key_set),
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
