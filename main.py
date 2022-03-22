from datetime import datetime, timedelta
from os import listdir
from os.path import exists
from os import remove as delete_file
import json
import asyncio
import re
import random
import functools

import discord 

from client import client
import tank
from common import call_member, mention_to_id, get_user_image, load_and_send_board, namer

"""
Todo:
Make haunting have setting for giving hearts instead of negating them.
Make setting for threshold haunts instead of most haunts

can time_delta be bigger than time_gap now?
That'd be neat
"""

help_message_game = """```
.help game
Displays this message

.move direction
Moves in one of the 8 cardinal directions.
> N | S | E | W | NW | NE | SW | SE
> U | D | L | R | UL | UR | DL | DR
> numpad direction

.attack <@player>
attacks a player in range

.giveap <user#0000>
gives AP to a player in range

.givehp <@player>
gives HP to a player in range

.push <@player> <direction>
pushes a targeted player

.haunt <@player>
If you are dead, mark a player for not getting AP

.unhaunt
Remove your haunt target

.heal
For 3 AP, heals you

.upgrade
For 3 AP, grows your range

.info
DMs game info, currently just your AP and range

.skip
If skip mode is enabled, marks you for skipping your turn if you still have AP.

.list
list players currently in the game

.gameinfo
Sends game info (like round time)

.whois <position>
Returns the player at the position 'position'

.whereis <@player>
Returns the position of mentioned player

.board [-r] [-n]
View the board
If "-r" is specified, your range will be highlighted
If "-n" is specified, players' names will be written on the board

.DELETE
Case sensitive
Stops and removes the current game running. Can only be used by the person who started the game or a server admin.
There is no warning.
```"""

help_message_main = """```
.help
Displays this message

.instructions
links how to play the game

.invite
Give the invite to the bot and server.

.create
If no games are running, make a new one
Creates a basic game, with points every 24 hours.

.create [-s] [-a 56m | 2h | 180s] [-t 24h | 12h | 30m] [-r radius] [-d density] [-q queue]
If no games are running, make a new one
if "-s" is specified, then when each player has 0 AP or has opped to skip, the remaining time will be fast-forwarded.
time and unit are the length of the time between AP gains, if unspecified, 24hours is used

-a specifies how long a round should last

-t Specifies how much time should seperate all the players's AP gains from the start of the round

-r sets the default radius of all spawning players [default 2]

-d sets the number of spaces free to the number of players, default is 4. 2 for half, 8 for double.

-q sets the order of how players get AP [default 1]
    1 = all players in a random order
    2 = Tetris Style, all players (twice) in a random order.
    3+ = Tetris Style, all players (multiple times) in a random order.

.join
Joins a game before it starts.

.start
(Game creator) Starts a game running

.selectgame
(DMs) Lists the games you are in

.selectgame <num>
(DMs) Chooses the game that DM commands will run for

.help game
Shows the help messgae for in-game commands
```"""

help_message_instructions = """```
TRUE COMBAT
Survive to the end!

RULES
* All players start at a random location on the grid, and have 3 hearts and 0 Action Points.
* Every 24 hours, everyone will receive 1 Action Point (AP).
* At any time you like, you can do one of the four following actions:
    1. Move to an adjacent, unoccupied square (1 AP)
    2. Shoot someone who is within your range (1 AP). Shooting someone removes 1 heart from their health.
    3. Add a heart (3 AP)
    4. Upgrade your range (3 AP)
* At the start of the game, everyone has a range of 2. That is, they can shoot or trade with somehow within 2 squares of them. Upgrading your shooting range increases this by 1 square each time.
* If a player is reduced to 0 hearts, then they are dead. Any action points the dead player had are transferred to the player who killed them. Dead players remain on the board and not removed.
* Players are able to send gifts of hearts or actions points to any player currently within their range.
* Dead players can have a heart sent to them. This will revive that player who will have 1 heart and 0 AP.

ADDITIONAL NOTES
* Dead players form a jury. Each day they vote, and whoever received most votes will be 'haunted', and not revive any AP for that day.
* Once a day, at a random time, a hear will spawn on the field. The first player to move into the square containing the heart will revive an additional heart.
* Action points are secret! Probably a good idea to try and hide how many you have.
* You can't win this game without making some friends and stabbing some backs. Probably.```"""

#assert(len(help_message_game) < 2000)
#assert(len(help_message_main) < 2000)
#assert(len(help_message_instructions) < 2000)


games = {}
users = {}

