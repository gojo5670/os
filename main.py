import os
import logging
import requests
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from telegram import Update
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Get environment variables
TOKEN = ("8114314056:AAE3GWzbQjF-86-L2vrFA-Wrp-SAC3aLYSc")
MOBILE_SEARCH_API = os.getenv("MOBILE_SEARCH_API", "https://stuff-pioneer-texts-possibility.trycloudflare.com/search?mobile=")
AADHAR_SEARCH_API = os.getenv("AADHAR_SEARCH_API", "https://stuff-pioneer-texts-possibility.trycloudflare.com/search?aadhar=")

# Search functions
async def mobile_search(update: Update, mobile: str):
    await update.message.reply_text(f"Searching for mobile: {mobile}...")
    
    try:
        response = requests.get(f"{MOBILE_SEARCH_API}{mobile}")
        data = response.json()
        
        if "data" in data and data["data"]:
            # First show how many results were found
            count = len(data["data"])
            await update.message.reply_text(f"Found {count} result(s) for mobile: {mobile}")
            
            # Process each person in the data array
            for i, person in enumerate(data["data"]):
                # Format information with copyable fields as code blocks
                mobile_num = person.get('mobile', 'N/A')
                alt_mobile = person.get('alt', 'N/A')
                person_id = person.get('id', 'N/A')
                
                # Prepare basic result
                result = (
                    f"Person Information ({i+1}/{count}):\n\n"
                    f"👤 *Name*: {person.get('name', 'N/A')}\n"
                    f"👨‍👦 *Father's Name*: {person.get('fname', 'N/A')}\n"
                    f"🏠 *Address*: `{person.get('address', 'N/A').replace('!', ', ')}`\n"
                    f"🌎 *Circle*: {person.get('circle', 'N/A')}\n\n"
                )
                
                # Add copyable information in horizontal format
                result += f"📱 *Mobile*: `{mobile_num}`\n"
                result += f"📞 *Alt Mobile*: `{alt_mobile}`\n"
                result += f"🆔 *ID*: `{person_id}`"
                
                # Add email if available
                if 'email' in person and person.get('email'):
                    email = person.get('email')
                    result += f"\n📧 *Email*: `{email}`"
                
                await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No information found for this mobile number.")
    except Exception as e:
        logger.error(f"Error in mobile search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

async def aadhar_search(update: Update, aadhar: str):
    await update.message.reply_text(f"Searching for Aadhar: {aadhar}...")
    
    try:
        response = requests.get(f"{AADHAR_SEARCH_API}{aadhar}")
        data = response.json()
        
        if "data" in data and data["data"]:
            # First show how many results were found
            count = len(data["data"])
            await update.message.reply_text(f"Found {count} result(s) for Aadhar: {aadhar}")
            
            # Process each person in the data array
            for i, person in enumerate(data["data"]):
                # Format information with copyable fields as code blocks
                mobile_num = person.get('mobile', 'N/A')
                alt_mobile = person.get('alt', 'N/A')
                person_id = person.get('id', 'N/A')
                
                # Prepare basic result
                result = (
                    f"Person Information ({i+1}/{count}):\n\n"
                    f"👤 *Name*: {person.get('name', 'N/A')}\n"
                    f"👨‍👦 *Father's Name*: {person.get('fname', 'N/A')}\n"
                    f"🏠 *Address*: `{person.get('address', 'N/A').replace('!', ', ')}`\n"
                    f"🌎 *Circle*: {person.get('circle', 'N/A')}\n\n"
                )
                
                # Add copyable information in horizontal format
                result += f"📱 *Mobile*: `{mobile_num}`\n"
                result += f"📞 *Alt Mobile*: `{alt_mobile}`\n"
                result += f"🆔 *ID*: `{person_id}`"
                
                # Add email if available
                if 'email' in person and person.get('email'):
                    email = person.get('email')
                    result += f"\n📧 *Email*: `{email}`"
                
                await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text("No information found for this Aadhar number.")
    except Exception as e:
        logger.error(f"Error in Aadhar search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

# Main message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Handle first-time users with welcome message
    if text.lower() in ['/start', 'start', 'hi', 'hello']:
        await update.message.reply_text(
            f"👋 Hello {update.effective_user.first_name}!\n\n"
            f"Send me a 10-digit mobile number to search by mobile.\n"
            f"Send me a 12-digit Aadhar number to search by Aadhar.\n\n"
            f"Developer: @icodeinbinary"
        )
        return
    
    # Handle help request
    if text.lower() in ['/help', 'help']:
        await update.message.reply_text(
            f"📋 *How to use this bot*:\n\n"
            f"📱 Send a 10-digit number to search by mobile\n"
            f"🆔 Send a 12-digit number to search by Aadhar\n\n"
            f"Developer: @icodeinbinary",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Check if the message is a number
    if text.isdigit():
        # If it's 10 digits, treat as mobile number
        if len(text) == 10:
            await mobile_search(update, text)
            return
        # If it's 12 digits, treat as Aadhar number
        elif len(text) == 12:
            await aadhar_search(update, text)
            return
        # If it's 11 digits, might be a mobile with country code
        elif len(text) == 11 and text.startswith('0'):
            # Remove leading 0
            await mobile_search(update, text[1:])
            return
        else:
            await update.message.reply_text(
                "Please send a valid number:\n"
                "• 10 digits for mobile number\n"
                "• 12 digits for Aadhar number"
            )
            return
    
    # If nothing matched
    await update.message.reply_text(
        "Please send a valid number:\n"
        "• 10 digits for mobile number\n"
        "• 12 digits for Aadhar number\n\n"
        "Type 'help' for more information."
    )

if __name__ == "__main__":
    # Clear existing updates and build application
    requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-1")
    
    # Create application and add handlers
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add message handler for all text messages
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    
    # Run the bot
    print("Starting bot...")
    app.run_polling(drop_pending_updates=True) 