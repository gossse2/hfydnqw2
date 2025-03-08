import sqlite3
import json 
import os
import logging
import string
import random
import requests

from aiogram import Bot, Dispatcher, types
from cfg import *
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class WalletStates(StatesGroup):
    waiting_for_address = State()

class DealStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_description = State()

class adminaddd(StatesGroup):
    waiting_for_admin = State()
    
class admnal(StatesGroup):
    waiting_for_nal = State()

class ivanf(StatesGroup):
    waiting_for_deal_id = State()

bot = Bot(token=bottoken)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

def get_db_connection():
    conn = sqlite3.connect('data/data.db')
    conn.row_factory = sqlite3.Row
    return conn
def get_usdt_price():
    try:
        response = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=TONUSDT')
        data = response.json()
        return float(data['price'])
    except:
        return None

def get_ton_price_dexscreener():
    try:
        response = requests.get('https://api.dexscreener.com/latest/dex/tokens/EQBynBO23ywHy_CgarY9NK9FTz0yDsG82PtcbSTQgGoXwiuA')
        data = response.json()
        price = float(data['pairs'][0]['priceTON'])
        return price
    except Exception as e:
        print(f"Ошибка получения цены DexScreener: {e}")
        return None

def create_admins():
    data = {}
    with open('data/admins.json', 'w') as file:
        json.dump(data, file, indent=4)
    return

def generate_ref_code():
    characters = string.ascii_letters + string.digits
    return ''.join(random.choice(characters) for _ in range(20))    

async def execute_db_query(query, params=(), fetchone=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    conn.commit()
    if fetchone:
        result = cursor.fetchone()
    else:
        result = cursor.fetchall()
    conn.close()
    return result

async def save_address(user_id, address):
    await execute_db_query("UPDATE users SET Ton_address = ? WHERE user_id = ?", (address, user_id))

async def create():
    await execute_db_query('''
    CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    Ton_address TEXT,
    ref_code TEXT UNIQUE,
    referrer_code TEXT,
    lan TEXT,
    sdelka INTEGER DEFAULT 0
    )''')

def generate_random_digits(length=10):
    digits = ''.join(random.choices('0123456789', k=length))
    return digits

def generate_deal_link():
    # Генерируем случайную строку из 8 символов (буквы и цифры)
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(10))

def load_texts():
    with open('data/texts.json', 'r', encoding='utf-8') as f:
        return json.load(f)

# Загружаем тексты при старте
texts = load_texts()

# Обновляем welcome_text и welcome_img из JSON

welcome_img = 'https://i.imgur.com/WVXdsNo.jpeg'

async def get_ref_link(ref_code: str):
    bot_info = await bot.get_me()
    return f"https://t.me/{bot_info.username}?start=ref={ref_code}"

async def save_user(user: types.User, referrer_code=None):
    ref_code = generate_ref_code()
    await execute_db_query('INSERT OR REPLACE INTO users (user_id, username, Ton_address, ref_code, referrer_code, lan) VALUES (?, ?, ?, ?, ?, ?)',
                     (user.id, user.username, 'none', ref_code, referrer_code, 'ru'))
    return ref_code

async def get_user_language(user_id: int) -> str:
    """Get user's preferred language from database"""
    result = await execute_db_query(
        'SELECT lan FROM users WHERE user_id = ?', 
        (user_id,), 
        fetchone=True
    )
    return result[0] if result else 'en'

async def get_user_language(user_id: int) -> str:
    """Get user's preferred language from database"""
    result = await execute_db_query(
        'SELECT lan FROM users WHERE user_id = ?', 
        (user_id,), 
        fetchone=True
    )
    return result[0] if result else 'en'  # fallback to English

async def get_text(category: str, key: str, user_id: int) -> str:
    """Get localized text based on user's language preference"""
    user_lang = await get_user_language(user_id)
    try:
        return texts[user_lang][category][key]
    except KeyError:
        logger.error(f"Missing text: {category}.{key} for language {user_lang}")
        return texts['en'][category][key]  # Fallback to English

def safe_json_load(filepath: str, default=None):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading JSON from {filepath}: {e}")
        return default if default is not None else {}