def save_users():
    global users
    usersfile = open('./users.json', 'w')
    usersfile.write(json.dumps(users))
    usersfile.close()

check_index = 0
async def day_loop():
    """
    Check if the time has passed on a game to give it more AP.

    player_next_hearts starts at empty, and requeue() appends every player, living or dead, and a time offset for them to get
    hearts. It is done this way so that it can be loaded with the same player more than once, and so restarting the code will
    not double give or skip giving players AP.

    I think it's been cleaned up a good amount.
    """
    global games
    global check_index
    while True:
        await asyncio.sleep(3) #don't check faster than every 3 seconds
        check_index = (check_index + 1) % len(games)
        channelID, game = list(games.items())[check_index]

        if game.test_hourly_AP():
            if not client.get_channel(channelID):
                print("BAD: ", channelID) #I think this only comes up if the channel is deleted but somehow not the game?
                continue                  #I think this shouldn't ever come up anymore?

            game.give_hourly_AP_onbeat()
            haunted_player = game.haunted_player()

            print("time", datetime.now(), channelID, haunted_player)
            game.requeue()
            print("requeue", game.player_next_hearts)
            for playerid, timedelta in game.player_next_hearts:
                client.loop.call_later(timedelta, asyncio.create_task, call_member(channelID, haunted_player, game, playerid, timedelta))

loop = True
@client.event
async def on_ready():
    global games
    global users
    global loop

    if exists('./users.json'):
        usersfile = open('./users.json', 'r')
        users = json.loads(usersfile.read())
        usersfile.close()
    else:
        save_users()

    if loop:
        loop = False
        for filename in listdir("./saves"):
            if filename.endswith(".JSON"):
                print("loaded", filename)
                game = tank.tank_game()
                game.load_state_from_file(f"./saves/{filename}")
                games[int(filename[:-5])] = game

        print("ready.")
        while True:
            #try:
            await day_loop()
            #except Exception as e:
                # can have some random errors
                # Ignore and continue chugging.
            #    print("You should fix:", e)

@client.event
async def on_guild_channel_delete(channel):
    try:
        games.pop(channel.id)
        delete_file(f"./saves/{channel.id}.JSON")
    except KeyError:
        pass

