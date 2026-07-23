"""Validation of TypeScript browser-solver benchmark reports."""

from __future__ import annotations

from math import isfinite

from mhwilds_skill_sim.api.ranked_search_request import (
    RankedSearchRequest,
    decode_ranked_search_request_payload,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentDefinition, EquipmentPart
from mhwilds_skill_sim.solver.build import BuildCandidate
from mhwilds_skill_sim.solver.preferences import (
    calculate_skill_preference_score,
)
from mhwilds_skill_sim.solver.requirements import (
    skill_levels_satisfy_requirements,
)
from mhwilds_skill_sim.validation.build import (
    aggregate_valid_build_skill_levels,
    validate_build,
)
from mhwilds_skill_sim.validation.placement import DecorationPlacement

from .catalog_export import (
    DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT,
    _prepare_expanded_equipment,
    build_browser_search_catalog,
)


_COMPLETED_STATUSES = ("optimal", "infeasible")
_BROWSER_STATUSES = (*_COMPLETED_STATUSES, "timed-out", "cancelled")
_ORACLE_STATUSES = (*_COMPLETED_STATUSES, "timed-out")
_PART_ORDER = tuple(EquipmentPart)


def validate_browser_solver_report(
    *,
    catalog: Catalog,
    browser_catalog: dict[str, object],
    oracle_report: dict[str, object],
    browser_report: dict[str, object],
) -> dict[str, object]:
    """Validate browser candidates and compare completed objectives to CP-SAT."""

    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")
    if type(browser_catalog) is not dict:
        raise TypeError("browser_catalog must be dict")
    if type(oracle_report) is not dict:
        raise TypeError("oracle_report must be dict")
    if type(browser_report) is not dict:
        raise TypeError("browser_report must be dict")

    source_sha256 = _browser_catalog_source_sha256(browser_catalog=browser_catalog)
    _validate_report_headers(
        source_sha256=source_sha256,
        oracle_report=oracle_report,
        browser_report=browser_report,
    )

    expected_browser_catalog = build_browser_search_catalog(
        catalog=catalog,
        source_catalog_sha256=source_sha256,
        maximum_expanded_equipment=DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT,
    )
    if browser_catalog != expected_browser_catalog:
        raise ValueError(
            "browser_catalog does not match the Catalog's deterministic export"
        )
    prepared = _prepare_expanded_equipment(
        catalog=catalog,
        maximum_expanded_equipment=DEFAULT_MAXIMUM_EXPANDED_EQUIPMENT,
    )
    variants_by_id = {
        variant_id: definition
        for variant_id, definition in enumerate(prepared.expanded)
    }

    oracle_cases = _case_list(report=oracle_report, location="oracle_report")
    browser_cases = _case_list(report=browser_report, location="browser_report")
    if len(browser_cases) != len(oracle_cases):
        raise ValueError("browser and oracle reports must contain the same cases")

    valid_candidate_count = 0
    completed_parity_count = 0
    completed_parity_failure_count = 0
    timed_out_count = 0
    cancelled_count = 0

    for index, (oracle_case, browser_case) in enumerate(
        zip(oracle_cases, browser_cases)
    ):
        location = f"cases[{index}]"
        oracle_name, oracle_request = _decode_report_case_identity(
            value=oracle_case,
            location=f"oracle_report.{location}",
        )
        browser_name, browser_request = _decode_report_case_identity(
            value=browser_case,
            location=f"browser_report.{location}",
        )
        if browser_name != oracle_name:
            raise ValueError(f"{location} name does not match the oracle")
        if browser_request != oracle_request:
            raise ValueError(f"{location} request does not match the oracle")

        oracle_objective = _decode_oracle_objective(
            case=oracle_case,
            location=f"oracle_report.{location}",
        )
        result = _required_dict(
            value=browser_case.get("result"),
            location=f"browser_report.{location}.result",
        )
        browser_status = _browser_status(
            result=result,
            location=f"browser_report.{location}.result",
        )
        _validate_benchmark_case_metadata(
            case=browser_case,
            browser_status=browser_status,
            location=f"browser_report.{location}",
        )

        candidate_objective = _validate_browser_result(
            catalog=catalog,
            variants_by_id=variants_by_id,
            request=browser_request,
            result=result,
            status=browser_status,
            location=f"browser_report.{location}.result",
        )
        if candidate_objective is not None:
            valid_candidate_count += 1

        if browser_status == "timed-out":
            timed_out_count += 1
        elif browser_status == "cancelled":
            cancelled_count += 1

        completed_comparison = (
            browser_status in _COMPLETED_STATUSES
            and oracle_objective.status in _COMPLETED_STATUSES
        )
        if completed_comparison:
            parity = _objectives_match(
                browser_status=browser_status,
                browser_objective=candidate_objective,
                oracle_objective=oracle_objective,
            )
            if parity:
                completed_parity_count += 1
            else:
                completed_parity_failure_count += 1
            _validate_reported_parity(
                value=browser_case.get("parity"),
                expected=parity,
                location=f"browser_report.{location}.parity",
            )
        else:
            _validate_reported_parity(
                value=browser_case.get("parity"),
                expected=None,
                location=f"browser_report.{location}.parity",
            )

    return {
        "case_count": len(browser_cases),
        "valid_candidate_count": valid_candidate_count,
        "completed_parity_count": completed_parity_count,
        "completed_parity_failure_count": completed_parity_failure_count,
        "timed_out_count": timed_out_count,
        "cancelled_count": cancelled_count,
    }


class _Objective:
    __slots__ = ("status", "candidate_exists", "preference_score", "decoration_count")

    def __init__(
        self,
        *,
        status: str,
        candidate_exists: bool,
        preference_score: int | None,
        decoration_count: int | None,
    ) -> None:
        self.status = status
        self.candidate_exists = candidate_exists
        self.preference_score = preference_score
        self.decoration_count = decoration_count


def _validate_browser_result(
    *,
    catalog: Catalog,
    variants_by_id: dict[int, EquipmentDefinition],
    request: RankedSearchRequest,
    result: dict[str, object],
    status: str,
    location: str,
) -> _Objective | None:
    expected_keys = {
        "status",
        "candidate",
        "selected_variant_ids",
        "preference_score",
        "decoration_count",
        "elapsed_ms",
        "visited_nodes",
        "pruned_nodes",
        "complete_equipment_selections",
    }
    if set(result) != expected_keys:
        raise ValueError(f"{location} has invalid result fields")

    _nonnegative_finite_number(
        value=result["elapsed_ms"],
        location=f"{location}.elapsed_ms",
    )
    for field_name in (
        "visited_nodes",
        "pruned_nodes",
        "complete_equipment_selections",
    ):
        _nonnegative_integer(
            value=result[field_name],
            location=f"{location}.{field_name}",
        )

    candidate_value = result["candidate"]
    selected_variant_ids = result["selected_variant_ids"]
    if candidate_value is None:
        if selected_variant_ids != []:
            raise ValueError(
                f"{location}.selected_variant_ids must be empty without a candidate"
            )
        if result["preference_score"] is not None:
            raise ValueError(
                f"{location}.preference_score must be null without a candidate"
            )
        if result["decoration_count"] is not None:
            raise ValueError(
                f"{location}.decoration_count must be null without a candidate"
            )
        if status == "optimal":
            raise ValueError(f"{location} optimal result requires a candidate")
        return None

    if status == "infeasible":
        raise ValueError(f"{location} infeasible result must not contain a candidate")
    if type(candidate_value) is not dict:
        raise TypeError(f"{location}.candidate must be object or null")
    if type(selected_variant_ids) is not list:
        raise TypeError(f"{location}.selected_variant_ids must be list")
    if len(selected_variant_ids) != len(_PART_ORDER):
        raise ValueError(
            f"{location}.selected_variant_ids must contain exactly seven IDs"
        )

    selected_equipment: list[EquipmentDefinition] = []
    for variant_index, variant_id in enumerate(selected_variant_ids):
        if type(variant_id) is not int:
            raise TypeError(
                f"{location}.selected_variant_ids[{variant_index}] must be int"
            )
        try:
            definition = variants_by_id[variant_id]
        except KeyError as error:
            raise ValueError(
                f"{location}.selected_variant_ids[{variant_index}] is unknown"
            ) from error
        selected_equipment.append(definition)

    selected_tuple = tuple(selected_equipment)
    if tuple(definition.part for definition in selected_tuple) != _PART_ORDER:
        raise ValueError(
            f"{location}.selected_variant_ids must use canonical seven-part order"
        )
    if (
        request.weapon_kind is not None
        and selected_tuple[0].weapon_kind is not request.weapon_kind
    ):
        raise ValueError(f"{location} selected weapon does not match weapon_kind")

    expected_candidate_keys = {
        "equipment",
        "placements",
        "skill_levels",
        "preference_score",
    }
    if set(candidate_value) != expected_candidate_keys:
        raise ValueError(f"{location}.candidate has invalid fields")
    expected_equipment = [
        _equipment_response(definition=definition) for definition in selected_tuple
    ]
    if candidate_value["equipment"] != expected_equipment:
        raise ValueError(
            f"{location}.candidate.equipment does not match selected variants"
        )

    placements = _decode_placements(
        value=candidate_value["placements"],
        location=f"{location}.candidate.placements",
    )
    validation = validate_build(
        equipment=selected_tuple,
        decorations=catalog.decorations,
        placements=placements,
    )
    if validation.equipment_selection_issues or validation.decoration_placement_issues:
        raise ValueError(f"{location}.candidate is not a valid build")

    skill_levels = aggregate_valid_build_skill_levels(
        equipment=selected_tuple,
        decorations=catalog.decorations,
        placements=placements,
        skill_definitions=catalog.skills,
    )
    if not skill_levels_satisfy_requirements(
        skill_levels=skill_levels,
        requirements=request.requirements,
    ):
        raise ValueError(f"{location}.candidate misses a hard requirement")
    reported_skill_levels = _decode_skill_levels(
        value=candidate_value["skill_levels"],
        location=f"{location}.candidate.skill_levels",
    )
    if reported_skill_levels != skill_levels:
        raise ValueError(f"{location}.candidate.skill_levels are incorrect")

    preference_score = calculate_skill_preference_score(
        skill_levels=skill_levels,
        preferences=request.preferences,
    )
    decoration_count = len(placements)
    if candidate_value["preference_score"] != preference_score:
        raise ValueError(f"{location}.candidate.preference_score is incorrect")
    if result["preference_score"] != preference_score:
        raise ValueError(f"{location}.preference_score is incorrect")
    if result["decoration_count"] != decoration_count:
        raise ValueError(f"{location}.decoration_count is incorrect")

    # Constructing the existing value object also enforces its response invariants.
    BuildCandidate(
        equipment=selected_tuple,
        placements=placements,
        skill_levels=tuple(skill_levels.items()),
    )
    return _Objective(
        status=status,
        candidate_exists=True,
        preference_score=preference_score,
        decoration_count=decoration_count,
    )


def _decode_placements(
    *,
    value: object,
    location: str,
) -> tuple[DecorationPlacement, ...]:
    if type(value) is not list:
        raise TypeError(f"{location} must be list")
    placements: list[DecorationPlacement] = []
    for index, item in enumerate(value):
        item_location = f"{location}[{index}]"
        if type(item) is not dict:
            raise TypeError(f"{item_location} must be object")
        if set(item) != {"equipment_id", "slot_index", "decoration_id"}:
            raise ValueError(f"{item_location} has invalid fields")
        try:
            placements.append(
                DecorationPlacement(
                    equipment_id=item["equipment_id"],
                    slot_index=item["slot_index"],
                    decoration_id=item["decoration_id"],
                )
            )
        except (TypeError, ValueError) as error:
            raise type(error)(f"{item_location}: {error}") from error
    return tuple(placements)


def _decode_skill_levels(*, value: object, location: str) -> dict[str, int]:
    if type(value) is not list:
        raise TypeError(f"{location} must be list")
    levels: dict[str, int] = {}
    for index, item in enumerate(value):
        item_location = f"{location}[{index}]"
        if type(item) is not dict:
            raise TypeError(f"{item_location} must be object")
        if set(item) != {"skill_id", "level"}:
            raise ValueError(f"{item_location} has invalid fields")
        skill_id = item["skill_id"]
        level = item["level"]
        if type(skill_id) is not str or not skill_id or skill_id.strip() != skill_id:
            raise ValueError(f"{item_location}.skill_id is invalid")
        if type(level) is not int or level < 1:
            raise ValueError(f"{item_location}.level must be a positive int")
        if skill_id in levels:
            raise ValueError(f"{location} must not contain duplicate skill IDs")
        levels[skill_id] = level
    return levels


def _equipment_response(
    *,
    definition: EquipmentDefinition,
) -> dict[str, object]:
    return {
        "equipment_id": definition.equipment_id,
        "display_name": definition.display_name,
        "part": definition.part.value,
        "weapon_kind": (
            definition.weapon_kind.value if definition.weapon_kind is not None else None
        ),
        "series_skill_id": definition.series_skill_id,
        "group_skill_id": definition.group_skill_id,
        "series_skill_ids": list(definition.series_skill_ids),
        "group_skill_ids": list(definition.group_skill_ids),
        "skills": [
            {
                "skill_id": contribution.skill_id,
                "level": contribution.level,
            }
            for contribution in definition.skills
        ],
        "slots": [
            {
                "kind": slot.kind.value,
                "level": slot.level,
            }
            for slot in definition.slots
        ],
    }


def _decode_oracle_objective(
    *,
    case: dict[str, object],
    location: str,
) -> _Objective:
    status = case.get("status")
    if status not in _ORACLE_STATUSES:
        raise ValueError(f"{location}.status is invalid")
    assert isinstance(status, str)
    candidate_exists = case.get("candidate_exists")
    if type(candidate_exists) is not bool:
        raise TypeError(f"{location}.candidate_exists must be bool")
    preference_score = case.get("preference_score")
    decoration_count = case.get("decoration_count")
    if candidate_exists:
        _nonnegative_integer(
            value=preference_score,
            location=f"{location}.preference_score",
        )
        _nonnegative_integer(
            value=decoration_count,
            location=f"{location}.decoration_count",
        )
    elif preference_score is not None or decoration_count is not None:
        raise ValueError(f"{location} objective must be null without a candidate")
    if status == "optimal" and not candidate_exists:
        raise ValueError(f"{location} optimal oracle result requires a candidate")
    if status == "infeasible" and candidate_exists:
        raise ValueError(f"{location} infeasible oracle result forbids a candidate")
    return _Objective(
        status=status,
        candidate_exists=candidate_exists,
        preference_score=preference_score,
        decoration_count=decoration_count,
    )


def _objectives_match(
    *,
    browser_status: str,
    browser_objective: _Objective | None,
    oracle_objective: _Objective,
) -> bool:
    browser_exists = browser_objective is not None
    if browser_status != oracle_objective.status:
        return False
    if browser_exists != oracle_objective.candidate_exists:
        return False
    if not browser_exists:
        return True
    assert browser_objective is not None
    return (
        browser_objective.preference_score == oracle_objective.preference_score
        and browser_objective.decoration_count == oracle_objective.decoration_count
    )


def _validate_report_headers(
    *,
    source_sha256: str,
    oracle_report: dict[str, object],
    browser_report: dict[str, object],
) -> None:
    if oracle_report.get("format_version") != 1:
        raise ValueError("oracle_report.format_version must be exactly 1")
    if browser_report.get("format_version") != 1:
        raise ValueError("browser_report.format_version must be exactly 1")
    if oracle_report.get("source_catalog_sha256") != source_sha256:
        raise ValueError("oracle_report source Catalog hash does not match")
    if browser_report.get("source_catalog_sha256") != source_sha256:
        raise ValueError("browser_report source Catalog hash does not match")
    if browser_report.get("runtime") not in ("node", "browser"):
        raise ValueError("browser_report.runtime must be node or browser")
    _nonnegative_finite_number(
        value=browser_report.get("timeout_ms"),
        location="browser_report.timeout_ms",
    )
    repeats = browser_report.get("repeats")
    if type(repeats) is not int or repeats < 1:
        raise ValueError("browser_report.repeats must be a positive int")


def _browser_catalog_source_sha256(
    *,
    browser_catalog: dict[str, object],
) -> str:
    source = _required_dict(
        value=browser_catalog.get("source_catalog"),
        location="browser_catalog.source_catalog",
    )
    sha256 = source.get("sha256")
    if type(sha256) is not str:
        raise TypeError("browser_catalog.source_catalog.sha256 must be str")
    return sha256


def _case_list(
    *,
    report: dict[str, object],
    location: str,
) -> list[dict[str, object]]:
    cases = report.get("cases")
    if type(cases) is not list:
        raise TypeError(f"{location}.cases must be list")
    decoded: list[dict[str, object]] = []
    for index, case in enumerate(cases):
        if type(case) is not dict:
            raise TypeError(f"{location}.cases[{index}] must be object")
        decoded.append(case)
    return decoded


def _decode_report_case_identity(
    *,
    value: dict[str, object],
    location: str,
) -> tuple[str, RankedSearchRequest]:
    name = value.get("name")
    if type(name) is not str:
        raise TypeError(f"{location}.name must be str")
    if not name or name.strip() != name:
        raise ValueError(f"{location}.name must be a non-blank trimmed string")
    request = decode_ranked_search_request_payload(payload=value.get("request"))
    if request.max_results != 1:
        raise ValueError(f"{location}.request.max_results must be exactly 1")
    return name, request


def _browser_status(*, result: dict[str, object], location: str) -> str:
    status = result.get("status")
    if status not in _BROWSER_STATUSES:
        raise ValueError(f"{location}.status is invalid")
    assert isinstance(status, str)
    return status


def _validate_benchmark_case_metadata(
    *,
    case: dict[str, object],
    browser_status: str,
    location: str,
) -> None:
    deterministic = case.get("deterministic")
    if type(deterministic) is not bool:
        raise TypeError(f"{location}.deterministic must be bool")
    if not deterministic:
        raise ValueError(f"{location} repeated objective is not deterministic")

    timings = _required_dict(
        value=case.get("timings_ms"),
        location=f"{location}.timings_ms",
    )
    if set(timings) != {"min", "median", "max"}:
        raise ValueError(f"{location}.timings_ms has invalid fields")
    minimum = _nonnegative_finite_number(
        value=timings["min"],
        location=f"{location}.timings_ms.min",
    )
    median = _nonnegative_finite_number(
        value=timings["median"],
        location=f"{location}.timings_ms.median",
    )
    maximum = _nonnegative_finite_number(
        value=timings["max"],
        location=f"{location}.timings_ms.max",
    )
    if not minimum <= median <= maximum:
        raise ValueError(f"{location}.timings_ms must satisfy min <= median <= max")
    if browser_status in ("timed-out", "cancelled") and case.get("parity") is not None:
        raise ValueError(f"{location}.parity must be null for incomplete search")


def _validate_reported_parity(
    *,
    value: object,
    expected: bool | None,
    location: str,
) -> None:
    if value is not expected:
        raise ValueError(f"{location} does not match independently verified parity")


def _required_dict(*, value: object, location: str) -> dict[str, object]:
    if type(value) is not dict:
        raise TypeError(f"{location} must be object")
    return value


def _nonnegative_integer(*, value: object, location: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{location} must be int")
    if value < 0:
        raise ValueError(f"{location} must be nonnegative")
    return value


def _nonnegative_finite_number(*, value: object, location: str) -> float:
    if type(value) not in (int, float):
        raise TypeError(f"{location} must be int or float")
    normalized = float(value)
    if not isfinite(normalized) or normalized < 0:
        raise ValueError(f"{location} must be finite and nonnegative")
    return normalized