def safe_json_save(filepath: str, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logger.error(f"Error saving JSON to {filepath}: {e}")
        return False

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await create()
    args = message.get_args()
    referrer_code = None
    user_id = message.from_user.id

    if not os.path.exists('data/admins.json'):
        create_admins()

    user_language = await get_user_language(user_id)
    welcome_text = texts[user_language]['welcome']['text']
    buttons = texts[user_language]['buttons']

    if args.startswith('ref='):
        referrer_code = args[4:]

    user_exists = await execute_db_query('SELECT COUNT(*) FROM users WHERE user_id = ?', 
                                       (user_id,), fetchone=True)
    
    if not user_exists[0]:
        await save_user(message.from_user, referrer_code)

    
    elif args:
        
        deal_files = os.listdir('temp')
        for file in deal_files:
            if file.endswith('.json'):
                with open(f'temp/{file}', 'r', encoding='utf-8') as f:
                    deal_data = json.load(f)
                    
                if deal_data.get('deal_link') == args:
                
                    if deal_data['user_id'] == message.from_user.id:
                        await message.reply(
                            "❌ Вы не можете участвовать в своей же сделке.",
                            parse_mode=types.ParseMode.MARKDOWN
                        )
                        return
                    
                    # Добавляем buyer_id в данные сделки
                    deal_data['buyer_id'] = message.from_user.id
                    userid = deal_data['user_id']
                    deal_data['linkid'] = deal_data['deal_link']
                    deal_data['deal_link'] = 'zakrep'

                    with open(f'temp/{file}', 'w', encoding='utf-8') as f:
                        json.dump(deal_data, f, ensure_ascii=False, indent=4)
                    
                    user_data = await execute_db_query('SELECT ref_code FROM users WHERE user_id = ?',(userid,), fetchone=True)
                    ref_code = user_data[0]

                    user_code = await execute_db_query('SELECT sdelka FROM users WHERE user_id = ?',(userid,), fetchone=True)
                    sdelka = user_code[0]

                    ton = deal_data['amount']  # 100.5
                    tonn = str(int(float(ton) * 1000000000))
                    price = get_usdt_price()
                    Pricepx = 0.05570
                    px = float(ton) * Pricepx
                    usdt = float(ton) * price

                    buyer_text = await get_text('deal', 'buyer_text', userid)
                    buyer_text = buyer_text.format(
                        deal_id=deal_data['linkid'],
                        username=deal_data['username'],
                        user_id=deal_data['user_id'],
                        deals_count=sdelka,
                        description=deal_data['description'],
                        address=ownerAdress,
                        px=px,
                        usdt=usdt,
                        ton=ton
                    )

                    buyer_joined_text = await get_text('deal', 'buyer_joined', message.from_user.id)
                    buyer_joined_text = buyer_joined_text.format(
                        username=message.from_user.username,
                        user_id=deal_data['user_id'],
                        deal_id=deal_data['linkid'],
                        deals_count=sdelka
                    )

                    keyboard123 = InlineKeyboardMarkup(row_width=1)
                    keyboard123.add(
                        InlineKeyboardButton(buttons['open_in_tonkeeper'], url=f"ton://transfer/{ownerAdress}?amount={tonn}&text={deal_data['linkid']}"),
                        InlineKeyboardButton(buttons['leave_deal'], callback_data=f"leave_deal_{deal_data['linkid']}")
                    )

                    idc = await message.reply(buyer_text,
                        parse_mode=types.ParseMode.MARKDOWN,
                        reply_markup=keyboard123
                    )
                    
                    await bot.send_message(chat_id=deal_data['user_id'], text=buyer_joined_text, parse_mode=types.ParseMode.MARKDOWN)

                    messageidd = idc.message_id
                    temp_json= {
                        'buyer': deal_data['user_id'],
                        'messageid': messageidd,
                    }
                    with open(f'temp/{message.from_user.id}.json', 'w', encoding='utf-8') as f:
                        json.dump(temp_json, f, ensure_ascii=False, indent=4)
                    
                    return

   
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(buttons['manage_wallet'], callback_data="manage_wallet"),
        InlineKeyboardButton(buttons['create_deal'], callback_data="create_deal"),
        InlineKeyboardButton(buttons['ref_link'], callback_data="ref_link"),
        InlineKeyboardButton(buttons['change_language'], callback_data="change_language"),
        InlineKeyboardButton(buttons['support'], url="https://t.me/otcgifttg/113382/113404")
    )
    
    await bot.send_photo(
        chat_id=message.chat.id,
        photo=texts[user_language]['welcome']['image'],
        caption=welcome_text,
        reply_markup=keyboard,
        parse_mode=types.ParseMode.MARKDOWN
    )

