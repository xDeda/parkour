import asyncio
import aiohttp
import aiotfm
from proxy_connector import Connection
import os
import random
import string
import traceback
import time
import re
import json
from forum import ForumClient


class env:
	proxy_token = os.getenv("PROXY_TOKEN")
	proxy_ip = os.getenv("PROXY_IP")
	proxy_port = os.getenv("PROXY_PORT")

	password = os.getenv("PARKOUR_PASSWORD")
	heroku_token = os.getenv("HEROKU_TOKEN")

	mod_chat = os.getenv("MOD_CHAT_WEBHOOK")
	mod_chat_announcement = os.getenv("MOD_CHAT_ANNOUNCEMENT_WEBHOOK")
	mapper_chat = os.getenv("MAPPER_CHAT_WEBHOOK")
	mapper_chat_announcement = os.getenv("MAPPER_CHAT_ANNOUNCEMENT_WEBHOOK")

	weekly_record_webhook = os.getenv("WEEKLY_RECORD_WEBHOOK")

	game_logs = os.getenv("GAME_LOGS_WEBHOOK")
	suspects = os.getenv("SUSPECT_WEBHOOK")
	suspects2 = os.getenv("SUSPECT2_WEBHOOK")
	sanctions = os.getenv("SANCTIONS_WEBHOOK")
	ranks = os.getenv("RANKS_WEBHOOK")
	join = os.getenv("JOIN_WEBHOOK")
	private = os.getenv("BOT_CRASH_WEBHOOK")
	default = os.getenv("DEFAULT_WEBHOOK")

	records_webhook = os.getenv("RECORDS_WEBHOOK")
	parkour_records_webhook = os.getenv("PARKOUR_RECORDS_WEBHOOK")
	record_badges_webhook = os.getenv("RECORD_BADGES_WEBHOOK")
	record_suspects = os.getenv("RECORD_SUSPECTS")

	suspects_norecord = os.getenv("SUSPECTS_NORECORD_WEBHOOK")
	game_victory = os.getenv("GAME_VICTORY_WEBHOOK")

	commands_webhook = os.getenv("COMMAND_LOG_WEBHOOK")

	report_channel = 773630094257815572


WEEKLY_RECORDS_MSG = """<a:blob_cheer1:683845978553450576> **[{} - {}]** <a:blob_cheer2:683846001421058071>
Congratulations to the highest achieving Weekly Leaderboard players!

> 🥇 [{}] `{}`: **{}** completed maps
> 🥈 [{}] `{}`: **{}** completed maps
> 🥉 [{}] `{}`: **{}** completed maps"""

SEND_OTHER = (1 << 8) + 255
SEND_ROOM = (2 << 8) + 255
SEND_WEBHOOK = (3 << 8) + 255
MODIFY_RANK = (4 << 8) + 255
SYNCHRONIZE = (5 << 8) + 255
CURRENT_CHAT = (9 << 8) + 255
NEW_CHAT = (10 << 8) + 255
WEEKLY_RESET = (12 << 8) + 255
ROOM_PASSWORD = (13 << 8) + 255
VERIFY_DISCORD = (14 << 8) + 255
VERSION_MISMATCH = (15 << 8) + 255
RECORD_SUBMISSION = (16 << 8) + 255
RECORD_BADGES = (17 << 8) + 255
SIMULATE_SUS = (18 << 8) + 255
LAST_SANCTION = (19 << 8) + 255
PLAYER_VICTORY = (21 << 8) + 255
GET_PLAYER_INFO = (22 << 8) + 255
IS_SANCTIONED = (23 << 8) + 255
CAN_REPORT = (24 << 8) + 255
TOGGLE_REPORT = (25 << 8) + 255
COMMAND_LOG = (26 << 8) + 255
POLL_VOTE = (27 << 8) + 255
GET_PLAYER_DATA = (29 << 8) + 255

MODULE_CRASH = (255 << 8) + 255

chats = (
	["mod", env.mod_chat_announcement, env.mod_chat],
	["mapper", env.mapper_chat_announcement, env.mapper_chat]
)

webhooks = {
	"**`[UPDATE]:`**": env.game_logs,
	"**`[CRASH]:`**": env.game_logs,
	"**`[SUS]:`**": env.suspects,
	"**`[SUS2]:`**": env.suspects2,
	"**`[BANS]:`**": env.sanctions,
	"**`[KILL]:`**": env.sanctions,
	"**`[NOREP]:`**": env.sanctions,
	"**`[RANKS]:`**": env.ranks,
	"**`[JOIN]:`**": env.join,
	"**`[BOTCRASH]:`**": env.private,
	"**`[RECORD]:`**": env.parkour_records_webhook,
	"**`[RECORD_SUS]:`**": env.record_suspects,
	"**`[RECORDS_BADGE]:`**": env.record_badges_webhook,
	"**`[COMMAND]:`**": env.commands_webhook
}


def normalize_name(name):
	"""Normalizes a transformice nickname."""
	if isinstance(name, aiotfm.Player):
		name = name.username

	if name[0] == "+":
		name = "+" + (name[1:].capitalize())
	else:
		name = name.capitalize()
	if "#" not in name:
		name += "#0000"
	return name


def enlarge_name(name):
	"""Enlarges a parkour room name."""
	if name[0] == "*":
		return "*#parkour" + name[1:]
	else:
		return name[:2] + "-#parkour" + name[2:]


def shorten_name(name):
	if name[0] == "*":
		return name.replace("#parkour", "", 1)
	return name.replace("-#parkour", "", 1)