@client.event
async def on_message(message):
    if message.author.bot:
        return

    args = message.content.split()
    if len(args) == 0:
        return

    if args[0].casefold() == ".help":
        if len(args) == 1:
            await message.channel.send(help_message_main)
        elif len(args) == 2 and args[1].casefold() == "game":
            await message.channel.send(help_message_game)
        else:
            await message.channel.send("Unknown help")
        return

        
    elif args[0].casefold() == ".invite":
        invite = await client.get_channel(870761497117196331).create_invite(max_age=10*60, unique=True, reason="Requested invite")
        print(f"User {message.author.name} ({message.author.id}) created invite {invite}")

        await message.channel.send(f"Invite the bot:\nhttps://discord.com/oauth2/authorize?client_id=809942527724486727&scope=bot&permissions=314432\nOr join the discord:\n{invite}")
        return
    elif args[0].casefold() == ".instructions":
        if message.author.dm_channel is None:
            await message.author.create_dm()
        try:
            await message.author.dm_channel.send(help_message_instructions)
            await message.channel.send("DMd how to play")
        except discord.errors.Forbidden:
            await message.channel.send("Can't DM!")
        return

    #if it's a command, continue.
    #commands can't start with .., so "..." won't be counted as a valid command by accident.
    if args[0].startswith(".") and not args[0].startswith(".."):
        game = None

        if message.channel.type  == discord.ChannelType.text:
            if message.channel.id in games:
                game = games[message.channel.id]
            else:
                #try loading the game from file if it already exists
                try:
                    game = tank.tank_game()
                    game.load_state_from_file(f"./saves/{message.channel.id}.JSON")
                    games[message.channel.id] = game
                except FileNotFoundError:
                    pass

        elif message.channel.type == discord.ChannelType.private:
            if str(message.author.id) in users:
                user = users[str(message.author.id)]
                if user["selected"] in games:
                    game = games[user["selected"]]

        try:
            if args[0].casefold() == ".create":
                if game != None:
                    await message.channel.send("Game already exists")
                else:
                    if message.channel.type == discord.ChannelType.private:
                        await message.channel.send("Cannot create a game in DMs")
                    else:
                        """
                        if game has -s, set to skipmode
                        if it has a time, then set that as the delta
                        """
                        g_args = {}
                        if "-s" in message.content:
                            g_args["skip_on_0"] = True

                        leng1 = 0
                        time1 = "s"
                        regex_test = re.search(r'-a ?(\d+)(h|m|s|H|M|S)', message.content)
                        if regex_test:
                            leng1 = int(regex_test.group(1))
                            time1 = {"h":"hours", "m":"minutes", "s":"seconds"}[regex_test.group(2).lower()]
                            g_args["time_gap"] = timedelta(**{time1: leng1})
                        
                        leng2 = 0
                        time2 = "s"
                        regex_test = re.search(r'-t ?(\d+)(h|m|s|H|M|S)', message.content)
                        if regex_test:
                            leng2 = int(regex_test.group(1))
                            time2 = {"h":"hours", "m":"minutes", "s":"seconds"}[regex_test.group(2).lower()]
                            g_args["time_delta"] = timedelta(**{time2: leng2})
                        
                        radius = 2
                        regex_test = re.search(r'-r ?(\d+)', message.content)
                        if regex_test:
                            radius = int(regex_test.group(1))
                            g_args["radius"] = radius
                        
                        density = 4
                        regex_test = re.search(r'-d ?(\d+)', message.content)
                        if regex_test:
                            density = int(regex_test.group(1))
                            g_args["density"] = density
                        
                        queue_tetris = 1
                        regex_test = re.search(r'-q ?(\d+)', message.content)
                        if regex_test:
                            queue_tetris = int(regex_test.group(1))
                            g_args["queue_tetris"] = queue_tetris

                        g_args["id"] = message.author.id

                        game = tank.tank_game(message.author.id, **g_args)
                        games[message.channel.id] = game

                        # and also join the user to the created game
                        game.insert_player(message.author.id)
                        await get_user_image(message.author)

                        game.save_state_to_file(f"./saves/{message.channel.id}.JSON")

                        await message.channel.send(f'Created a game{game.game_info()}')
                        return

            elif args[0].casefold() == ".selectgame":
                if message.channel.type == discord.ChannelType.private:
                    if str(message.author.id) not in users:
                        users[str(message.author.id)] = {"selected": None}
                    user = users[str(message.author.id)]

                    if len(args) > 1 and "choices" in user:
                        if args[1].isdigit() and int(args[1]) > 0 and int(args[1]) <= len(user["choices"]):
                            user["selected"] = user["choices"][int(args[1])-1]
                            del user["choices"]
                            save_users()
                            await message.channel.send("Successfully selected game")
                        else:
                            await message.channel.send("Invalid choice")
                    else:
                        choices = []
                        for k,v in games.items():
                            if message.author.id in v.players:
                                choices.append(k)
                        if len(choices) > 0:
                            user["choices"] = choices
                            await message.channel.send("Use `.selectgame <num>` to select one of the following games to use in DMs:\n\n"+"\n".join([f'{str(i+1)}) <#{str(choices[i])}>' for i in range(len(choices))]))
                        else:
                            await message.channel.send("You're not currently part of any games.")
                return

            if game == None:
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("No game selected. Use .selectgame to select a game to use in DMs")
                else:
                    await message.channel.send("No game running")
                return
                #if game does not exist, nothing below should run

            if args[0].casefold() == ".join":
                await get_user_image(message.author)
                await message.channel.send(game.insert_player(message.author.id))

            elif args[0].casefold() == ".start":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                else:
                    await load_and_send_board(message, game, game.start_game(message.author.id))

            elif args[0].casefold() == ".move":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                elif len(args) == 2:
                    await message.channel.send(game.move(message.author.id, args[1]))
                else:
                    await message.channel.send(".move <direction>")

            elif args[0].casefold() == ".push":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                elif len(args) == 3:
                    await message.channel.send(game.push(message.author.id, mention_to_id(args[1]), args[2]))
                else:
                    await message.channel.send(".push <@player> <direction>")

            elif args[0].casefold() == ".whois":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                elif len(args) == 2:
                    await message.channel.send(namer(message.guild, game.who_is(args[1])))
                else:
                    await message.channel.send(".whois <position F4>")

            elif args[0].casefold() == ".whereis":
                if len(args) == 2:
                    await message.channel.send(game.where_is(mention_to_id(args[1])))
                else:
                    await message.channel.send(".whereis <@player>")

            elif args[0].casefold() == ".attack":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                elif len(args) == 2:
                    ret = game.attack(message.author.id, mention_to_id(args[1]))
                    if len(ret) == 2:
                        if message.author.dm_channel is None:
                            await message.author.create_dm()
                        await message.author.dm_channel.send(ret[1])
                    await message.channel.send(ret[0])
                else:
                    await message.channel.send(".attack <player>")

            elif args[0].casefold() == ".giveap":
                if message.channel.type != discord.ChannelType.private:
                    await message.channel.send("Action points are private, so this should be used in a DM channel.")
                elif len(args) == 2:
                    target = None
                    for user in client.users:
                        if args[1] == f"{user.name}#{user.discriminator}":
                            target = user
                            break
                    if target != None:
                        await message.channel.send(await game.giveAP(message.author.id, target))
                    else:
                        await message.channel.send("Could not find that user.")
                else:
                    await message.channel.send(".giveap <user#0000>")

            elif args[0].casefold() == ".givehp":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                elif len(args) == 2:
                    await message.channel.send(game.giveHP(message.author.id, mention_to_id(args[1])))
                else:
                    await message.channel.send(".givehp <player>")

            elif args[0].casefold() == ".haunt":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                elif len(args) == 2:
                    await message.channel.send(game.haunt(message.author.id, mention_to_id(args[1])))
                else:
                    await message.channel.send(".haunt <player>")

            elif args[0].casefold() == ".unhaunt":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                else:
                    await message.channel.send(game.haunt(message.author.id, None))

            elif args[0].casefold() == ".heal":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                else:
                    await message.channel.send(game.heal(message.author.id))

            elif args[0].casefold() == ".upgrade":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                else:
                    await message.channel.send(game.upgrade(message.author.id))

            elif args[0].casefold() == ".skip":
                await message.channel.send(game.skip_turn(message.author.id))

            elif args[0].casefold() == ".list":
                if message.channel.type == discord.ChannelType.private:
                    await message.channel.send("Cannot use this in a DM")
                else:
                    #ERROR: 2K character limit
                    plist = [namer(message.guild, p) + (f' (haunting {namer(message.guild, v["haunting"])})' if v["HP"] == 0 and v["haunting"] else "") for p,v in game.players.items()]
                    pre = f"{len(plist)} players in game:\n"
                    hp = game.haunted_player()
                    post = ("\n\nHaunted player: " + (namer(message.guild, hp) if hp else "Tied!")) if any(v["HP"] == 0 for v in game.players.values()) else ""
                    await message.channel.send(pre + "\n".join(plist) + post)

            elif args[0].casefold() == ".info":
                if message.author.dm_channel is None:
                    await message.author.create_dm()
                await message.author.dm_channel.send(f"{game.info(message.author.id)} in <#{game.id}>")
                if message.channel.type != discord.ChannelType.private:
                    await message.channel.send("DMd AP and Range")

            elif args[0].casefold() == ".gameinfo":
                await message.channel.send(game.game_info())

            elif args[0].casefold() == ".board":
                await get_user_image(message.author)
                #get PFPs and display board
                if game.active():
                    await load_and_send_board(message, game, show_range="-r" in message.content, show_names="-n" in message.content)
                else:
                    await message.channel.send("Game not running yet.")

            elif args[0] == ".DELETE":
                if game.owner == message.author.id or message.author.guild_permissions.administrator:
                    games.pop(game.id)
                    delete_file(f"./saves/{game.id}.JSON")
                    await message.channel.send("Game has been deleted successfully.")
                else:
                    await message.channel.send("Not game owner.")
                return

            if game.active() and not game.is_playable():
                game.finish()
                for player in game.get_all_players():
                    if game.players[player]["HP"] >= 1:
                        await message.channel.send(f"The game is over! <@{player}> is the winner!")
                        break
                for user in users:
                    if user["selected"] == game.id:
                        user["selected"] = None
                save_users()
                delete_file(f"./saves/{game.id}.JSON")
                games.pop(game.id)
            else:
                game.save_state_to_file(f"./saves/{game.id}.JSON")

        except tank.GameError as e:
            try:
                await message.channel.send(str(e) or "Unknown Error :(")
            except discord.errors.Forbidden:
                pass
        except discord.errors.Forbidden as e:
            try:
                print(e)
                await message.channel.send("Error: Not enough permissions (Does someone have their DMs blocked?)")
            except discord.errors.Forbidden:
                pass

if __name__ == '__main__':
    #points to a file containing only the bot token.
    client.run(open("TOKEN", "r").read().rstrip())
