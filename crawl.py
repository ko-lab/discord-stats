import csv
import os
from tempfile import NamedTemporaryFile

import discord


TOKEN = os.environ["DISCORD_TOKEN"]
DATA_FILE = os.environ.get('DATA_FILE', 'kolab_messages.csv')

GUILD_ID = 830768294906167327  # Ko-Lab

CHANNELS = {
    830772889573130251,  # introductions,
    830768294906167330,  # discord/topic:general-pub,
    863456400898129920,  # discord/topic:bot-testing,
    1151115596986069103,  # discord/topic:meme,
    1219998752442548224,  # discord/topic:media,
    878407769219285012,  # discord/topic:item-proposals,
    1192953356818337922,  # discord/topic:supply-and-demand,
    1380196868767748127,  # discord/topic:osm-mobiliteit-en-verkeer,
    1425183206659067986,  # discord/topic:discord-alt,
    914188368835932271,  # discord/topic:advent-of-code,
    1175396080670756904,  # discord/topic:astronautics,
    878187233465733130,  # discord/topic:crypto,
    863413687310221342,  # discord/topic:chemistry-and-biology,
    884350289019289620,  # discord/topic:cnc-3d-lasercutting,
    863413513329180703,  # discord/topic:electronics,
    1187390899936829481,  # discord/topic:entrepreneurship,
    863413829870026762,  # discord/topic:experimental-gastronomy,
    863479805847666729,  # discord/topic:gaming,
    1171348925807067177,  # discord/topic:hackernews,
    1151135087908368444,  # discord/topic:home-automation,
    1260114504830681128,  # discord/topic:lego,
    1071897855821873202,  # discord/topic:light,
    866932341950513203,  # discord/topic:lock-picking,
    863413899998003201,  # discord/topic:mechanics,
    1218208784564883537,  # discord/topic:meshtastic,
    1220410610546770061,  # discord/topic:movies-to-see,
    1160490200225546290,  # discord/topic:osint,
    878576854221619230,  # discord/topic:photography,
    863414394133545000,  # discord/topic:plastic-moon,
    863463935914541056,  # discord/topic:privacy-security,
    863414317584351242,  # discord/topic:woodworking,
    863735933445865492,  # discord/topic:video-synthesis,
    863413326544371722,  # discord/topic:music-production,
    863413984250036235,  # discord/topic:radio,
    863443214521729034,  # discord/topic:right-to-repair,
    866210105409404938,  # discord/topic:youtube-gold,
    1275100303632629833,  # discord/topic:ko-lab-cyberstride,
    863414610610356254,  # discord/topic:programming,
  }

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    guild = client.get_guild(GUILD_ID)

    print('Fetching channels...')
    channels = await guild.fetch_channels()
    print(f'Fetched {len(channels)} channels...')

    channels = [c for c in channels if c.id in CHANNELS]
    for c in channels:
        print(c.name, c.id)

    with NamedTemporaryFile(mode="w", dir=os.path.dirname(DATA_FILE), encoding="utf-8", delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(["channel_id", "channel_name", "message_id", "author_id", "author_name", "author_created",
                         "author_avatar", "timestamp", "content"])

        for channel in channels:
            print(f"Fetching messages from #{channel.name}...")
            async for msg in channel.history(limit=None, oldest_first=True):
                if not msg.author.bot:
                    row = [
                        channel.id,
                        channel.name,
                        msg.id,
                        msg.author.id,
                        str(msg.author),
                        msg.author.created_at.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                        msg.author.avatar.url if msg.author.avatar else None,
                        msg.created_at.strftime("%Y-%m-%dT%H:%M:%S.%f"),
                        msg.content.replace('\n', ' ')
                    ]
                    print(row)
                    writer.writerow(row)

    os.rename(f.name, DATA_FILE)    # Move into place atomically
    print(f"Done.")
    await client.close()


def main():
    client.run(TOKEN)


if __name__ == "__main__":
    main()