class Proxy(Connection):
	def __init__(self, client, *args, **kwargs):
		self.client = client
		super().__init__(*args, **kwargs)

	async def connection_lost(self):
		await self.client.restart()

	async def received_proxy(self, client, packet):
		loop = self.client.loop

		if client == "records":
			if packet["type"] == "records":
				player = packet["player"] # id
				records = packet["records"] # records quantity

				if records > 0 and (records == 1 or records % 5 == 0):
					loop.create_task(self.client.send_record_badge(player, records))

			elif packet["type"] == "map-records":
				self.client.dispatch("map_records", packet["map"], packet["records"])
			return

		elif client == "api":
			if packet["type"] == "get_roles":
				roles = self.client.get_player_rank(packet["player"])
				role_list = []

				for name, active in roles.items():
					if active:
						role_list.append(name)

				await self.sendTo({
					"type": "get_roles",
					"player": packet["player"],
					"roles": role_list
				}, client)

			elif packet["type"] == "whois":
				name = await self.client.get_player_name(packet["id"])

				await self.sendTo({
					"type": "whois",
					"id": packet["id"],
					"name": name
				}, client)

			elif packet["type"] == "profile":
				if "id" in packet:
					name = await self.client.get_player_name(packet["id"])
					pid = packet["id"]

				else:
					pid = await self.client.get_player_id(packet["name"])
					name = packet["name"]

				response = {
					"type": "profile",
					"id": pid,
					"name": name
				}

				if pid is None or name is None:
					response["profile"] = None
					await self.sendTo(response, client)
					return
				
				roles = self.client.get_player_rank(name)
				role_list = []

				for role, active in roles.items():
					if active:
						role_list.append(role)

				response["profile"] = profile = {
					"roles": role_list
				}

				await self.client.send_callback(GET_PLAYER_DATA, name)

				try:
					txt_id, text = await self.client.wait_for(
						"on_lua_textarea",
						lambda txt_id, text: (
							txt_id in (GET_PLAYER_DATA, VERSION_MISMATCH)
							and text.startswith(name)
						),
						timeout=2.0
					)
				except Exception:
					profile["online"] = False
					return await self.sendTo(response, client)

				profile["online"] = True

				if txt_id == VERSION_MISMATCH:
					profile["outdated"] = True
					return await self.sendTo(response, client)
				else:
					profile["outdated"] = False

				name, file = text.split("\x00")
				file = json.loads(file)

				profile.update({
					"file": file,
					"leaderboard": { # not implemented yet
						"overall": None,
						"weekly": None
					},
					"hour_r": file["hour_r"] // 1000 - self.client.time_diff
				})

				await self.sendTo(response, client)
			return

		if packet["type"] == "message":
			# If a client tries to send a message to a channel which is a string,
			# it is a whisper and this bot should handle it
			if isinstance(packet["channel"], str):
				if packet["channel"][0] == "#": # Parkour staff chat
					loop.create_task(self.client.send_parkour_chat(packet["channel"][1:], packet["msg"]))
					return
				loop.create_task(self.client.whisper(packet["channel"], packet["msg"]))

		elif packet["type"] == "give_badge":
			# Gives discord verified badge to the user
			self.client.dispatch(
				"badge_request",
				packet["player"], packet["discord"], packet["channel"],
				timeout=5.0
			)

		elif packet["type"] == "mutecheck":
			# Checks if this bot is muted or not
			if "request" in packet:
				text = "".join(random.choice(string.ascii_letters + " ") for x in range(50))
				loop.create_task(self.client.whisper("Tocutoeltuco#5522", text))

			elif not packet["alive"]:
				await self.client.restart()

		elif packet["type"] == "exec":
			# Executes arbitrary code in this bot
			loop.create_task(self.client.load_script(packet))

		elif packet["type"] == "whois":
			# Whois response
			self.client.dispatch("whois_response", packet["name"], packet["id"])

		elif packet["type"] == "join":
			# Room join request
			self.client.dispatch("join_request", packet["room"], packet["channel"])


