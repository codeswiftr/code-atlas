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

from .logging_config import get_logger

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

    In production this would:
    1. Lookup user by email or user_id in metadata
    2. Update user's tier in database
    3. Create subscription record
    4. Send confirmation email
    """
    metadata = session.metadata or {}
    tier = metadata.get("tier", "unknown")
    user_id = metadata.get("user_id", "unknown")
    customer_id = session.customer

    logger.info(
        "Checkout completed - upgrading tier",
        user_id=user_id,
        tier=tier,
        customer_id=customer_id,
        session_id=session.id,
    )

    # TODO: In production, update user in database
    # For MVP, log and track via PostHog or similar
    # Example:
    # user = await get_user_by_id(user_id)
    # user.tier = tier
    # user.stripe_customer_id = customer_id
    # await user.save()


async def _handle_subscription_updated(subscription: stripe.Subscription) -> None:
    """Handle subscription updates (plan changes, renewals)."""
    metadata = subscription.metadata or {}
    user_id = metadata.get("user_id", "unknown")
    status = subscription.status

    logger.info(
        "Subscription updated",
        user_id=user_id,
        status=status,
        subscription_id=subscription.id,
    )

    # TODO: Update subscription status in database
    # Handle status: active, past_due, canceled, etc.


async def _handle_subscription_deleted(subscription: stripe.Subscription) -> None:
    """Handle subscription cancellation - downgrade to free."""
    metadata = subscription.metadata or {}
    user_id = metadata.get("user_id", "unknown")

    logger.info(
        "Subscription canceled - downgrading to free",
        user_id=user_id,
        subscription_id=subscription.id,
    )

    # TODO: Downgrade user to free tier in database


async def _handle_payment_failed(invoice: stripe.Invoice) -> None:
    """Handle failed payment - mark subscription past_due."""
    customer_id = invoice.customer

    logger.warning(
        "Payment failed",
        customer_id=customer_id,
        invoice_id=invoice.id,
    )

    # TODO: Mark subscription as past_due, notify user
