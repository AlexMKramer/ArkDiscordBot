import discord
from discord.ext import commands
import docker
import os
from dotenv import load_dotenv
from rcon.source import Client

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
SERVER_IP = os.getenv('SERVER_IP')
SERVER_PORT = int(os.getenv('SERVER_PORT'))
RCON_PASSWORD = os.getenv('RCON_PASSWORD')

# Docker client setup
docker_client = docker.from_env()


# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)
bot.auto_sync_commands = True


def is_anyone_online():
    with Client(SERVER_IP, SERVER_PORT, passwd=RCON_PASSWORD) as client:
        response = client.run('listPlayers')
    response = response.strip()
    if response == 'No Players Connected':
        return 'No'
    else:
        return response


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
        # Check if anyone is online
        response = is_anyone_online()
        if response == 'No':
            await ctx.respond('No one is online.  :(')
        else:
            await ctx.respond('Someone is online!  :D')
            await ctx.respond(response)
        return
    else:
        await ctx.respond('Server is offline.  :(  Run "/start_server" to start it up!')


@bot.slash_command(description='Start the ARK server')
async def start_server(ctx):
    # Check if server is running
    container = docker_client.containers.get('ark-server')
    if container.status == 'running':
        await ctx.respond('Server is already running')
        return
    else:
        # Start the server
        container.start()
        await ctx.respond('Starting ARK server...')


@bot.slash_command(description='Stop the ARK server')
async def stop_server(ctx):
    container = docker_client.containers.get('ark-server')
    # Check if server is running
    if container.status != 'running':
        await ctx.respond('Server is not running')
        return
    else:
        # Check if anyone is online
        response = is_anyone_online()
        if response == 'No':
            await ctx.respond('No one is online, stopping server')
            container.stop()
        else:
            await ctx.respond('Someone is online!  Run "/kill_server" to stop the server anyway.  :D')
            await ctx.respond(response)
        return


@bot.slash_command(description='Stop the ARK server')
async def kill_server(ctx):
    container = docker_client.containers.get('ark-server')
    # Check if server is running
    if container.status != 'running':
        await ctx.respond('Server is not running')
        return
    else:
        # Check if anyone is online
        response = is_anyone_online()
        if response == 'No':
            await ctx.respond('No one is online, stopping server')
            container.stop()
        else:
            await ctx.respond('Someone is online, but killing the server anyway.  :D')
            await ctx.respond('Booting' + response)
            container.stop()
        return

# Run the bot
bot.run(TOKEN)
