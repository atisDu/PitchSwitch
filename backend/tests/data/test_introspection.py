"""The field map: baseline + what live introspection recorded."""

import json

from data import introspection
from data.introspection import Fields, fields_for, refresh, summarise


def test_fields_for_known_types_include_what_the_store_needs():
    company = fields_for("Company")
    assert {"name", "description", "funding_stage", "total_funding"} <= set(company.properties)
    assert "PARTICIPATES_IN_FUNDING_ROUND" in company.outgoing
    assert {"INVESTED_IN", "IS_BOARD_MEMBER_OF", "FOUNDED"} <= set(company.incoming)

    funding_round = fields_for("FundingRound")
    assert {"round_label", "announcement_date", "transaction_value"} <= set(
        funding_round.properties
    )
    assert funding_round.incoming == ("PARTICIPATES_IN_FUNDING_ROUND",)

    assert "IS_BOARD_MEMBER_OF" in fields_for("Person").outgoing


def test_recorded_file_adds_fields_found_live():
    recorded = json.loads(introspection.PATH.read_text())["types"]
    assert set(recorded) == {"Company", "Organization", "FundingRound", "Person"}
    assert "HAS_HEADQUARTERS_IN" in fields_for("Organization").outgoing  # not in the baseline
    for entity_type, fields in recorded.items():
        assert set(fields["properties"]) <= set(fields_for(entity_type).properties)


def test_union_of_types_and_unknown_type():
    either = fields_for("Company", "Organization")
    assert set(fields_for("Company").properties) <= set(either.properties)
    assert set(fields_for("Organization").outgoing) <= set(either.outgoing)
    assert len(set(either.properties)) == len(either.properties)
    assert fields_for("Spaceship") == Fields((), (), ())


def test_only_keeps_wanted_names_that_exist():
    fields = fields_for("Company").only(
        properties=["name", "made_up", "funding_stage"], incoming=["INVESTED_IN", "NOPE"]
    )
    assert fields == Fields(("name", "funding_stage"), (), ("INVESTED_IN",))


def test_summarise_unions_and_drops_ids_and_precision_fields():
    summary = summarise(
        [
            {
                "properties": ["id", "name", "founding_date__precision"],
                "relationships": {"outgoing": ["A"], "incoming": []},
            },
            {"properties": ["name", "website"], "relationships": {"outgoing": ["B", "A"]}},
        ]
    )
    assert summary == {"properties": ["name", "website"], "outgoing": ["A", "B"], "incoming": []}


async def test_refresh_writes_a_sorted_file(tmp_path):
    class FakeCala:
        async def introspect(self, entity_id):
            return {"properties": ["name", entity_id], "relationships": {"outgoing": ["Z", "A"]}}

    path = tmp_path / "introspection.json"
    document = await refresh(FakeCala(), path, {"Company": ["c2", "c1"]})
    assert json.loads(path.read_text()) == document
    assert document["types"]["Company"] == {
        "properties": ["c1", "c2", "name"],
        "outgoing": ["A", "Z"],
        "incoming": [],
        "samples": ["c2", "c1"],
    }
    introspection._recorded.cache_clear()
