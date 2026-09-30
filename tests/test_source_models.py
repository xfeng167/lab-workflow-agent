import pytest
from pydantic import ValidationError

from lab_workflow_agent.source_models import MaterialRead


@pytest.fixture
def material_payload():
    return {
        "id": 12,
        "material_code": "TEST-MAT-012",
        "material_name": "Test buffer",
        "material_type": "buffer",
        "quantity_available": 100,
        "quantity_reserved": 25,
        "unit": "mL",
        "minimum_quantity": 10,
        "availability_status": "available",
        "qc_status": "passed",
        "location_id": 3,
        "is_archived": False,
    }


def test_material_parsing_and_stock(material_payload):
    material = MaterialRead.model_validate(material_payload)

    assert material.id == 12
    assert material.quantity_available == 100
    assert material.quantity_reserved == 25
    assert material.quantity_unreserved == 75


def test_missing_reserved_quantity_is_rejected(material_payload):
    del material_payload["quantity_reserved"]

    with pytest.raises(ValidationError):
        MaterialRead.model_validate(material_payload)


def test_string_quantity_is_rejected(material_payload):
    material_payload["quantity_available"] = "100"

    with pytest.raises(ValidationError):
        MaterialRead.model_validate(material_payload)


def test_unassigned_location_is_allowed(material_payload):
    material_payload["location_id"] = None

    material = MaterialRead.model_validate(material_payload)

    assert material.location_id is None


def test_unused_response_field_is_ignored(material_payload):
    material_payload["created_at"] = "2026-09-28T10:00:00"

    material = MaterialRead.model_validate(material_payload)

    assert "created_at" not in material.model_dump()