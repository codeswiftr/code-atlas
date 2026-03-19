"""Stripe billing routes for Code Atlas Operator MVP.

Provides checkout sessions, webhook handling, and subscription management.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ...auth.api_keys import APIKeyManager, get_key_manager
from ...logging_config import get_logger
from ...schemas.auth import APITier, APIKeyScope

logger = get_logger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])

# Stripe configuration (use test keys in development)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "sk_test_...")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_test_...")
STRIPE_API_KEY = os.getenv("STRIPE_API_KEY", "")

# Price IDs for Stripe (create in Stripe dashboard)
PRICE_IDS = {
    "pro_monthly": os.getenv("STRIPE_PRICE_PRO_MONTHLY", "price_pro_monthly"),
    "team_monthly": os.getenv("STRIPE_PRICE_TEAM_MONTHLY", "price_team_monthly"),
}


class CheckoutRequest(BaseModel):
    """Request to create a Stripe checkout session."""

    tier: APITier = Field(..., description="Tier to subscribe to")
    success_url: str | None = Field(
        None, description="URL to redirect after success"
    )
    cancel_url: str | None = Field(
        None, description="URL to redirect on cancellation"
    )


class CheckoutResponse(BaseModel):
    """Response with Stripe checkout session URL."""

    session_id: str = Field(..., description="Stripe checkout session ID")
    url: str = Field(..., description="Stripe checkout URL")
    tier: APITier
    amount_cents: int = Field(..., description="Price in cents")


class SubscriptionStatus(BaseModel):
    """Current subscription status for an API key."""

    tier: APITier
    status: str = Field(..., description="Subscription status (active, past_due, canceled)")
    current_period_start: datetime | None
    current_period_end: datetime | None
    requests_used: int = Field(default=0, description="Requests used in current period")
    requests_limit: int = Field(default=10, description="Rate limit for tier")


# In-memory subscription storage (replace with database in production)
# Format: {api_key_prefix: {tier, status, stripe_customer_id, stripe_subscription_id}}
_subscriptions: dict[str, dict[str, Any]] = {}


def _get_stripe_client():
    """Get Stripe client (lazy import)."""
    try:
        import stripe
        stripe.api_key = STRIPE_API_KEY
        return stripe
    except ImportError:
        logger.warning("Stripe library not installed, using mock mode")
        return None


def _require_admin_key(api_key: APIKeyManager = Depends(get_key_manager)) -> str:
    """Dependency that requires admin scope."""
    # In production, validate the API key has admin scope
    # For now, check if key exists and has admin scope
    # This is a simplified check - production would validate properly
    api_key_header = "admin-test-key"  # Would come from request in real impl
    return api_key_header


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe checkout session",
    description="Create a Stripe checkout session for subscription.",
)
async def create_checkout(
    request: CheckoutRequest,
    api_key: str = Depends(_require_admin_key),
) -> CheckoutResponse:
    """Create a Stripe checkout session.

    This endpoint creates a Stripe checkout session for subscribing
    to a paid tier. The user will be redirected to Stripe to complete payment.
    """
    stripe = _get_stripe_client()

    if not stripe or not STRIPE_SECRET_KEY.startswith("sk_live"):
        # Development mode - return mock response
        logger.info(
            "Checkout requested in development mode",
            tier=request.tier.value,
        )
        return CheckoutResponse(
            session_id="cs_test_" + datetime.now(tz=UTC).strftime("%Y%m%d%H%M%S"),
            url="https://checkout.stripe.com/mock",
            tier=request.tier,
            amount_cents=_get_tier_price(request.tier),
        )

    # Production mode - create real Stripe session
    try:
        session = stripe.checkout.Session.create(
            mode="subscription" if request.tier != APITier.FREE else "payment",
            line_items=[
                {
                    "price": PRICE_IDS.get(
                        "pro_monthly" if request.tier == APITier.PRO else "team_monthly"
                    ),
                    "quantity": 1,
                }
            ],
            success_url=request.success_url or "https://atlas.codeswiftr.com/billing/success",
            cancel_url=request.cancel_url or "https://atlas.codeswiftr.com/billing/cancel",
            metadata={
                "tier": request.tier.value,
            },
        )

        logger.info(
            "Stripe checkout session created",
            session_id=session.id,
            tier=request.tier.value,
        )

        return CheckoutResponse(
            session_id=session.id,
            url=session.url,
            tier=request.tier,
            amount_cents=_get_tier_price(request.tier),
        )

    except Exception as exc:
        logger.error(
            "Failed to create checkout session",
            error=str(exc),
            tier=request.tier.value,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create checkout session: {exc}",
        )


@router.post(
    "/webhook",
    status_code=status.HTTP_200_OK,
    summary="Handle Stripe webhooks",
    description="Handle webhooks from Stripe for subscription events.",
)
async def stripe_webhook(
    request: Request,
) -> dict[str, Any]:
    """Handle Stripe webhook events.

    Processes the following events:
    - checkout.session.completed: New subscription
    - customer.subscription.updated: Tier change or status update
    - customer.subscription.deleted: Cancellation
    - invoice.payment_failed: Payment failure notification
    """
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    # Verify webhook signature
    stripe = _get_stripe_client()
    if stripe and STRIPE_WEBHOOK_SECRET.startswith("whsec_"):
        try:
            event = stripe.Webhook.construct_event(
                payload,
                sig_header,
                STRIPE_WEBHOOK_SECRET,
            )
        except Exception as exc:
            logger.warning("Invalid webhook signature", error=str(exc))
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid webhook signature",
            )
    else:
        # Development mode - skip signature verification; parse JSON payload
        try:
            event = json.loads(payload)
        except (json.JSONDecodeError, ValueError):
            event = {}
        logger.debug("Webhook received in development mode")

    # Handle different event types
    event_type = event.get("type", "unknown")
    data = event.get("data", {})

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(data)
    else:
        logger.debug("Unhandled webhook event", event_type=event_type)

    return {"status": "received"}


async def _handle_checkout_completed(data: dict) -> None:
    """Handle successful checkout completion."""
    tier = data.get("metadata", {}).get("tier", "free")
    customer_id = data.get("customer", "")

    logger.info(
        "Checkout completed",
        customer_id=customer_id,
        tier=tier,
    )

    # Store subscription (would update database in production)
    # For now, store in memory
    _subscriptions[customer_id] = {
        "tier": APITier(tier),
        "status": "active",
        "stripe_customer_id": customer_id,
        "stripe_subscription_id": data.get("subscription", ""),
        "created_at": datetime.now(tz=UTC),
    }


async def _handle_subscription_updated(data: dict) -> None:
    """Handle subscription updates."""
    subscription_id = data.get("id", "")
    status_str = data.get("status", "active")
    customer_id = data.get("customer", "")

    logger.info(
        "Subscription updated",
        subscription_id=subscription_id,
        status=status_str,
    )

    # Update subscription status
    for key_prefix, sub in _subscriptions.items():
        if sub.get("stripe_subscription_id") == subscription_id:
            sub["status"] = status_str
            break


async def _handle_subscription_deleted(data: dict) -> None:
    """Handle subscription deletion."""
    subscription_id = data.get("id", "")
    customer_id = data.get("customer", "")

    logger.info(
        "Subscription deleted",
        subscription_id=subscription_id,
        customer_id=customer_id,
    )

    # Downgrade to free tier
    for key_prefix, sub in _subscriptions.items():
        if sub.get("stripe_subscription_id") == subscription_id:
            sub["tier"] = APITier.FREE
            sub["status"] = "canceled"
            break


async def _handle_payment_failed(data: dict) -> None:
    """Handle payment failure."""
    customer_id = data.get("customer", "")
    attempt_count = data.get("attempt_count", 1)

    logger.warning(
        "Payment failed",
        customer_id=customer_id,
        attempt_count=attempt_count,
    )

    # Note: Don't immediately downgrade - Stripe will retry
    # The subscription.updated event with status="unpaid" will handle final downgrade


@router.get(
    "/subscription/{key_prefix}",
    response_model=SubscriptionStatus,
    summary="Get subscription status",
    description="Get current subscription status for an API key.",
)
async def get_subscription_status(
    key_prefix: str,
    api_key: str = Depends(_require_admin_key),
) -> SubscriptionStatus:
    """Get subscription status for an API key."""
    sub = _subscriptions.get(key_prefix, {})

    tier = sub.get("tier", APITier.FREE)
    status_str = sub.get("status", "active")

    # Get usage for current period
    from ...usage_tracker import get_tracker
    tracker = get_tracker()
    hourly_usage = tracker.get_hourly_usage(f"key:{key_prefix}")

    limits = {
        APITier.FREE: 10,
        APITier.PRO: 100,
        APITier.TEAM: 1000,
    }

    return SubscriptionStatus(
        tier=tier,
        status=status_str,
        current_period_start=None,
        current_period_end=None,
        requests_used=hourly_usage,
        requests_limit=limits.get(tier, 10),
    )


def _get_tier_price(tier: APITier) -> int:
    """Get price in cents for a tier."""
    prices = {
        APITier.FREE: 0,
        APITier.PRO: 2900,  # $29.00
        APITier.TEAM: 9900,  # $99.00
    }
    return prices.get(tier, 0)
