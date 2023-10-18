#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

from typing import Any, List, Mapping, MutableMapping, Tuple

import pendulum
import stripe
from airbyte_cdk import AirbyteLogger
from airbyte_cdk.entrypoint import logger as entrypoint_logger
from airbyte_cdk.models import FailureType
from airbyte_cdk.models.airbyte_protocol import SyncMode
from airbyte_cdk.sources import AbstractSource
from airbyte_cdk.sources.connector_state_manager import ConnectorStateManager
from airbyte_cdk.sources.message.repository import InMemoryMessageRepository
from airbyte_cdk.sources.streams import Stream
from airbyte_cdk.sources.streams.concurrent.adapters import StreamFacade
from airbyte_cdk.sources.streams.concurrent.cursor import ConcurrentCursor, CursorField, NoopCursor
from airbyte_cdk.sources.streams.http.auth import TokenAuthenticator
from airbyte_cdk.utils import AirbyteTracedException
from source_stripe.streams import (
    CheckoutSessionsLineItems,
    CreatedCursorIncrementalStripeStream,
    CustomerBalanceTransactions,
    Events,
    FilteringRecordExtractor,
    IncrementalStripeStream,
    Persons,
    SetupAttempts,
    StripeLazySubStream,
    StripeStream,
    StripeSubStream,
    UpdatedCursorIncrementalStripeLazySubStream,
    UpdatedCursorIncrementalStripeStream,
)


