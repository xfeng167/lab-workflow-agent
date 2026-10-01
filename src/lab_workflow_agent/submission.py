"""Application-owned confirmation and one-attempt submission. No model calls."""
import hashlib
import json
import secrets
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from .config import AppError
from . import draft_state as ds
from .draft import DraftInputError
from .order_models import OrderCreate
from .source_client import AmbiguousWrite, SourceError

# Terminal execution outcomes never return to previewed/confirmed in this process.
TRANSITIONS = {
    'draft_ready': {'previewed', 'invalidated'},
    'previewed': {'confirmed', 'invalidated'},
    'confirmed': {'executing', 'invalidated', 'failed'},
    'executing': {'succeeded', 'failed', 'needs_reconciliation'},
    'needs_reconciliation': {'succeeded'},
    'invalidated': {'draft_ready'},
    'failed': set(), 'succeeded': set(),
}
MAX_ORDER_PAGES = 10  # 100 visible orders; complete baseline required.


def identity(user):
    return {'id': user.id, 'username': user.username, 'role': user.role}


def facts(material):
    return {key: getattr(material, key) for key in (
        'id', 'material_code', 'material_name', 'unit', 'qc_status', 'location_id',
        'is_archived', 'quantity_available', 'quantity_reserved', 'updated_at')}


def binding(draft):
    return json.dumps({'revision': draft.revision, 'user': identity(draft.user),
                      'material': facts(draft.selected) if draft.selected else None,
                      'quantity': draft.requested_quantity, 'notes': draft.request_notes,
                      'status': draft.status}, sort_keys=True, separators=(',', ':'))


@dataclass(frozen=True)
class Preview:
    capability: str = field(repr=False)
    reference: str
    draft_binding: str
    payload: OrderCreate
    user_json: str
    material_json: str
    read_at: str


