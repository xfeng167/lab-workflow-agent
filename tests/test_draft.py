import json

import pytest
from pydantic import ValidationError

from lab_workflow_agent import draft_state as state
from lab_workflow_agent.config import AppError
from lab_workflow_agent.draft import DraftEdit, DraftInputError, DraftSession, interact
from lab_workflow_agent.provider import Completion
from lab_workflow_agent.source_client import SourceError
from lab_workflow_agent.source_models import MaterialRead, Page, UserRead


def material(i=1, **updates):
    values = dict(id=i, material_code=f"TEST-{i}", material_name=f"Buffer {i}",
                  material_type="buffer", quantity_available=100, quantity_reserved=20,
                  unit="mL", minimum_quantity=10, availability_status="available",
                  qc_status="passed", location_id=3, is_archived=False,
                  updated_at="2026-09-30T12:00:00")
    values.update(updates)
    return MaterialRead(**values)


class FakeSource:
    def __init__(self, items=None, total=None):
        self.items = [material()] if items is None else items
        self.total = len(self.items) if total is None else total
        self.calls = []
        self.missing = False

    def current_user(self):
        self.calls.append(("GET /users/me", None))
        return UserRead(id=10, username="viewer", email="v@example.com", role="viewer")

    def search_materials(self, **filters):
        self.calls.append(("GET /materials/search", filters))
        size = filters["size"]
        return Page[MaterialRead](items=self.items[:size], page=1, size=size,
                                  total=self.total, pages=(self.total + size - 1)//size)

    def get_material(self, material_id):
        self.calls.append((f"GET /materials/{material_id}", None))
        if self.missing:
            raise SourceError("Missing material", status=404, code="MATERIAL_NOT_FOUND")
        found = next((m for m in self.items if m.id == material_id), None)
        if found is None:
            raise SourceError("Missing material", status=404, code="MATERIAL_NOT_FOUND")
        return found


class FakeProvider:
    def __init__(self, *edits):
        self.edits = iter(edits)
        self.calls = []

    def complete(self, messages, *, structured=False):
        assert structured is True
        self.calls.append(messages)
        value = next(self.edits)
        if isinstance(value, Exception): raise value
        if isinstance(value, Completion): return value
        return Completion(json.dumps(value), "fake", "stop")


def session(*edits, source=None):
    return DraftSession(FakeProvider(*edits), source or FakeSource(), "I need a buffer")


def ready():
    s = session()
    s.handle('/material 1')
    s.handle('/quantity 12')
    return s


def test_zero_matches_and_revised_search():
    source = FakeSource([])
    s = session({"operation":"search", "query":"absent"}, source=source)
    out = s.handle("find absent")
    assert "No matching source record" in out and '"keyword": "absent"' in out
    assert s.state.selected is None and s.state.status == "collecting"
    source.items, source.total = [material()], 1
    s.handle('/search buffer')
    assert len(s.state.candidates) == 1 and s.state.selected is None


@pytest.mark.parametrize("identity", ["1", "TEST-1"])
def test_exact_identity_selects(identity):
    s = session()
    out = s.handle('/material ' + identity)
    assert s.state.selected.id == 1
    assert "How many units?" in out


def test_fuzzy_one_requires_selection():
    s = session({"operation":"search", "query":"buffer"})
    out = s.handle("I need buffer")
    assert "ID 1" in out and "Which material ID?" in out
    assert s.state.selected is None
    s.handle('/select 1')
    assert s.state.selected.id == 1


def test_multiple_candidates_and_stale_revision():
    s = session(source=FakeSource([material(i) for i in range(1,6)], total=9))
    output = s.handle('/search buffer')
    assert len(s.state.candidates) == 5 and "More matches" in output
    previous = s.state
    before = len(s.source.calls)
    with pytest.raises(DraftInputError): s.handle('/select 99')
    assert s.state == previous and len(s.source.calls) == before
    revision = s.state.candidate_revision
    s.handle('/search different')
    with pytest.raises(DraftInputError): s.handle(f'/select 1 {revision}')
    s.handle(f'/select 1 {s.state.candidate_revision}')
    assert s.state.selected.id == 1


def test_ordinal_selection_not_accepted():
    s = session({"operation":"select", "material_id":2}, source=FakeSource([material(1),material(2)]))
    s.handle('/search buffer')
    with pytest.raises(DraftInputError): s.handle('the second one')
    assert s.state.selected is None


@pytest.mark.parametrize("value", [0, -1, True, "12", 1.5, 1000001, None])
def test_quantity_state_rejects_wrong_values(value):
    prior = ready().state
    with pytest.raises(AppError): state.set_quantity(prior, value)
    assert prior.requested_quantity == 12


@pytest.mark.parametrize("text", ['0', '-1', '1.5', 'true', '1000001', '12 mg', '1e2'])
def test_quantity_command_rejects_without_mutation(text):
    s = ready()
    prior = s.state
    with pytest.raises(DraftInputError): s.handle('/quantity ' + text)
    assert s.state == prior


def test_notes_optional_replace_clear_and_trim():
    s = ready()
    assert s.state.status == "ready" and s.state.request_notes is None
    for text, expected in [(' first ', 'first'), ('replacement', 'replacement'), ('', None)]:
        s.handle('/notes ' + text)
        assert s.state.request_notes == expected
        assert s.state.status == 'ready'
    s.handle('/notes keep cold')
    s.handle('/clear-notes')
    assert s.state.request_notes is None
    with pytest.raises(DraftInputError): s.handle('/notes ' + 'x'*5001)


def test_quantity_correction_preserves_fields_and_insufficient_stock():
    s = ready()
    s.handle('/notes keep cold')
    out = s.handle('/quantity 90')
    assert s.state.requested_quantity == 90 and s.state.status == 'collecting'
    assert "exceeds current unreserved" in out
    assert s.state.request_notes == 'keep cold' and s.state.selected.id == 1
    s.handle('/quantity 20')
    assert s.state.status == 'ready'


def test_new_search_clears_old_selection_preserves_other_fields():
    s = ready()
    s.handle('/notes keep cold')
    s.source.items = [material(2, unit='units')]
    s.handle('/search other')
    assert s.state.selected is None and s.state.read_at is None
    assert s.state.requested_quantity == 12 and s.state.request_notes == 'keep cold'
    s.handle('/select 2')
    assert s.state.selected.unit == 'units' and s.state.selected.id == 2


def test_source_objects_cannot_mutate_snapshot():
    s = ready()
    s.source.items[0].quantity_available = 1
    assert s.state.selected.quantity_available == 100
    with pytest.raises(ValidationError): s.state.selected.quantity_available = 1


@pytest.mark.parametrize("kind", ['missing','archive','stock'])
def test_refresh_invalidates_readiness(kind):
    s = ready()
    if kind == 'missing': s.source.missing = True
    elif kind == 'archive': s.source.items[0].is_archived = True
    else: s.source.items[0].quantity_available = 20
    out = s.handle('/refresh')
    assert s.state.status == 'collecting' and s.state.requested_quantity == 12
    if kind == 'missing': assert s.state.selected is None and not s.state.candidates
    if kind == 'archive': assert 'archived. Choose another' in out


def test_ready_preview_fields_and_show_no_revision_change():
    s = ready()
    revision = s.state.revision
    out = s.handle('/show')
    for text in ['DRAFT ONLY — NO ORDER CREATED', 'Revision:', '10 / "viewer" / "viewer"',
                 'TEST-1', 'Buffer 1', 'mL', 'Requested quantity: 12', 'Notes: none',
                 'available: 100', 'reserved: 20', 'unreserved: 80', 'passed',
                 'location ID: 3', 'archived: False', '2026-09-30T12:00:00', 'read at:',
                 'Advisory stock sufficient: True']:
        assert text in out
    assert s.state.revision == revision
    assert all(call[0].startswith('GET ') for call in s.source.calls)


def test_reset_abandon_and_confirm_rejection():
    s = ready()
    prior = s.state
    with pytest.raises(DraftInputError): s.handle('/confirm anything')
    assert s.state == prior
    s.handle('/reset')
    assert s.state.selected is None and s.state.requested_quantity is None
    assert not s.state.candidates and s.state.messages == ()
    s.handle('/abandon')
    assert s.state.status == 'abandoned'
    with pytest.raises(DraftInputError): s.handle('/quantity 1')


def test_model_edits_and_history_preserve_other_fields():
    s = session({"operation":"search","query":"buffer","qc_status":"passed"},
                {"operation":"quantity","quantity":12},
                {"operation":"notes","notes":"keep cold"},
                {"operation":"quantity","quantity":15},
                {"operation":"clear_notes"})
    s.handle('I need passed buffers')
    s.handle('/select 1')
    s.handle('make it 12 instead')
    s.handle('notes: keep cold')
    s.handle('change quantity to 15')
    assert s.state.request_notes == 'keep cold'
    assert s.state.requested_quantity == 15
    s.handle('clear the notes')
    assert s.state.status == 'ready' and s.state.request_notes is None
    assert len(s.state.messages) <= 8
    assert s.provider.calls[-1][0].role == 'system'


@pytest.mark.parametrize("edit", [
    {"operation":"ready"}, {"operation":"quantity","quantity":"12"},
    {"operation":"quantity","quantity":True}, {"operation":"quantity","quantity":0},
    {"operation":"quantity","quantity":1.5}, {"operation":"quantity","quantity":12,"status":"ready"},
    {"operation":"show","material_id":1},
])
def test_model_invalid_updates_do_not_change_state(edit):
    s = session(edit)
    prior = s.state
    with pytest.raises(DraftInputError): s.handle('12')
    assert s.state == prior


@pytest.mark.parametrize("text,quantity", [('make it 1.5', 5), ('quantity -12',12),
    ('I need material 12',12), ('quantity 1e2',100), ('quantity 1,000',1000), ('a dozen',12),
    ('quantity 12 kg',12)])
def test_model_cannot_invent_round_or_convert_quantity(text, quantity):
    s = session({"operation":"quantity","quantity":quantity})
    with pytest.raises(DraftInputError): s.handle(text)
    assert s.state.requested_quantity is None


def test_natural_search_with_quantity():
    s = session({"operation":"search", "query":"buffer", "quantity":12})
    s.handle('I need 12 of the buffer')
    assert s.state.requested_quantity == 12 and s.state.selected is None


def test_unknown_candidate_from_model_makes_no_detail_read():
    s = session({"operation":"select", "material_id":99})
    s.handle('/search buffer')
    before = len(s.source.calls)
    with pytest.raises(DraftInputError): s.handle('select material 99')
    assert len(s.source.calls) == before


def test_model_cannot_invent_notes():
    s = session({"operation":"notes", "notes":"invented"})
    with pytest.raises(DraftInputError): s.handle('add notes keep cold')
    assert s.state.request_notes is None


def test_six_provider_attempt_limit():
    s = session(*[{"operation":"show"}]*6)
    for _ in range(6): s.handle('please display draft')
    with pytest.raises(AppError, match='limit reached'): s.handle('please display draft')
    assert len(s.provider.calls) == 6
    s.handle('/show')  # Deterministic commands consume no paid requests.


def test_provider_failure_does_not_mutate_state():
    s = session(AppError('Provider unavailable.'))
    previous = s.state
    with pytest.raises(AppError): s.handle('find buffer')
    assert s.state == previous


def test_interaction_edit_and_discard_on_eof():
    s = session({"operation":"search","query":"buffer"})
    outputs=[]
    inputs=iter(['/select 1','/quantity 12','/notes keep cold','/quantity 15','/show'])
    def read(_):
        try: return next(inputs)
        except StopIteration: raise EOFError
    interact(s, 'find buffer', outputs.append, read)
    assert any('status: ready' in output for output in outputs)
    assert any('Requested quantity: 15' in output for output in outputs)
    assert 'draft discarded' in outputs[-1]
    assert s.state.status == 'abandoned' and s.state.requested_quantity is None
    assert all(method.startswith('GET ') for method,_ in s.source.calls)


def test_discard_on_keyboard_interrupt():
    s = session()
    outputs=[]
    def read(_): raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt): interact(s, '/show', outputs.append, read)
    assert 'draft discarded' in outputs[-1]
    assert s.state.status == 'abandoned'