@dp.callback_query_handler(lambda c: c.data == 'manage_wallet')
async def process_callback_edit_wallet(callback_query: types.CallbackQuery, state: FSMContext):
    user_id = callback_query.from_user.id
    message = callback_query.message
    
    if not message:
        return
        
    await bot.answer_callback_query(callback_query.id)
    ton = await execute_db_query('SELECT Ton_address FROM users WHERE user_id = ?', 
                                 (user_id,), fetchone=True)

    if ton and isinstance(ton[0], str):
        wallet_address = ton[0]
        text_key = 'add_new' if wallet_address == 'none' else 'current'
        new_text = await get_text('wallet', text_key, user_id)
        if text_key == 'current':
            new_text = new_text.format(address=wallet_address)

        back_button = InlineKeyboardMarkup().add(
            InlineKeyboardButton(
                (await get_text('buttons', 'back_to_menu', user_id)), 
                callback_data="back_to_menu"
            )
        )

        if hasattr(message, 'caption') and message.caption:
            await bot.edit_message_caption(
                chat_id=message.chat.id,
                message_id=message.message_id,
                caption=new_text,
                reply_markup=back_button,
                parse_mode=types.ParseMode.MARKDOWN
            )
        elif hasattr(message, 'text') and message.text:
            await bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=new_text,
                reply_markup=back_button,
                parse_mode=types.ParseMode.MARKDOWN
            )
            
        await WalletStates.waiting_for_address.set()

@dp.message_handler(state=WalletStates.waiting_for_address)
async def process_wallet_input(message: types.Message, state: FSMContext):
    wallet_address = message.text.strip()
    
    if len(wallet_address) < 48:
        error_text = await get_text('wallet', 'invalid', message.from_user.id)
        await message.reply(error_text, parse_mode=types.ParseMode.MARKDOWN)
        return
    
  
    await execute_db_query(
        'UPDATE users SET Ton_address = ? WHERE user_id = ?',
        (wallet_address, message.from_user.id)
    )
    
    success_text = await get_text('wallet', 'success', message.from_user.id)
    back_button_text = await get_text('buttons', 'back_to_menu', message.from_user.id)
    back_button = InlineKeyboardMarkup().add(
        InlineKeyboardButton(back_button_text, callback_data="back_to_menu")
    )
    await message.reply(success_text, parse_mode=types.ParseMode.MARKDOWN, reply_markup=back_button)

    await state.finish()
    

