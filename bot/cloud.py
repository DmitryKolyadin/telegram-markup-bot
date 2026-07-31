"""Yandex.Cloud functions handler for the bot."""

import json
import logging
import traceback

from aiogram import Bot, Dispatcher
from .main import bot, dp

logger = logging.getLogger(__name__)


async def process_event(event, bot: Bot, dp: Dispatcher):
    """
    Converting an Yandex.Cloud functions event to an update and
    handling tha update.
    """

    update = json.loads(event["body"])
    logger.info("Handling update_id=%s", update.get("update_id"))

    await dp.feed_raw_update(bot, update)

    logger.info("Finished update_id=%s", update.get("update_id"))


async def handler(event, context):
    """Main function for Yandex.Cloud functions."""
    logger.info("handler invoked, request_id=%s", getattr(context, "request_id", None))

    try:
        await process_event(event, bot, dp)

    except BaseException as err:
        logger.exception("Error while processing event: %s", err)
        print(err)
        print(traceback.format_exc())
    return {"statusCode": 200}