"""Python CP-SAT oracle workloads for browser-solver comparison."""

from __future__ import annotations

from math import isfinite
from time import perf_counter

from mhwilds_skill_sim.api.ranked_search_request import (
    RankedSearchRequest,
    decode_ranked_search_request_payload,
)
from mhwilds_skill_sim.catalog.model import Catalog
from mhwilds_skill_sim.domain.equipment import EquipmentPart
from mhwilds_skill_sim.domain.skill import SkillKind
from mhwilds_skill_sim.solver.cp_sat_search import (
    CpSatBuildSearchResult,
    search_catalog_ranked_build_candidates_with_cp_sat,
)
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


BROWSER_SOLVER_ORACLE_FORMAT_VERSION = 1


def build_representative_browser_solver_cases(
    *,
    catalog: Catalog,
) -> tuple[dict[str, object], ...]:
    """Select a stable, representative top-1 workload in Catalog order."""

    _validate_catalog(catalog=catalog)
    normal_skills = tuple(
        definition
        for definition in catalog.skills
        if definition.kind in (SkillKind.ARMOR, SkillKind.WEAPON)
    )
    series_skills = tuple(
        definition
        for definition in catalog.skills
        if definition.kind is SkillKind.SERIES
    )
    group_skills = tuple(
        definition
        for definition in catalog.skills
        if definition.kind is SkillKind.GROUP
    )

    cases: list[dict[str, object]] = [
        _case(
            name="empty",
            requirements=[],
            preferences=[],
        )
    ]
    if normal_skills:
        first_normal = normal_skills[0]
        cases.append(
            _case(
                name="normal-required",
                requirements=[
                    {
                        "skill_id": first_normal.skill_id,
                        "min_level": first_normal.ranks[0].level,
                    }
                ],
                preferences=[],
            )
        )
        cases.append(
            _case(
                name="normal-preferred",
                requirements=[],
                preferences=[
                    {
                        "skill_id": first_normal.skill_id,
                        "target_level": first_normal.ranks[0].level,
                    }
                ],
            )
        )

    if len(normal_skills) >= 2:
        preference_skills = normal_skills[1:3]
        cases.append(
            _case(
                name="mixed-ranked",
                requirements=[
                    {
                        "skill_id": normal_skills[0].skill_id,
                        "min_level": normal_skills[0].ranks[0].level,
                    }
                ],
                preferences=[
                    {
                        "skill_id": definition.skill_id,
                        "target_level": definition.ranks[0].level,
                    }
                    for definition in preference_skills
                ],
            )
        )

    if series_skills:
        cases.append(
            _case(
                name="series-required",
                requirements=[
                    {
                        "skill_id": series_skills[0].skill_id,
                        "min_level": series_skills[0].ranks[0].level,
                    }
                ],
                preferences=[],
            )
        )

    if group_skills:
        cases.append(
            _case(
                name="group-preferred",
                requirements=[],
                preferences=[
                    {
                        "skill_id": group_skills[0].skill_id,
                        "target_level": group_skills[0].ranks[0].level,
                    }
                ],
            )
        )

    weapon_kind = next(
        (
            definition.weapon_kind
            for definition in catalog.equipment
            if definition.part is EquipmentPart.WEAPON
            and definition.weapon_kind is not None
        ),
        None,
    )
    if weapon_kind is not None:
        cases.append(
            _case(
                name="weapon-filter",
                requirements=[],
                preferences=[],
                weapon_kind=weapon_kind.value,
            )
        )

    if normal_skills:
        first_normal = normal_skills[0]
        cases.append(
            _case(
                name="impossible-stress",
                requirements=[
                    {
                        "skill_id": first_normal.skill_id,
                        "min_level": first_normal.ranks[-1].level + 1,
                    }
                ],
                preferences=[],
            )
        )

    return tuple(cases)


