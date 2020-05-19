# tgfilestream - A Telegram bot that can stream Telegram files to users over HTTP.
# Copyright (C) 2019 Tulir Asokan
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
import asyncio
import sys

from aiohttp import web
from telethon import functions
from tgfilestream.telegram import client, transfer
from tgfilestream.web_routes import routes
from tgfilestream.config import host, port, link_prefix, allowed_user, bot_token, debug, show_index, keep_awake, keep_awake_url
from tgfilestream.log import log
from apscheduler.schedulers.background import BackgroundScheduler
import requests

server = web.Application()
server.add_routes(routes)
runner = web.AppRunner(server)

loop = asyncio.get_event_loop()


async def start() -> None:
    await client.start(bot_token=bot_token)

    config = await client(functions.help.GetConfigRequest())
    for option in config.dc_options:
        if option.ip_address == client.session.server_address:
            if client.session.dc_id != option.id:
                log.warning(f"Fixed DC ID in session from {client.session.dc_id} to {option.id}")
            client.session.set_dc(option.id, option.ip_address, option.port)
            client.session.save()
            break
    transfer.post_init()
    await runner.setup()
    await web.TCPSite(runner, host, port).start()


async def stop() -> None:
    await runner.cleanup()
    await client.disconnect()


def keep_wake():
    resp = requests.get(keep_awake_url)
    log.debug('keep_wake', 'get', str(keep_awake_url), 'result', resp.status_code, resp.content)


try:
    loop.run_until_complete(start())
except Exception:
    log.fatal('Failed to initialize', exc_info=True)
    sys.exit(2)

log.info('Initialization complete')
log.debug(f'Listening at http://{host}:{port}')
log.debug(f'Public URL prefix is {link_prefix}')
log.debug(f'allowed user ids {allowed_user}')
log.debug(f'Debug={debug},show_index={show_index}')

scheduler = BackgroundScheduler()

try:
    if keep_awake:
        scheduler.add_job(keep_wake, 'interval', seconds=120)
        scheduler.start()
    loop.run_forever()
except KeyboardInterrupt:
    if keep_awake:
        scheduler.shutdown()
    loop.run_until_complete(stop())
except Exception:
    log.fatal('Fatal error in event loop', exc_info=True)
    if keep_awake:
        scheduler.shutdown()
    sys.exit(3)
