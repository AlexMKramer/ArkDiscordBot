import discord
from discord import option
from discord.ext import commands, tasks
import docker
import os
from dotenv import load_dotenv
from rcon.source import Client
import re
import json
from collections import defaultdict

load_dotenv()
TOKEN = os.getenv('BOT_TOKEN')
SERVER_IP = os.getenv('SERVER_IP')
SERVER_PORT = int(os.getenv('SERVER_PORT'))
PALWORLD_PORT = int(os.getenv('PALWORLD_PORT'))
RCON_PASSWORD = os.getenv('RCON_PASSWORD')
PALWORLD_RCON_PASSWORD = os.getenv('PALWORLD_RCON_PASSWORD')
TRIBE_LOG_PATH = os.getenv('TRIBE_LOG_PATH')

# Docker client setup
docker_client = docker.from_env()


# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)
bot.auto_sync_commands = True


server_types = [
    "ark-server",
    "satisfactory-server-coop",
    "palworld-dedicated-server"
]


# Function to return server_types for autocomplete
async def server_types_autocomplete(ctx: discord.AutocompleteContext):
    return (name for name in server_types if name.startswith(ctx.value.lower()))


def reformat_file(file_path, output_path):
    try:
        # Try to open the file with utf-8 encoding
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except UnicodeDecodeError:
        # If utf-8 encoding fails, try reading the file as binary
        with open(file_path, 'rb') as file:
            content = file.read().decode('latin1')  # Trying latin1 encoding which might decode without errors

    # Regular expression to match the timestamps and events
    pattern = re.compile(r'(Day \d+, \d{2}:\d{2}:\d{2}): <RichColor[^>]+>([^<]+)</>')

    # Find all matches in the file content
    matches = pattern.findall(content)

    # Write the formatted content to the output file
    with open(output_path, 'w', encoding='utf-8') as output_file:
        for match in matches:
            output_file.write(f'{match[0]}: {match[1].strip()}\n')


# Function to load data from a JSON file
def load_data_from_json(filename):
    try:
        with open(filename, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}


# Function to compare data and print the changes
def compare_data(original_data, new_data, data_type):
    message = ""
    no_changes = True  # Flag to detect if any changes occurred

    for key, value in new_data.items():
        if key in original_data:
            if value != original_data[key]:
                no_changes = False  # Changes detected, update flag
                change = value - original_data[key]
                if data_type == 'player_deaths' and change > 0:
                    print(f"{key} died {change} more time(s)!")
                    message += f"{key} died {change} more time(s)! Shocking!\n"

                elif value > original_data[key]:
                    print(f"Change in {key}: was {original_data[key]}, now {value}")
                    message += f"We gained {change} more {key}s!\n"

                elif value < original_data[key]:
                    print(f"Change in {key}: was {original_data[key]}, now {value}")
                    message += f"We lost {change} {key}s. :(\n"
        else:
            no_changes = False  # New key detected, update flag
            if data_type == 'player_deaths':
                print(f"{key} died {value} time(s)!")
                message += f"{key} joined and died {value} time(s)!\n"
            else:
                print(f"{value} {key}s added to the army!")
                message += f"{value} {key}s added to the army!\n"

    for key in original_data.keys() - new_data.keys():
        no_changes = False  # Key removal detected, update flag
        print(f"{key} was removed.")
        message += f"We lost all of our {key}s. :(\n"

    if no_changes:
        # If no changes, print all current values from new_data
        message = "No changes detected.\nCurrent stats:\n"
        for key, value in new_data.items():
            message += f"{key}: {value}\n"
    return message


# Parse the log file
def parse_log_file():
    # Initialize counters
    tamed_dinos = defaultdict(int)
    player_deaths = defaultdict(int)
    try:
        reformat_file(TRIBE_LOG_PATH, 'tribe_log.txt')
        with open('tribe_log.txt', 'r') as file:
            for line in file:
                if "Tamed" in line:
                    dino_type = line[line.find("(")+1:line.find(")")]
                    tamed_dinos[dino_type] += 1
                elif "Tribemember" in line and "was killed" in line:
                    player_name = line.split("Tribemember")[1].split(" -")[0].strip()
                    player_deaths[player_name] += 1
                elif "Your" in line and "was killed" in line:
                    dino_type = line[line.find("(")+1:line.find(")")]
                    tamed_dinos[dino_type] -= 1
    except FileNotFoundError:
        print("The log file was not found.")
    except Exception as e:
        print(f"An error occurred: {e}")

    # Load original data from JSON
    original_data = load_data_from_json('data.json')

    # Compare new data with original data
    dino_message = compare_data(original_data.get('tamed_dinos', {}), tamed_dinos, 'tamed_dinos')
    player_message = compare_data(original_data.get('player_deaths', {}), player_deaths, 'player_deaths')

    # Update JSON file with new data
    new_data = {
        'tamed_dinos': tamed_dinos,
        'player_deaths': player_deaths
    }

    with open('data.json', 'w') as file:
        json.dump(new_data, file, indent=4)

    return dino_message, player_message


def is_anyone_online(port, rcon_password, command):
    with Client(SERVER_IP, port, passwd=rcon_password) as client:
        response = client.run(command)
    response = response.strip()
    if response.startswith('No Players Connected'):
        response = 'No'
        player_count = 0
        return response, player_count
    elif response.endswith('name,playeruid,steamid'):
        response = 'No'
        player_count = 0
        return response, player_count
    else:
        player_count = len(response.split('\n'))
        return response, player_count


def is_container_running(container_name):
    container = docker_client.containers.get(container_name)
    if container.status == 'running':
        return True
    else:
        return False


