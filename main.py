import os
from dotenv import load_dotenv
import discord
from discord.ext import commands, tasks
from discord.ui import Select, View
import aiohttp

load_dotenv()

TOKEN = os.getenv('DISCORD_TOKEN')

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)

registered_channels = {}

class ChannelSelect(Select):
    def __init__(self, channels, channel_name):
        self.channel_name = channel_name  # 방송 이름 저장
        options = [
            discord.SelectOption(label=channel.name, value=str(channel.id))
            for channel in channels
        ]
        super().__init__(placeholder="채널을 선택하세요...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        channel_id = int(self.values[0])
        registered_channels[self.channel_name] = {"channel_id": channel_id, "notified": False}
        await interaction.response.send_message(f"'{self.channel_name}' 방송 알림이 '{interaction.guild.get_channel(channel_id).name}' 채널에 설정되었습니다.", ephemeral=True)

# 봇이 준비되었을 때 실행되는 이벤트
@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    check_live_status.start()

async def search_channel_and_check_live_status(channel_name):
    url = f"https://api.chzzk.naver.com/service/v1/search/channels?keyword={channel_name}&offset=0&size=1&withFirstChannelContent=true"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data['content']['data']:  # 데이터 리스트가 비어있지 않은지 확인
                    channel_data = data['content']['data'][0]
                    channel_info = channel_data['channel']
                    openLive = channel_info.get('openLive', False)
                    if openLive:
                        channelName = channel_info.get('channelName', 'No channel name')
                        channelId = channel_info.get('channelId', '')
                        channelImageUrl = channel_info.get('channelImageUrl', '')
                        live_data = channel_data['content']['live']
                        liveTitle = live_data.get('liveTitle', 'No title')
                        liveImageUrl = live_data.get('liveImageUrl', '').replace("{type}", "1080")
                        concurrentUserCount = live_data.get('concurrentUserCount', 0)
                        broadcastUrl = f"https://chzzk.naver.com/live/{channelId}"  # 방송 URL 생성
                        return True, channelName, channelImageUrl, liveTitle, liveImageUrl, concurrentUserCount, broadcastUrl
                    else:
                        return False, None, None, None, None, None, None
                else:
                    return None, None, None, None, None, None, None  # 검색 결과가 없는 경우
            else:
                return None, None, None, None, None, None, None  # API 요청 실패

# 간단한 명령어 처리 예 ('!hello' 명령어에 반응하여 'Hello!' 메시지 전송)
@bot.command(name='방송확인')
async def check(ctx, *, channel_name: str):
    openLive, channelName, channelImageUrl, liveTitle, liveImageUrl, concurrentUserCount, broadcastUrl = await search_channel_and_check_live_status(channel_name)
    if openLive is None:
        await ctx.send("방송 상태를 확인할 수 없습니다. API 요청에 실패했습니다.")
    elif openLive:
        await ctx.send(f"{channelName}님께서는 현재 방송 중입니다!")
        # 임베드 메시지 생성
        embed = discord.Embed(
            title=liveTitle,  # 방송 제목을 임베드 제목으로 설정
            url=broadcastUrl,  # 방송 제목 클릭 시 방송 페이지로 이동
            color=discord.Color.blue()
        )
        embed.set_author(name=channelName)
        # 채널 프로필 이미지를 임베드 오른쪽 상단에 썸네일로 설정
        embed.set_thumbnail(url=channelImageUrl)
        # 시청자 수를 별도의 필드로 추가
        embed.add_field(name="시청자 수", value=str(concurrentUserCount), inline=False)
        # 방송 이미지를 임베드 메인 이미지로 설정
        embed.set_image(url=liveImageUrl)
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"{channel_name}님은 현재 방송 중이 아닙니다.")

@bot.command(name='치지직등록')
async def register_channel(ctx, *, channel_name: str):
    select = ChannelSelect(ctx.guild.text_channels, channel_name)
    view = View()
    view.add_item(select)
    await ctx.send("알림을 받을 채널을 선택해주세요:", view=view)

@tasks.loop(minutes=1)
async def check_live_status():
    for channel_name, info in registered_channels.items():
        openLive, channelName, channelImageUrl, liveTitle, liveImageUrl, concurrentUserCount, broadcastUrl = await search_channel_and_check_live_status(channel_name)
        channel = bot.get_channel(info["channel_id"])
        if openLive is None:
            await channel.send("방송 상태를 확인할 수 없습니다. API 요청에 실패했습니다.")
        elif openLive:
            if not info["notified"]:
                # 임베드 메시지와 함께 @everyone 멘션을 사용하여 알림을 보냅니다.
                message = f"@everyone {channelName}님께서는 현재 방송 중입니다!"
                # 임베드 메시지 생성
                embed = discord.Embed(
                    title=liveTitle,  # 방송 제목을 임베드 제목으로 설정
                    url=broadcastUrl,  # 방송 제목 클릭 시 방송 페이지로 이동
                    color=discord.Color.blue()
                )
                embed.set_author(name=channelName)
                # 채널 프로필 이미지를 임베드 오른쪽 상단에 썸네일로 설정
                embed.set_thumbnail(url=channelImageUrl)
                # 시청자 수를 별도의 필드로 추가
                embed.add_field(name="시청자 수", value=str(concurrentUserCount), inline=False)
                # 방송 이미지를 임베드 메인 이미지로 설정
                embed.set_image(url=liveImageUrl)
                await channel.send(content=message, embed=embed)
                info["notified"] = True
        else:
            info["notified"] = False

@bot.command(name='치지직등록취소')
async def unregister_channel(ctx, *, channel_name: str):
    # 등록된 방송이름이 딕셔너리에 있는지 확인
    if channel_name in registered_channels:
        # 등록된 방송 제거
        del registered_channels[channel_name]
        await ctx.send(f"'{channel_name}'님의 방송 알림이 취소되었습니다.")
    else:
        # 등록되지 않은 방송 이름인 경우 사용자에게 알림
        await ctx.send(f"'{channel_name}'님은 등록된 방송이 아닙니다.")


@bot.command(name='명령어')
async def show_commands(ctx):
    commands_description = """
    다음은 사용 가능한 명령어 목록입니다:

    `!방송확인 [치지직채널이름]` : 채널이름은 정확해야 하며 해당채널의 방송 여부를 확인합니다.
    `!치지직등록 [치지직채널이름]` : 해당 채널에 대한 방송 알림을 현재 디스코드 서버 내의 채널을 선택하여 알림을 받습니다.
    `!치지직등록취소 [치지직채널이름]` : 해당 채널의 방송 알림을 없앱니다.
    """
    await ctx.send(commands_description)

# 봇을 실행합니다. 여기서 'your_token_here'는 실제 디스코드 봇 토큰으로 대체해야 합니다.
bot.run(TOKEN)