from datetime import datetime, timedelta
from os import listdir
from os import remove as delete_file
import asyncio
import re
import discord
import tank
import random

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

async def day_loop():
    """
    Check if the time has passed on a game to give it more AP

    I'll be honest, this entire section has becomes a mess.
    """
    global games
    while True:
        await asyncio.sleep(10)
        for channelID, game in games.items():
            if game.test_hourly_AP():
                channel = client.get_channel(channelID)
                if not channel:
                    print("BAD: ", channelID)
                    continue
                hp = game.haunted_player()
    
                timedeltas = sorted([random.random() * game.time_delta.total_seconds() for _ in game.get_all_players()])
                print("time", datetime.now(), channelID, timedeltas)

                for index, playerid in enumerate(random.sample( game.get_all_players(), len(game.players) )):
                    if index == 0:
                        await asyncio.sleep(timedeltas[index])
                    else:
                        await asyncio.sleep(timedeltas[index] - timedeltas[index-1])
    
                    member = client.get_user(playerid)
                    if not member:# if player has left the game
                        continue
                    if member.dm_channel is None:
                        await member.create_dm()
    
                    try:
                        if game.players[playerid]["HP"] == 0:
                            await member.dm_channel.send("Dead!\nGained 0 AP in <#{}>\n{}".format(channelID, game.info(playerid)))
                        elif hp == playerid:
                            #hauntlist = [channel.guild.get_member(i).display_name for i,v in game.players.items() if v["haunting"] == playerid]
                            hauntlist = []
                            for i,v in game.players.items():
                                if v["haunting"] == playerid:
                                    try:
                                        hauntlist.append(channel.guild.get_member(i).display_name)
                                    except AttributeError:
                                        hauntlist.append("Removed Player")
                                        pass
                            await member.dm_channel.send("Haunted by {}!\nGained 0 AP in <#{}>\n{}".format(multiliststr(hauntlist), channelID, game.info(playerid)))
                        else:
                            await member.dm_channel.send("Gained 1 AP in <#{}>\n{}".format(channelID, game.info(playerid)))
                    except discord.errors.Forbidden:
                        print("Can't DM {} ({})".format(client.get_user(playerid).name, playerid))

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
                game.load_state_from_file("saves/{}".format(fn))
                games[int(fn[:-5])] = game

        print("ready.")
        while True:
            try:
                await day_loop()
            except Exception as e:
                # can have some random errors
                # Ignore and continue chugging.
                print(e)

board_size = 64

async def get_user_image(user):
    url = user.avatar_url_as(format="png", static_format='png')
    await url.save("dynamic_images/{}.png".format(user.id, board_size))

async def load_and_send_board(message, game, content=None):
    game.display("maps/{}.png".format(message.channel.id), box_size=board_size, thickness=2)
    await message.channel.send(content, file=discord.File("maps/{}.png".format(message.channel.id)))

