import main
import discord
from discord import option
from discord.ext import commands

intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)


# Slash commands
# Check the status of the server and return the number of players online and names
@bot.slash_command(description='Check the status of the server')
async def check_status(ctx):
    # Update the rich presence
    await main.update_rich_presence()
    # Run for loop to check if any servers in container_types are running
    for i in main.container_types:
        # If any server is running, check if anyone is online
        if main.is_container_running(i):
            if i == 'palworld-dedicated-server':
                response = main.palworld_command('ShowPlayers')
                response, player_count = main.palworld_online_players(response)
                info = main.palworld_command('info')
                await ctx.send(info)
            else:
                response, player_count = main.is_anyone_online(main.container_types[i]['port'], main.container_types[i]['rcon_password'], main.container_types[i]['players_command'])
            if not response:
                await ctx.respond(f'{main.container_types[i]["long_name"]}: Nobody online!')
                print(f'{main.container_types[i]["long_name"]}: No one online')
            else:
                # If no player count is returned, set the bots status to the server name
                if player_count is None:
                    await ctx.respond(f'{main.container_types[i]["long_name"]}: Server online')
                    print(f'{main.container_types[i]["long_name"]}: Server online')
                # If player count is 1, respond with "1 player online" and the players name
                elif player_count == 1:
                    await ctx.respond(f'{main.container_types[i]["long_name"]}: {player_count} player online!\n' + response)
                else:
                    await ctx.respond(f'{main.container_types[i]["long_name"]}: {player_count} players online!\n' + response)
                print(f'{main.container_types[i]["long_name"]}: Someone online')
            break
    else:
        await ctx.respond('No servers running')
        print('No servers running')


@bot.slash_command(description='Get player death stats!')
async def player_stats(ctx):
    # Parse the log file
    dino_message, player_message = main.parse_log_file()
    await ctx.respond(player_message)


@bot.slash_command(description='Get tamed dino stats!')
async def dino_stats(ctx):
    # Parse the log file
    dino_message, player_message = main.parse_log_file()
    await ctx.respond(dino_message)


@bot.slash_command(description='Start one of the servers!')
@option(
    "server_type",
    description="Choose a server to start",
    autocomplete=main.container_types_autocomplete,
    required=True
)
async def start_server(ctx, server_type: str):
    # Check if server is running
    container = main.docker_client.containers.get(server_type)
    # Go through all server types and check if any are running
    for i in main.container_types:
        # if any server is running respond with the server type
        if main.is_container_running(i):
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
    autocomplete=main.container_types_autocomplete,
    required=True
)
async def stop_server(ctx, server_type: str):
    container = main.docker_client.containers.get(server_type)
    # Check if server is running
    if not main.is_container_running(server_type):
        await ctx.respond('Server is not running')
    else:
        if main.is_container_running(server_type):
            if server_type == 'palworld-dedicated-server':
                response = main.palworld_command('ShowPlayers')
                response, player_count = main.palworld_online_players(response)
            else:
                response, player_count = main.is_anyone_online(main.container_types[server_type]['port'], main.container_types[server_type]['rcon_password'], main.container_types[server_type]['players_command'])
            if not response:
                await ctx.respond('No one is online, stopping server')
                print('No one is online, stopping server')
                container.stop()
            else:
                # If player count is None, respond with "Server is running, can't check for players"
                if player_count is None:
                    await ctx.respond("Satisfactory server running, can't check for players")
                    print("Satisfactory server running, can't check for players")
                # If player count is >0 respond with "Someone is online"
                else:
                    await ctx.respond('Someone is online!  Run "/kill_server" to stop the server anyway.  :D')
                    await ctx.send(f'Users online:\n' + response)


@bot.slash_command(description='Kill a server')
@option(
    "server_type",
    description="Choose a server to kill",
    autocomplete=main.container_types_autocomplete,
    required=True
)
async def kill_server(ctx, server_type: str):
    container = main.docker_client.containers.get(server_type)
    # Check if server is running
    if not main.is_container_running(server_type):
        await ctx.respond('Server is not running')
    else:
        if main.is_container_running(server_type):
            if server_type == 'palworld-dedicated-server':
                response = main.palworld_command('ShowPlayers')
                response, player_count = main.palworld_online_players(response)
            else:
                response, player_count = main.is_anyone_online(main.container_types[server_type]['port'], main.container_types[server_type]['rcon_password'], main.container_types[server_type]['players_command'])
            if not response:
                await ctx.respond('No one is online, stopping server')
                print('No one is online, stopping server')
                container.stop()
            else:
                # If player count is None, respond with "Server is running, can't check for players"
                if player_count is None:
                    await ctx.respond("Satisfactory server running, can't check for players, but still killing it")
                    print("Satisfactory server running, can't check for players")
                    container.stop()
                # If player count is >0 respond with "Someone is online"
                else:
                    await ctx.respond('Someone is online!  Killing the server anyway! :D')
                    await ctx.send(f'Suck it:\n' + response)
                    container.stop()
