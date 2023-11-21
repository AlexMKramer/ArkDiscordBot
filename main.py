import discord
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
RCON_PASSWORD = os.getenv('RCON_PASSWORD')
TRIBE_LOG_PATH = os.getenv('TRIBE_LOG_PATH')

# Docker client setup
docker_client = docker.from_env()


# Bot setup
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)
bot.auto_sync_commands = True


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


def is_anyone_online():
    with Client(SERVER_IP, SERVER_PORT, passwd=RCON_PASSWORD) as client:
        response = client.run('listPlayers')
    response = response.strip()
    if str.startswith(response, 'No Players Connected'):
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
        response, player_count = is_anyone_online()
        if response == 'No':
            await bot.change_presence(activity=discord.Game(name='ASA: Nobody online!'))
        else:
            if player_count == 1:
                await bot.change_presence(activity=discord.Game(name=f'ASA: {player_count} player online!'))
            else:
                await bot.change_presence(activity=discord.Game(name=f'ASA: {player_count} players online!'))
    else:
        await bot.change_presence(activity=discord.Game(name='ASA: Server offline'))


@bot.event
async def on_connect():
    if bot.auto_sync_commands:
        await bot.sync_commands()
    update_rich_presence.start()
    print(f'Logged in as {bot.user.name}')


@bot.slash_command(description='Check the status of the ARK server')
async def check_status(ctx):
    if is_container_running('ark-server'):
        await ctx.respond('Server is online!')
        # Check if anyone is online
        response, player_count = is_anyone_online()
        if response == 'No':
            await ctx.send('No one is online.  :(')
        else:
            if player_count == 1:
                await ctx.send(f'There is {player_count} player online!  :D\n' + response)
            else:
                await ctx.send(f'There are {player_count} players online!  :D\n' + response)
        return
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
    if not is_container_running('ark-server'):
        await ctx.respond('Server is not running')
        return
    else:
        # Check if anyone is online
        response, player_count = is_anyone_online()
        if response == 'No':
            await ctx.respond('No one is online, stopping server')
            container.stop()
        else:
            await ctx.respond('Someone is online!  Run "/kill_server" to stop the server anyway.  :D')
            await ctx.send(f'Users online:\n' + response)
        return


@bot.slash_command(description='Stop the ARK server')
async def kill_server(ctx):
    container = docker_client.containers.get('ark-server')
    # Check if server is running
    if not is_container_running('ark-server'):
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
            await ctx.send('Booting\n' + response)
            container.stop()
        return

# Run the bot
bot.run(TOKEN)