class Submission:
    def __init__(self, session):
        self.session = session
        self.source = session.source
        self.stage = 'draft_ready' if session.state.status == 'ready' else 'invalidated'
        self.preview = None
        self.displayed = False
        self.capabilities = set()
        self.consumed = False
        self.post_attempts = 0
        self.source_reads = 0
        self.baseline = set()
        self.request_id = None
        self.known_order_ids = set()
        self.started_at = None
        self.receipt = None
        self._lock = threading.Lock()

    def _move(self, target):
        if target not in TRANSITIONS[self.stage]:
            raise AppError('Invalid submission state transition.')
        self.stage = target

    def _read(self, operation, *args, **kwargs):
        self.source_reads += 1
        return operation(*args, **kwargs)

    def invalidate(self):
        if self.stage in ('draft_ready', 'previewed', 'confirmed'):
            self._move('invalidated')
        self.displayed = False
        self.preview = None

    def show_preview(self, emit):
        """Mark displayed only after the terminal callback completes successfully."""
        with self._lock:
            if self.consumed or self.stage in ('failed', 'succeeded', 'needs_reconciliation'):
                raise DraftInputError('This session cannot create another order. Review its outcome before starting again.')
            if self.session.state.status != 'ready':
                raise DraftInputError('A ready draft is required before /preview.')
            self.invalidate()
            user = self._read(self.source.current_user)
            material = self._read(self.source.get_material, self.session.state.selected.id)
            if user.role not in ('viewer', 'staff', 'admin'):
                raise DraftInputError('Current role cannot submit an order.')
            self.session.state = ds.change(self.session.state,
                user=ds.Identity(**identity(user)),
                selected=ds.MaterialSnapshot.model_validate(material.model_dump()), read_at=ds.now())
            if self.session.state.status != 'ready':
                raise DraftInputError('Refreshed material is not ready. Edit the draft before creating a preview.')
            self._move('draft_ready')
            draft = self.session.state
            payload = OrderCreate(material_id=material.id, requested_quantity=draft.requested_quantity,
                                  request_notes=draft.request_notes)
            token = secrets.token_urlsafe(24)
            self.capabilities.add(token)
            self.preview = Preview(token, hashlib.sha256(token.encode()).hexdigest()[:16], binding(draft),
                                   payload, json.dumps(identity(user), sort_keys=True),
                                   json.dumps(facts(material), sort_keys=True), draft.read_at)
            self._move('previewed')
            emit(ds.preview(draft) + '\n\nACTION PREVIEW: POST /orders\n'
                 + f'Preview ID: {token}\nPreview reference: {self.preview.reference}\n'
                 + f'Canonical payload: {payload.canonical()}\n'
                 + 'Expected result: submitted order; reserved quantity 0.\n'
                 + 'Submission does not reserve stock. Approval checks current stock again.\n'
                 + f'To submit exactly once enter: confirm {token}\n'
                 + 'Use /cancel or edit the draft instead. Re-displaying a preview never submits it.')
            self.displayed = True

    def _orders(self):
        orders = []; total = None
        for page in range(1, MAX_ORDER_PAGES + 1):
            batch = self._read(self.source.list_orders, material_id=self.preview.payload.material_id,
                               page=page, size=10)
            if batch.page != page or batch.size != 10 or (total is not None and total != batch.total):
                raise AppError('Order pagination changed; a complete comparison is unavailable.')
            total = batch.total
            if batch.pages > MAX_ORDER_PAGES:
                raise AppError('Order pagination exceeds the 100-order safety bound.')
            if any(o.material_id != self.preview.payload.material_id for o in batch.items):
                raise AppError('Order list contains an unexpected material.')
            orders.extend(batch.items)
            if page >= batch.pages:
                break
        if len(orders) != total or len({o.id for o in orders}) != total:
            raise AppError('Order list is incomplete; no reliable comparison is available.')
        return orders

    def _matches(self, order, *, timestamp=False):
        p = self.preview.payload; user = json.loads(self.preview.user_json)
        good = (order.requested_by_user_id == user['id'] and order.material_id == p.material_id
                and order.requested_quantity == p.requested_quantity and order.request_notes == p.request_notes
                and order.status == 'submitted' and order.reserved_quantity == 0 and not order.is_archived)
        if timestamp:
            if not order.created_at: return False
            created = datetime.fromisoformat(order.created_at)
            # Local source MySQL DATETIME values use UTC without an offset.
            if created.tzinfo is None: created = created.replace(tzinfo=timezone.utc)
            good = good and self.started_at - timedelta(seconds=2) <= created <= datetime.now(timezone.utc) + timedelta(seconds=2)
        return good

    def _verify(self, order, origin):
        self.known_order_ids.add(order.id)
        if order.id in self.baseline or not self._matches(order):
            raise AppError('Order response does not match the confirmed action.')
        verified = self._read(self.source.get_order, order.id)
        material = self._read(self.source.get_material, self.preview.payload.material_id)
        if verified.id != order.id or not self._matches(verified) or material.id != self.preview.payload.material_id:
            raise AppError('Verification does not match the confirmed action.')
        before = json.loads(self.preview.material_json)
        observed = {'available': material.quantity_available, 'reserved': material.quantity_reserved}
        unchanged = (observed['available'] == before['quantity_available'] and observed['reserved'] == before['quantity_reserved'])
        self.receipt = {'outcome': 'succeeded', 'origin': origin, 'preview_reference': self.preview.reference,
            'request_id': self.request_id, 'order_id': verified.id, 'status': verified.status,
            'requester_id': verified.requested_by_user_id, 'material_id': verified.material_id,
            'material_code': before['material_code'], 'quantity': verified.requested_quantity,
            'notes': verified.request_notes, 'reserved_quantity': verified.reserved_quantity,
            'verified_at': ds.now(), 'material_before': {'available': before['quantity_available'], 'reserved': before['quantity_reserved']},
            'material_after': observed, 'stock_observation': 'unchanged' if unchanged else
            'changed since preview; concurrent activity is possible; causation is not established',
            'post_attempts': self.post_attempts}
        self._move('succeeded')

    def _reconcile(self):
        try:
            candidates = self._orders()
            matches = []
            uncertain_timestamp = False
            for candidate in candidates:
                if candidate.id in self.baseline: continue
                self.known_order_ids.add(candidate.id)
                order = self._read(self.source.get_order, candidate.id)
                if order.id != candidate.id:
                    raise AppError('Reconciliation returned an unexpected order ID.')
                if self._matches(order) and not order.created_at:
                    uncertain_timestamp = True
                if self._matches(order, timestamp=True): matches.append(order)
            if len(matches) == 1 and not uncertain_timestamp:
                self._verify(matches[0], 'reconciliation')
                self.receipt['caution'] = 'One new matching order was found; the source has no idempotency guarantee.'
            else:
                self.receipt = {'outcome': 'needs_reconciliation', 'reason':
                    'No unique new matching order. Owner review required; do not blindly resubmit.'}
        except AppError:
            self.receipt = {'outcome': 'needs_reconciliation', 'reason':
                'Reconciliation could not fully verify an order. Owner review required; no POST retry.'}

    def confirm(self, command):
        with self._lock:
            if (self.stage != 'previewed' or not self.displayed or not self.preview or self.consumed
                    or command != 'confirm ' + self.preview.capability):
                raise DraftInputError('Enter the exact confirmation command for the displayed current preview. No POST sent.')
            if binding(self.session.state) != self.preview.draft_binding:
                self.invalidate()
                raise DraftInputError('Draft changed. Use /preview and confirm the new preview. No POST sent.')
            self._move('confirmed')
            try:
                # Complete baseline first so identity/material refresh is immediately before POST.
                self.baseline = {o.id for o in self._orders()}
                user = self._read(self.source.current_user)
                material = self._read(self.source.get_material, self.preview.payload.material_id)
                old_user = json.loads(self.preview.user_json); old_material = json.loads(self.preview.material_json)
                changed = ['user.' + k for k,v in identity(user).items() if old_user[k] != v]
                changed += ['material.' + k for k,v in facts(material).items() if old_material[k] != v]
                if changed:
                    self.session.state = ds.change(self.session.state, user=ds.Identity(**identity(user)),
                        selected=ds.MaterialSnapshot.model_validate(material.model_dump()), read_at=ds.now())
                    self.invalidate()
                    return 'Confirmation invalidated; changed fields: ' + ', '.join(changed) + '. No POST sent. Review /show, then choose /preview.'
            except AppError:
                self.invalidate()
                return 'Pre-execution reads failed or baseline was incomplete. Confirmation invalidated; no POST sent. Refresh and review before continuing.'
            self.consumed = True  # Protected by the same lock as validation and execution.
            self.request_id = uuid4().hex
            self.started_at = datetime.now(timezone.utc)
            self._move('executing')
            self.post_attempts += 1
            try:
                order = self.source.create_order(self.preview.payload, request_id=self.request_id)
                try:
                    self._verify(order, 'response')
                except AppError:
                    self._move('needs_reconciliation')
                    self._reconcile()
            except AmbiguousWrite:
                self._move('needs_reconciliation')
                self._reconcile()
            except SourceError as error:
                if error.status in (401,403,404,409,422):
                    self._move('failed')
                    self.receipt = {'outcome': 'failed', 'reason': 'Source rejected submission.', 'status': error.status, 'code': error.code}
                else:
                    self._move('needs_reconciliation'); self._reconcile()
            except AppError:
                self._move('needs_reconciliation'); self._reconcile()
            except BaseException:
                # Includes interruption after sending. Preserve an honest state, never retry.
                self._move('needs_reconciliation')
                self.receipt = {'outcome': 'needs_reconciliation', 'reason': 'Execution interrupted; source outcome unknown.'}
                raise
            return self.result()

    def result(self):
        data = dict(self.receipt or {'outcome': self.stage})
        data.update(request_id=self.request_id, known_order_ids=sorted(self.known_order_ids),
                    baseline_order_ids=sorted(self.baseline), post_attempts=self.post_attempts,
                    action_source_reads=self.source_reads)
        return json.dumps(data, sort_keys=True, indent=2, ensure_ascii=True)