class SourceStripe(AbstractSource):
    def __init__(self, state, catalog, use_concurrent_cdk: bool = False, **kwargs):
        super().__init__(**kwargs)
        self._state = state
        self._catalog = catalog
        self._use_concurrent_cdk = use_concurrent_cdk

    message_repository = InMemoryMessageRepository(entrypoint_logger.level)

    @staticmethod
    def validate_and_fill_with_defaults(config: MutableMapping) -> MutableMapping:
        start_date, lookback_window_days, slice_range = (
            config.get("start_date"),
            config.get("lookback_window_days"),
            config.get("slice_range"),
        )
        if lookback_window_days is None:
            config["lookback_window_days"] = 0
        elif not isinstance(lookback_window_days, int) or lookback_window_days < 0:
            message = f"Invalid lookback window {lookback_window_days}. Please use only positive integer values or 0."
            raise AirbyteTracedException(
                message=message,
                internal_message=message,
                failure_type=FailureType.config_error,
            )
        if start_date:
            try:
                start_date = pendulum.parse(start_date).int_timestamp
            except pendulum.parsing.exceptions.ParserError as e:
                message = f"Invalid start date {start_date}. Please use YYYY-MM-DDTHH:MM:SSZ format."
                raise AirbyteTracedException(
                    message=message,
                    internal_message=message,
                    failure_type=FailureType.config_error,
                ) from e
        else:
            start_date = pendulum.datetime(2017, 1, 25).int_timestamp
        config["start_date"] = start_date
        if slice_range is None:
            config["slice_range"] = 365
        elif not isinstance(slice_range, int) or slice_range < 1:
            message = f"Invalid slice range value {slice_range}. Please use positive integer values only."
            raise AirbyteTracedException(
                message=message,
                internal_message=message,
                failure_type=FailureType.config_error,
            )
        return config

    def check_connection(self, logger: AirbyteLogger, config: Mapping[str, Any]) -> Tuple[bool, Any]:
        self.validate_and_fill_with_defaults(config)
        stripe.api_key = config["client_secret"]
        try:
            stripe.Account.retrieve(config["account_id"])
        except (stripe.error.AuthenticationError, stripe.error.PermissionError) as e:
            return False, str(e)
        return True, None

    def streams(self, config: Mapping[str, Any]) -> List[Stream]:
        config = self.validate_and_fill_with_defaults(config)
        authenticator = TokenAuthenticator(config["client_secret"])
        args = {
            "authenticator": authenticator,
            "account_id": config["account_id"],
            "start_date": config["start_date"],
            "slice_range": config["slice_range"],
        }
        customers = IncrementalStripeStream(
            name="customers",
            path="customers",
            use_cache=True,
            event_types=["customer.created", "customer.updated", "customer.deleted"],
            **args,
        )
        bank_accounts = UpdatedCursorIncrementalStripeLazySubStream(
            name="bank_accounts",
            path=lambda self, stream_slice, *args, **kwargs: f"customers/{stream_slice[self.parent_id]}/sources",
            parent=customers,
            event_types=["customer.source.created", "customer.source.expiring", "customer.source.updated", "customer.source.deleted"],
            legacy_cursor_field=None,
            parent_id="customer_id",
            sub_items_attr="sources",
            response_filter={"attr": "object", "value": "bank_account"},
            extra_request_params={"object": "bank_account"},
            record_extractor=FilteringRecordExtractor("updated", None, "bank_account"),
            **args,
        )
        # invoices = IncrementalStripeStream(
        #     name="invoices",
        #     path="invoices",
        #     use_cache=True,
        #     event_types=[
        #         "invoice.created",
        #         "invoice.finalization_failed",
        #         "invoice.finalized",
        #         "invoice.marked_uncollectible",
        #         "invoice.paid",
        #         "invoice.payment_action_required",
        #         "invoice.payment_failed",
        #         "invoice.payment_succeeded",
        #         "invoice.sent",
        #         "invoice.updated",
        #         "invoice.voided",
        #         "invoice.deleted",
        #     ],
        #     **args,
        # )
        # invoice_line_items = StripeLazySubStream(
        #     name="invoice_line_items",
        #     path=lambda self, *args, stream_slice, **kwargs: f"invoices/{stream_slice[self.parent_id]}/lines",
        #     parent=invoices,
        #     parent_id="invoice_id",
        #     sub_items_attr="lines",
        #     add_parent_id=True,
        #     **args,
        # )
        # subscriptions = IncrementalStripeStream(
        #     name="subscriptions",
        #     path="subscriptions",
        #     use_cache=True,
        #     extra_request_params={"status": "all"},
        #     event_types=[
        #         "customer.subscription.created",
        #         "customer.subscription.paused",
        #         "customer.subscription.pending_update_applied",
        #         "customer.subscription.pending_update_expired",
        #         "customer.subscription.resumed",
        #         "customer.subscription.trial_will_end",
        #         "customer.subscription.updated",
        #         "customer.subscription.deleted",
        #     ],
        #     **args,
        # )
        # subscription_items = StripeLazySubStream(
        #     name="subscription_items",
        #     path="subscription_items",
        #     extra_request_params=lambda self, *args, stream_slice, **kwargs: {"subscription": stream_slice[self.parent_id]},
        #     parent=subscriptions,
        #     use_cache=True,
        #     parent_id="subscription_id",
        #     sub_items_attr="items",
        #     **args,
        # )
        streams = [
            bank_accounts,
            # customers,
            #invoice_line_items,
            #subscription_items,
        ]
        if self._use_concurrent_cdk:
            state_manager = ConnectorStateManager(stream_instance_map={s.name: s for s in streams}, state=self._state)
            return [
                StreamFacade.create_from_stream(
                    stream,
                    self,
                    entrypoint_logger,
                    4,
                    state_manager.get_stream_state(stream.name, stream.namespace),
                    ConcurrentCursor(
                        stream.name,
                        stream.namespace,
                        state_manager.get_stream_state(stream.name, stream.namespace),
                        self.message_repository,
                        state_manager,
                        CursorField(stream.cursor_field if type(stream.cursor_field) == list else [stream.cursor_field]),
                        self._get_slice_boundary_fields(stream, state_manager)
                    ) if self._is_incremental(stream) else NoopCursor(),
                ) for stream in streams
            ]
        else:
            return streams

    def _get_slice_boundary_fields(self, stream: Stream, state_manager: ConnectorStateManager):
        if isinstance(stream, UpdatedCursorIncrementalStripeLazySubStream):
            return None  # TODO validate on incremental with state
        return None if state_manager.get_stream_state(stream.name, stream.namespace) else ("created[gte]", "created[lte]")

    def _is_incremental(self, stream: Stream):
        catalog_stream = [catalog_stream for catalog_stream in self._catalog.streams if catalog_stream.stream.name == stream.name]
        if len(catalog_stream) != 1:
            raise ValueError(f"Stream {stream.name} is in catalog {len(catalog_stream)} times")
        # FIXME This seems to create duplication with AbstractSource which I'm not a big fan of
        return catalog_stream[0].sync_mode == SyncMode.incremental and stream.supports_incremental
