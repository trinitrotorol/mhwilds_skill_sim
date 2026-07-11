from __future__ import annotations

from collections.abc import Iterator
from dataclasses import FrozenInstanceError

import pytest

from mhwilds_skill_sim.domain import (
    SkillContribution,
    SkillDefinition,
    SkillKind,
    SkillRankDefinition,
    aggregate_skill_levels,
)


def rank(
    level: int = 1,
    required_pieces: int | None = None,
) -> SkillRankDefinition:
    return SkillRankDefinition(level=level, required_pieces=required_pieces)


def definition(
    *,
    skill_id: str = "skill:attack-boost",
    kind: SkillKind = SkillKind.ARMOR,
    ranks: tuple[SkillRankDefinition, ...] = (SkillRankDefinition(1, None),),
    display_name: str | None = None,
) -> SkillDefinition:
    return SkillDefinition(
        skill_id=skill_id,
        kind=kind,
        ranks=ranks,
        display_name=display_name,
    )


def rank_generator() -> Iterator[SkillRankDefinition]:
    yield rank()


def test_skill_kind_has_exact_members_in_declaration_order() -> None:
    assert [(member.name, member.value) for member in SkillKind] == [
        ("ARMOR", "armor"),
        ("WEAPON", "weapon"),
        ("SERIES", "set"),
        ("GROUP", "group"),
    ]
    assert list(SkillKind.__members__) == ["ARMOR", "WEAPON", "SERIES", "GROUP"]


def test_skill_kind_series_string_is_normalized_set_value() -> None:
    assert str(SkillKind.SERIES) == "set"


@pytest.mark.parametrize(
    ("skill_id", "kind", "ranks"),
    [
        (
            "skill:attack-boost",
            SkillKind.ARMOR,
            (rank(1), rank(2), rank(3)),
        ),
        ("skill:weapon-technique", SkillKind.WEAPON, (rank(1),)),
        (
            "skill:series-bonus",
            SkillKind.SERIES,
            (rank(1, 2), rank(2, 4)),
        ),
        ("skill:group-bonus", SkillKind.GROUP, (rank(1, 3),)),
    ],
)
def test_can_create_each_skill_definition_kind(
    skill_id: str,
    kind: SkillKind,
    ranks: tuple[SkillRankDefinition, ...],
) -> None:
    created = definition(skill_id=skill_id, kind=kind, ranks=ranks)

    assert created.skill_id == skill_id
    assert created.kind is kind
    assert created.ranks == ranks


def test_skill_rank_definition_is_frozen_hashable_and_compares_by_value() -> None:
    created = rank(1, 2)

    assert created == rank(1, 2)
    assert created != rank(1, 3)
    assert hash(created) == hash(rank(1, 2))
    with pytest.raises(FrozenInstanceError):
        created.level = 2


def test_skill_definition_is_frozen_hashable_and_compares_by_value() -> None:
    created = definition()

    assert created == definition()
    assert created != definition(skill_id="skill:critical-eye")
    assert hash(created) == hash(definition())
    with pytest.raises(FrozenInstanceError):
        created.skill_id = "skill:critical-eye"


@pytest.mark.parametrize(
    "skill_id",
    [
        "skill:attack-boost",
        "wilds:skill:123456",
        "Skill:Internal_ID-01",
    ],
)
def test_skill_definition_preserves_valid_skill_id(skill_id: str) -> None:
    assert definition(skill_id=skill_id).skill_id == skill_id