@client.event
async def on_guild_channel_delete(channel):
    try:
        games.pop(channel.id)
        delete_file("saves/{}.JSON".format(channel.id))
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
        await message.channel.send("""```
.help
Displays this message

.instructions
links how to play the game

.invite
Give the invite to the bot and server.

.create [-s] [56m | 2h | 180s] [-24h | -5m | -30s]
If no games are running, make a new one
if "-s" is specified, then when each player has 0 AP or has opped to skip, the remaining time will be skipped.
time and unit are the length of the time between AP gains, if unspecified, 24hours is used
if `-time` is specified (with a dash), then it gives some randomization in the time between people's AP gains.

.join
Joins a game before it starts.

.start
(Game creator) Stats a game running

Game actions:

.move Direction
Moves in one of the 8 cardinal directions.
> N | S | E | W | NW | NE | SW | SE
> U | D | L | R | UL | UR | DL | DR
> numpad direction

.attack @player
attacks a player in range

.giveap @player
gives AP to a player in range

.givehp @player
gives HP to a player in range

.haunt @player
If you are dead, mark a player for not getting AP

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

.board
view the board

.DELETE
Case sensitive
Stops and removed the current game running. Can only be used by the person who start it or a server admin.
There is no warning.
```""")
        return

    elif args[0].casefold() == ".invite":
        await message.channel.send("""
Invite the bot:
https://discord.com/oauth2/authorize?client_id=809942527724486727&scope=bot&permissions=314432
Or join the discord:
https://discord.gg/BRSEPxXFuS
""")
        return
    elif args[0].casefold() == ".instructions":
        if message.author.dm_channel is None:
            await message.author.create_dm()
        try:
            await message.author.dm_channel.send("""```
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
* You can't win this game without making some friends and stabbing some backs. Probably.```""")
            await message.channel.send("DMd how to play")
        except discord.errors.Forbidden:
            await message.channel.send("Can't DM!")
        return

    elif args[0][0] == '.' and message.channel.id not in games:
        #try loading the game from file if it already exists
        try:
            game = tank.tank_game()
            game.load_state_from_file("saves/{}.JSON".format(message.channel.id))
            games[message.channel.id] = game
        except FileNotFoundError:
            pass

    if args[0][0] == '.':
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

                    time_regex = re.search(r' (\d+)(h|m|s|H|M|S)', message.content)
                    if time_regex:
                        leng1 = int(time_regex.group(1))
                        time1 = {"h":"hours", "m":"minutes", "s":"seconds"}[time_regex.group(2).lower()]
                        g_args["time_gap"] = timedelta(**{time1: leng1})
                    
                    time_regex2 = re.search(r' -(\d+)(h|m|s|H|M|S)', message.content)
                    if time_regex2:
                        leng2 = int(time_regex2.group(1))
                        time2 = {"h":"hours", "m":"minutes", "s":"seconds"}[time_regex2.group(2).lower()]
                        g_args["time_delta"] = timedelta(**{time2: leng2})
                    
                    games[message.channel.id] = tank.tank_game(message.author.id, **g_args)

                    # and also join the user to the created game
                    games[message.channel.id].insert_player(message.author.id)
                    await get_user_image(message.author)

                    games[message.channel.id].save_state_to_file("saves/{}.JSON".format(message.channel.id))

                    await message.channel.send("Created a game with rounds every {} {}, random offset of {} {}, and auto-skip turned {}.".format(leng1, time1, leng2, time2, "on" if g_args["skip_on_0"] else "off"))
                    return

            if message.channel.id not in games:
                #if game does not exist, nothing below should run
                await message.channel.send("No game running")
                return

            game = games[message.channel.id]

            await get_user_image(message.author)

            if args[0].casefold() == ".join":
                await message.channel.send(game.insert_player(message.author.id))
                await get_user_image(message.author)

            elif args[0].casefold() == ".start":
                await load_and_send_board(message, game, game.start_game(message.author.id))

            elif args[0].casefold() == ".move":
                if len(args) == 2:
                    await message.channel.send(game.move(message.author.id, args[1]))
                else:
                    await message.channel.send(".move <direction>")

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

            elif args[0].casefold() == ".heal":
                await message.channel.send(game.heal(message.author.id))

            elif args[0].casefold() == ".upgrade":
                await message.channel.send(game.upgrade(message.author.id))

            elif args[0].casefold() == ".skip":
                await message.channel.send(game.skip_turn(message.author.id))

            elif args[0].casefold() == ".list":
                namer = lambda p: (message.guild.get_member(p) or message.guild.get_member(809942527724486727)).display_name.replace("@", "@.")
                plist = [namer(p) + (" (haunting {})".format(namer(v["haunting"])) if v["haunting"] else "") for p,v in game.players.items()]
                pre = "{} players in game:\n".format(len(plist))
                await message.channel.send(pre + "\n".join(plist))

            elif args[0].casefold() == ".info":
                if message.author.dm_channel is None:
                    await message.author.create_dm()
                await message.author.dm_channel.send("{} in <#{}>".format(game.info(message.author.id), message.channel.id))
                await message.channel.send("DMd AP and Range")

            elif args[0].casefold() == ".board":
                #get PFPs and display board
                if game.active():
                    await load_and_send_board(message, game)
                else:
                    await message.channel.send("Game not running yet.")

            elif args[0] == ".DELETE":
                if game.owner == message.author.id or message.author.guild_permissions.administrator:
                    games.pop(message.channel.id)
                    delete_file("saves/{}.JSON".format(message.channel.id))
                    await message.channel.send("Game has been deleted successfully.")
                else:
                    await message.channel.send("Not game owner.")
                return

            if game.active() and not game.is_playable():
                for p in game.get_all_players():
                    if game.players[p]["HP"] >= 1:
                        await message.channel.send("The game is over! <@{}> is the winner!".format(p))
                        break
                delete_file("saves/{}.JSON".format(message.channel.id))
                games.pop(message.channel.id)
            else:
                if game.test_all_ready_ap():
                    for p in game.get_all_players():
                        member = client.get_user(p)
                        if member.dm_channel is None:
                            await member.create_dm()
                        await member.dm_channel.send("Gained 1 AP in <#{}>".format(message.channel.id))

                game.save_state_to_file("saves/{}.JSON".format(message.channel.id))

        except tank.NotEnoughHealth as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        except tank.UnknownCommand as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        except tank.NotEnoughAP as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        except tank.NotInRange as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        except tank.BadDirection as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        except tank.PlayerNotInGame as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        except tank.GameJoinError as e:
            await message.channel.send(str(e) or "Unknown Error :(")
        #except ValueError as e:
        #    await message.channel.send("Not a valid player.")
        except discord.errors.Forbidden as e:
            await message.channel.send("Error: Not enough permissions")

client.run(open("../Discord/TOKENTANK", "r").read().rstrip())
