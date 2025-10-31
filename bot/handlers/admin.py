from aiogram import types, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode

from bot.auth import perms_admins
from bot.core.database import (
    get_all_users_from_db,
    remove_user_from_db,
    add_user_to_db,
    get_global_prompts,
    add_global_prompt,
    delete_global_prompt,
)
from bot.core.ollama import model_list, manage_model
from bot.ui import settings_kb, PromptStates
from bot import state

admin_router = Router()

# --- Settings and Model Management ---


@admin_router.message(Command("settings"))
@perms_admins
async def settings_command_handler(message: types.Message) -> None:
    await message.answer("⚙️ Admin Control Panel", reply_markup=settings_kb.as_markup())


@admin_router.message(Command("pullmodel"))
@perms_admins
async def pull_model_handler(message: types.Message) -> None:
    model_name = message.text.split(maxsplit=1)[1] if len(message.text.split()) > 1 else None
    if model_name:
        response = await manage_model("pull", model_name)
        if response.status == 200:
            await message.answer(f"Model '{model_name}' is being pulled.")
        else:
            await message.answer(f"Failed to pull model '{model_name}': {response.reason}")
    else:
        await message.answer("Please provide a model name to pull.")


@admin_router.callback_query(lambda query: query.data == "switchllm")
@perms_admins
async def switchllm_callback_handler(query: types.CallbackQuery):
    models = await model_list()
    switchllm_builder = InlineKeyboardBuilder()
    for model in models:
        model_name = model["name"]
        switchllm_builder.row(
            types.InlineKeyboardButton(text=model_name, callback_data=f"model_{model_name}")
        )
    switchllm_builder.row(
        types.InlineKeyboardButton(text="❌ Back", callback_data="settings_reopen")
    )
    await query.message.edit_text(
        f"⚙️⚡ {len(models)} MODELS AVAILABLE:", reply_markup=switchllm_builder.as_markup()
    )


@admin_router.callback_query(lambda query: query.data.startswith("model_"))
@perms_admins
async def model_callback_handler(query: types.CallbackQuery):
    # To properly modify the global state, we must import the `state` module
    # and modify the variable directly on it.
    new_modelname = query.data.split("model_")[1]
    state.modelname = new_modelname
    await query.answer(f"Model changed to: {new_modelname}")
    await query.message.edit_text(f"✅ Model changed to: {new_modelname}")


@admin_router.callback_query(lambda query: query.data == "delete_model")
@perms_admins
async def delete_model_callback_handler(query: types.CallbackQuery):
    models = await model_list()
    delete_model_kb = InlineKeyboardBuilder()
    for model in models:
        model_name = model["name"]
        delete_model_kb.row(
            types.InlineKeyboardButton(text=model_name, callback_data=f"delete_model_{model_name}")
        )
    delete_model_kb.row(types.InlineKeyboardButton(text="❌ Back", callback_data="settings_reopen"))
    await query.message.edit_text(
        f"{len(models)} models available for deletion.", reply_markup=delete_model_kb.as_markup()
    )


@admin_router.callback_query(lambda query: query.data.startswith("delete_model_"))
@perms_admins
async def delete_model_confirm_handler(query: types.CallbackQuery):
    modelname_to_delete = query.data.split("delete_model_")[1]
    response = await manage_model("delete", modelname_to_delete)
    if response.status == 200:
        await query.answer(f"Deleted model: {modelname_to_delete}")
    else:
        await query.answer(f"Failed to delete model: {modelname_to_delete}")


# --- User Management ---


@admin_router.callback_query(lambda query: query.data == "list_users")
@perms_admins
async def list_users_callback_handler(query: types.CallbackQuery):
    users = get_all_users_from_db()
    user_kb = InlineKeyboardBuilder()
    for user_id, user_name, _ in users:
        user_kb.row(
            types.InlineKeyboardButton(
                text=f"{user_name} ({user_id})", callback_data=f"remove_{user_id}"
            )
        )
    user_kb.row(types.InlineKeyboardButton(text="❌ Back", callback_data="settings_reopen"))
    await query.message.edit_text("Select a user to remove:", reply_markup=user_kb.as_markup())


@admin_router.callback_query(lambda query: query.data.startswith("remove_"))
@perms_admins
async def remove_user_from_list_handler(query: types.CallbackQuery):
    user_id = int(query.data.split("_")[1])
    if remove_user_from_db(user_id):
        await query.answer(f"User {user_id} has been removed.")
        await query.message.edit_text(f"User {user_id} has been removed.")
    else:
        await query.answer(f"User {user_id} not found.")