def test_unknown_units_never_silently_converted():
    s = session({"operation":"quantity", "quantity":12})
    s.handle('/material 1')
    with pytest.raises(DraftInputError): s.handle('make it 12 microliters')
    assert s.state.requested_quantity is None


def test_exact_code_language_requires_explicit_full_code():
    s = session({"operation":"search", "query":"TEST-1"})
    s.handle('TEST-1')
    assert s.state.selected.id == 1


def test_source_failure_leaves_prior_draft_unchanged():
    s = ready()
    prior = s.state
    def failure(**kwargs): raise SourceError('Read failed', status=503)
    s.source.search_materials = failure
    with pytest.raises(SourceError): s.handle('/search another')
    assert s.state == prior


def test_terminal_control_characters_are_quoted():
    s = ready()
    s.handle('/notes line1\nline2\x1b[31m')
    out = s.handle('/show')
    assert '\x1b' not in out
    assert 'line1\\nline2' in out


def test_source_read_limit_precedes_network():
    s = ready()
    s.source_reads = 60
    calls = len(s.source.calls)
    with pytest.raises(AppError, match='limit reached'): s.handle('/refresh')
    assert len(s.source.calls) == calls


def test_unknown_model_confirmation_rejected_without_write():
    s = session({"operation":"submit", "confirm":True})
    with pytest.raises(DraftInputError): s.handle('yes go ahead')
    assert s.state.status == 'collecting'
    assert len(s.source.calls) == 1
