from datetime import datetime, timedelta
from os import listdir
from os import remove as delete_file
import asyncio
import re
import random
import functools

import discord  #pip install discord.py
                #which has been depricated with no replacement as of now...
                #this makes me sad.
import tank

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

.giveap <@player>
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

.whois <position>
Returns the player at the position 'position'

.whereis <@player>
Returns the player at the position 'position'

.board
view the board

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
(Game creator) Stats a game running

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

me_st = discord.Game("battles! ⚔")
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents, activity=me_st)
games = {}

def multiliststr(items):
    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + " and " + items[1]
    return ", ".join(items[:~0]) + " and " + items[~0]

check_index = 0
async def day_loop():
    """
    Check if the time has passed on a game to give it more AP

    I'll be honest, this entire section has becomes a mess.
    """
    global games
    global check_index
    while True:
        await asyncio.sleep(3) #don't check faster than every 10 seconds
        check_index = (check_index + 1) % len(games)
        channelID, game = list(games.items())[check_index]

        if game.test_hourly_AP():
            if not client.get_channel(channelID):
                print("BAD: ", channelID) #I think this only comes up if the channel is deleted but somehow not the game?
                continue                  #I think this shouldn't ever come up anymore?

            game.give_hourly_AP_onbeat()
            haunted_player = game.haunted_player()

            print("time", datetime.now(), channelID, haunted_player)
            if game.time_delta.total_seconds() < 10:
                for playerid in game.get_all_players():
                    await call_member(channelID, haunted_player, game, playerid)
            else:
                #Someone must instantly gain AP, or else the loop will see all players with 0 AP and repeatedly call.
                game.requeue()
                timedelta = 0
                for playerid in game.player_next_hearts:
                    client.loop.call_later(timedelta, asyncio.create_task, call_member(channelID, haunted_player, game, playerid))
                    timedelta = random.random() * game.time_delta.total_seconds()

async def call_member(channelID, haunted_player, game, playerid):
    if game.finished():
        return

    member = client.get_user(playerid)
    if not member: # if player has left the game
        return
    if member.dm_channel is None: # If there is no DM channel, make one.
        await member.create_dm()  # Does this do anything, or is it placebo?

    return_value = game.give_hourly_AP_offbeat(playerid, haunted_player)

    # I think this fixes double giving hearts if I restart the code mid-giving out.
    # It will still leave a visual error if the board is not changed.
    print(playerid, game.player_next_hearts)
    #game.player_next_hearts.remove(playerid)

    try:
        if return_value == "dead":
            # People have requested they don't get messaged while dead.
            # await member.dm_channel.send(f"Dead!\nGained 0 AP in <#{channelID}>\n{game.info(playerid)}")
            pass
        elif return_value == "haunted":
            # Get a list of every person haunting 'playerid' (That could be you!)
            hauntlist = []
            for index, player in game.players.items():
                if player["haunting"] == playerid:
                    hauntlist.append(namer(client.get_channel(channelID).guild, index))
            await member.dm_channel.send(f"Haunted by {multiliststr(hauntlist)}!\nGained 0 AP in <#{channelID}>\n{game.info(playerid)}")
        elif return_value == "+":
            await member.dm_channel.send(f"Gained 1 AP in <#{channelID}>\n{game.info(playerid)}")

        else:
            print("Something went wrong:", return_value)

    except discord.errors.Forbidden:
        print(f"Disabled DMs: {namer(client.get_channel(channelID).guild, playerid)} ({playerid})")

def mention_to_id(m):
    if m.startswith("<@!"):
        return int(m[3:-1])
    elif m.startswith("<@"):
        return int(m[2:-1])
    else:
        return int(m)

loop = True
@client.event
async def on_ready():
    global games
    global loop
    if loop:
        loop = False
        for fn in listdir("./saves"):
            if fn.endswith(".JSON"):
                print("loaded", fn)
                game = tank.tank_game()
                game.load_state_from_file(f"./saves/{fn}")
                games[int(fn[:-5])] = game

        print("ready.")
        while True:
            #try:
            await day_loop()
            #except Exception as e:
                # can have some random errors
                # Ignore and continue chugging.
            #    print("You should fix:", e)

#The width in pixels of any user's image
board_size = 64

async def get_user_image(user):
    url = user.avatar_url_as(format="png", static_format='png')
    await url.save(f"./dynamic_images/{user.id}.png")

async def load_and_send_board(message, game, content=None, *, show_range=False):
    game.display(f"./maps/{message.channel.id}.png", who_id=message.author.id, show_range=show_range, box_size=board_size, thickness=2)
    await message.channel.send(content, file=discord.File(f"./maps/{message.channel.id}.png"))

@client.event
async def on_guild_channel_delete(channel):
    try:
        games.pop(channel.id)
        delete_file(f"./saves/{channel.id}.JSON")
    except KeyError:
        pass