@admin_router.message(Command("adduser"))
@perms_admins
async def add_user_command_handler(message: types.Message):
    try:
        parts = message.text.split(maxsplit=2)
        user_id = int(parts[1])
        user_name = parts[2] if len(parts) > 2 else f"User {user_id}"
        if add_user_to_db(user_id, user_name):
            await message.reply(f"✅ User {user_name} ({user_id}) has been added to the allowlist.")
        else:
            await message.reply(f"⚠️ User {user_id} is already in the allowlist.")
    except (IndexError, ValueError):
        await message.reply("❌ Incorrect format. Use: `/adduser <user_id> [user_name]`")


@admin_router.message(Command("rmuser"))
@perms_admins
async def rm_user_command_handler(message: types.Message):
    try:
        user_id = int(message.text.split(maxsplit=1)[1])
        if remove_user_from_db(user_id):
            await message.reply(f"✅ User {user_id} has been removed from the allowlist.")
        else:
            await message.reply(f"⚠️ User {user_id} was not found in the allowlist.")
    except (IndexError, ValueError):
        await message.reply("❌ Incorrect format. Use: `/rmuser <user_id>`")


@admin_router.message(Command("listusers"))
@perms_admins
async def list_users_command_handler(message: types.Message):
    users = get_all_users_from_db()
    if not users:
        await message.reply("No users found in the allowlist.")
        return
    user_list = "👥 **Allowed Users**:\n\n"
    for user_id, user_name, _ in users:
        user_list += f"- `{user_id}`: {user_name}\n"
    await message.reply(user_list, parse_mode=ParseMode.MARKDOWN)


# --- Prompt Management ---


@admin_router.callback_query(lambda query: query.data == "admin_prompts")
@perms_admins
async def admin_prompts_callback_handler(query: types.CallbackQuery):
    prompts = get_global_prompts()
    admin_prompts_kb = InlineKeyboardBuilder()
    for prompt_id, name, _ in prompts:
        admin_prompts_kb.row(
            types.InlineKeyboardButton(text=name, callback_data=f"view_prompt_{prompt_id}")
        )
    admin_prompts_kb.row(
        types.InlineKeyboardButton(text="➕ Add Prompt", callback_data="add_prompt_start")
    )
    admin_prompts_kb.row(
        types.InlineKeyboardButton(text="🗑️ Delete Prompt", callback_data="delete_prompt_menu")
    )
    admin_prompts_kb.row(
        types.InlineKeyboardButton(text="❌ Back", callback_data="settings_reopen")
    )
    await query.message.edit_text(
        "⚙️ Manage Global Prompts", reply_markup=admin_prompts_kb.as_markup()
    )


@admin_router.callback_query(lambda query: query.data == "settings_reopen")
@perms_admins
async def settings_reopen_handler(query: types.CallbackQuery):
    await query.message.edit_text("⚙️ Admin Control Panel", reply_markup=settings_kb.as_markup())


@admin_router.callback_query(lambda query: query.data == "add_prompt_start")
@perms_admins
async def add_prompt_start_handler(query: types.CallbackQuery, state: FSMContext):
    await state.set_state(PromptStates.awaiting_name)
    await query.message.edit_text("Enter a short Name for the new System Prompt:")


@admin_router.message(PromptStates.awaiting_name)
@perms_admins
async def prompt_name_handler(message: types.Message, state: FSMContext):
    await state.update_data(prompt_name=message.text)
    await state.set_state(PromptStates.awaiting_text)
    await message.reply("Now, Enter the System Prompt:")


@admin_router.message(PromptStates.awaiting_text)
@perms_admins
async def prompt_text_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    prompt_name = data["prompt_name"]
    prompt_text = message.text
    add_global_prompt(prompt_name, prompt_text)
    await state.clear()
    await message.reply(f"✅ The new system prompt '{prompt_name}' has been saved.")


@admin_router.callback_query(lambda query: query.data == "delete_prompt_menu")
@perms_admins
async def delete_prompt_menu_handler(query: types.CallbackQuery):
    prompts = get_global_prompts()
    delete_prompt_kb = InlineKeyboardBuilder()
    for prompt_id, name, _ in prompts:
        delete_prompt_kb.row(
            types.InlineKeyboardButton(text=f"🗑️ {name}", callback_data=f"delete_prompt_{prompt_id}")
        )
    delete_prompt_kb.row(types.InlineKeyboardButton(text="❌ Back", callback_data="admin_prompts"))
    await query.message.edit_text(
        "Select a prompt to delete:", reply_markup=delete_prompt_kb.as_markup()
    )


@admin_router.callback_query(lambda query: query.data.startswith("delete_prompt_"))
@perms_admins
async def delete_prompt_confirm_handler(query: types.CallbackQuery):
    prompt_id = int(query.data.split("_")[2])
    delete_global_prompt(prompt_id)
    await query.answer("Prompt deleted successfully.")
    await admin_prompts_callback_handler(query)


@admin_router.callback_query(lambda query: query.data == "close_settings")
@perms_admins
async def close_settings_handler(query: types.CallbackQuery):
    await query.message.delete()