def build_browser_solver_oracle_report(
    *,
    catalog: Catalog,
    cases: tuple[dict[str, object], ...],
    timeout_seconds: float = 30.0,
) -> dict[str, object]:
    """Run existing ranked CP-SAT search once for every workload case."""

    _validate_catalog(catalog=catalog)
    normalized_timeout = _normalize_timeout_seconds(value=timeout_seconds)
    decoded_cases = _decode_cases(cases=cases)

    case_reports: list[dict[str, object]] = []
    for name, request in decoded_cases:
        started_at = perf_counter()
        result = search_catalog_ranked_build_candidates_with_cp_sat(
            catalog=catalog,
            requirements=request.requirements,
            preferences=request.preferences,
            max_results=request.max_results,
            weapon_kind=request.weapon_kind,
            timeout_seconds=normalized_timeout,
        )
        elapsed_seconds = round(perf_counter() - started_at, 6)
        case_reports.append(
            _build_case_report(
                catalog=catalog,
                name=name,
                request=request,
                elapsed_seconds=elapsed_seconds,
                result=result,
            )
        )

    case_names = {name for name, _ in decoded_cases}
    return {
        "format_version": BROWSER_SOLVER_ORACLE_FORMAT_VERSION,
        "timeout_seconds": normalized_timeout,
        "omitted_cases": _build_omitted_case_reports(
            catalog=catalog,
            included_names=case_names,
        ),
        "cases": case_reports,
    }


def _case(
    *,
    name: str,
    requirements: list[dict[str, object]],
    preferences: list[dict[str, object]],
    weapon_kind: str | None = None,
) -> dict[str, object]:
    request: dict[str, object] = {
        "requirements": requirements,
        "preferences": preferences,
        "max_results": 1,
    }
    if weapon_kind is not None:
        request["weapon_kind"] = weapon_kind
    return {"name": name, "request": request}


def _build_case_report(
    *,
    catalog: Catalog,
    name: str,
    request: RankedSearchRequest,
    elapsed_seconds: float,
    result: CpSatBuildSearchResult,
) -> dict[str, object]:
    if len(result.candidates) > 1:
        raise RuntimeError("top-1 oracle returned more than one candidate")

    candidate = result.candidates[0] if result.candidates else None
    if result.timed_out:
        status = "timed-out"
    elif candidate is not None:
        status = "optimal"
    elif result.exhausted:
        status = "infeasible"
    else:
        raise RuntimeError("CP-SAT oracle returned an unclassified result")

    preference_score: int | None = None
    decoration_count: int | None = None
    equipment_signature: list[dict[str, object]] = []
    if candidate is not None:
        validation = validate_build(
            equipment=candidate.equipment,
            decorations=catalog.decorations,
            placements=candidate.placements,
        )
        if (
            validation.equipment_selection_issues
            or validation.decoration_placement_issues
        ):
            raise RuntimeError("CP-SAT oracle returned an invalid build")

        skill_levels = aggregate_valid_build_skill_levels(
            equipment=candidate.equipment,
            decorations=catalog.decorations,
            placements=candidate.placements,
            skill_definitions=catalog.skills,
        )
        if skill_levels != dict(candidate.skill_levels):
            raise RuntimeError("CP-SAT oracle candidate skill levels do not match")
        if not skill_levels_satisfy_requirements(
            skill_levels=skill_levels,
            requirements=request.requirements,
        ):
            raise RuntimeError("CP-SAT oracle candidate misses a hard requirement")

        preference_score = calculate_skill_preference_score(
            skill_levels=skill_levels,
            preferences=request.preferences,
        )
        decoration_count = len(candidate.placements)
        equipment_signature = [
            {
                "equipment_id": definition.equipment_id,
                "part": definition.part.value,
                "series_skill_id": definition.series_skill_id,
                "additional_series_skill_ids": list(
                    definition.additional_series_skill_ids
                ),
                "group_skill_id": definition.group_skill_id,
                "additional_group_skill_ids": list(
                    definition.additional_group_skill_ids
                ),
            }
            for definition in candidate.equipment
        ]

    return {
        "name": name,
        "request": _request_to_payload(request=request),
        "elapsed_seconds": elapsed_seconds,
        "status": status,
        "candidate_exists": candidate is not None,
        "preference_score": preference_score,
        "decoration_count": decoration_count,
        "equipment_signature": equipment_signature,
    }


