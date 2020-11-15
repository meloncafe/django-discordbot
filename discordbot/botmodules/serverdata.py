from discord.ext import commands

from discordbot.botmodules.audio import AudioManager, YouTubePlayer

from asgiref.sync import sync_to_async

#####

class MusicQueue():
    def __init__(self, server):
        self.server = server

        self._players = []

    def addPlayer(self, player):
        self._players.append(player)

    def hasPlayer(self):
        return bool(self._players)

    def playNext(self, ctx):
        if self.hasPlayer() and ctx.voice_client and ctx.voice_client.is_connected():
            player = self._players.pop(0)
            player.play(ctx)
            return player
        else:
            return None

    async def sendNowPlaying(self, ctx):
        if ctx.voice_client and ctx.voice_client.source:
            if isinstance(ctx.voice_client.source, YouTubePlayer):
                await ctx.voice_client.source.send(ctx, status="Wird aktuell gespielt.")
        else:
            raise commands.CommandError("Aktuell wird nichts abgespielt.")

    async def sendQueue(self, ctx):
        description = "\n".join(i.getinfo() for i in self._players)
        await ctx.sendEmbed(
            title="Warteschlange",
            color=ctx.command.cog.color,
            description=description,
        )

    async def createYoutubePlayer(self, search, loop=None, stream=False):
        return await YouTubePlayer.from_url(search, queue=self, loop=loop, stream=stream)



class Server():
    _all = {}

    def __init__(self,id):
        self.id = id
        self.musicqueue = MusicQueue(server=self)
        #self.polls = {}

    @classmethod
    def getServer(self, serverid:int):
        if not serverid in self._all:
            self._all[serverid] = Server(serverid)
        return self._all[serverid]




### NEW

from discordbot.models import Server as DB_Server, User as DB_User, Report as DB_Report, Member as DB_Member, AudioSource, Playlist, AmongUsGame, VierGewinntGame, BotPermission, NotifierSub
from django.db import connection, connections