@dp.callback_query_handler(lambda c: c.data == 'cancel_action')
async def process_callback_create_deal(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.delete_message(chat_id=callback_query.message.chat.id, message_id=callback_query.message.message_id)

@dp.callback_query_handler(lambda c: c.data and c.data.startswith('leave_deal_'))
async def process_user_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    id = callback_query.data.split('_')[2]
    message = callback_query.message
    user_id = callback_query.from_user.id

    try:
        with open(f'temp/{user_id}.json', 'r', encoding='utf-8') as f:
            id_buy = json.load(f)
        idByu = id_buy['buyer']

        with open(f'temp/deal_{idByu}.json', 'r', encoding='utf-8') as f:
            deal_data = json.load(f)

        link = deal_data['linkid']

        keyboard123 = InlineKeyboardMarkup(row_width=1)
        keyboard123.add(
            InlineKeyboardButton(await get_text('buttons', 'confirm_leave', user_id), callback_data=f"confirm_leave_deal_{link}"),
            InlineKeyboardButton(await get_text('buttons', 'confirm_no', user_id), callback_data="cancel_action")
        )

        otmena_text_template = await get_text('deal', 'leave_confirmation', user_id)
        otmena_text = otmena_text_template.format(deal_id=link)

        await message.reply(
            otmena_text,
            parse_mode=types.ParseMode.MARKDOWN,
            reply_markup=keyboard123
        )
    except FileNotFoundError:
        await message.reply(
            await get_text('deal', 'already_left', user_id),
            parse_mode=types.ParseMode.MARKDOWN
        )
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('confirm_leave_deal_'))
async def process_user_callback(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    ids = callback_query.data.split('_')[3]
    message = callback_query.message
    user_id = callback_query.from_user.id

    if not os.path.exists(f'temp/{user_id}.json'):
        await bot.answer_callback_query(callback_query.id)
        await bot.delete_message(
            chat_id=callback_query.message.chat.id,
            message_id=callback_query.message.message_id
        )
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=await get_text('deal', 'already_left', user_id),
            parse_mode=types.ParseMode.MARKDOWN
        )
        return

    with open(f'temp/{user_id}.json', 'r', encoding='utf-8') as f:
        id_buy = json.load(f)
        idByuf = id_buy['buyer']
        idmes = id_buy['messageid']

    if os.path.exists(f'temp/deal_{idByuf}.json'):
        with open(f'temp/deal_{idByuf}.json', 'r', encoding='utf-8') as f:
            deal_data = json.load(f)
            deal_data['deal_link'] = f'{ids}'
            buyq = deal_data['buyer_id']
        
        with open(f'temp/deal_{idByuf}.json', 'w', encoding='utf-8') as file:
            json.dump(deal_data, file, ensure_ascii=False, indent=4)

        byupola = await get_text('deal', 'buyer_left', user_id).format(user_id=user_id,username=callback_query.from_user.username,deal_id=ids)

        try:
            await bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=callback_query.message.message_id
            )
            await bot.delete_message(
                chat_id=callback_query.message.chat.id,
                message_id=idmes
            )
        except Exception:
            pass

        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=await get_text('deal', 'left_deal', user_id),
            parse_mode=types.ParseMode.MARKDOWN
        )
        
        await bot.send_message(
            chat_id=buyq,
            text=byupola,
            parse_mode=types.ParseMode.MARKDOWN
        )

        try:
            os.remove(f'temp/{user_id}.json')
        except FileNotFoundError:
            await bot.answer_callback_query(callback_query.id, 'Вы не можете покинуть эту сделку')
        else:
            await bot.answer_callback_query(callback_query.id, 'Вы не можете покинуть эту сделку')
    else:
        await bot.send_message(
            chat_id=callback_query.message.chat.id,
            text=await get_text('deal', 'already_left', user_id),
            parse_mode=types.ParseMode.MARKDOWN
        )


@dp.callback_query_handler(lambda c: c.data == 'create_deal')
async def process_callback_create_deal(callback_query: types.CallbackQuery, state: FSMContext):
    message = callback_query.message
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username
    await bot.answer_callback_query(callback_query.id)

    temp_data = {
        'user_id': user_id,
        'username': username,
        'status': 'жду_сумму'
    }

    with open(f'temp/deal_{user_id}.json', 'w', encoding='utf-8') as f:
        json.dump(temp_data, f, ensure_ascii=False, indent=4)
    back_button_text = await get_text('buttons', 'back_to_menu', message.from_user.id)

    back_button = InlineKeyboardMarkup().add(
        InlineKeyboardButton(back_button_text, callback_data="back_to_menu")
    )

    text = await get_text('deal', 'create', user_id)
    back_button = InlineKeyboardMarkup().add(
        InlineKeyboardButton(await get_text('buttons', 'back_to_menu', user_id), callback_data="back_to_menu")
    )

    if hasattr(message, 'caption') and message.caption:
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=message.message_id,
            caption=text,
            reply_markup=back_button,
            parse_mode=types.ParseMode.MARKDOWN
        )
    elif hasattr(message, 'text') and message.text:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=text,
            reply_markup=back_button,
            parse_mode=types.ParseMode.MARKDOWN
        )

    await DealStates.waiting_for_amount.set()

