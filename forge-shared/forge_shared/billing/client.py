"""
Stripe client for billing operations.

Provides a unified client for Stripe operations including checkout sessions,
subscriptions, and customer management across the FORGE portfolio.

Example:
    ```python
    from forge_shared.billing import StripeClient

    client = StripeClient(api_key="sk_test_...")
    session = await client.create_checkout_session(
        product="interview-simulator",
        tier="pro",
        user_id="user_123",
        success_url="https://app.example.com/success",
        cancel_url="https://app.example.com/cancel"
    )
    print(session.url)
    ```
"""

from datetime import datetime, timezone
from typing import Any

import stripe
from stripe import StripeError

from forge_shared.billing.config import get_price_id, is_valid_product, is_valid_tier
from forge_shared.billing.models import (
    BillingError,
    CheckoutSession,
    Customer,
    PricingTier,
    Subscription,
    SubscriptionStatus,
)


class StripeClient:
    """
    Async-compatible Stripe client for billing operations.

    Provides methods for creating checkout sessions, managing subscriptions,
    and handling customers. All methods are designed to work in async contexts
    though Stripe's library uses synchronous I/O.

    Attributes:
        api_key: Stripe API secret key
        webhook_secret: Stripe webhook signing secret (optional)

    Example:
        ```python
        client = StripeClient(
            api_key="sk_test_...",
            webhook_secret="whsec_..."
        )

        # Create checkout session
        session = await client.create_checkout_session(
            product="interview-simulator",
            tier="pro",
            user_id="user_123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )

        # Get subscription
        sub = await client.get_subscription("sub_123")
        ```
    """

    def __init__(
        self,
        api_key: str,
        webhook_secret: str | None = None,
    ) -> None:
        """
        Initialize Stripe client.

        Args:
            api_key: Stripe API secret key (sk_test_... or sk_live_...)
            webhook_secret: Stripe webhook signing secret (whsec_...)
        """
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        stripe.api_key = api_key

    async def create_checkout_session(
        self,
        product: str,
        tier: str | PricingTier,
        user_id: str,
        success_url: str,
        cancel_url: str,
        customer_id: str | None = None,
        customer_email: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> CheckoutSession:
        """
        Create a Stripe Checkout session.

        Args:
            product: FORGE product identifier (e.g., "interview-simulator")
            tier: Pricing tier (e.g., "pro" or PricingTier.PRO)
            user_id: Internal user identifier
            success_url: URL to redirect on successful payment
            cancel_url: URL to redirect on canceled payment
            customer_id: Existing Stripe customer ID (optional)
            customer_email: Customer email for new customers (optional)
            metadata: Additional metadata for the session (optional)

        Returns:
            CheckoutSession with session ID and checkout URL

        Raises:
            BillingError: If checkout session creation fails

        Example:
            ```python
            session = await client.create_checkout_session(
                product="interview-simulator",
                tier=PricingTier.PRO,
                user_id="user_123",
                success_url="https://app.codeswiftr.com/success?session_id={CHECKOUT_SESSION_ID}",
                cancel_url="https://app.codeswiftr.com/pricing"
            )
            # Redirect user to session.url
            ```
        """
        tier_enum = PricingTier(tier) if isinstance(tier, str) else tier
        tier_str = tier_enum.value

        if not is_valid_product(product):
            raise BillingError(
                message=f"Invalid product: {product}",
                code="invalid_product",
            )

        if not is_valid_tier(product, tier_str):
            raise BillingError(
                message=f"Invalid tier '{tier_str}' for product '{product}'",
                code="invalid_tier",
            )

        price_id = get_price_id(product, tier_str)
        if price_id is None:
            raise BillingError(
                message="Free tier does not require checkout",
                code="free_tier_no_checkout",
            )

        session_metadata = {
            "product": product,
            "tier": tier_str,
            "user_id": user_id,
            **(metadata or {}),
        }

        session_params: dict[str, Any] = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": session_metadata,
            "subscription_data": {"metadata": session_metadata},
        }

        if customer_id:
            session_params["customer"] = customer_id
        elif customer_email:
            session_params["customer_email"] = customer_email

        try:
            session = stripe.checkout.Session.create(**session_params)

            return CheckoutSession(
                id=session.id,
                url=session.url or "",
                product=product,
                tier=tier_enum,
                user_id=user_id,
                customer_id=session.customer if isinstance(session.customer, str) else None,
                expires_at=datetime.fromtimestamp(session.expires_at, tz=timezone.utc)
                if session.expires_at
                else None,
            )
        except StripeError as e:
            raise BillingError(
                message=f"Failed to create checkout session: {e}",
                code="checkout_creation_failed",
                details={"stripe_error": str(e)},
            ) from e

    async def create_customer(
        self,
        user_id: str,
        email: str,
        name: str | None = None,
        metadata: dict[str, str] | None = None,
    ) -> Customer:
        """
        Create a Stripe customer.

        Args:
            user_id: Internal user identifier
            email: Customer email address
            name: Customer name (optional)
            metadata: Additional metadata (optional)

        Returns:
            Customer with Stripe customer ID

        Raises:
            BillingError: If customer creation fails
        """
        customer_metadata = {"user_id": user_id, **(metadata or {})}

        try:
            create_params: dict[str, Any] = {
                "email": email,
                "metadata": customer_metadata,
            }
            if name:
                create_params["name"] = name
            customer = stripe.Customer.create(**create_params)

            return Customer(
                id=customer.id,
                email=email,
                user_id=user_id,
                name=name,
                created_at=datetime.fromtimestamp(customer.created, tz=timezone.utc)
                if customer.created
                else None,
            )
        except StripeError as e:
            raise BillingError(
                message=f"Failed to create customer: {e}",
                code="customer_creation_failed",
                details={"stripe_error": str(e)},
            ) from e

    async def get_subscription(self, subscription_id: str) -> Subscription | None:
        """
        Get subscription by ID.

        Args:
            subscription_id: Stripe subscription ID

        Returns:
            Subscription if found, None otherwise

        Raises:
            BillingError: If retrieval fails (except not found)
        """
        try:
            sub = stripe.Subscription.retrieve(subscription_id)
            return self._parse_subscription(sub)
        except stripe.InvalidRequestError:
            return None
        except StripeError as e:
            raise BillingError(
                message=f"Failed to retrieve subscription: {e}",
                code="subscription_retrieval_failed",
                details={"stripe_error": str(e)},
            ) from e

    async def cancel_subscription(
        self,
        subscription_id: str,
        cancel_at_period_end: bool = True,
    ) -> bool:
        """
        Cancel a subscription.

        Args:
            subscription_id: Stripe subscription ID
            cancel_at_period_end: If True, cancel at end of billing period;
                                  if False, cancel immediately

        Returns:
            True if cancellation successful

        Raises:
            BillingError: If cancellation fails
        """
        try:
            if cancel_at_period_end:
                stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                stripe.Subscription.cancel(subscription_id)
            return True
        except StripeError as e:
            raise BillingError(
                message=f"Failed to cancel subscription: {e}",
                code="subscription_cancellation_failed",
                details={"stripe_error": str(e)},
            ) from e

    async def get_customer_subscriptions(
        self,
        customer_id: str,
        active_only: bool = True,
    ) -> list[Subscription]:
        """
        Get all subscriptions for a customer.

        Args:
            customer_id: Stripe customer ID
            active_only: If True, only return active subscriptions

        Returns:
            List of subscriptions

        Raises:
            BillingError: If retrieval fails
        """
        try:
            params: dict[str, Any] = {"customer": customer_id}
            if active_only:
                params["status"] = "active"

            subscriptions = stripe.Subscription.list(**params)

            return [
                sub
                for sub in (self._parse_subscription(s) for s in subscriptions.data)
                if sub is not None
            ]
        except StripeError as e:
            raise BillingError(
                message=f"Failed to retrieve customer subscriptions: {e}",
                code="subscriptions_retrieval_failed",
                details={"stripe_error": str(e)},
            ) from e

    async def get_customer_by_user_id(self, user_id: str) -> Customer | None:
        """
        Find customer by internal user ID.

        Args:
            user_id: Internal user identifier

        Returns:
            Customer if found, None otherwise
        """
        try:
            customers = stripe.Customer.search(
                query=f"metadata['user_id']:'{user_id}'",
            )

            if not customers.data:
                return None

            customer = customers.data[0]
            return Customer(
                id=customer.id,
                email=customer.email or "",
                user_id=user_id,
                name=customer.name,
                created_at=datetime.fromtimestamp(customer.created, tz=timezone.utc)
                if customer.created
                else None,
            )
        except StripeError:
            return None

    def _parse_subscription(self, sub: stripe.Subscription) -> Subscription | None:
        """Parse Stripe subscription object to internal model."""
        metadata = sub.metadata or {}
        product = metadata.get("product", "")
        tier_str = metadata.get("tier", "free")
        user_id = metadata.get("user_id", "")

        try:
            tier = PricingTier(tier_str)
        except ValueError:
            tier = PricingTier.FREE

        try:
            status = SubscriptionStatus(sub.status)
        except ValueError:
            status = SubscriptionStatus.CANCELED

        customer_id = sub.customer if isinstance(sub.customer, str) else ""

        period_start = getattr(sub, "current_period_start", None)
        period_end = getattr(sub, "current_period_end", None)

        return Subscription(
            id=sub.id,
            status=status,
            product=product,
            tier=tier,
            user_id=user_id,
            customer_id=customer_id,
            current_period_start=datetime.fromtimestamp(period_start, tz=timezone.utc)
            if period_start
            else None,
            current_period_end=datetime.fromtimestamp(period_end, tz=timezone.utc)
            if period_end
            else None,
            cancel_at_period_end=sub.cancel_at_period_end or False,
            canceled_at=datetime.fromtimestamp(sub.canceled_at, tz=timezone.utc)
            if sub.canceled_at
            else None,
        )
