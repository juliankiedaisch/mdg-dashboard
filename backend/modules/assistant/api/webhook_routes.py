# Assistant Module - API: Webhook Routes
"""
Public endpoint for receiving BookStack webhook events.

This endpoint is NOT protected by login/permission decorators because
it is called by BookStack itself (server-to-server).  Validation is
handled via the webhook_enabled flag in each source's config.
"""
import logging
from flask import request, jsonify

logger = logging.getLogger(__name__)


def register_webhook_routes(bp):
    """Register webhook receiver routes on the given Blueprint."""

    @bp.route('/api/assistant/webhooks/bookstack', methods=['POST'])
    def bookstack_webhook():
        """Receive a BookStack webhook event and trigger incremental re-indexing.

        BookStack sends a JSON payload with event details including the
        related item and who triggered the change.  The service layer
        determines which source(s) to update and which pages to re-index.
        """
        payload = request.get_json(silent=True)
        if not payload:
            logger.warning("[Webhook] Received empty or invalid JSON payload")
            return jsonify({'status': 'error', 'message': 'Invalid JSON payload'}), 400

        event = payload.get('event', '')
        if not event:
            logger.warning("[Webhook] Received payload without 'event' field")
            return jsonify({'status': 'error', 'message': 'Missing event field'}), 400

        logger.info("[Webhook] Received BookStack event: %s", event)

        try:
            from modules.assistant.services.webhook_service import process_webhook
            result = process_webhook(payload)
            status_code = 200 if result.get('status') != 'error' else 500
            return jsonify(result), status_code
        except Exception as exc:
            logger.error("[Webhook] Unhandled error processing webhook: %s",
                         exc, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': f'Internal error: {str(exc)}',
            }), 500

    @bp.route('/api/assistant/webhooks/bookstack', methods=['GET'])
    def bookstack_webhook_health():
        """Simple health-check endpoint for the webhook receiver.

        Returns 200 so BookStack can verify the endpoint is reachable
        when configuring the webhook.
        """
        return jsonify({
            'status': 'ok',
            'message': 'BookStack webhook endpoint is active',
        })
