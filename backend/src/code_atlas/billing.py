"""Stripe billing integration for Code Atlas.

Provides checkout session creation and webhook handling for
tier upgrades (free/pro/team).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from typing import Any

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status

from .auth.api_keys import get_key_manager
from .logging_config import get_logger
from .schemas.auth import APITier

logger = get_logger(__name__)

router = APIRouter(prefix="/billing", tags=["Billing"])


class SubscriptionTier(str, Enum):
    """Subscription tier levels for Code Atlas."""

    FREE = "free"
    PRO = "pro"
    TEAM = "team"


# Price IDs - in production these come from Stripe Dashboard
# These are placeholders that should be set via environment variables
PRICE_IDS: dict[SubscriptionTier, str | None] = {
    SubscriptionTier.FREE: None,  # Free tier has no price
    SubscriptionTier.PRO: os.getenv("STRIPE_PRICE_PRO", "price_pro_placeholder"),
    SubscriptionTier.TEAM: os.getenv("STRIPE_PRICE_TEAM", "price_team_placeholder"),
}

# Tier limits for API features
TIER_LIMITS: dict[SubscriptionTier, dict[str, Any]] = {
    SubscriptionTier.FREE: {
        "max_sessions_per_report": 5,
        "max_projects": 3,
        "use_llm": False,
        "support": "community",
    },
    SubscriptionTier.PRO: {
        "max_sessions_per_report": 50,
        "max_projects": 10,
        "use_llm": True,
        "support": "email",
    },
    SubscriptionTier.TEAM: {
        "max_sessions_per_report": 200,
        "max_projects": 100,
        "use_llm": True,
        "support": "priority",
    },
}


def get_stripe_api_key() -> str:
    """Get Stripe API key from environment."""
    key = os.getenv("STRIPE_API_KEY", "")
    if not key:
        logger.warning("STRIPE_API_KEY not set - billing features disabled")
    return key


def get_stripe_webhook_secret() -> str:
    """Get Stripe webhook secret from environment."""
    return os.getenv("STRIPE_WEBHOOK_SECRET", "")


def is_billing_enabled() -> bool:
    """Check if billing is configured."""
    return bool(get_stripe_api_key())


def get_price_id(tier: SubscriptionTier) -> str | None:
    """Get Stripe price ID for a tier."""
    return PRICE_IDS.get(tier)


def get_tier_limits(tier: SubscriptionTier) -> dict[str, Any]:
    """Get feature limits for a tier."""
    return TIER_LIMITS.get(tier, TIER_LIMITS[SubscriptionTier.FREE])


@dataclass
class CheckoutSession:
    """Stripe checkout session data."""

    session_id: str
    url: str
    tier: SubscriptionTier


@dataclass
class CheckoutRequest:
    """Request to create a checkout session."""

    tier: SubscriptionTier
    success_url: str
    cancel_url: str
    customer_email: str | None = None


def create_checkout_session(
    tier: SubscriptionTier,
    success_url: str,
    cancel_url: str,
    customer_email: str | None = None,
    user_id: str | None = None,
) -> CheckoutSession:
    """Create a Stripe Checkout session for tier upgrade.

    Args:
        tier: Target subscription tier
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect if payment cancelled
        customer_email: Optional customer email for checkout
        user_id: Internal user ID to associate with session

    Returns:
        CheckoutSession with session ID and checkout URL

    Raises:
        HTTPException: If billing not configured or tier invalid
    """
    if tier == SubscriptionTier.FREE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot create checkout for free tier",
        )

    # Check billing configuration (Stripe key first, then price ID)
    stripe_key = get_stripe_api_key()
    if not stripe_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )
    
    price_id = get_price_id(tier)
    if not price_id or "placeholder" in price_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Price not configured for tier: {tier.value}",
        )

    stripe.api_key = stripe_key

    try:
        session_params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "subscription_data": {
                "metadata": {
                    "tier": tier.value,
                    "user_id": user_id or "anonymous",
                    "product": "code-atlas",
                }
            },
        }

        if customer_email:
            session_params["customer_email"] = customer_email

        session = stripe.checkout.Session.create(**session_params)

        logger.info(
            "Checkout session created",
            session_id=session.id,
            tier=tier.value,
            user_id=user_id,
        )

        return CheckoutSession(
            session_id=session.id,
            url=session.url or "",
            tier=tier,
        )

    except stripe.error.StripeError as e:
        logger.error("Stripe checkout failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Checkout creation failed: {str(e)}",
        ) from e


@router.post("/checkout")
async def checkout_endpoint(request: CheckoutRequest) -> dict[str, str]:
    """Create a Stripe Checkout session for tier upgrade.

    Request body:
        - tier: Target tier (pro, team)
        - success_url: Redirect URL after payment
        - cancel_url: Redirect URL if cancelled
        - customer_email: Optional email for checkout

    Returns:
        - session_id: Stripe session ID
        - url: Checkout URL to redirect user to
        - tier: Selected tier
    """
    session = create_checkout_session(
        tier=request.tier,
        success_url=request.success_url,
        cancel_url=request.cancel_url,
        customer_email=request.customer_email,
    )

    return {
        "session_id": session.session_id,
        "url": session.url,
        "tier": session.tier.value,
    }


@router.get("/tiers")
async def list_tiers() -> dict[str, Any]:
    """List available subscription tiers and their limits.

    Returns:
        Dictionary of tier names to feature limits
    """
    return {
        tier.value: {
            "name": tier.value.capitalize(),
            "price_id": get_price_id(tier),
            "limits": get_tier_limits(tier),
        }
        for tier in SubscriptionTier
    }


@router.get("/tier/{tier}")
async def get_tier_info(tier: SubscriptionTier) -> dict[str, Any]:
    """Get details for a specific tier.

    Args:
        tier: Tier name (free, pro, team)

    Returns:
        Tier details including limits
    """
    return {
        "tier": tier.value,
        "limits": get_tier_limits(tier),
        "price_id": get_price_id(tier),
    }


# Webhook handler for Stripe events
@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(None, alias="stripe-signature"),
) -> dict[str, str]:
    """Handle Stripe webhook events.

    Processes:
        - checkout.session.completed: Upgrade user tier
        - customer.subscription.deleted: Downgrade to free
        - invoice.payment_failed: Mark subscription past_due

    Returns:
        { "status": "success" } on successful processing
    """
    if not is_billing_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Billing not configured",
        )

    payload = await request.body()
    webhook_secret = get_stripe_webhook_secret()

    if not webhook_secret:
        logger.error("STRIPE_WEBHOOK_SECRET not set")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured",
        )

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature or "",
            secret=webhook_secret,
        )
    except stripe.error.SignatureVerificationError as e:
        logger.error("Webhook signature verification failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid signature",
        ) from e
    except ValueError as e:
        logger.error("Webhook payload invalid", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid payload",
        ) from e

    logger.info("Webhook received", event_type=event.type, event_id=event.id)

    # Handle checkout.session.completed - upgrade user tier
    if event.type == "checkout.session.completed":
        await _handle_checkout_completed(event.data.object)

    # Handle subscription updates
    elif event.type == "customer.subscription.updated":
        await _handle_subscription_updated(event.data.object)

    # Handle subscription cancellation
    elif event.type == "customer.subscription.deleted":
        await _handle_subscription_deleted(event.data.object)

    elif event.type == "invoice.payment_failed":
        await _handle_payment_failed(event.data.object)

    else:
        logger.debug("Unhandled webhook event type", event_type=event.type)

    return {"status": "success"}


async def _handle_checkout_completed(session: stripe.checkout.Session) -> None:
    """Handle successful checkout - upgrade user to paid tier.

    Looks up the API key by the user_id stored in subscription metadata,
    upgrades its tier, links the Stripe customer ID for future webhook lookups,
    and marks the subscription as active.
    """
    metadata = session.metadata or {}
    tier_str = metadata.get("tier", "")
    user_id = metadata.get("user_id", "")
    customer_id = session.customer
    subscription_id = session.subscription

    logger.info(
        "Checkout completed - upgrading tier",
        user_id=user_id,
        tier=tier_str,
        customer_id=customer_id,
        session_id=session.id,
    )

    if not user_id or user_id == "anonymous":
        logger.warning(
            "Checkout completed but user_id missing in metadata — cannot update tier",
            session_id=session.id,
        )
        return

    try:
        new_tier = APITier(tier_str)
    except ValueError:
        logger.error(
            "Checkout completed with unrecognised tier — defaulting to PRO",
            tier=tier_str,
            user_id=user_id,
        )
        new_tier = APITier.PRO

    key_manager = get_key_manager()
    tier_updated = key_manager.update_tier(user_id, new_tier)
    key_manager.update_subscription_status(user_id, "active")
    key_manager.set_stripe_customer(user_id, customer_id or "", subscription_id or None)

    if tier_updated:
        logger.info(
            "User tier upgraded in database",
            user_id=user_id,
            new_tier=new_tier.value,
            customer_id=customer_id,
        )
    else:
        logger.warning(
            "Checkout completed but API key not found in database",
            user_id=user_id,
            customer_id=customer_id,
        )


async def _handle_subscription_updated(subscription: stripe.Subscription) -> None:
    """Handle subscription updates (plan changes, status changes, renewals).

    Syncs the Stripe subscription status (active/trialing/past_due/canceled/unpaid)
    into the local api_keys record. When status becomes 'canceled' or 'unpaid' the
    key is downgraded to the free tier so rate limiting takes effect immediately.
    """
    metadata = subscription.metadata or {}
    user_id = metadata.get("user_id", "")
    new_status = subscription.status  # e.g. active, past_due, canceled, trialing
    customer_id = subscription.customer

    logger.info(
        "Subscription updated",
        user_id=user_id,
        status=new_status,
        subscription_id=subscription.id,
        customer_id=customer_id,
    )

    key_manager = get_key_manager()

    # Resolve the API key: prefer user_id from metadata, fall back to Stripe customer ID
    record = None
    if user_id and user_id != "unknown":
        record = key_manager.get_key(user_id)
    if record is None and customer_id:
        record = key_manager.get_key_by_stripe_customer(customer_id)

    if record is None:
        logger.warning(
            "Subscription updated but no matching API key found",
            user_id=user_id,
            customer_id=customer_id,
            subscription_id=subscription.id,
        )
        return

    key_manager.update_subscription_status(record.key_id, new_status)

    # Downgrade to free on terminal statuses so rate limiting applies immediately
    if new_status in ("canceled", "unpaid"):
        key_manager.update_tier(record.key_id, APITier.FREE)
        logger.info(
            "Subscription terminal — key downgraded to free tier",
            key_id=record.key_id,
            status=new_status,
        )
    else:
        logger.info(
            "Subscription status synced",
            key_id=record.key_id,
            status=new_status,
        )


async def _handle_subscription_deleted(subscription: stripe.Subscription) -> None:
    """Handle subscription cancellation — downgrade key to free tier.

    Stripe fires this event when a subscription is permanently deleted (end of
    billing period after cancellation, or immediate cancellation). The key is
    downgraded to free and the subscription status set to 'canceled'.
    """
    metadata = subscription.metadata or {}
    user_id = metadata.get("user_id", "")
    customer_id = subscription.customer

    logger.info(
        "Subscription canceled - downgrading to free",
        user_id=user_id,
        subscription_id=subscription.id,
        customer_id=customer_id,
    )

    key_manager = get_key_manager()

    record = None
    if user_id and user_id != "unknown":
        record = key_manager.get_key(user_id)
    if record is None and customer_id:
        record = key_manager.get_key_by_stripe_customer(customer_id)

    if record is None:
        logger.warning(
            "Subscription deleted but no matching API key found",
            user_id=user_id,
            customer_id=customer_id,
            subscription_id=subscription.id,
        )
        return

    key_manager.update_tier(record.key_id, APITier.FREE)
    key_manager.update_subscription_status(record.key_id, "canceled")
    logger.info(
        "Key downgraded to free tier after cancellation",
        key_id=record.key_id,
        customer_id=customer_id,
    )


async def _handle_payment_failed(invoice: stripe.Invoice) -> None:
    """Handle failed payment — mark subscription as past_due.

    Stripe retries failed payments automatically (Smart Retries / Dunning). We
    mark the key as past_due immediately so the application can surface a
    warning banner, but we do NOT downgrade the tier yet — Stripe will send
    customer.subscription.updated with status='unpaid' (or 'canceled') if
    retries are exhausted, at which point _handle_subscription_updated will
    perform the tier downgrade.
    """
    customer_id = invoice.customer
    invoice_id = invoice.id
    attempt_count = getattr(invoice, "attempt_count", None)

    logger.warning(
        "Payment failed — marking subscription past_due",
        customer_id=customer_id,
        invoice_id=invoice_id,
        attempt_count=attempt_count,
    )

    key_manager = get_key_manager()
    record = key_manager.get_key_by_stripe_customer(customer_id) if customer_id else None

    if record is None:
        logger.warning(
            "Payment failed but no matching API key found for customer",
            customer_id=customer_id,
            invoice_id=invoice_id,
        )
        return

    key_manager.update_subscription_status(record.key_id, "past_due")
    logger.info(
        "Key subscription status set to past_due — tier preserved pending Stripe retries",
        key_id=record.key_id,
        customer_id=customer_id,
        attempt_count=attempt_count,
    )
