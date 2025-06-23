import discord
import asyncio
from discord.ext import commands
from discord import app_commands, ui
from cogs.economy import Economy
from utils.commands import get_group_role_id, get_admin_info
from utils.loader import load_data
import os
from dotenv import load_dotenv


async def get_shop_items():
    # This correctly uses asyncio.to_thread for the synchronous load_data call
    return await asyncio.to_thread(load_data, "shop")

# --- View for "Not enough points" message ---
class InsufficientFundsView(ui.View):
    def __init__(self, item_name, required_points):
        super().__init__(timeout=60)
        self.item_name = item_name
        self.required_points = required_points

    @ui.button(label="Return", style=discord.ButtonStyle.blurple)
    async def return_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=f"Purchase of **{self.item_name}** cancelled.",
            embed=None,
            view=None
        )
        self.stop() # Stop the view after the button is clicked

# --- Modal for Username Input ---
class UsernameModal(discord.ui.Modal, title="Fakepixel Beta Tester Store"):
    def __init__(self, bot, item_id, user_id, item_name, item_price, interaction_original):
        super().__init__()
        self.bot = bot
        self.item_id = item_id
        self.user_id = user_id
        self.item_name = item_name
        self.item_price = item_price
        self.interaction_original = interaction_original # Store original interaction to edit its message later

        self.username_input = discord.ui.TextInput(
            label="Enter your in-game name here (IGN):",
            placeholder="Your in-game name",
            required=True,
            max_length=32,
            custom_id="ign_input" # Add a custom_id for easier access
        )
        self.add_item(self.username_input)

    async def on_submit(self, interaction_modal: discord.Interaction):
        # Acknowledge the modal submission first, so it closes immediately
        # This gives you more time to do other operations without timing out
        await interaction_modal.response.defer(ephemeral=True, thinking=False)

        eco = self.bot.get_cog("Economy")
        if not eco:
            # Edit the original message to show error if Economy cog is missing
            await self.interaction_original.edit_original_response(
                content="Error: Economy cog not found. Please contact an administrator.",
                embed=None,
                view=None
            )
            return

        current_balance = await eco.get_balance(self.user_id) # Await get_balance
        ign = self.username_input.value # Access the value from the defined TextInput

        if current_balance >= self.item_price:
            await eco._remove_points_from_data(self.user_id, self.item_price)

            # Edit the original message that brought up the modal
            await self.interaction_original.edit_original_response(
                content=f"🎉 {interaction_modal.user.mention}, You've successfully purchased **{self.item_name}** for {self.item_price} points!\nAn administrator will shortly contact you regarding this purchase.",
                embed=None,
                view=None # Ensure previous view is removed
            )

            channel_id = os.getenv("PURCHASE_CHANNEL_ID")
            if channel_id:
                receipt_channel = self.bot.get_channel(int(channel_id))
                if receipt_channel:
                    embed = discord.Embed(
                        title=f"New Purchase!",
                        description=(
                            f"{interaction_modal.user.mention} has bought **{self.item_name}** for **{self.item_price}** points\n"
                            f"On {interaction_modal.created_at.strftime('%B %d, %Y - %I:%M %p')}\n"
                            f"\n"
                            f"In-game Name provided: `{ign}`\n"
                        ),
                        color=discord.Color.blue()
                    )
                    embed.set_thumbnail(url=interaction_modal.user.avatar.url if interaction_modal.user.avatar else None)
                    embed.set_footer(text=f"User ID: {self.user_id}")
                    await receipt_channel.send(embed=embed)
        else:
            # If not enough points, edit the original message to reflect that
            await self.interaction_original.edit_original_response(
                content=f"You no longer have enough points to buy **{self.item_name}**.",
                embed=None,
                view=None # Ensure previous view is removed
            )


# --- View for purchase confirmation ---
class ConfirmPurchaseView(ui.View):
    def __init__(self, bot, item_id, user_id, item_name, item_price, interaction_original):
        super().__init__(timeout=60)
        self.bot = bot
        self.item_id = item_id
        self.user_id = user_id
        self.item_name = item_name
        self.item_price = item_price
        self.interaction_original = interaction_original # Store the initial interaction

    @ui.button(label="✅", style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: ui.Button):
        # Respond to the button click by sending the modal
        await interaction.response.send_modal(
            UsernameModal(self.bot, self.item_id, self.user_id, self.item_name, self.item_price, self.interaction_original)
        )
        self.stop() # Stop the confirmation view as modal takes over

    @ui.button(label="❌", style=discord.ButtonStyle.red)
    async def cancel_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(
            content=f"Purchase of **{self.item_name}** cancelled.",
            embed=None,
            view=None
        )
        self.stop()