class DjangoConnection():
    def __init__(self, dc_user, dc_guild):
        self.dc_user = dc_user
        self.dc_guild = dc_guild
        self._db_user = None
        self._db_server = None
        self._db_playlist = None
        
    @classmethod
    def ensure_connection(self):
        if connection.connection and not connection.is_usable():
            del connections._connections.default

    @classmethod
    @sync_to_async
    def fetch_user(self, dc_user):
        self.ensure_connection()
        if not DB_User.objects.filter(id=str(dc_user.id)).exists():
            user = DB_User.objects.create(id=str(dc_user.id), name=dc_user.name+"#"+dc_user.discriminator)
        else:
            user = DB_User.objects.get(id=str(dc_user.id))
            if not user.name == (dc_user.name+"#"+dc_user.discriminator):
                user.name = (dc_user.name+"#"+dc_user.discriminator)
                user.save()
        return user

    async def get_user(self):
        if self._db_user is None:
            self._db_user = await self.fetch_user(self.dc_user)
        return self._db_user

    @classmethod
    @sync_to_async
    def fetch_server(self, dc_guild):
        self.ensure_connection()
        if not DB_Server.objects.filter(id=str(dc_guild.id)).exists():
            server = DB_Server.objects.create(id=str(dc_guild.id), name=dc_guild.name)
        else:
            server = DB_Server.objects.get(id=str(dc_guild.id))
            if not server.name == dc_guild.name:
                server.name = dc_guild.name
                server.save()
        return server

    async def get_server(self):
        if self._db_server is None:
            self._db_server = await self.fetch_server(self.dc_guild)
        return self._db_server

    async def get_playlist(self):
        if self._db_playlist is None:
            server = await self.get_server()
            self._db_playlist = await server.getPlaylist()
        return self._db_playlist

    # Basic Methods

    @classmethod
    @sync_to_async
    def _save(self, obj):
        self.ensure_connection()
        obj.save()

    @classmethod
    @sync_to_async
    def _delete(self, obj):
        self.ensure_connection()
        obj.delete()

    @classmethod
    @sync_to_async
    def _create(self, model, **kwargs):
        self.ensure_connection()
        return model.objects.create(**kwargs)

    @classmethod
    @sync_to_async
    def _exists(self, model, **kwargs):
        self.ensure_connection()
        return model.objects.filter(**kwargs).exists()

    @classmethod
    @sync_to_async
    def _get(self, model, **kwargs):
        self.ensure_connection()
        return model.objects.get(**kwargs)

    @classmethod
    @sync_to_async
    def _list(self, model, **kwargs):
        self.ensure_connection()
        return list(model.objects.filter(**kwargs))

    # Music

    @classmethod
    @sync_to_async
    def _createAudioSourceFromDict(self, data):
        return AudioSource.create_from_dict(data)

    @classmethod
    async def getOrCreateAudioSourceFromDict(self, data):
        if await self._exists(AudioSource, url_watch=data.get("webpage_url", data.get("url", None))):
            audio = await self._get(AudioSource, url_watch=data.get("webpage_url", data.get("url")))
            audio.url_source = data.get("url", "")
            await self._save(audio)
            return audio
        else:
            return await self._createAudioSourceFromDict(data)

    # Reports

    async def createReport(self, dc_user, reason:str="", reportedby_dc_user=None):
        server = await self.get_server()
        user = (await self.get_user()) if reportedby_dc_user is None else (await self.fetch_user(reportedby_dc_user))
        await user.joinServer(server)
        reporteduser = await self.fetch_user(dc_user)
        await reporteduser.joinServer(server)
        return await self._create(DB_Report, server=server, user=reporteduser, reported_by=user, reason=reason)

    async def getReports(self, dc_user=None):
        server = await self.get_server()
        if dc_user is None:
            reports = await server.getReports()
            print(reports)
            return reports
        else:
            user = await self.fetch_user(dc_user)
            reports = await server.getReports(user=user)
            print(reports)
            return reports

    # Remote

    @classmethod
    @sync_to_async
    def _has_permissions(self, **kwargs):
        self.ensure_connection()
        return BotPermission.objects.filter(**kwargs).exists()

    @classmethod
    @sync_to_async
    def _delete_permissions(self, **kwargs):
        self.ensure_connection()
        BotPermission.objects.filter(**kwargs).delete()

    @classmethod
    @sync_to_async
    def _create_permissions(self, **kwargs):
        self.ensure_connection()
        return BotPermission.objects.create(**kwargs)

    @classmethod
    @sync_to_async
    def _list_permissions(self, **kwargs):
        self.ensure_connection()
        return list(BotPermission.objects.filter(**kwargs))

    # AmongUs

    @classmethod
    @sync_to_async
    def _getAmongUsGame(self, **kwargs):
        self.ensure_connection()
        return AmongUsGame.objects.get(**kwargs)

    async def getAmongUsGame(self, **kwargs):
        user = await self.get_user()
        server = await self.get_server()
        return await self._get(AmongUsGame, creator=user, guild=server, **kwargs)

    @classmethod
    @sync_to_async
    def _hasAmongUsGame(self, **kwargs):
        self.ensure_connection()
        return AmongUsGame.objects.filter(**kwargs).exists()

    async def hasAmongUsGame(self, **kwargs):
        user = await self.get_user()
        server = await self.get_server()
        return await self._hasAmongUsGame(creator=user, guild=server, **kwargs)

    @classmethod
    @sync_to_async
    def _createAmongUsGame(self, **kwargs):
        self.ensure_connection()
        return AmongUsGame.objects.create(**kwargs)

    async def createAmongUsGame(self, **kwargs):
        user = await self.get_user()
        server = await self.get_server()
        return await self._create(AmongUsGame, creator=user, guild=server, **kwargs)

    # VierGewinnt

    @classmethod
    @sync_to_async
    def _getVierGewinntGame(self, **kwargs):
        self.ensure_connection()
        return VierGewinntGame.objects.get(**kwargs)

    @classmethod
    @sync_to_async
    def _hasVierGewinntGame(self, **kwargs):
        self.ensure_connection()
        return VierGewinntGame.objects.filter(**kwargs).exists()

    @classmethod
    @sync_to_async
    def _listVierGewinntGames(self, get_as_queryset: bool=False, **kwargs):
        self.ensure_connection()
        if get_as_queryset:
            return VierGewinntGame.objects.filter(**kwargs).order_by("id")
        else:
            return list(VierGewinntGame.objects.filter(**kwargs).order_by("id"))

    @classmethod
    @sync_to_async
    def _createVierGewinntGame(self, **kwargs):
        self.ensure_connection()
        return VierGewinntGame.create(**kwargs)

    # NotifierSub

    @classmethod
    @sync_to_async
    def _getNotifierSub(self, **kwargs):
        self.ensure_connection()
        return NotifierSub.objects.get(**kwargs)

    @classmethod
    @sync_to_async
    def _listNotifierSubs(self, **kwargs):
        self.ensure_connection()
        return list(NotifierSub.objects.filter(**kwargs))

    @classmethod
    @sync_to_async
    def _createNotifierSub(self, **kwargs):
        self.ensure_connection()
        return NotifierSub.objects.create(**kwargs)
