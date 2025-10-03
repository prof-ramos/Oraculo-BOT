import datetime
import asyncio
from typing import Optional
from pathlib import Path
import tempfile
import os

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from .moderation_logger import ModerationLogger

# RAG system imports
try:
    from rag.rag_system import RAGSystem
except ImportError:
    RAGSystem = None


class AdminCog(commands.Cog):
    """Cog for administrative moderation commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.logger = ModerationLogger()

    @commands.hybrid_command(name="ban", description="Ban a user from the server.")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @app_commands.describe(user="The user to ban", reason="Reason for the ban")
    async def ban_user(
        self,
        ctx: commands.Context,
        user: discord.Member,
        *,
        reason: Optional[str] = None,
    ):
        if user == ctx.author:
            return await ctx.send("You cannot ban yourself.")
        if user == self.bot.user:
            return await ctx.send("You cannot ban the bot.")

        try:
            await user.ban(reason=reason)
            await self.logger.log_action({
                "type": "ban",
                "user": user.id,
                "reason": reason,
                "moderator": str(ctx.author),
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })
            embed = discord.Embed(
                title="User Banned",
                description=f"{user.mention} has been banned from the server.",
                color=discord.Color.red(),
            )
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(
                name="Moderator", value=ctx.author.mention, inline=True
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I do not have permission to ban this user.")
        except discord.HTTPException:
            await ctx.send("Failed to ban the user.")

    @commands.hybrid_command(name="kick", description="Kick a user from the server.")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @app_commands.describe(user="The user to kick", reason="Reason for the kick")
    async def kick_user(
        self,
        ctx: commands.Context,
        user: discord.Member,
        *,
        reason: Optional[str] = None,
    ):
        if user == ctx.author:
            return await ctx.send("You cannot kick yourself.")
        if user == self.bot.user:
            return await ctx.send("You cannot kick the bot.")

        try:
            await user.kick(reason=reason)
            await self.logger.log_action({
                "type": "kick",
                "user": user.id,
                "reason": reason,
                "moderator": str(ctx.author),
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })
            embed = discord.Embed(
                title="User Kicked",
                description=f"{user.mention} has been kicked from the server.",
                color=discord.Color.orange(),
            )
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(
                name="Moderator", value=ctx.author.mention, inline=True
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I do not have permission to kick this user.")
        except discord.HTTPException:
            await ctx.send("Failed to kick the user.")

    @commands.hybrid_command(
        name="mute", description="Mute a user for a specified duration."
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(
        user="The user to mute",
        duration="Duration in minutes (default: 60)",
        reason="Reason for the mute",
    )
    async def mute_user(
        self,
        ctx: commands.Context,
        user: discord.Member,
        duration: Optional[int] = 60,
        *,
        reason: Optional[str] = None,
    ):
        if user == ctx.author:
            return await ctx.send("You cannot mute yourself.")
        if user == self.bot.user:
            return await ctx.send("You cannot mute the bot.")

        if not duration or duration <= 0:
            return await ctx.send("Duration must be a positive number.")

        timeout_until = discord.utils.utcnow() + datetime.timedelta(minutes=duration)

        try:
            await user.edit(timeout_until=timeout_until, reason=reason)
            await self.logger.log_action({
                "type": "mute",
                "user": user.id,
                "duration": duration,
                "reason": reason,
                "moderator": str(ctx.author),
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })
            embed = discord.Embed(
                title="User Muted",
                description=f"{user.mention} has been muted for {duration} minutes.",
                color=discord.Color.blue(),
            )
            if reason:
                embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(
                name="Moderator", value=ctx.author.mention, inline=True
            )
            await ctx.send(embed=embed)
        except discord.Forbidden:
            await ctx.send("I do not have permission to mute this user.")
        except discord.HTTPException:
            await ctx.send("Failed to mute the user.")

    @commands.hybrid_command(name="unmute", description="Unmute a user.")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @app_commands.describe(user="The user to unmute", reason="Reason for the unmute")
    async def unmute_user(
        self,
        ctx: commands.Context,
        user: discord.Member,
        *,
        reason: Optional[str] = None,
    ):
        if user.is_timed_out():
            try:
                await user.edit(timeout_until=None, reason=reason)
                await self.logger.log_action({
                    "type": "unmute",
                    "user": user.id,
                    "reason": reason,
                    "moderator": str(ctx.author),
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                })
                embed = discord.Embed(
                    title="User Unmuted",
                    description=f"{user.mention} has been unmuted.",
                    color=discord.Color.green(),
                )
                if reason:
                    embed.add_field(name="Reason", value=reason, inline=False)
                embed.add_field(
                    name="Moderator", value=ctx.author.mention, inline=True
                )
                await ctx.send(embed=embed)
            except discord.Forbidden:
                await ctx.send("I do not have permission to unmute this user.")
            except discord.HTTPException:
                await ctx.send("Failed to unmute the user.")
        else:
            await ctx.send(f"{user.mention} is not currently muted.")

    @commands.hybrid_command(name="warn", description="Warn a user for inappropriate behavior.")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(send_messages=True)
    @app_commands.describe(user="The user to warn", reason="Reason for the warning")
    async def warn_user_cmd(
        self,
        ctx: commands.Context,
        user: discord.Member,
        *,
        reason: Optional[str] = None,
    ):
        if user == ctx.author:
            return await ctx.send("You cannot warn yourself.")
        if user == self.bot.user:
            return await ctx.send("You cannot warn the bot.")

        count = await self.logger.warn_user(user.id, reason or "No reason", str(ctx.author))
        await self.logger.log_action({
            "type": "warn",
            "user": user.id,
            "reason": reason,
            "moderator": str(ctx.author),
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })

        embed = discord.Embed(
            title="User Warned",
            description=f"{user.mention} has been warned.",
            color=discord.Color.yellow(),
        )
        if reason:
            embed.add_field(name="Reason", value=reason, inline=False)
        embed.add_field(name="Warning Count", value=str(count), inline=True)
        embed.add_field(
            name="Moderator", value=ctx.author.mention, inline=True
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="purge", description="Delete a number of messages.")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @app_commands.describe(amount="Number of messages to delete (max 100)")
    async def purge_messages(
        self,
        ctx: commands.Context,
        amount: int,
    ):
        if amount < 1 or amount > 100:
            return await ctx.send("Amount must be between 1 and 100.")

        deleted = await ctx.channel.purge(limit=amount)
        await self.logger.log_action({
            "type": "purge",
            "channel": ctx.channel.id,
            "amount": amount,
            "moderator": str(ctx.author),
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })
        await ctx.send(f"Deleted {len(deleted)} messages.", delete_after=5)

    @commands.hybrid_command(name="add_document", description="Upload a legal document to the RAG system.")
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(send_messages=True, attach_files=True)
    @app_commands.describe(attachment="Legal document file (PDF, DOCX, DOC, MD, TXT)")
    async def add_document(
        self,
        ctx: commands.Context,
        attachment: discord.Attachment,
    ):
        """Upload and process a legal document for the RAG system."""
        if not attachment:
            return await ctx.send("Por favor, anexe um arquivo de documento.")

        # Check if RAG system is available
        if RAGSystem is None:
            return await ctx.send("Sistema RAG não está disponível.")

        # Check if bot has RAG system initialized
        bot_with_rag = getattr(ctx.bot, '_rag_system', None)
        if not bot_with_rag:
            return await ctx.send("Sistema RAG não está inicializado no bot.")

        # Check file extension
        allowed_extensions = {'.pdf', '.docx', '.doc', '.md', '.txt'}
        file_ext = Path(attachment.filename).suffix.lower()

        if file_ext not in allowed_extensions:
            return await ctx.send(
                f"Formato de arquivo não suportado. Use: {', '.join(allowed_extensions)}"
            )

        # Check file size (limit to 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if attachment.size > max_size:
            return await ctx.send("Arquivo muito grande. Tamanho máximo: 10MB.")

        try:
            # Download file temporarily
            async with aiohttp.ClientSession() as session:
                async with session.get(attachment.url) as response:
                    if response.status != 200:
                        return await ctx.send("Erro ao baixar o arquivo.")

                    file_data = await response.read()

            # Save to temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
                temp_file.write(file_data)
                temp_file_path = Path(temp_file.name)

            try:
                # Show processing message
                processing_msg = await ctx.send("🔄 Processando documento...")

                # Process document with RAG system
                result = await bot_with_rag.add_document(temp_file_path)

                # Clean up temporary file
                temp_file_path.unlink(missing_ok=True)

                if result['success']:
                    embed = discord.Embed(
                        title="Documento Adicionado com Sucesso",
                        description=f"📄 **{attachment.filename}** foi processado e adicionado ao sistema RAG.",
                        color=discord.Color.green(),
                    )
                    embed.add_field(
                        name="Chunks Processados",
                        value=f"{result.get('chunks_stored', 0)}/{result.get('total_chunks', 0)}",
                        inline=True
                    )
                    embed.add_field(
                        name="Hash do Documento",
                        value=result.get('content_hash', 'N/A')[:16] + "...",
                        inline=True
                    )
                    embed.set_footer(text=f"Processado por {ctx.author.display_name}")

                    await processing_msg.edit(content="", embed=embed)

                else:
                    if result.get('duplicate'):
                        await processing_msg.edit(content="⚠️ Este documento já foi processado anteriormente (conteúdo duplicado).")
                    else:
                        await processing_msg.edit(content=f"❌ Erro ao processar documento: {result.get('error', 'Erro desconhecido')}")

            except Exception as e:
                # Clean up temporary file in case of error
                temp_file_path.unlink(missing_ok=True)
                raise e

        except Exception as e:
            await ctx.send(f"❌ Erro ao processar documento: {str(e)}")


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
