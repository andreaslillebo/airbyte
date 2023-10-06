#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#
from dataclasses import InitVar, dataclass
from typing import Any, List, Mapping, Union

import requests
from airbyte_cdk.sources.declarative.decoders.decoder import Decoder
from airbyte_cdk.sources.declarative.decoders.json_decoder import JsonDecoder
from airbyte_cdk.sources.declarative.extractors.dpath_extractor import DpathExtractor
from airbyte_cdk.sources.declarative.extractors.record_extractor import RecordExtractor
from airbyte_cdk.sources.declarative.interpolation.interpolated_string import InterpolatedString
from airbyte_cdk.sources.declarative.types import Config


@dataclass
class NullCheckedDpathExtractor(RecordExtractor):
    field_path: List[Union[InterpolatedString, str]]
    nullable_nested_field: Union[InterpolatedString, str]
    config: Config
    parameters: InitVar[Mapping[str, Any]]
    decoder: Decoder = JsonDecoder(parameters={})

    def __post_init__(self, parameters: Mapping[str, Any]):
        self._dpath_extractor = DpathExtractor(
            field_path=self.field_path,
            config=self.config,
            parameters=parameters,
            decoder=self.decoder,
        )

    def extract_records(self, response: requests.Response) -> List[Mapping[str, Any]]:
        records = self._dpath_extractor.extract_records(response)
        return [record.get(self.nullable_nested_field) or record for record in records]
