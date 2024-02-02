import discord
import rcon.exceptions
from discord import option
from discord.ext import commands, tasks
import slash_commands
import docker
import os
from dotenv import load_dotenv
from rcon.source import Client
import re
import json
from collections import defaultdict

import subprocess


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


container_types = {
    "ark-server": {
        "short_name": "ASA",  # "Ark Survival Ascended"
        "long_name": "Ark Survival Ascended Dedicated Server",
        "port": SERVER_PORT,
        "rcon_password": RCON_PASSWORD,
        "players_command": "listplayers"
    },
    "palworld-dedicated-server": {
        "short_name": "Pal",  # "Palworld"
        "long_name": "Palworld Dedicated Server",  # "Palworld"
        "port": PALWORLD_PORT,
        "rcon_password": PALWORLD_RCON_PASSWORD,
        "players_command": "ShowPlayers"
    },
    "satisfactory-server-coop": {
        "short_name": "Satisfactory",
        "long_name": "Satisfactory Dedicated Server",
        "port": None,
        "rcon_password": None,
        "players_command": None
    }
}


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
    try:
        if port is None or rcon_password is None or command is None:
            return 'No', None
        with Client(SERVER_IP, port, passwd=rcon_password, timeout=4) as client:
            response = client.run(command)
        response = response.strip()
        if response.startswith('No Players Connected'):
            print('No players connected')
            player_count = 0
            return False, player_count
        else:
            player_count = len(response.split('\n'))
            print(f'{player_count} players connected')
            return response, player_count
    except rcon.exceptions.SessionTimeout:
        print('Socket timed out')
        return 'No', 0
    except Exception as e:
        print(f'An error occurred: {e}')
        return 'No', 0


def is_container_running(container_name):
    container = docker_client.containers.get(container_name)
    if container.status == 'running':
        print(container_name + ' is running')
        return True
    else:
        print(container_name + ' is not running')
        return False


def palworld_command(command):
    # Specify the path to your Docker Compose file
    compose_file_path = "/home/alexk/Desktop/palworld/docker-compose.yml"

    # Define your Docker Compose command
    docker_compose_command = [
        "docker", "compose", "-f", compose_file_path,
        "run", "--rm", "rcon", command
    ]
    try:
        # Run the Docker Compose command and capture the output
        result = subprocess.run(docker_compose_command, check=True, stdout=subprocess.PIPE, text=True)

        # Access the output through the stdout attribute and store it in the 'response' variable
        response = result.stdout.strip()
        return response
    except subprocess.CalledProcessError as e:
        # Handle errors if the command fails
        print(f"Error: {e}")


def palworld_online_players(response):
    if response.endswith('name,playeruid,steamid'):
        print('No players connected')
        player_count = 0
        return False, player_count
    else:
        # Remove string "name,playeruid,steamid" and new line from beginning of response
        response = response[23:]
        # Remove anything after the first coma from each line
        response = re.sub(r',.*', '', response)
        player_count = len(response.split('\n'))
        print(f'{player_count} players connected')
        print(response)
        return response, player_count


# Task that runs every 5 minutes
@tasks.loop(minutes=5)
async def update_rich_presence():
    # Run for loop to check if any servers in container_types are running
    for i in container_types:
        # If any server is running, check if anyone is online
        if is_container_running(i):
            if i == 'palworld-dedicated-server':
                response = palworld_command('ShowPlayers')
                response, player_count = palworld_online_players(response)
            else:
                response, player_count = is_anyone_online(container_types[i]['port'], container_types[i]['rcon_password'], container_types[i]['players_command'])
            if not response:
                await bot.change_presence(activity=discord.Game(name=f'{container_types[i]["short_name"]}: Nobody online!'))
                print(f'{container_types[i]["short_name"]}: No one online')
            else:
                if player_count is None:
                    await bot.change_presence(activity=discord.Game(name=f'{container_types[i]["short_name"]}'))
                    print(f'{container_types[i]["short_name"]}: Server online')
                elif player_count == 1:
                    await bot.change_presence(activity=discord.Game(name=f'{container_types[i]["short_name"]}: {player_count} player online!'))
                else:
                    await bot.change_presence(activity=discord.Game(name=f'{container_types[i]["short_name"]}: {player_count} players online!'))
                print(f'{container_types[i]["short_name"]}: Someone online')
            break
    # if none of the containers are running, set the bots status to "No servers running"
    else:
        await bot.change_presence(activity=discord.Game(name='No servers running.'))
        print('No servers running')


# Function to return container_types for autocomplete
async def container_types_autocomplete(ctx: discord.AutocompleteContext):
    return (name for name in container_types if name.startswith(ctx.value.lower()))


@bot.event
async def on_connect():
    if bot.auto_sync_commands:
        await bot.sync_commands()
    update_rich_presence.start()
    print(f'Logged in as {bot.user.name}')


# Load the slash commands
slash_commands.setup(bot)
# Run the bot
bot.run(TOKEN)
