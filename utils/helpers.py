import json
import discord
from utils.emojis import e

def load_config():
    with open("config.json", "r", encoding="utf-8") as f:
        return json.load(f)

def success_embed(titulo: str, descricao: str = None, cor=0x2ecc71):
    em = discord.Embed(title=f"{e.correct} {titulo}", description=descricao, color=cor)
    return em

def error_embed(titulo: str, descricao: str = None, cor=0xe74c3c):
    em = discord.Embed(title=f"{e.wrong} {titulo}", description=descricao, color=cor)
    return em

def info_embed(titulo: str, descricao: str = None, cor=0x3498db):
    em = discord.Embed(title=f"{e.information} {titulo}", description=descricao, color=cor)
    return em

def warn_embed(titulo: str, descricao: str = None, cor=0xf39c12):
    em = discord.Embed(title=f"{e.warn} {titulo}", description=descricao, color=cor)
    return em

def is_owner(user_id: int, config: dict) -> bool:
    return str(user_id) == str(config.get("owner_id", ""))

async def is_bot_admin(user_id: int) -> bool:
    from database.db import is_admin
    return is_admin(str(user_id))
