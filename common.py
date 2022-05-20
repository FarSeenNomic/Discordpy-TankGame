import discord
from client import client

def multiliststr(items):
    if len(items) == 0:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return items[0] + " and " + items[1]
    return ", ".join(items[:~0]) + " and " + items[~0]

async def call_member(channelID, haunted_player, game, playerid, timedelta):
    if game.finished():
        return

    print([playerid, timedelta] in game.player_next_hearts, [playerid, timedelta], game.player_next_hearts)
    if [playerid, timedelta] in game.player_next_hearts:
        #should always be true.
        game.player_next_hearts.remove( [playerid, timedelta] )
    else:
        return

    return_value = game.give_hourly_AP_offbeat(playerid, haunted_player)

    # tell humans what is happening
    member = client.get_user(playerid)
    if not member: # if player has left the game
        return
    if member.dm_channel is None: # If there is no DM channel, make one.
        await member.create_dm()

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

def mention_to_id(m, channel=None):
    if m.startswith("<@!"):
        return int(m[3:-1])
    elif m.startswith("<@"):
        return int(m[2:-1])
    elif channel:
        testname = m
        if m.startswith("@"):
            testname = m[1:]
        target = None
        for user in channel.guild.members:
            if testname == f"{user.name}":
                target = user.id
                break
            if testname == f"{user.name}#{user.discriminator}":
                target = user.id
                break
        if target:
            return target
    else:
        return int(m)

#The width in pixels of any user's image
board_size = 64

async def get_user_image(user):
    #url = user.avatar_url_as(format="png", static_format='png')
    #await url.save(f"./dynamic_images/{user.id}.png")

    #await user.display_avatar.with_static_format("png").to_file(f"./dynamic_images/{user.id}.png")
    await user.display_avatar.with_static_format("png").save(f"./dynamic_images/{user.id}.png")

async def load_and_send_board(message, game_id, game, content=None, *, show_range=False, show_names=False):
    game.display(f"./maps/{game_id}.png", guild=message.guild, who_id=message.author.id, show_range=show_range, show_names=show_names, box_size=board_size, thickness=2)
    await message.channel.send(content, file=discord.File(f"./maps/{game_id}.png"))

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

def time_as_words(time):
    seconds = time.total_seconds()
    h = seconds // 3600
    m = (seconds // 60) % 60
    s = seconds % 60
    text = []
    for i in range(3):
        n = round([h,m,s][i])
        if n > 0 or (i == 2 and len(text) == 0):
            text.append(f"{str(n)} {(['hour', 'minute', 'second'][i])}{'s' if n != 1 else ''}")
    return ", ".join(text)