@dp.message_handler(content_types=['text'], state=DealStates.waiting_for_amount)
async def process_deal_amount(message: types.Message, state: FSMContext):
    try:
        text = message.text.replace(',', '.')
        amount = float(text)
        
        if amount <= 0:
            raise ValueError
            
        deal_file = f'temp/deal_{message.from_user.id}.json'
        if os.path.exists(deal_file):
            with open(deal_file, 'r', encoding='utf-8') as f:
                deal_data = json.load(f)
            
            deal_data['amount'] = amount
            deal_data['status'] = 'жду_описание'

            
            with open(deal_file, 'w', encoding='utf-8') as f:
                json.dump(deal_data, f, ensure_ascii=False, indent=4)

            back_button = InlineKeyboardMarkup().add(
                InlineKeyboardButton(await get_text('buttons', 'back_to_menu', message.from_user.id), callback_data="back_to_menu")
            )
            
            await message.reply(
                await get_text('deal', 'enter_description', message.from_user.id),
                reply_markup=back_button,
                parse_mode=types.ParseMode.MARKDOWN
            )
            
            await DealStates.waiting_for_description.set()  # Переходим к ожиданию описания
            
    except (ValueError, TypeError):
        await message.reply(
            await get_text('deal', 'invalid_amount', message.from_user.id),
            parse_mode=types.ParseMode.MARKDOWN
        )

@dp.message_handler(content_types=['text'], state=DealStates.waiting_for_description)
async def process_deal_description(message: types.Message, state: FSMContext):
    description = message.text.strip()
    deal_link = generate_deal_link()
    bot_info = await bot.get_me()
    
    deal_file = f'temp/deal_{message.from_user.id}.json'
    if os.path.exists(deal_file):
        with open(deal_file, 'r', encoding='utf-8') as f:
            deal_data = json.load(f)
            
        deal_data['description'] = description
        deal_data['deal_link'] = deal_link
        deal_data['status'] = 'описание_получено'
        price = deal_data['amount']
        
        with open(deal_file, 'w', encoding='utf-8') as f:
            json.dump(deal_data, f, ensure_ascii=False, indent=4)

        data = {
            "userid": message.from_user.id, 
            }

        with open(f'temp/#{deal_link}.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        # Формируем ссылку правильно
        bot_link = f"https://t.me/{bot_info.username}?start={deal_link}"

        keyboard = InlineKeyboardMarkup(row_width=1)
        cancel_button_text = await get_text('buttons', 'cancel_deal', message.from_user.id)
        keyboard.add(InlineKeyboardButton(cancel_button_text, callback_data=f"cancel_deal_{deal_link}"))

        success_text = await get_text('deal', 'success', message.from_user.id)
        await message.reply(
            success_text.format(amount=price, description=description, link=bot_link),
            parse_mode=types.ParseMode.MARKDOWN,
            reply_markup=keyboard
        )
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'ref_link')
async def process_callback_referral_link(callback_query: types.CallbackQuery):
    message = callback_query.message
    await bot.answer_callback_query(callback_query.id)
    
    user_data = await execute_db_query('SELECT ref_code FROM users WHERE user_id = ?', 
                                     (callback_query.from_user.id,), 
                                     fetchone=True)
    
    if user_data:
        ref_code = user_data[0]
        ref_link = await get_ref_link(ref_code)
        
        result = await execute_db_query('SELECT COUNT(*) FROM users WHERE referrer_code = ?', 
                                      (ref_code,), 
                                      fetchone=True)
        referrals_count = result[0] if result else 0
        
        message_text = (
            f"🔗 *{await get_text('messages', 'ref_link', callback_query.from_user.id)}*\n\n"
            f"`{ref_link}`\n\n"
            f"👥 *{await get_text('messages', 'referrals_count', callback_query.from_user.id)}:* {referrals_count}\n"
            f"💰 *{await get_text('messages', 'earnings', callback_query.from_user.id)}:* 0.0 TON\n"
            f"40% {await get_text('messages', 'bot_fee', callback_query.from_user.id)}"
        )

        await message.reply(
            text=message_text,
            parse_mode=types.ParseMode.MARKDOWN
        )
    else:
        await message.reply(
            text= await get_text('deal', 'ref_error', message.from_user.id),
            parse_mode=types.ParseMode.MARKDOWN
        )