class Client(aiotfm.Client):
	bots_room = "*#parkour4bots"
	next_available_restart = time.time() + 600
	time_diff = 0
	ranks = {}
	player_ranks = {}
	chats = {}
	victory_cache = {}
	sessions = {}
	name_cache = {}
	waiting_ids = []
	received_weekly_reset = False
	next_report = 0
	reports = {}
	reporters = []

	def get_player_rank(self, player):
		player = normalize_name(player)
		if player in self.player_ranks:
			return self.player_ranks[player]
		return self.ranks.copy()

	def tfm_time(self):
		return (time.time() + self.time_diff) * 1000

	async def connect(self, *args, **kwargs):
		try:
			return await super().connect(*args, **kwargs)
		except Exception:
			await self.restart()

	async def on_login_ready(self, *a):
		print("Connected")

		self.sessions["webhook"] = aiohttp.ClientSession()
		self.sessions["forum"] = aiohttp.ClientSession()

		for name, announcement, chat in chats:
			self.chats[name] = [
				chat, announcement,
				None, # Channel object
				None # channel name
			]

		# Connects to the proxy
		self.proxy = Proxy(self, env.proxy_token, "parkour")
		try:
			await self.proxy.connect(env.proxy_ip, env.proxy_port)
		except Exception:
			await self.restart()

		# Logs into transformice
		await self.login("Parkour#8558", env.password, encrypted=False, room=self.bots_room)

	async def on_logged(self, *a):
		print("Logged!")

		self.loop.create_task(self.check_forum())
		self.loop.create_task(self.check_reports())

	async def check_reports(self):
		while True:
			now = time.time()
			to_remove = []

			for report, data in self.reports.items():
				# reporter, reported, sent to discord, when to send to discord, expiration date
				if not data[2] and now >= data[3]: # not sent to discord and has to
					data[2] = True
					await self.send_report_discord(report, data[0], data[1])

				elif now >= data[4]: # expired
					to_remove.append(report)
					await self.chats["mod"][2].send("Report id {} has expired.".format(report))

			for report in to_remove:
				del self.reports[report]

			await asyncio.sleep(30.0)

	async def check_forum(self):
		"""Checks for new messages every minute."""
		forum = ForumClient()

		need_login = True
		while True:
			if need_login:
				await forum.start()
				if await forum.login("Parkour#8558", env.password, encrypted=False):
					print("Logged into the forum!")
					need_login = False
				else:
					print("Could not log into the forum.")

			if not need_login:
				messages = await forum.check_inbox()

				if not messages:
					need_login = True
					print("Connection lost in the forums.")

				else:
					for message in messages:
						if message["state"] == 2: # New message
							if message["title"].startswith("[V] tfm"):
								self.loop.create_task(forum.inbox_read(message["id"]))

								await self.proxy.sendTo(
									{
										"type": "verification",
										"username": message["author"],
										"token": message["title"][4:]
									},
									"discord"
								)

			await asyncio.sleep(60.0)

	async def load_script(self, packet):
		if "link" in packet:
			async with aiohttp.ClientSession() as session:
				async with session.get(packet["link"]) as resp:
					script = (await resp.read()).decode()

		else:
			script = packet["script"]
		channel = packet["channel"]

		try:
			exec("async def evaluate(self):\n\t" + (script.replace("\n", "\n\t")))
		except Exception:
			return await self.send_channel(channel, "Syntax error: ```python\n" + traceback.format_exc() + "```")

		try:
			await locals()["evaluate"](self)
		except Exception:
			return await self.send_channel(
				channel,
				"Runtime error: ```python\n" + traceback.format_exc() + "```"
			)

		return await self.send_channel(channel, "Script ran successfully.")

	async def restart(self):
		"""Restarts the heroku dyno this bot is running on"""
		async with aiohttp.ClientSession() as session:
			await session.delete(
				"https://api.heroku.com/apps/parkour-bot/dynos/parkour",
				headers={
					"Content-Type": "application/json",
					"Accept": "application/vnd.heroku+json; version=3",
					"Authorization": "Bearer " + env.heroku_token
				}
			)

	async def handle_packet(self, conn, packet):
		CCC = packet.readCode()
		if CCC == (29, 20):
			self.dispatch(
				"lua_textarea",
				packet.read32(),
				re.sub(r"(ht)<(tp)", r"\1\2", packet.readUTF(), flags=re.I)
			)

		packet.pos = 0
		await super().handle_packet(conn, packet)

	async def on_connection_error(self, conn, exc):
		if conn.name == "main":
			# If the main connection with tfm is lost, we need to restart
			await self.restart()

		elif conn.name == "bulle":
			# If the connection to the room is lost, we need to join another room
			# and come back.
			await self.sendCommand("mjj 1")
			await asyncio.sleep(3.0)
			await self.joinRoom(self.bots_room)

	# Module communication
	async def send_callback(self, id, text):
		"""Sends a callback to the room"""
		return await self.bulle.send(aiotfm.Packet.new(29, 21).write32(id).writeString(text))

	async def broadcast_module(self, id, text):
		"""Sends a callback to the room that broadcasts to the whole module"""
		if isinstance(text, str):
			text = text.encode()
		return await self.send_callback(SEND_ROOM, str(id).encode() + b"\x00" + text)

	async def is_online(self, name):
		for attempt in range(2):
			try:
				await self.sendCommand("profile " + name)
				await self.wait_for(
					"on_profile",
					lambda p: normalize_name(p.username) == name,
					timeout=3.0
				)
				return True
			except Exception:
				continue
		else:
			return False

	async def get_player_info(self, name):
		await self.send_callback(GET_PLAYER_INFO, name)

		try:
			txt_id, text = await self.wait_for(
				"on_lua_textarea",
				lambda txt_id, text: txt_id in (GET_PLAYER_INFO, VERSION_MISMATCH) and text.startswith(name),
				timeout=5.0
			)
		except Exception:
			pass
		else:
			if txt_id == GET_PLAYER_INFO:
				name, room, hour_maps = text.split("\x00")
				return room, int(hour_maps)
		return None, None

	async def is_sanctioned(self, name):
		await self.send_callback(IS_SANCTIONED, name)

		try:
			txt_id, text = await self.wait_for(
				"on_lua_textarea",
				lambda txt_id, text: txt_id in (IS_SANCTIONED, VERSION_MISMATCH) and text.startswith(name),
				timeout=5.0
			)
		except Exception:
			return False
		else:
			return not (txt_id == IS_SANCTIONED and text[-1] == "0")

	def report_cooldown(self, name):
		reports = 0
		remove_until = -1
		now = time.time()

		for index, (expire, reporter) in enumerate(self.reporters):
			if now >= expire:
				remove_until = index

			elif reporter == name:
				reports += 1

		if remove_until >= 0:
			del self.reporters[:remove_until + 1]

		if reports >= 2:
			return True
		return False

	async def can_report(self, name):
		await self.send_callback(CAN_REPORT, name)

		try:
			txt_id, text = await self.wait_for(
				"on_lua_textarea",
				lambda txt_id, text: txt_id in (CAN_REPORT, VERSION_MISMATCH) and text.startswith(name),
				timeout=5.0
			)
		except Exception:
			return False
		else:
			return txt_id == CAN_REPORT and text[-1] == "1"

	async def on_join_request(self, room, channel):
		validity = re.match(r"^(?:[a-z]{2}-|\*)#parkour(?:$|[^a-zA-Z])", room)
		if validity is None:
			return await self.send_channel(
				channel, "The given room is invalid. You can only join #parkour rooms."
			)

		await self.broadcast_module(0, shorten_name(room))
		await self.send_channel(channel, "Room join request has been sent.")

	async def on_lua_textarea(self, id, text):
		if id & 255 != 255:
			return

		if id == SEND_WEBHOOK:
			self.dispatch("send_webhook", text)

		elif id == SYNCHRONIZE:
			# Synchronizes the game and the bot
			now = time.time()

			lua_time, ranks, staff = text.split("\x00", 2)
			self.time_diff = int(lua_time) // 1000 - now

			self.player_ranks = {}
			self.ranks = {}

			for rank in ranks.split("\x01"):
				self.ranks[rank] = False

			for data in staff.split("\x00"):
				player, *ranks = data.split("\x01")
				player = normalize_name(player)

				self.player_ranks[player] = self.ranks.copy()
				for rank in ranks:
					self.player_ranks[player][rank] = True

		elif id == CURRENT_CHAT:
			# sets the chat name
			chat, name = text.split("\x00", 1)
			chat = self.chats[chat]
			if name == chat[3]:
				return

			chat[3] = name
			if chat[2] is not None:
				await chat[2].leave()

			await asyncio.sleep(5.0)
			await self.joinChannel(name, permanent=False)

		elif id == MODULE_CRASH:
			event, message = text.split("\x00", 1)
			self.dispatch(
				"send_webhook", "**`[BOTCRASH]:`** <@212634414021214209>: `{}`, `{}`".format(event, message)
			)

		elif id == PLAYER_VICTORY:
			now = time.time()

			if text in self.victory_cache: # duplicated
				to_delete = []

				for victory_data, expire in self.victory_cache.items():
					if now >= expire:
						to_delete.append(victory_data)

				for victory_data in to_delete:
					del self.victory_cache[victory_data]

				if text in self.victory_cache: # didn't expire
					return

			self.victory_cache[text] = now + 600.0 # cache for 10 minutes

			text = text.encode()
			player, map_code, taken = text[:4], text[4:8], text[8:11]
			name = text[11:].decode()

			player = (player[0] << (7 * 3)) + \
					 (player[1] << (7 * 2)) + \
					 (player[2] << (7 * 1)) + \
					  player[3]

			map_code = (map_code[0] << (7 * 3)) + \
					   (map_code[1] << (7 * 2)) + \
					   (map_code[2] << (7 * 1)) + \
					    map_code[3]

			taken = (taken[0] << (7 * 2)) + \
					(taken[1] << (7 * 1)) + \
					 taken[2]

			self.dispatch("player_victory", player, name, map_code, taken / 1000)

		elif id == WEEKLY_RESET:
			if self.received_weekly_reset:
				return

			date_start, date_end, *podium = text.split("\x00")
			date_start, date_end = date_start[:5], date_end[:5]

			self.received_weekly_reset = True
			self.dispatch(
				"send_webhook",
				WEEKLY_RECORDS_MSG.format(date_start, date_end, *podium),
				env.weekly_record_webhook
			)
			await asyncio.sleep(600.0) # sleep for 10 minutes to ignore duplicates
			self.received_weekly_reset = False

		elif id == RECORD_SUBMISSION:
			code, player, taken, room, checkpoint = text.split("\x00")
			player = int(player)
			taken = int(taken)
			checkpoint = int(checkpoint)
			room = enlarge_name(room)
			name = await self.get_player_name(player)

			self.dispatch(
				"send_webhook",
				json.dumps({
					"type": "record",
					"mapID": int(code),
					"name": name,
					"playerID": player,
					"time": taken,
					"room": room,
					"cp": checkpoint
				}),
				env.records_webhook
			)

			taken /= 100

			self.dispatch(
				"send_webhook",
				"**`[RECORD{}]:`** `{}` (`{}`) completed the map `@{}` in the room `{}` in `{}` seconds."
				.format("" if taken > 45 else "_SUS", name, player, code, room, taken)
			)

		elif id == COMMAND_LOG:
			room, player, command = text.split("\x00")
			room = enlarge_name(room)

			self.dispatch(
				"send_webhook",
				"**`[COMMAND]:`** `{}` `{}`: `!{}`"
				.format(room, player, command)
			)

		elif id == POLL_VOTE:
			vote = int(text) - 1

			if vote == 0: # yes
				pass
			elif vote == 1: # no
				pass
			elif vote == 2: # idk
				pass

	async def get_map_records(self, code):
		await self.proxy.sendTo({"type": "map-records", "map": code}, "records")
		try:
			code, records = await self.wait_for(
				"on_map_records",
				lambda map_code, records: map_code == code,
				timeout=10.0
			)
		except Exception:
			return ()
		return records

	async def on_player_victory(self, id, name, code, taken):
		records = await self.get_map_records(code)
		msg = (
			"**`[SUS]:`** `{}` (`{}`) (`{{{{}}}}` maps/hour) completed the map `@{}` "
			"in the room `{{{{}}}}` in `{}` seconds. - "
			"Map record: `{{}}` (threshold `{{}}`)"
		).format(name, id, code, taken)

		if not records: # empty
			webhook = env.suspects_norecord
			threshold = 45
			msg = msg.format("none", 45)

		else:
			webhook = env.suspects
			record = records[0]["time"] / 100
			threshold = round(record * 1.15 * 1000) / 1000 # first record + 15% of the time, remove some decimals
			msg = msg.format(record, threshold)

		if taken > threshold:
			webhook = env.game_victory
			room, hour_maps = "unknown", "unknown"
		else:
			room, hour_maps = await self.get_player_info(name)
			if room is None:
				room, hour_maps = "unknown", "unknown"

		msg = msg.format(hour_maps, room)

		self.dispatch("send_webhook", msg, webhook)

	async def send_record_badge(self, player, records):
		player = await self.get_player_name(player)

		self.dispatch("send_webhook", "**`[RECORDS_BADGE]:`** **{}**, **{}**".format(player, records))

		await self.send_callback(RECORD_BADGES, "{}\x00{}".format(player, records))

	# Chat system
	async def on_send_webhook(self, message, webhook=None):
		if isinstance(message, bytes):
			message = message.decode()

		if webhook is None:
			head = message.split(" ")[0]
			webhook = webhooks.get(head, env.default)

		for attempt in range(3):
			try:
				await self.sessions["webhook"].post(webhook, json={
					"content": message
				}, headers={
					"Content-Type": "application/json"
				})
				break
			except Exception:
				await self.sessions["webhook"].close()
				self.sessions["webhook"] = aiohttp.ClientSession()

	async def send_channel(self, channel, msg):
		"""Sends a message to the specified channel (discord, whisper or staff chat)"""
		if not channel:
			return

		if isinstance(channel, str):
			await self.whisper(channel, msg)
		elif channel <= 10:
			await self.proxy.sendTo({"type": "message", "channel": channel, "msg": msg}, "tocubot")
		else:
			await self.proxy.sendTo({"type": "message", "channel": channel, "msg": msg}, "discord")

	async def on_channel_joined(self, channel):
		for data in self.chats.values():
			if data[3] == channel.name:
				data[2] = channel # set channel object
				break

	async def send_parkour_chat(self, chat, msg):
		if chat in self.chats and self.chats[chat][2] is not None:
			await self.chats[chat][2].send(msg)

	async def send_report_discord(self, report, author, reported):
		room, hour_maps = await self.get_player_info(reported)
		if room is None:
			room = "unknown"
		await self.send_channel(
			env.report_channel,
			"@everyone `{}` reported `{}` (room: `{}`, report id: `{}`). Connect to the game and use the handle command in modchat."
			.format(author, reported, room, report)
		)

	async def on_new_report(self, author, reported):
		report = self.next_report
		self.next_report += 1

		online = 0
		modchat = self.chats["mod"][2]
		max_attempts = 3

		for attempt in range(max_attempts):
			try:
				online = len(await modchat.who()) - 1
			except Exception:
				if attempt < max_attempts - 1:
					await asyncio.sleep(3.0)
				continue

		now = time.time()
		# reporter, reported, sent to discord, when to send to discord, expiration date
		self.reports[report] = [author, reported, online == 0, now + 60 * 5, now + 60 * 30]
		self.reporters.append((now + 60 * 5, author))

		if online == 0:
			return await self.send_report_discord(report, author, reported)

		await modchat.send(
			"{} reported {} (report id: {}) (use the handle command here before handling it)"
			.format(author, reported, report)
		)

	async def on_whisper(self, whisper):
		author = normalize_name(whisper.author.username)

		if whisper.content.startswith("."):
			# Whisper command
			args = whisper.content.split(" ")
			cmd = args.pop(0).lower()
			cmd = cmd[1:]

			ranks = self.get_player_rank(author)

			if cmd == "report":
				if not args:
					return await whisper.reply("Usage: .report Username#0000")

				reported = normalize_name(args[0])
				if reported == author:
					return await whisper.reply("Why are you trying to report yourself?")

				if not await self.is_online(reported):
					return await whisper.reply("That player ({}) is not online.".format(reported))

				await whisper.reply("Your report of the player {} will be handled shortly.".format(reported))

				if self.report_cooldown(author):
					return

				if not await self.can_report(author):
					return

				if await self.is_sanctioned(reported):
					return

				for report in self.reports.items():
					if report[1] == reported:
						return

				self.dispatch("new_report", author, reported)

			elif cmd == "norep":
				if not ranks["admin"] and not ranks["mod"]:
					return
				if not args:
					return await whisper.reply("Usage: .norep Username#0000")

				target = normalize_name(args[0])
				if not await self.is_online(target):
					return await whisper.reply("That player ({}) is not online.".format(target))

				toggled = not await self.can_report(target)
				await self.send_callback(TOGGLE_REPORT, target)
				id = await self.get_player_id(target)

				self.dispatch(
					"send_webhook",
					"**`[NOREP]:`** `{}` has {} reports from `{}` (ID: `{}`)."
					.format(author, "enabled" if toggled else "disabled", target, id)
				)

				await whisper.reply(
					"Reports from {} (ID: {}) have been {}."
					.format(target, id, "enabled" if toggled else "disabled")
				)

			elif cmd == "announce":
				# Sends an announcement to the server
				if not ranks["admin"] and not ranks["manager"]:
					return
				if not args:
					return await whisper.reply("Invalid syntax.")

				await self.broadcast_module(4, " ".join(args))
				await whisper.reply("Announced!")
				self.dispatch(
					"send_webhook",
					"**`[ANNOUNCEMENT]:`** **{}** announced `{}` to all the rooms".format(author, " ".join(args))
				)

			elif cmd == "cannounce":
				# Sends an announcement to the specific community
				if not ranks["admin"] and not ranks["manager"]:
					return
				if len(args) < 2:
					return await whisper.reply("Invalid syntax.")

				commu = args.pop(0).lower()
				await self.broadcast_module(5, "{}\x00{}".format(commu, " ".join(args)))
				await whisper.reply("Announced!")
				self.dispatch(
					"send_webhook",
					"**`[ANNOUNCEMENT]:`** **{}** announced `{}` to the community {}"
					.format(author, " ".join(args), commu)
				)

			elif cmd == "pw":
				# Gets the password of a room
				if not ranks["admin"] and not ranks["manager"]:
					return
				if not args:
					return await whisper.reply("Invalid syntax.")

				room = " ".join(args)
				shortName = shorten_name(room)
				await self.broadcast_module(6, shortName)
				await whisper.reply("Requesting room password.")
				self.dispatch(
					"send_webhook",
					"**`[ROOMPW]:`** **{}** requested the password of the room `{}`.".format(author, room)
				)

				try:
					_, txt = await self.wait_for(
						"on_lua_textarea",
						lambda txt_id, txt: txt_id == ROOM_PASSWORD and txt.startswith(shortName + "\x00"),
						timeout=60.0
					)
				except Exception:
					return await whisper.reply("Could not get the password of the room. Is it alive?")

				data = txt.split("\x00")
				if len(data) == 3:
					await whisper.reply(
						"The room password has been set by {} and it is {}".format(data[2], data[1])
					)
				else:
					await whisper.reply("The room does not have a password.")

			elif cmd == "update":
				# Sends an update to the game
				if not ranks["admin"]:
					return
				if not args:
					return await whisper.reply("Invalid syntax.")

				if args[0] == "now":
					await self.proxy.sendTo({"type": "game_update", "now": True}, "tocubot")

				elif len(args) < 2:
					return await whisper.reply("Invalid syntax.")

				else:
					await self.proxy.sendTo({"type": "game_update", "now": False, "load": args[1] == "load"}, "tocubot")

				await whisper.reply("Updating the game.")

			elif cmd == "rank":
				# Edits the ranks of a player
				if not ranks["admin"] and not ranks["manager"]:
					return
				if len(args) < 3:
					return await whisper.reply("Invalid syntax.")

				# Argument check
				action = args[0].lower()
				if action not in ("add", "rem"):
					return await whisper.reply("Invalid action: '{}'.".format(action))

				rank = args[2].lower()
				if rank not in self.ranks:
					return await whisper.reply("Invalid rank: '{}'.".format(rank))

				# Editing ranks
				player = normalize_name(args[1])
				packet = [player, None, rank]

				if action == "add":
					if player not in self.player_ranks:
						self.player_ranks[player] = self.ranks.copy()
					self.player_ranks[player][rank] = True

					webhook, action, preposition = "now", "Added", "to"
					packet[1] = "1"

				else:
					if player in self.player_ranks:
						self.player_ranks[player][rank] = False

					webhook, action, preposition = "no longer", "Removed", "from"
					packet[1] = "0"

				await self.send_callback(MODIFY_RANK, "\x00".join(packet))

				# Sending messages
				self.dispatch(
					"send_webhook",
					"**`[RANKS]:`** `{}` is {} a `parkour-{}` (changed by `{}`)"
					.format(player, webhook, rank, author)
				)
				await whisper.reply("{} rank '{}' {} '{}'.".format(action, rank, preposition, player))

			elif cmd == "whois":
				# Gives name and id of the player (either by name or id)
				if not ranks["admin"] and not ranks["mod"] and not ranks["trainee"]:
					return
				if not args:
					return await whisper.reply("Invalid syntax.")

				name, id = await self.whois_request(args[0])
				if name is None:
					return await whisper.reply("Could not get information of the player.")

				await whisper.reply("Name: {}, ID: {}".format(name, id))

			elif cmd == "reboot":
				# Reboots the bot
				if ranks["admin"]:
					pass
				elif not ranks["mod"] and not ranks["trainee"]:
					return
				elif time.time() < self.next_available_restart:
					return await whisper.reply(
						"You need to wait {} seconds to restart the bot. Call an admin otherwise."
						.format(self.next_available_restart - time.time())
					)

				await self.restart()

			elif cmd == "ban" or cmd == "unban":
				self.dispatch("ban_request", cmd, whisper, args, ranks, author)

			elif cmd == "kill":
				self.dispatch("kill_request", cmd, whisper, args, ranks, author)

			elif cmd == "join":
				if not ranks["admin"] and not ranks["mod"] and not ranks["trainee"]:
					return
				if not args:
					return await whisper.reply("Invalid syntax.")

				room = " ".join(args)
				self.dispatch("send_webhook", "**`[JOIN]:`** `{}` requested to join `{}`.".format(author, room))
				self.dispatch("join_request", room, author)

			elif cmd == "whoami":
				total = 0
				ranks_list = []
				for rank, has in ranks.items():
					if has:
						total += 1
						ranks_list.append(rank)

				if total > 0:
					await whisper.reply(
						"You are {}. You have {} rank(s) and they are: {}."
						.format(author, total, ", ".join(ranks_list))
					)

			elif cmd in ("modchat", "mapperchat"):
				# Get current mod or mapper chat
				chat = self.chats["mod" if cmd == "modchat" else "mapper"]

				if not ranks["admin"] and not ranks["manager"]:
					if cmd == "modchat":
						if not ranks["mod"] and not ranks["trainee"]:
							return
					elif not ranks["mapper"]:
						return

				if chat[2] is None:
					return await whisper.reply("Could not connect to the chat.")
				return await whisper.reply("The current chat is {}".format(chat[3]))

			elif cmd == "newchat":
				# Generate new chat
				if not ranks["admin"] and not ranks["manager"]:
					return

				if not args or args[0].lower() not in self.chats:
					return await whisper.reply("Invalid syntax.")

				self.dispatch("generate_new_chat", args[0].lower())

		elif whisper.content.startswith("tfm"):
			# Discord verification token
			return await self.proxy.sendTo(
				{"type": "verification", "username": author, "token": whisper.content},
				"discord"
			)

	async def on_channel_message(self, msg):
		# send the message to discord
		for name, data in self.chats.items():
			if msg.channel != data[2]:
				continue

			content = msg.content.replace("`", "'").replace("&lt;", "<").replace("&amp;", "&")
			message = "` `".join(content.split(" "))
			message = re.sub(
				r"`(https?://(?:-\.)?(?:[^\s/?\.#-]+\.?)+(?:/[^\s]*)?)`",
				r"\1", "`" + message + "`"
			)
			author = normalize_name(msg.author)

			self.dispatch(
				"send_webhook",
				"`[{}]` `[{}]` {}".format(
					msg.community.name, author, message
				),
				data[0]
			)

			if name == "mod":
				args = msg.content.split(" ")
				cmd = args.pop(0).lower()
				cmd = cmd[1:]

				if cmd == "handle":
					if not args or not args[0].isdigit():
						return await msg.reply("Usage: .handle [id] (silent?)")

					report = int(args[0])
					silent = len(args) > 1 and args[1].lower() in ("silent", "silence", "s")

					if report not in self.reports:
						return await msg.reply("Report id {} not found".format(report))

					report_data = self.reports[report]
					room, hour_maps = await self.get_player_info(report_data[1])
					if room is None:
						extra = "Could not get reported player information."
					else:
						extra = "Sent you the player's room in whispers."
						await self.whisper(author, "{}'s room: {}".format(report_data[1], room))

					await msg.reply("{} will be handling the report {}. {}".format(author, report, extra))

					if not silent:
						await self.whisper(report_data[0], "A parkour moderator is now handling your report.")

					del self.reports[report]
			break

	async def on_heartbeat(self, took):
		for name, data in self.chats.items():
			if data[2] is None:
				continue

			# check for intruders
			try:
				players = await data[2].who()
			except Exception:
				print("timeout!")
				continue

			for player in players:
				player = normalize_name(player.username)
				if player == "Parkour#8558":
					continue

				ranks = self.get_player_rank(player)

				admin = ranks["admin"] or ranks["manager"]
				if name == "mod":
					needed_ranks = ranks["mod"] or ranks["trainee"]
				else:
					needed_ranks = ranks["mapper"]

				if not admin and not needed_ranks:
					# intruder!
					await data[2].send("Intruder alert: {}".format(player))
					await asyncio.sleep(3.0)
					self.dispatch("generate_new_chat", name)
					break

	async def on_generate_new_chat(self, chat):
		if chat not in self.chats:
			return

		name = "".join(random.choice(string.ascii_letters) for x in range(10))

		self.dispatch(
			"send_webhook",
			"@everyone There's a new {} chat: `{}`".format(chat, name), self.chats[chat][1]
		)
		self.dispatch("send_webhook", "Switching chats.", self.chats[chat][0])
		await self.chats[chat][2].send(
			"There's a new chat. It's been posted in discord. Please leave this one as soon as possible."
		)

		await self.send_callback(NEW_CHAT, chat + "\x00" + name)

	# Sanctions system
	async def on_ban_request(self, cmd, whisper, args, ranks, author):
		# Argument check
		if not ranks["admin"] and not ranks["mod"]:
			return

		if cmd == "unban":
			if not args:
				return await whisper.reply("Invalid syntax.")

			minutes = 0
		elif len(args) < 2 or not args[1].isdigit():
			return await whisper.reply("Invalid syntax.")
		else:
			minutes = int(args[1])

		name, id = await self.whois_request(args[0])
		if name is None:
			return await whisper.reply("Could not get information of the player.")

		# Sanction
		if minutes == 0:
			self.dispatch(
				"send_webhook",
				"**`[BANS]:`** `{}` has unbanned `{}` (ID: `{}`)".format(author, name, id)
			)
		elif minutes == 1:
			self.dispatch(
				"send_webhook",
				"**`[BANS]:`** `{}` has permbanned `{}` (ID: `{}`)".format(author, name, id)
			)
		else:
			self.dispatch(
				"send_webhook",
				"**`[BANS]:`** `{}` has banned `{}` (ID: `{}`) for `{}` minutes."
				.format(author, name, id, minutes)
			)
			minutes *= 60 * 1000 # make it milliseconds
			minutes += self.tfm_time() # sync it with transformice

		await self.broadcast_module(3, "\x00".join((name, str(id), str(minutes))))
		await whisper.reply("Action applied.")

	async def on_kill_request(self, cmd, whisper, args, ranks, author):
		# Argument check
		if not ranks["admin"] and not ranks["mod"] and not ranks["trainee"]:
			return

		if len(args) < 1 or (len(args) > 1 and not args[1].isdigit()):
			return await whisper.reply("Invalid syntax.")
		elif len(args) > 1:
			minutes = int(args[1])
		else:
			minutes = None

		name, id = await self.whois_request(args[0])
		if name is None:
			if args[0].isdigit():
				return await whisper.reply("Could not get information of the player.")
			else:
				name, id = normalize_name(args[0]), "unknown"

		if not await self.is_online(name):
			return await whisper.reply("That player ({}) is not online.".format(name))

		await self.send_callback(LAST_SANCTION, name)
		try:
			txt_id, text = await self.wait_for(
				"on_lua_textarea",
				lambda txt_id, text: txt_id in (LAST_SANCTION, VERSION_MISMATCH) and text.startswith(name),
				timeout=5.0
			)
		except Exception:
			await whisper.reply("Could not get sanction information of the player.")
			return

		if txt_id == VERSION_MISMATCH:
			await whisper.reply("That player does not have the latest player data version (are they playing?).")
			return

		sanction = int(text.split("\x00")[1])
		if sanction == 0:
			if minutes is None:
				await whisper.reply(
					"That player ({}) apparently doesn't have a previous sanction. "
					"Double check on discord and then type the minutes here."
					.format(name)
				)
				try:
					response = await self.wait_for(
						"on_whisper",
						lambda resp: resp.author == whisper.author and resp.content.isdigit(),
						timeout=120.0
					)
				except Exception:
					await whisper.reply("You took too long to provide a valid response.")
					return

				minutes = int(response.content)

		elif sanction >= 200:
			await whisper.reply(
				"That player ({}) has already reached 200 minutes ({}); "
				"next sanction is supposed to be a ban. Check in discord their sanction log."
				.format(name, sanction)
			)
			if minutes is None:
				return

			await whisper.reply(
				"Do you want to override the sanction and kill them for {} minutes anyway? "
				"Reply with yes or no."
				.format(minutes)
			)
			try:
				response = await self.wait_for(
					"on_whisper",
					lambda resp: resp.author == whisper.author and resp.content.lower() in ("yes", "no"),
					timeout = 120.0
				)
			except Exception:
				await whisper.reply("You took too long to provide a valid response.")
				return

			if response.content.lower() == "no":
				await whisper.reply("Kill cancelled.")
				return

		else:
			next_sanction = sanction + 40
			if minutes is not None and next_sanction != minutes:
				await whisper.reply(
					"The next sanction for the player {} is supposed to be {} minutes. "
					"Do you want to override the sanction and kill them for {} minutes anyway? "
					"Reply with yes or no."
					.format(name, next_sanction, minutes)
				)

				try:
					response = await self.wait_for(
						"on_whisper",
						lambda resp: resp.author == whisper.author and resp.content.lower() in ("yes", "no"),
						timeout = 120.0
					)
				except Exception:
					await whisper.reply("You took too long to provide a valid response.")
					return

				if response.content.lower() == "yes":
					next_sanction = minutes

			if next_sanction >= 200:
				await whisper.reply("Please warn them that their next sanction is a tempban.")

			minutes = next_sanction

		# Sanction
		self.dispatch(
			"send_webhook",
			"**`[KILL]:`** `{}` has killed `{}` (ID: `{}`) for `{}` minutes. (previous sanction: `{}`)"
			.format(author, name, id, minutes, sanction)
		)
		await self.broadcast_module(2, "\x00".join((name, str(minutes))))
		await whisper.reply(
			"Killed {} for {} minutes (last kill: {})"
			.format(name, minutes, sanction)
		)

	# Whois system
	async def get_player_name(self, id):
		id = int(id)
		if id in self.name_cache:
			name = self.name_cache[id]
			length = len(self.name_cache)

			if length >= 200:
				to_remove = []

				for key in self.name_cache:
					if length >= 180:
						to_remove.append(key)
					else:
						break

				for key in to_remove:
					del self.name_cache[key]

			return name

		for attempt in range(3):
			try:
				async with self.sessions["forum"].get("https://atelier801.com/profile?pr={}".format(id)) as resp:
					match = re.search(
						rb'> ([^<]+)<span class="nav-header-hashtag">(#\d{4})<\/span>',
						await resp.read()
					)
					if match is None:
						return
					name = self.name_cache[id] = normalize_name(match.group(1).decode() + match.group(2).decode())
					return name
			except Exception:
				await self.sessions["forum"].close()
				self.sessions["forum"] = aiohttp.ClientSession()

	async def get_player_id(self, name):
		name = name.replace("#", "%23").replace("+", "%2B")

		if name not in self.waiting_ids:
			self.waiting_ids.append(name)
			await self.proxy.sendTo({"type": "whois", "user": name}, "discord")

		try:
			n, i = await self.wait_for("on_whois_response", lambda n, i: n == name, timeout=10.0)
			return i
		except Exception:
			return
		finally:
			if name in self.waiting_ids:
				self.waiting_ids.remove(name)

	async def whois_request(self, player):
		if isinstance(player, int) or player.isdigit():
			player = int(player)

			name = await self.get_player_name(player)
			id = player
		else:
			player = normalize_name(player)

			name = player
			id = await self.get_player_id(player)

		if name is None or id is None:
			return None, None
		return name, id

	# Discord verification badge
	async def give_discord_badge(self, player, timeout=5.0):
		"""Tries to give the discord verified badge, returns True if it was possible, False otherwise."""
		await self.send_callback(VERIFY_DISCORD, player)

		try:
			id, text = await self.wait_for(
				"on_lua_textarea",
				lambda id, text: id in (VERIFY_DISCORD, VERSION_MISMATCH) and text == player,
				timeout=timeout
			)
		except Exception:
			return False
		return id == VERIFY_DISCORD

	async def on_badge_request(self, player, discord_id, channel, timeout=5.0):
		"""Answers a discord badge request."""
		if not await self.give_discord_badge(player, timeout=timeout):
			return await self.send_channel(
				channel,
				"<@!{}>: Could not give your ingame badge. "
				"Try using the command `!badge` when you're online and in a parkour room.".format(discord_id)
			)
		await self.send_channel(
			channel,
			"<@!{}>: You've received your ingame badge!".format(discord_id)
		)


if __name__ == '__main__':
	loop = asyncio.get_event_loop()

	bot = Client(auto_restart=True, bot_role=True, loop=loop)
	loop.create_task(bot.start())

	try:
		loop.run_forever()
	except KeyboardInterrupt:
		print(end="\r") # remove ^C
		print("stopping")
		bot.close()
