#
# Copyright (c) 2022 Airbyte, Inc., all rights reserved.
#

from typing import Optional

import requests
from airbyte_cdk.sources.declarative.requesters.retriers.backoff_strategy import BackoffStrategy


class ExponentialBackoffStrategy(BackoffStrategy):
    def __init__(self, factor: float = 5):
        self._factor = factor

    def backoff(self, response: requests.Response, attempt_count: int) -> Optional[float]:
        return self._factor * 2**attempt_count