# Task that runs every 5 minutes
@tasks.loop(minutes=5)
async def update_rich_presence():
    if is_container_running('ark-server'):
        response, player_count = is_anyone_online(SERVER_PORT, RCON_PASSWORD, 'listplayers')
        if response == 'No':
            await bot.change_presence(activity=discord.Game(name='ASA: Nobody online!'))
        else:
            if player_count == 1:
                await bot.change_presence(activity=discord.Game(name=f'ASA: {player_count} player online!'))
            else:
                await bot.change_presence(activity=discord.Game(name=f'ASA: {player_count} players online!'))
    elif is_container_running('palworld-dedicated-server'):
        response, player_count = is_anyone_online(PALWORLD_PORT, PALWORLD_RCON_PASSWORD, 'ShowPlayers')
        if response == 'No':
            await bot.change_presence(activity=discord.Game(name='Pal: Nobody online!'))
        else:
            if player_count == 1:
                await bot.change_presence(activity=discord.Game(name=f'Pal: {player_count} player online!'))
            else:
                await bot.change_presence(activity=discord.Game(name=f'Pal: {player_count} players online!'))
    elif is_container_running('satisfactory-server-coop'):
        await bot.change_presence(activity=discord.Game(name='Satisfactory'))
    else:
        await bot.change_presence(activity=discord.Game(name='Servers offline'))


@bot.event
async def on_connect():
    if bot.auto_sync_commands:
        await bot.sync_commands()
    update_rich_presence.start()
    print(f'Logged in as {bot.user.name}')


@bot.slash_command(description='Check the status of the server.')
async def check_status(ctx):
    if is_container_running('ark-server'):
        await ctx.respond('Ark server is online!')
        # Check if anyone is online
        response, player_count = is_anyone_online(SERVER_PORT, RCON_PASSWORD, 'listplayers')
        if response == 'No':
            await ctx.send('No one is online.  :(')
        else:
            if player_count == 1:
                await ctx.send(f'There is {player_count} player online!  :D\n' + response)
            else:
                await ctx.send(f'There are {player_count} players online!  :D\n' + response)
        return
    elif is_container_running('palworld-dedicated-server'):
        await ctx.respond('Palworld server is online!')
        # Check if anyone is online
        response, player_count = is_anyone_online(PALWORLD_PORT, PALWORLD_RCON_PASSWORD, 'ShowPlayers')
        if response == 'No':
            await ctx.send('No one is online.  :(')
        else:
            if player_count == 1:
                await ctx.send(f'There is {player_count} player online!  :D\n' + response)
            else:
                await ctx.send(f'There are {player_count} players online!  :D\n' + response)
        return
    elif is_container_running('satisfactory-server-coop'):
        await ctx.respond('Satisfactory server is online!')
    else:
        await ctx.respond('Server is offline.  :(  Run "/start_server" to start it up!')


@bot.slash_command(description='Get player death stats!')
async def player_stats(ctx):
    # Parse the log file
    dino_message, player_message = parse_log_file()
    await ctx.respond(player_message)


@bot.slash_command(description='Get tamed dino stats!')
async def dino_stats(ctx):
    # Parse the log file
    dino_message, player_message = parse_log_file()
    await ctx.respond(dino_message)


@bot.slash_command(description='Start one of the servers!')
@option(
    "server_type",
    description="Choose a server to start",
    autocomplete=server_types_autocomplete,
    required=True
)
async def start_server(ctx, server_type: str):
    # Check if server is running
    container = docker_client.containers.get(server_type)
    # Go through all server types and check if any are running
    for i in server_types:
        # if any server is running respond with the server type
        if is_container_running(i):
            # If the server that is running is the same as the one that was requested, tell the user its already running
            if i == server_type:
                await ctx.respond(f'{i} is already running')
                return
            # If the server that is running is not the same as the one that was requested, tell the user to stop the
            # running server first
            else:
                await ctx.respond(f'{i} is already running.  Stop it first!')
                return
    # If no servers are running, start the server
    container.start()
    await ctx.respond(f'Starting {server_type}...')
    return


@bot.slash_command(description='Stop a server')
@option(
    "server_type",
    description="Choose a server to stop",
    autocomplete=server_types_autocomplete,
    required=True
)
async def stop_server(ctx, server_type: str):
    container = docker_client.containers.get(server_type)
    # Check if server is running
    if not is_container_running(server_type):
        await ctx.respond('Server is not running')
        return
    else:
        if server_type == 'ark-server':
            # Check if anyone is online
            response, player_count = is_anyone_online()
            if response == 'No':
                await ctx.respond('No one is online, stopping server')
                container.stop()
            else:
                await ctx.respond('Someone is online!  Run "/kill_server" to stop the server anyway.  :D')
                await ctx.send(f'Users online:\n' + response)
        else:
            await ctx.respond('Stopping server...')
            container.stop()
        return


@bot.slash_command(description='Kill a server')
@option(
    "server_type",
    description="Choose a server to stop",
    autocomplete=server_types_autocomplete,
    required=True
)
async def kill_server(ctx, server_type: str):
    container = docker_client.containers.get(server_type)
    # Check if server is running
    if not is_container_running(server_type):
        await ctx.respond('Server is not running')
        return
    else:
        if server_type == 'ark-server':
            # Check if anyone is online
            response = is_anyone_online()
            if response == 'No':
                await ctx.respond('No one is online, stopping server')
                container.stop()
            else:
                await ctx.respond('Someone is online, but killing the server anyway.  :D')
                await ctx.send('Booting\n' + response)
                container.stop()
        else:
            await ctx.respond('Killing server...')
            container.stop()
        return

# Run the bot
bot.run(TOKEN)
