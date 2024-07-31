import logging
import random
import string
import gspread
import requests
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, CallbackQueryHandler, ConversationHandler
from datetime import datetime

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Your bot token from BotFather
TOKEN = 'your_token'

# Google Sheets setup
scope = [
'https://www.googleapis.com/auth/spreadsheets',
'https://www.googleapis.com/auth/drive'
]
creds = ServiceAccountCredentials.from_json_keyfile_name('your_credentials.json', scope)
client = gspread.authorize(creds)
sheet = client.open("google_sheet_name").sheet1

# Define states for conversation handler
CHOOSING_ITEM, TYPING_ADDRESS, TYPING_NAME, TYPING_PHONE, ORDER_CHECK, TO_MENU, CHECKING_DETAILS = range(7)

# Define available goods
GOODS = [
    {'name': 'good_name', 'price': '40000'}
]

def get_max_row_id() -> int:
    row_ids = sheet.col_values(1)[1:]
    row_ids = [int(value) for value in row_ids if value.isdigit()]
    return max(row_ids, default=0)

def start(update: Update, context: CallbackContext) -> int:
    update.message.reply_text(f"""Welcome to this bot.
                                    """)
    keyboard = [
        [InlineKeyboardButton("Place an order", callback_data='create')],
        [InlineKeyboardButton("Check my order status", callback_data='check')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Select:', reply_markup=reply_markup)
    return CHOOSING_ITEM

def button(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    if query.data == 'create':
        keyboard = [
            [InlineKeyboardButton(f"{item['name']} - price is {item['price']}", callback_data=item['name'])] for item in GOODS
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.edit_message_text(text="Choose a good:", reply_markup=reply_markup)
        return CHOOSING_ITEM
    elif query.data == 'check':
        query.edit_message_text(text="Enter your order number:")
        return ORDER_CHECK

def choose_item(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    context.user_data['item'] = query.data
    for item in GOODS:
        if item['name'] == query.data:
            context.user_data['price'] = item['price']
            break
    query.edit_message_text(text=f"You have chosen {query.data}. PLease provide your address:")
    return TYPING_ADDRESS

def receive_address(update: Update, context: CallbackContext) -> int:
    context.user_data['address'] = update.message.text
    update.message.reply_text('Please provide your name:')
    return TYPING_NAME

def receive_name(update: Update, context: CallbackContext) -> int:
    context.user_data['name'] = update.message.text
    update.message.reply_text('Please provide your phone number:')
    return TYPING_PHONE

def receive_phone(update: Update, context: CallbackContext) -> int:
    context.user_data['phone'] = update.message.text
    order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
    context.user_data['order_id'] = order_id
    update.message.reply_text(f"""Your data: 
Address: {context.user_data['address']} 
Name: {context.user_data['name']} 
Phone: {context.user_data['phone']}""")
    keyboard = [
        [InlineKeyboardButton("Yes", callback_data='positive')],
        [InlineKeyboardButton("No", callback_data='negative')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('Correct?', reply_markup=reply_markup)
    return CHECKING_DETAILS


def check_details(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()
    if query.data == 'negative':
        query.message.reply_text('Re-enter your data.')
        query.message.reply_text("Please provide your address:")
        return TYPING_ADDRESS
    else:
        #order_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        #context.user_data['order_id'] = order_id
        max_row_id = get_max_row_id() + 1
        sheet.append_row([
            max_row_id,
            datetime.today().strftime('%Y-%m-%d'),
            context.user_data['address'],
            context.user_data['name'],
            context.user_data['phone'],
            context.user_data['order_id'],
            'создан'
        ])
        query.message.reply_text(f"Thank you! Your order number is {context.user_data['order_id']}.")
        keyboard = [[InlineKeyboardButton("Back to main menu", callback_data='back_to_menu')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        query.message.reply_text('Select:', reply_markup=reply_markup)
        return TO_MENU
    return TO_MENU

def check_order(update: Update, context: CallbackContext) -> int:
    order_id = update.message.text
    logger.info(f'Checking order ID: {order_id}')
    cell = sheet.find(order_id)
    if cell:
        order_data = sheet.row_values(cell.row)
        if order_data[5] == order_id:
            update.message.reply_text(f"Your order's status: {order_data[6]}")
            keyboard = [[InlineKeyboardButton("Back to main menu", callback_data='back_to_menu')]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text('Select:', reply_markup=reply_markup)
            return TO_MENU
        else:
            update.message.reply_text("Order number not found. Try again.")
            return ORDER_CHECK
    else:
        update.message.reply_text("Order number not found. Try again.")
        logger.warning(f'Order ID {order_id} not found')
        return ORDER_CHECK
    return TO_MENU

def to_main_menu(update: Update, context: CallbackContext) -> int:
    query = update.callback_query
    query.answer()

    keyboard = [
        [InlineKeyboardButton("Place an order", callback_data='create')],
        [InlineKeyboardButton("Check my order status", callback_data='check')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text('Select:', reply_markup=reply_markup)
    return CHOOSING_ITEM


def cancel(update: Update, context: CallbackContext) -> int:
    update.message.reply_text('Процесс заказа прерван.')
    return ConversationHandler.END

def main() -> None:
    updater = Updater(TOKEN)
    dispatcher = updater.dispatcher

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            CHOOSING_ITEM: [
                CallbackQueryHandler(button, pattern='^(create|check)$'),
                CallbackQueryHandler(choose_item)
            ],
            TYPING_ADDRESS: [MessageHandler(Filters.text & ~Filters.command, receive_address)],
            TYPING_NAME: [MessageHandler(Filters.text & ~Filters.command, receive_name)],
            TYPING_PHONE: [MessageHandler(Filters.text & ~Filters.command, receive_phone)],
            CHECKING_DETAILS: [CallbackQueryHandler(check_details, pattern='^(positive|negative)$')],
            ORDER_CHECK: [MessageHandler(Filters.text & ~Filters.command, check_order)],
            TO_MENU: [CallbackQueryHandler(to_main_menu, pattern='^back_to_menu$')]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    dispatcher.add_handler(conv_handler)

    updater.start_polling()
    logger.info('Bot started')
    updater.idle()

if __name__ == '__main__':
    main()