def interact_order(session, goal, emit, read_input=input):
    action = Submission(session)
    def handle(text):
        # The capability and agreement never enter the provider/history, including typos.
        if text == '/help':
            emit('Draft commands: /material ID_OR_CODE, /search TEXT, /select ID, /quantity INTEGER, /notes TEXT, /clear-notes, /refresh, /reset, /show, /exit. Submission: /preview, exact confirm command, /cancel.'); return
        if text == '/preview':
            action.show_preview(emit); return
        if text == '/cancel':
            action.invalidate(); emit('Preview canceled. No additional POST sent.'); return
        if text.strip().lower().startswith(('confirm', '/confirm')):
            emit(action.confirm(text)); return
        if any(token in text for token in action.capabilities):
            raise DraftInputError('Confirmation capability is accepted only in the exact confirmation command.')
        if text.strip().lower() in ('yes','ok','okay','go ahead','submit','/confirm'):
            raise DraftInputError('Agreement cannot submit an order. Use /preview and its exact command.')
        if action.consumed:
            if text not in ('/show','/exit','/abandon'):
                raise DraftInputError('Submission was attempted. Review the receipt; this session cannot submit again.')
            if text == '/show': emit(action.result()); return
        revision = session.state.revision
        output = session.handle(text)
        if session.state.revision != revision: action.invalidate()
        emit(output)
    try:
        emit('Order session: build a draft, /preview, then exact confirm command. /cancel is safe. At most one POST per session.')
        try: handle(goal)
        except DraftInputError as error: emit(str(error))
        for _ in range(60):
            if session.state.abandoned: break
            try: text = read_input('order> ')
            except EOFError: break
            try: handle(text)
            except DraftInputError as error: emit(str(error))
    finally:
        if action.post_attempts: emit(action.result())
        if not session.state.abandoned: session.state = ds.abandon(session.state)
        emit(f'In-memory draft and confirmation discarded. POST attempts: {action.post_attempts}; '
             f'model responses: {session.model_responses}; draft reads: {session.source_reads}; action reads: {action.source_reads}. '
             'Discarding this session does not undo a submitted order.')
