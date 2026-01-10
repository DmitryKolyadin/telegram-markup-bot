"""Yandex.Cloud functions handler for the bot."""

import json
import os
import traceback

from aiogram import Bot, Dispatcher
from .main import bot, dp


async def process_event(event, bot: Bot, dp: Dispatcher):
    """
    Converting an Yandex.Cloud functions event to an update and
    handling tha update.
    """

    update = json.loads(event["body"])

    await dp.feed_raw_update(bot, update)


async def handler(event, context):
    """Main function for Yandex.Cloud functions."""

    try:
        await process_event(event, bot, dp)

    except BaseException as err:
        print(err)
        print(traceback.format_exc())
    return {"statusCode": 200}