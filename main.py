import discord
from discord.ext import commands
import docker
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')

# Docker client setup
docker_client = docker.from_env()


# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)
bot.auto_sync_commands = True


@bot.event
async def on_connect():
    if bot.auto_sync_commands:
        await bot.sync_commands()
    print(f'Logged in as {bot.user.name}')


@bot.slash_command(description='Check the status of the ARK server')
async def check_status(ctx):
    container = docker_client.containers.get('ark-server')
    if container.status == 'running':
        await ctx.respond('Server is online!')
        return
    else:
        await ctx.respond('Server is offline.  :(  Run /start_server to start it up!')


@bot.slash_command(description='Start the ARK server')
async def start_server(ctx):
    # Check if server is running
    container = docker_client.containers.get('ark-server')
    if container.status == 'running':
        await ctx.respond('Server is already running')
        return
    else:
        # Start the server
        container.start(detached=True)
        await ctx.respond('Starting ARK server...')


@bot.slash_command(description='Stop the ARK server')
async def stop_server(ctx):
    container = docker_client.containers.get('ark-server')
    # Check if server is running
    if container.status != 'running':
        await ctx.respond('Server is not running')
        return
    else:
        await ctx.respond('Stopping ARK server...')
        container.stop()

# Run the bot
bot.run(TOKEN)