def namer(guild, p):
    """
    Takes a member.id p and returns a string of their display name, if it exists.
    Else return something.
    """
    #return (message.guild.get_member(p) or message.guild.get_member(809942527724486727)).display_name.replace("@", "@.")
    if not p:
        # if p is None or otherwise false-y, it should not be stringified
        return "Nobody"
    elif guild.get_member(p):
        return guild.get_member(p).display_name.replace("@", "@.")
    else:
        return f"{p} (<@{p}>)"

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
        if message.channel.id not in games:
            #try loading the game from file if it already exists
            try:
                game = tank.tank_game()
                game.load_state_from_file(f"./saves/{message.channel.id}.JSON")
                games[message.channel.id] = game
            except FileNotFoundError:
                pass

        try:
            if args[0].casefold() == ".create":
                if message.channel.id in games:
                    await message.channel.send("Game already exists")
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

                    games[message.channel.id] = tank.tank_game(message.author.id, **g_args)

                    # and also join the user to the created game
                    games[message.channel.id].insert_player(message.author.id)
                    await get_user_image(message.author)

                    games[message.channel.id].save_state_to_file(f"./saves/{message.channel.id}.JSON")

                    await message.channel.send(
f'''Created a game
```Auto-skip turned {"on" if g_args.get("skip_on_0", False) else "off"}
With rounds every {leng1} {time1}
Random offset of {leng2} {time2}
Radius of {radius}
Density of {density} ({4./density} times normal)
Queue multiplier of {queue_tetris}```
''')
                    return

            if message.channel.id not in games:
                #if game does not exist, nothing below should run
                await message.channel.send("No game running")
                return

            game = games[message.channel.id]

            if args[0].casefold() == ".join":
                await get_user_image(message.author)
                await message.channel.send(game.insert_player(message.author.id))

            elif args[0].casefold() == ".start":
                await load_and_send_board(message, game, game.start_game(message.author.id))

            elif args[0].casefold() == ".move":
                if len(args) == 2:
                    await message.channel.send(game.move(message.author.id, args[1]))
                else:
                    await message.channel.send(".move <direction>")

            elif args[0].casefold() == ".push":
                if len(args) == 3:
                    await message.channel.send(game.push(message.author.id, mention_to_id(args[1]), args[2]))
                else:
                    await message.channel.send(".push <@player> <direction>")

            elif args[0].casefold() == ".whois":
                if len(args) == 2:
                    await message.channel.send(namer(message.guild, game.who_is(args[1])))
                else:
                    await message.channel.send(".whois <position F4>")

            elif args[0].casefold() == ".whereis":
                if len(args) == 2:
                    await message.channel.send(game.where_is(mention_to_id(args[1])))
                else:
                    await message.channel.send(".whereis <@player>")

            elif args[0].casefold() == ".attack":
                if len(args) == 2:
                    ret = game.attack(message.author.id, mention_to_id(args[1]))
                    if len(ret) == 2:
                        if message.author.dm_channel is None:
                            await message.author.create_dm()
                        await message.author.dm_channel.send(ret[1])
                    await message.channel.send(ret[0])
                else:
                    await message.channel.send(".attack <player>")

            elif args[0].casefold() == ".giveap":
                if len(args) == 2:
                    await message.channel.send(game.giveAP(message.author.id, mention_to_id(args[1])))
                else:
                    await message.channel.send(".giveap <player>")

            elif args[0].casefold() == ".givehp":
                if len(args) == 2:
                    await message.channel.send(game.giveHP(message.author.id, mention_to_id(args[1])))
                else:
                    await message.channel.send(".givehp <player>")

            elif args[0].casefold() == ".haunt":
                if len(args) == 2:
                    await message.channel.send(game.haunt(message.author.id, mention_to_id(args[1])))
                else:
                    await message.channel.send(".haunt <player>")

            elif args[0].casefold() == ".unhaunt":
                await message.channel.send(game.haunt(message.author.id, None))

            elif args[0].casefold() == ".heal":
                await message.channel.send(game.heal(message.author.id))

            elif args[0].casefold() == ".upgrade":
                await message.channel.send(game.upgrade(message.author.id))

            elif args[0].casefold() == ".skip":
                await message.channel.send(game.skip_turn(message.author.id))

            elif args[0].casefold() == ".list":
                #ERROR: 2K character limit
                plist = [namer(message.guild, p) + (f' (haunting {namer(message.guild, v["haunting"])})' if v["HP"] == 0 and v["haunting"] else "") for p,v in game.players.items()]
                pre = f"{len(plist)} players in game:\n"
                hp = game.haunted_player()
                post = ("\n\nHaunted player: " + (namer(message.guild, hp) if hp else "Tied!")) if any(v["HP"] == 0 for v in game.players.values()) else ""
                await message.channel.send(pre + "\n".join(plist) + post)

            elif args[0].casefold() == ".info":
                if message.author.dm_channel is None:
                    await message.author.create_dm()
                await message.author.dm_channel.send(f"{game.info(message.author.id)} in <#{message.channel.id}>")
                await message.channel.send("DMd AP and Range")

            elif args[0].casefold() == ".board":
                await get_user_image(message.author)
                #get PFPs and display board
                if game.active():
                    await load_and_send_board(message, game, show_range="-r" in message.content)
                else:
                    await message.channel.send("Game not running yet.")

            elif args[0] == ".DELETE":
                if game.owner == message.author.id or message.author.guild_permissions.administrator:
                    games.pop(message.channel.id)
                    delete_file(f"./saves/{message.channel.id}.JSON")
                    await message.channel.send("Game has been deleted successfully.")
                else:
                    await message.channel.send("Not game owner.")
                return

            if game.active() and not game.is_playable():
                game.finish()
                for p in game.get_all_players():
                    if game.players[p]["HP"] >= 1:
                        await message.channel.send(f"The game is over! <@{p}> is the winner!")
                        break
                delete_file(f"./saves/{message.channel.id}.JSON")
                games.pop(message.channel.id)
            else:

                #TODO: check if statemtnt is correct

                game.save_state_to_file(f"./saves/{message.channel.id}.JSON")

        except tank.GameError as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        except discord.errors.Forbidden as e:
            await message.channel.send("Error: Not enough permissions (Does someone have their DMs blocked?)")
            print(e)

#points to a file containing only the bot token.
client.run(open("TOKEN", "r").read().rstrip())