def _decode_cases(
    *,
    cases: object,
) -> tuple[tuple[str, RankedSearchRequest], ...]:
    if type(cases) is not tuple:
        raise TypeError("cases must be tuple")

    decoded: list[tuple[str, RankedSearchRequest]] = []
    seen_names: set[str] = set()
    for index, case in enumerate(cases):
        location = f"cases[{index}]"
        if type(case) is not dict:
            raise TypeError(f"{location} must be object")
        if set(case) != {"name", "request"}:
            raise ValueError(f"{location} must contain exactly name and request")

        name = case["name"]
        if type(name) is not str:
            raise TypeError(f"{location}.name must be str")
        if not name or name.strip() != name:
            raise ValueError(f"{location}.name must be a non-blank trimmed string")
        if name in seen_names:
            raise ValueError("cases must not contain duplicate names")

        request = decode_ranked_search_request_payload(payload=case["request"])
        if request.max_results != 1:
            raise ValueError(f"{location}.request.max_results must be exactly 1")
        decoded.append((name, request))
        seen_names.add(name)

    return tuple(decoded)


def _request_to_payload(*, request: RankedSearchRequest) -> dict[str, object]:
    payload: dict[str, object] = {
        "requirements": [
            {
                "skill_id": requirement.skill_id,
                "min_level": requirement.min_level,
            }
            for requirement in request.requirements
        ],
        "preferences": [
            {
                "skill_id": preference.skill_id,
                "target_level": preference.target_level,
            }
            for preference in request.preferences
        ],
        "max_results": request.max_results,
    }
    if request.weapon_kind is not None:
        payload["weapon_kind"] = request.weapon_kind.value
    return payload


def _build_omitted_case_reports(
    *,
    catalog: Catalog,
    included_names: set[str],
) -> list[dict[str, str]]:
    normal_count = sum(
        definition.kind in (SkillKind.ARMOR, SkillKind.WEAPON)
        for definition in catalog.skills
    )
    has_series = any(
        definition.kind is SkillKind.SERIES for definition in catalog.skills
    )
    has_group = any(definition.kind is SkillKind.GROUP for definition in catalog.skills)
    has_weapon_kind = any(
        definition.part is EquipmentPart.WEAPON and definition.weapon_kind is not None
        for definition in catalog.equipment
    )
    potential_omissions = (
        ("normal-required", normal_count == 0, "no normal skill exists"),
        ("normal-preferred", normal_count == 0, "no normal skill exists"),
        (
            "mixed-ranked",
            normal_count < 2,
            "fewer than two distinct normal skills exist",
        ),
        ("series-required", not has_series, "no series skill exists"),
        ("group-preferred", not has_group, "no group skill exists"),
        ("weapon-filter", not has_weapon_kind, "no weapon kind exists"),
        ("impossible-stress", normal_count == 0, "no normal skill exists"),
    )
    return [
        {"name": name, "reason": reason}
        for name, unavailable, reason in potential_omissions
        if unavailable and name not in included_names
    ]


def _normalize_timeout_seconds(*, value: object) -> float:
    if type(value) not in (int, float):
        raise TypeError("timeout_seconds must be int or float")
    try:
        normalized = float(value)
    except OverflowError as error:
        raise ValueError("timeout_seconds must be finite") from error
    if not isfinite(normalized):
        raise ValueError("timeout_seconds must be finite")
    if normalized <= 0:
        raise ValueError("timeout_seconds must be greater than zero")
    return normalized


def _validate_catalog(*, catalog: object) -> None:
    if not isinstance(catalog, Catalog):
        raise TypeError("catalog must be Catalog")
