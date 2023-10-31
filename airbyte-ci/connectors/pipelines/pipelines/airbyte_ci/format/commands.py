#
# Copyright (c) 2023 Airbyte, Inc., all rights reserved.
#

"""
Module exposing the format command.
"""

from typing import Optional

import asyncclick as click
import dagger
from pipelines.cli.click_decorators import LazyPassDecorator, click_ignore_unused_kwargs, click_merge_args_into_context_obj
from pipelines.cli.lazy_group import LazyGroup
from pipelines.models.contexts.click_pipeline_context import ClickPipelineContext

pass_pipeline_context: LazyPassDecorator = LazyPassDecorator(ClickPipelineContext)


@click.group(
    cls=LazyGroup,
    help="Commands related to formatting.",
    lazy_subcommands={
        "check": "pipelines.airbyte_ci.format.check.commands.check",
        "fix": "pipelines.airbyte_ci.format.fix.commands.fix",
    },
    invoke_without_command=True,
)
@click_merge_args_into_context_obj
@pass_pipeline_context
@click_ignore_unused_kwargs
async def format(ctx: click.Context, pipeline_ctx: ClickPipelineContext):
    pass
