import aiofiles
import asyncio
import logging
import os
import pathlib

from aiohttp import web
from argparse import ArgumentParser
from asyncio import create_subprocess_exec, subprocess


logger = logging.getLogger(__file__)


async def archive(request):
    photos_dir = request.app['photos_dir']
    throttle_tick_time = request.app['throttle_tick_time']

    archive_hash = request.match_info['archive_hash']

    if not os.path.exists(os.path.join(photos_dir, archive_hash)):
        raise web.HTTPNotFound(text=f'404: Archive {archive_hash} does not exist.')

    response = web.StreamResponse(
        headers={
            'Content-Disposition': f'attachment; filename="{archive_hash}.zip"',
            'Content-Type': 'application/zip'
        }
    )

    await response.prepare(request)

    exec = 'zip'
    args = ['-rq', '-', archive_hash]
    process = await create_subprocess_exec(exec, *args, stdout=subprocess.PIPE, cwd=photos_dir)

    try:
        while True:
            chunk = await process.stdout.read(512000)
            logger.info(f'Sending archive chunk {archive_hash}({len(chunk)})')

            if throttle_tick_time:
                await asyncio.sleep(throttle_tick_time)

            await response.write(chunk)
            if process.stdout.at_eof():
                break
        
        await response.write_eof()
    finally:
        process.kill()
        logger.info(f'Download was interrupted.')


async def handle_index_page(request):
    async with aiofiles.open('index.html', mode='r') as index_file:
        index_contents = await index_file.read()
    return web.Response(text=index_contents, content_type='text/html')


if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true', help='Flag for verbose output')
    parser.add_argument('-t', '--throttle_tick', type=int, default=0, help='Amount of forced delay on stream response iteration')
    parser.add_argument('-p', '--photo_dir', type=pathlib.Path, default='test_photos', help='Path to photo archive directory')
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)
    if args.verbose:
        logger.setLevel(logging.INFO)

    app = web.Application()
    app['throttle_tick_time'] = args.throttle_tick
    app['photos_dir'] = args.photo_dir
    app.add_routes([
        web.get('/', handle_index_page),
        web.get('/archive/{archive_hash}/', archive),
    ])
    web.run_app(app)