@pytest.mark.parametrize("skill_id", ["", " ", "\t\n"])
def test_skill_definition_rejects_empty_or_blank_skill_id(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_id"):
        definition(skill_id=skill_id)


@pytest.mark.parametrize(
    "skill_id",
    [" skill:attack-boost", "\tskill:attack-boost", "skill:attack-boost ", "x\n"],
)
def test_skill_definition_rejects_surrounding_whitespace(skill_id: str) -> None:
    with pytest.raises(ValueError, match="skill_id"):
        definition(skill_id=skill_id)


@pytest.mark.parametrize("skill_id", [1, None, True])
def test_skill_definition_rejects_non_string_skill_id(skill_id: object) -> None:
    with pytest.raises(TypeError, match="skill_id"):
        SkillDefinition(
            skill_id=skill_id,  # type: ignore[arg-type]
            kind=SkillKind.ARMOR,
            ranks=(rank(),),
        )


def test_skill_definition_rejects_string_subclass_skill_id() -> None:
    class SkillId(str):
        pass

    with pytest.raises(TypeError, match="skill_id"):
        definition(skill_id=SkillId("skill:attack-boost"))


def test_skill_definition_rejects_raw_string_kind() -> None:
    with pytest.raises(TypeError, match="kind"):
        SkillDefinition(
            skill_id="skill:attack-boost",
            kind="armor",  # type: ignore[arg-type]
            ranks=(rank(),),
        )


@pytest.mark.parametrize(
    "ranks",
    [
        [rank()],
        {rank()},
        rank_generator(),
    ],
)
def test_skill_definition_rejects_non_tuple_ranks(ranks: object) -> None:
    with pytest.raises(TypeError, match="ranks"):
        SkillDefinition(
            skill_id="skill:attack-boost",
            kind=SkillKind.ARMOR,
            ranks=ranks,  # type: ignore[arg-type]
        )


def test_skill_definition_rejects_tuple_subclass_ranks() -> None:
    class RankTuple(tuple[SkillRankDefinition, ...]):
        pass

    with pytest.raises(TypeError, match="ranks"):
        definition(ranks=RankTuple((rank(),)))


def test_skill_definition_rejects_empty_ranks() -> None:
    with pytest.raises(ValueError, match="ranks"):
        definition(ranks=())


@pytest.mark.parametrize("invalid_rank", [None, "rank", 1])
def test_skill_definition_rejects_invalid_rank_items(invalid_rank: object) -> None:
    with pytest.raises(TypeError, match="ranks"):
        definition(ranks=(invalid_rank,))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "ranks",
    [
        (rank(2),),
        (rank(1), rank(3)),
        (rank(1), rank(1)),
        (rank(1), rank(2), rank(4)),
    ],
)
def test_skill_definition_requires_contiguous_ordered_rank_levels(
    ranks: tuple[SkillRankDefinition, ...],
) -> None:
    with pytest.raises(ValueError, match="ranks"):
        definition(ranks=ranks)


@pytest.mark.parametrize("kind", [SkillKind.ARMOR, SkillKind.WEAPON])
def test_normal_skill_kinds_reject_required_piece_thresholds(kind: SkillKind) -> None:
    with pytest.raises(ValueError, match="ranks"):
        definition(kind=kind, ranks=(rank(1, 1),))


@pytest.mark.parametrize("kind", [SkillKind.SERIES, SkillKind.GROUP])
def test_piece_activated_skill_kinds_require_thresholds(kind: SkillKind) -> None:
    with pytest.raises(ValueError, match="ranks"):
        definition(kind=kind, ranks=(rank(1, 2), rank(2, None)))


@pytest.mark.parametrize("kind", [SkillKind.SERIES, SkillKind.GROUP])
@pytest.mark.parametrize(
    "ranks",
    [
        (rank(1, 2), rank(2, 2)),
        (rank(1, 4), rank(2, 2)),
        (rank(1, 2), rank(2, 4), rank(3, 3)),
    ],
)
def test_piece_activated_skill_thresholds_must_strictly_increase(
    kind: SkillKind,
    ranks: tuple[SkillRankDefinition, ...],
) -> None:
    with pytest.raises(ValueError, match="ranks"):
        definition(kind=kind, ranks=ranks)


@pytest.mark.parametrize("required_pieces", [None, 1, 999])
def test_skill_rank_definition_accepts_valid_values(
    required_pieces: int | None,
) -> None:
    created = rank(level=1, required_pieces=required_pieces)

    assert created.level == 1
    assert created.required_pieces == required_pieces


@pytest.mark.parametrize("level", [True, 1.5, "1", None])
def test_skill_rank_definition_rejects_non_exact_int_level(level: object) -> None:
    with pytest.raises(TypeError, match="level"):
        SkillRankDefinition(level=level, required_pieces=None)  # type: ignore[arg-type]


@pytest.mark.parametrize("level", [0, -1])
def test_skill_rank_definition_rejects_non_positive_level(level: int) -> None:
    with pytest.raises(ValueError, match="level"):
        rank(level=level)


