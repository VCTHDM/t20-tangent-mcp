"""Pure-offline regression tests for the headless ezdxf backend."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from t20_mcp.backends.ezdxf_backend import EzdxfBackend


def _initialized_backend() -> EzdxfBackend:
    backend = EzdxfBackend()
    result = asyncio.run(backend.initialize())
    assert result.ok, result.error
    return backend


def _entity_count(backend: EzdxfBackend) -> int:
    result = asyncio.run(backend.entity_count())
    assert result.ok, result.error
    return int(result.payload["count"])


def test_zero_length_mirror_fails_without_leaving_a_copy() -> None:
    backend = _initialized_backend()
    created = asyncio.run(backend.create_line(0, 0, 10, 0))
    assert created.ok
    before = _entity_count(backend)

    result = asyncio.run(backend.entity_mirror(created.payload["handle"], 5, 5, 5, 5))

    assert result.ok is False
    assert "zero length" in (result.error or "").lower()
    assert _entity_count(backend) == before


def test_mirror_success_reflects_geometry_and_adds_one_copy() -> None:
    backend = _initialized_backend()
    created = asyncio.run(backend.create_line(1, 0, 2, 0))
    assert created.ok

    result = asyncio.run(backend.entity_mirror(created.payload["handle"], 0, -1, 0, 1))

    assert result.ok, result.error
    assert _entity_count(backend) == 2
    mirrored = asyncio.run(backend.entity_get(result.payload["handle"]))
    assert mirrored.ok
    assert mirrored.payload["start"] == pytest.approx([-1, 0])
    assert mirrored.payload["end"] == pytest.approx([-2, 0])


def test_purge_reports_that_headless_backend_does_not_support_it() -> None:
    backend = _initialized_backend()

    result = asyncio.run(backend.drawing_purge())

    assert result.ok is False
    assert "not supported" in (result.error or "").lower()


def test_lineweight_failure_is_explicit_and_does_not_partially_change_layer() -> None:
    backend = _initialized_backend()
    created = asyncio.run(backend.layer_create("PIPE", color=2))
    assert created.ok

    result = asyncio.run(backend.layer_set_properties("PIPE", color=4, lineweight="0.25"))

    assert result.ok is False
    assert "lineweight" in (result.error or "").lower()
    assert "not supported" in (result.error or "").lower()
    assert backend._doc.layers.get("PIPE").color == 2


def test_invalid_linetype_does_not_partially_change_layer() -> None:
    backend = _initialized_backend()
    created = asyncio.run(backend.layer_create("PIPE", color=2))
    assert created.ok

    result = asyncio.run(backend.layer_set_properties("PIPE", color=4, linetype="MISSING"))

    assert result.ok is False
    assert "does not exist" in (result.error or "")
    assert backend._doc.layers.get("PIPE").color == 2


def test_hatch_rejects_non_polyline_without_leaving_an_entity() -> None:
    backend = _initialized_backend()
    created = asyncio.run(backend.create_line(0, 0, 10, 0))
    assert created.ok
    before = _entity_count(backend)

    result = asyncio.run(backend.create_hatch(created.payload["handle"]))

    assert result.ok is False
    assert "LWPOLYLINE" in (result.error or "")
    assert _entity_count(backend) == before


def test_block_attributes_are_not_silently_dropped_without_attdef() -> None:
    backend = _initialized_backend()
    defined = asyncio.run(
        backend.block_define(
            "PUMP",
            [{"type": "CIRCLE", "cx": 0, "cy": 0, "radius": 2}],
        )
    )
    assert defined.ok

    inserted = asyncio.run(
        backend.block_insert_with_attributes(
            "PUMP",
            10,
            20,
            attributes={"TAG": "P-101", "SERVICE": "COOLING"},
        )
    )

    assert inserted.ok, inserted.error
    assert inserted.payload["attributes_written"] == 2
    attributes = asyncio.run(backend.block_get_attributes(inserted.payload["handle"]))
    assert attributes.ok
    assert attributes.payload["attributes"] == {
        "TAG": "P-101",
        "SERVICE": "COOLING",
    }


def test_unsupported_block_entity_type_is_rejected_before_definition() -> None:
    backend = _initialized_backend()

    result = asyncio.run(backend.block_define("BAD", [{"type": "SPLINE", "points": []}]))

    assert result.ok is False
    assert "SPLINE" in (result.error or "")
    assert "BAD" not in backend._doc.blocks


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("pid_insert_valve", (0, 0, "gate")),
        ("pid_insert_pump", (0, 0, "centrifugal")),
        ("pid_insert_tank", (0, 0, "vertical")),
    ],
)
def test_pid_attributes_fail_explicitly_without_creating_entities(
    method_name: str,
    args: tuple[Any, ...],
) -> None:
    backend = _initialized_backend()
    setup = asyncio.run(backend.pid_setup_layers())
    assert setup.ok
    before = _entity_count(backend)
    method = getattr(backend, method_name)

    result = asyncio.run(method(*args, attributes={"tag": "P-101"}))

    assert result.ok is False
    assert "attributes" in (result.error or "").lower()
    assert "not supported" in (result.error or "").lower()
    assert _entity_count(backend) == before


def test_pid_symbol_rotation_changes_geometry_and_text_rotation() -> None:
    backend = _initialized_backend()

    result = asyncio.run(
        backend.pid_insert_symbol(
            "equipment",
            "PUMP",
            0,
            0,
            scale=1,
            rotation=45,
        )
    )

    assert result.ok, result.error
    symbol = backend._doc.entitydb[result.payload["handle"]]
    points = [(round(x, 3), round(y, 3)) for x, y in symbol.get_points("xy")]
    assert set(points) == {
        (0.0, -7.071),
        (7.071, 0.0),
        (0.0, 7.071),
        (-7.071, 0.0),
    }
    labels = list(backend._msp.query('TEXT[layer=="PID-ANNOTATION"]'))
    assert len(labels) == 1
    assert labels[0].dxf.text == "PUMP"
    assert labels[0].dxf.rotation == pytest.approx(45)


def test_pid_instrument_rotation_and_range_are_preserved() -> None:
    backend = _initialized_backend()

    result = asyncio.run(
        backend.pid_insert_instrument(
            10,
            20,
            "pressure",
            rotation=90,
            tag_id="PI-101",
            range_value="0-100 kPa",
        )
    )

    assert result.ok, result.error
    assert result.payload["range_handle"]
    direction_lines = list(backend._msp.query('LINE[layer=="PID-INSTRUMENTS"]'))
    assert len(direction_lines) == 1
    line = direction_lines[0]
    assert (line.dxf.start.x, line.dxf.start.y) == pytest.approx((10, 16))
    assert (line.dxf.end.x, line.dxf.end.y) == pytest.approx((10, 24))

    labels = {
        entity.dxf.text: entity for entity in backend._msp.query('TEXT[layer=="PID-ANNOTATION"]')
    }
    assert set(labels) == {"PI-101", "0-100 kPa"}
    assert labels["PI-101"].dxf.rotation == pytest.approx(90)
    assert labels["0-100 kPa"].dxf.rotation == pytest.approx(90)
    assert labels["0-100 kPa"].dxf.handle == result.payload["range_handle"]


@pytest.mark.parametrize(
    ("method_name", "args"),
    [
        ("pid_insert_valve", (0, 0, "gate")),
        ("pid_insert_pump", (0, 0, "centrifugal")),
        ("pid_insert_tank", (0, 0, "vertical")),
    ],
)
def test_pid_entrypoints_create_their_own_required_layers(
    method_name: str,
    args: tuple[Any, ...],
) -> None:
    backend = _initialized_backend()

    result = asyncio.run(getattr(backend, method_name)(*args))

    assert result.ok, result.error
    assert "PID-EQUIPMENT" in backend._doc.layers or "PID-VALVES" in backend._doc.layers
    assert "PID-ANNOTATION" in backend._doc.layers


def test_pid_pump_rotation_is_preserved_on_label() -> None:
    backend = _initialized_backend()

    result = asyncio.run(backend.pid_insert_pump(10, 20, "centrifugal", rotation=30))

    assert result.ok, result.error
    label = next(
        entity
        for entity in backend._msp.query('TEXT[layer=="PID-ANNOTATION"]')
        if entity.dxf.text == "centrifugal"
    )
    assert label.dxf.rotation == pytest.approx(30)
