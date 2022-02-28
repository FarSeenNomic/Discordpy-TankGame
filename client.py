import discord
                
me_st = discord.Game("battles! ⚔")
intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents, activity=me_st)