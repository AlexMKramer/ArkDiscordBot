import discord
from discord.ext import commands
from rcon.source import Client
import docker
import os
from dotenv import load_dotenv

load_dotenv()
SERVER_IP = os.getenv('SERVER_IP')
SERVER_PORT = int(os.getenv('SERVER_PORT'))
RCON_PASSWORD = os.getenv('RCON_PASSWORD')
TOKEN = os.getenv('BOT_TOKEN')
# Bot setup
bot = commands.Bot(command_prefix="!")

# Docker client setup
docker_client = docker.from_env()


@bot.command()
async def check_status(ctx):
    try:
        with Client(SERVER_IP, SERVER_PORT, passwd=RCON_PASSWORD) as client:
            response = client.run('admincheat', 'listplayers')
        await ctx.send(f'Server status: {response}')
    except Exception as e:
        await ctx.send(f'Error checking server status: {e}')


@bot.command()
async def start_server(ctx):
    # Check if server is running
    container = docker_client.containers.get('ark-server')
    if container.status == 'running':
        await ctx.send('Server is already running')
        return
    else:
        docker_client.containers.run('ark-server', detach=True)
        await ctx.send('Starting ARK server...')

@bot.command()
async def stop_server(ctx):
    container = docker_client.containers.get('ark-server')
    # Check if server is running
    if container.status != 'running':
        await ctx.send('Server is not running')
        return
    else:
        container.stop()
        await ctx.send('Stopping ARK server...')

# Run the bot
bot.run(TOKEN)