# --- Dropdown for item selection ---
class ItemSelect(ui.Select):
    def __init__(self, bot, items): # 'items' are now passed in
        self.bot = bot
        options = [
            discord.SelectOption(label=item['name'], value=str(item['id']))
            for item in items if 'price' in item
        ]
        super().__init__(placeholder="Select an item to buy", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        selected_item_id = int(self.values[0])
        shop_items = await get_shop_items() # Re-fetch to ensure latest data
        selected_item = next((item for item in shop_items if item['id'] == selected_item_id), None)

        if not selected_item:
            await interaction.followup.send("Error: Item not found in shop.", ephemeral=True)
            return

        item_name = selected_item.get('name', 'Unknown Item')
        item_price = selected_item.get('price', 0)
        item_new = selected_item.get('new_item', False) # Use 'new' as per shop.json structure

        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.followup.send("Economy cog not found. Please contact an administrator.", ephemeral=True)
            return
        user_balance = await eco.get_balance(interaction.user.id) # Await get_balance


        if user_balance < item_price:
            new_tag = "NEW! " if item_new else ""
            embed = discord.Embed(
                title="Error",
                description=f"Not enough points. You need **{item_price}** points to buy {new_tag}**{item_name}**",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, view=InsufficientFundsView(item_name, item_price), ephemeral=True)
        else:
            embed = discord.Embed(
                title="Confirm",
                description=f"{interaction.user.mention}, you sure you want to buy **{item_name}** for **{item_price} points**?",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
            confirm_view = ConfirmPurchaseView(self.bot, selected_item_id, interaction.user.id, item_name, item_price, interaction)
            await interaction.followup.send(embed=embed, view=confirm_view, ephemeral=True)

# --- View for displaying shop items with pagination ---
class ShopItemsView(ui.View):
    def __init__(self, bot, shop_items, current_page=1, items_per_page=5):
        super().__init__(timeout=300)
        self.bot = bot
        self.shop_items = shop_items # shop_items are now passed in as an already awaited list
        self.items_per_page = items_per_page
        self.current_page = current_page
        self.message = None # To store the message to edit later
        self.update_view_elements() # Call to set up buttons immediately

    async def on_timeout(self) -> None:
        if self.message:
            await self.message.edit(view=None) # Remove buttons on timeout

    def update_view_elements(self):
        self.clear_items()
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        items_on_page = self.shop_items[start_index:end_index]

        # Add item buttons
        for i, item in enumerate(items_on_page):
            button_label = str(start_index + i + 1)
            # Ensure custom_id is unique and does not collide with other buttons
            button = ui.Button(label=button_label, style=discord.ButtonStyle.blurple, custom_id=f"shop_item_buy_{item['id']}_{self.current_page}", row=0)
            button.callback = self.buy_button_callback
            self.add_item(button)

        # Fill remaining slots in the first row
        for _ in range(self.items_per_page - len(items_on_page)):
            self.add_item(ui.Button(label="\u200b", style=discord.ButtonStyle.secondary, disabled=True, row=0))

        # Add ItemSelect dropdown if there are items
        if self.shop_items:
            # Pass the shop_items list directly to ItemSelect, as it's already loaded
            self.add_item(ItemSelect(self.bot, self.shop_items))

        total_pages = (len(self.shop_items) + self.items_per_page - 1) // self.items_per_page

        # Pagination buttons
        first = ui.Button(label="«", style=discord.ButtonStyle.secondary, custom_id="shop_first_page", disabled=self.current_page == 1, row=2)
        async def first_callback(interaction: discord.Interaction):
            self.current_page = 1
            embed = await self.create_shop_embed()
            self.update_view_elements()
            await interaction.response.edit_message(embed=embed, view=self)
        first.callback = first_callback
        self.add_item(first)

        prev = ui.Button(label="◀", style=discord.ButtonStyle.secondary, custom_id="shop_prev_page", disabled=self.current_page == 1, row=2)
        async def prev_callback(interaction: discord.Interaction):
            self.current_page -= 1
            embed = await self.create_shop_embed()
            self.update_view_elements()
            await interaction.response.edit_message(embed=embed, view=self)
        prev.callback = prev_callback
        self.add_item(prev)

        next_btn = ui.Button(label="▶", style=discord.ButtonStyle.secondary, custom_id="shop_next_page", disabled=self.current_page == total_pages, row=2) # Renamed to next_btn to avoid conflict with built-in next()
        async def next_callback(interaction: discord.Interaction):
            self.current_page += 1
            embed = await self.create_shop_embed()
            self.update_view_elements()
            await interaction.response.edit_message(embed=embed, view=self)
        next_btn.callback = next_callback
        self.add_item(next_btn)

        last = ui.Button(label="»", style=discord.ButtonStyle.secondary, custom_id="shop_last_page", disabled=self.current_page == total_pages, row=2)
        async def last_callback(interaction: discord.Interaction):
            self.current_page = total_pages
            embed = await self.create_shop_embed()
            self.update_view_elements()
            await interaction.response.edit_message(embed=embed, view=self)
        last.callback = last_callback
        self.add_item(last)

    async def buy_button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        # Extract item_id from custom_id (e.g., "shop_item_buy_123_1")
        item_id = int(interaction.data['custom_id'].split('_')[-2])
        shop_items = await get_shop_items() # Re-fetch to ensure latest data, in case it changed
        selected_item = next((item for item in shop_items if item['id'] == item_id), None)

        if not selected_item:
            await interaction.followup.send("Error: Item not found in shop.", ephemeral=True)
            return

        item_name = selected_item.get('name', 'Unknown Item')
        item_price = selected_item.get('price', 0)
        item_new = selected_item.get('new_item', False) # Corrected key

        eco = self.bot.get_cog("Economy")
        if not eco:
            await interaction.followup.send("Economy cog not found. Please contact an administrator.", ephemeral=True)
            return
        user_balance = await eco.get_balance(interaction.user.id) # Await get_balance

        if user_balance < item_price:
            embed = discord.Embed(
                title="Error",
                description=f"Not enough points. You need **{item_price}** points to buy **{item_name}**",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, view=InsufficientFundsView(item_name, item_price), ephemeral=True)
        else:
            embed = discord.Embed(
                title="Confirm",
                description=f"{interaction.user.mention}, you sure you want to buy **{item_name}** for **{item_price} points**?",
                color=discord.Color.green()
            )
            embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
            # Pass the initial interaction (self) to ConfirmPurchaseView for proper message editing
            confirm_view = ConfirmPurchaseView(self.bot, item_id, interaction.user.id, item_name, item_price, interaction)
            await interaction.followup.send(embed=embed, view=confirm_view, ephemeral=True)

    async def create_shop_embed(self):
        embed = discord.Embed(title="Shop", color=discord.Color.blue())
        total_items = len(self.shop_items)
        total_pages = (total_items + self.items_per_page - 1) // self.items_per_page
        start_index = (self.current_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        items_on_page = self.shop_items[start_index:end_index]

        if not items_on_page:
            embed.description = "The shop is currently empty or this page has no items."
        else:
            description_lines = []
            for i, item in enumerate(items_on_page):
                new_tag = "**NEW!** " if item.get('new', False) else "" # Corrected key to 'new'
                item_description = item.get('description', 'No description provided.') # Default description
                description_lines.append(
                f"{start_index + i + 1}). {new_tag}{item['name']}\n" +
                ''.join(f"> {line}\n" for line in item_description.splitlines()) +
                f"**Price:** {item['price']} points\n"
            )
            embed.description = "\n\n".join(description_lines)

        embed.set_footer(text=f"Page {self.current_page} of {total_pages}")
        return embed


# --- MainGUIButtons (the initial GUI with "Check Shop" and "View Balance") ---
class MainGUIButtons(ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    def has_access(self, member: discord.Member) -> bool:
        allowed_roles = {
            get_group_role_id("admin"),
            get_group_role_id("beta tester"),
            get_group_role_id("verified")
        }
        return any(role.id in allowed_roles for role in member.roles if isinstance(role.id, int))

    @ui.button(label="Check the Shop", style=discord.ButtonStyle.blurple, custom_id="main_gui_check_shop")
    async def check_shop_button(self, interaction: discord.Interaction, button: ui.Button):
        if not self.has_access(interaction.user):
            await interaction.response.send_message("You do not have permission to use this button.", ephemeral=True)
            return

        shop_items_data = await get_shop_items() # Await here to get the actual data 
        shop_view = ShopItemsView(self.bot, shop_items_data) # Pass the loaded data to the view 
        shop_embed = await shop_view.create_shop_embed()

        # Send the initial response
        await interaction.response.send_message(embed=shop_embed, view=shop_view, ephemeral=True)

        # Get the original message object from the interaction
        shop_view.message = await interaction.original_response()


    @ui.button(label="View Balance", style=discord.ButtonStyle.success, custom_id="main_gui_view_balance")
    async def view_balance_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if not interaction.response.is_done():
                await interaction.response.defer(ephemeral=True)
            eco = self.bot.get_cog("Economy")
            if not eco:
                await interaction.followup.send("Economy system not found.", ephemeral=True)
                return
            balance = await eco.get_balance(interaction.user.id)
            await interaction.followup.send(
                f"Your balance is **{balance} points**, {interaction.user.mention}.",
                ephemeral=True
            )
        except discord.errors.NotFound:
            pass
        except Exception as e:
            try:
                await interaction.followup.send(f"❌ An error occurred: {e}", ephemeral=True)
            except discord.errors.NotFound:
                pass

# --- Command Cog ---
class shop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_admin(interaction: discord.Interaction) -> bool:
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)

        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
            return False

        return True

    @app_commands.command(name="setup", description="Open the main GUI interface.")
    @app_commands.check(is_admin) # Apply the check directly
    async def setup_gui(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Beta Tester Shop",
            description="Looks cool right? It is! \nGrab your goods before they run out!",
            color=discord.Color.blue()
        )
        embed.set_image(url="https://drive.google.com/uc?export=download&id=1TuINCr7OxWRqUf6fCLo_l_5bj_rBTd2k")
        embed.set_footer(text="By _Suspected_ - 23/06/2025", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        await interaction.response.send_message(embed=embed, view=MainGUIButtons(self.bot))

async def setup(bot):
    await bot.add_cog(shop(bot))