@dp.callback_query_handler(lambda c: c.data == 'change_language')
async def process_callback_change_language(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    user_language = await get_user_language(callback_query.from_user.id)
    select_language_text = texts['messages']['select_language'][user_language]
    await bot.send_message(callback_query.from_user.id, select_language_text)

@dp.callback_query_handler(lambda c: c.data == 'back_to_menu', state='*')
async def back_to_main(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    message = callback_query.message
    user_id = callback_query.from_user.id
    await state.finish()

    # Проверяем и удаляем временный файл сделки
    deal_file = f'temp/deal_{user_id}.json'
    if (os.path.exists(deal_file)):
        try:
            os.remove(deal_file)
        except Exception as e:
            print(f"Ошибка при удалении файла: {e}")

    user_language = await get_user_language(user_id)
    welcome_text = texts[user_language]['welcome']['text']
    buttons = texts[user_language]['buttons']
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(buttons['manage_wallet'], callback_data="manage_wallet"),
        InlineKeyboardButton(buttons['create_deal'], callback_data="create_deal"),
        InlineKeyboardButton(buttons['ref_link'], callback_data="ref_link")
    )

    if hasattr(message, 'caption') and message.caption:
        await bot.edit_message_caption(
            chat_id=message.chat.id,
            message_id=message.message_id,
            caption=welcome_text,
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )
    elif hasattr(message, 'text') and message.text:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=welcome_text,
            reply_markup=keyboard,
            parse_mode=types.ParseMode.MARKDOWN
        )

@dp.message_handler(commands=['apanel'])
async def send_welcome(message: types.Message):
    userid = message.from_user.id
    with open('data/admins.json', 'r') as file:
        admin_data = json.load(file)
    
    admins = admin_data.get("admins", [])
    
    if userid == int(Owner) or userid in admins:
        admin_keyboard = InlineKeyboardMarkup(row_width=1)
        admin_keyboard.add(
            InlineKeyboardButton(await get_text('adminb', 'add_deals', message.from_user.id), callback_data="userManager"),
            InlineKeyboardButton(await get_text('adminb', 'add_admin', message.from_user.id), callback_data="addAdmin"),
            InlineKeyboardButton(await get_text('adminb', 'confirm_deal', message.from_user.id), callback_data="cnf")
        )

        await message.reply(await get_text('admin', 'welcome', message.from_user.id), reply_markup=admin_keyboard)
    else:
        print(f"{userid} попытался зайти в админку")

@dp.callback_query_handler(lambda c: c.data == 'addAdmin')
async def process_callback_change_language(callback_query: types.CallbackQuery, state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    userid = callback_query.from_user.id
    with open('data/admins.json', 'r') as file:
        admins = json.load(file)

    if userid == Owner or userid in admins:
        await bot.send_message(callback_query.from_user.id, await get_text('admin', 'enter_user_id', callback_query.from_user.id))
        await adminaddd.waiting_for_admin.set()

@dp.message_handler(content_types=['text'], state=adminaddd.waiting_for_admin)
async def durak(message: types.Message, state: FSMContext):
    try:
        user_id = int(message.text.strip())
        try:
            with open('data/admins.json', 'r') as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"admins": [], "owner": None}
            
        if "admins" not in data:
            data["admins"] = []
            
        if user_id not in data["admins"]:
            data["admins"].append(user_id)
            
        with open('data/admins.json', 'w') as file:
            json.dump(data, file, indent=4)
            
        await message.answer(await get_text('admin', 'admin_added', message.from_user.id).format(user_id=user_id))
        await state.finish()
    except ValueError:
        await message.answer("Пожалуйста, введите корректный ID пользователя")
    await state.finish()   

@dp.callback_query_handler(lambda c: c.data == 'userManager')
async def func(callback_query: types.CallbackQuery,state: FSMContext):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, await get_text('admin', 'enter_deal_count', callback_query.from_user.id))
    await admnal.waiting_for_nal.set()
    