@pytest.mark.parametrize("required_pieces", [True, 1.5, "1", ()])
def test_skill_rank_definition_rejects_non_exact_int_required_pieces(
    required_pieces: object,
) -> None:
    with pytest.raises(TypeError, match="required_pieces"):
        SkillRankDefinition(
            level=1,
            required_pieces=required_pieces,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("required_pieces", [0, -1])
def test_skill_rank_definition_rejects_non_positive_required_pieces(
    required_pieces: int,
) -> None:
    with pytest.raises(ValueError, match="required_pieces"):
        rank(required_pieces=required_pieces)


def test_domain_package_exports_skill_metadata_types() -> None:
    from mhwilds_skill_sim.domain import (
        SkillDefinition as ExportedSkillDefinition,
    )
    from mhwilds_skill_sim.domain import SkillKind as ExportedSkillKind
    from mhwilds_skill_sim.domain import (
        SkillRankDefinition as ExportedSkillRankDefinition,
    )

    assert ExportedSkillDefinition is SkillDefinition
    assert ExportedSkillKind is SkillKind
    assert ExportedSkillRankDefinition is SkillRankDefinition


def test_existing_skill_exports_remain_available() -> None:
    from mhwilds_skill_sim.domain import (
        SkillContribution as ExportedSkillContribution,
    )
    from mhwilds_skill_sim.domain import (
        aggregate_skill_levels as exported_aggregate_skill_levels,
    )

    assert ExportedSkillContribution is SkillContribution
    assert exported_aggregate_skill_levels is aggregate_skill_levels
    assert aggregate_skill_levels(
        contributions=(SkillContribution("skill:attack-boost", 1),)
    ) == {"skill:attack-boost": 1}


def test_skill_definition_display_name_defaults_to_none() -> None:
    created = SkillDefinition(
        skill_id="skill:attack-boost",
        kind=SkillKind.ARMOR,
        ranks=(rank(),),
    )

    assert created.display_name is None


@pytest.mark.parametrize(
    "display_name",
    [
        "攻撃力強化（テスト）",
        "Attack Boost (Test)",
        "Mixed CASE: Internal  Spaces!",
    ],
)
def test_skill_definition_preserves_valid_display_name_exactly(
    display_name: str,
) -> None:
    created = definition(display_name=display_name)

    assert created.display_name == display_name


def test_skill_definition_equality_and_hash_include_display_name() -> None:
    japanese = definition(display_name="攻撃力強化（テスト）")
    same = definition(display_name="攻撃力強化（テスト）")
    english = definition(display_name="Attack Boost (Test)")
    absent = definition()

    assert japanese == same
    assert hash(japanese) == hash(same)
    assert japanese != english
    assert japanese != absent


def test_skill_definition_display_name_is_frozen() -> None:
    created = definition(display_name="攻撃力強化（テスト）")

    with pytest.raises(FrozenInstanceError):
        created.display_name = "変更"


@pytest.mark.parametrize("display_name", ["", " ", "\t\n"])
def test_skill_definition_rejects_empty_or_blank_display_name(
    display_name: str,
) -> None:
    with pytest.raises(ValueError, match="display_name"):
        definition(display_name=display_name)


@pytest.mark.parametrize(
    "display_name",
    [" 攻撃力強化", "\tAttack Boost", "攻撃力強化 ", "Attack Boost\n"],
)
def test_skill_definition_rejects_display_name_edge_whitespace(
    display_name: str,
) -> None:
    with pytest.raises(ValueError, match="display_name"):
        definition(display_name=display_name)


@pytest.mark.parametrize("display_name", [True, False, 1, 1.5, (), []])
def test_skill_definition_rejects_non_string_display_name(
    display_name: object,
) -> None:
    with pytest.raises(TypeError, match="display_name"):
        SkillDefinition(
            skill_id="skill:attack-boost",
            kind=SkillKind.ARMOR,
            ranks=(rank(),),
            display_name=display_name,  # type: ignore[arg-type]
        )


def test_skill_definition_rejects_display_name_string_subclass() -> None:
    class DisplayName(str):
        pass

    with pytest.raises(TypeError, match="display_name"):
        definition(display_name=DisplayName("Attack Boost"))