@dp.message_handler(content_types=['text'], state=admnal.waiting_for_nal)
async def dsdsad(message: types.Message, state: FSMContext):
    
    userid = message.from_user.id
    ton = message.text.strip()
    await execute_db_query(
    'UPDATE users SET sdelka = ? WHERE user_id = ?', 
    (ton, userid))
    await message.answer(await get_text('admin', 'deals_added', message.from_user.id).format(count=ton))
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == 'cnf')
async def picun(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    
    await bot.send_message(callback_query.from_user.id, await get_text('admin', 'enter_deal_id', callback_query.from_user.id))
    await ivanf.waiting_for_deal_id.set()

@dp.message_handler(content_types=['text'], state=ivanf.waiting_for_deal_id)
async def dsdsad(message: types.Message, state: FSMContext):
    deal_id = message.text.strip()
    with open(f'temp/#{deal_id}.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    user_id = data.get('userid')
    with open(f'temp/deal_{user_id}.json', 'r', encoding='utf-8') as f:
        deal_data = json.load(f)

    userd = deal_data['buyer_id']
    done = await get_text('deal', 'deal_confirmed', message.from_user.id)
    donedd = InlineKeyboardMarkup(row_width=1)
    donedd.add(InlineKeyboardButton("✅ Подтвердить выполнение", callback_data=f"acceptdeal_{user_id}"))  
    doned = await get_text('deal', 'seller_confirmed', message.from_user.id)

    await message.reply(done, reply_markup=None)
    await bot.send_message(userd, doned, reply_markup=donedd, parse_mode=types.ParseMode.MARKDOWN)


    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('acceptdeal_'))
async def accept_deal(callback_query: types.CallbackQuery):
    user_id = int(callback_query.data.split('_')[1])
    message = callback_query.message

    with open(f'temp/deal_{user_id}.json', 'r', encoding='utf-8') as f:
        deal_data = json.load(f)

    buy = deal_data['buyer_id']
    lk = deal_data['linkid']

    await bot.answer_callback_query(callback_query.id)
    await message.reply(await get_text('deal', 'deal_success', callback_query.from_user.id), parse_mode=types.ParseMode.MARKDOWN)
    await bot.send_message(user_id, await get_text('deal', 'deal_success', callback_query.from_user.id), parse_mode=types.ParseMode.MARKDOWN)
    os.remove(f'temp/{buy}.json')
    os.remove(f'temp/deal_{user_id}.json')
    os.remove(f'temp/#{lk}.json')
    

@dp.callback_query_handler(lambda c: c.data.startswith('cancel_deal_'))
async def lavanda(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    idd = callback_query.data.split('_')
    message = callback_query.message
    id = idd[2]
    ru = await get_text('deal', 'cancel_confirmation', callback_query.from_user.id).format(id=id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(await get_text('adminb', 'confirm_leave', callback_query.from_user.id), callback_data=f"confirm_cancel_deal_{id}"),
        InlineKeyboardButton(await get_text('adminb', 'cancel_action', callback_query.from_user.id), callback_data="cancel_action")
    )
    await message.reply(ru,reply_markup=keyboard, parse_mode=types.ParseMode.MARKDOWN)

@dp.callback_query_handler(lambda c: c.data.startswith('confirm_cancel_deal_'))
async def son(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    id = callback_query.data.split('_')[3]

    with open(f'temp/#{id}.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    createrid = data['userid']
 
    await bot.send_message(createrid, await get_text('deal', 'cancelled', callback_query.from_user.id))
    os.remove(f'temp/#{id}.json')
    os.remove(f'temp/deal_{createrid}.json')
# Запуск бота
if __name__ == '__main__':
    from aiogram import executor
    import os
    import logging

    # Создаем необходимые директории
    directories = ['temp', 'logs', 'data']
    for directory in directories:
        if not os.path.exists(directory):
            os.makedirs(directory)
            logging.info(f'Created directory: {directory}')

    # Логируем запуск бота
    print("Bot started")
    logging.info("Bot started")

    # Запускаем бота
    executor.start_polling(dp, skip_updates=True)