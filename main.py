import os
import logging
import requests
import httpx
import asyncio
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes, CommandHandler, ConversationHandler, CallbackQueryHandler
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardRemove
from telegram.constants import ParseMode

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', 
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Bot configuration
TOKEN = ("8114314056:AAE3GWzbQjF-86-L2vrFA-Wrp-SAC3aLYSc")

# Admin and channel verification
ADMIN_IDS = [1074750898]
REQUIRED_CHANNELS = [
    {
        "username": "OSINT", 
        "url": "https://t.me/+g0PXmxFjHWs1MTE1", 
        "chat_id": "-1002830525000"  # OSINT private channel chat ID
    },
    {
        "username": "UR_IMAGE", 
        "url": "https://t.me/UR_IMAGE", 
        "chat_id": "-1002508479565"  # UR_IMAGE public channel chat ID
    }
]

# Get environment variables
MOBILE_SEARCH_API = os.getenv("MOBILE_SEARCH_API", "https://doxit.me/?key=icodeinbinary&mobile=")
AADHAR_SEARCH_API = os.getenv("AADHAR_SEARCH_API", "https://doxit.me/?key=icodeinbinary&aadhaar=")
AGE_API = "https://doxit.me/?key=icodeinbinary&age="
VEHICLE_API = "http://3.109.155.50/rc-details/"
VEHICLE_API_KEY = "king_bhai_2388d259"
SOCIAL_LINKS_API = "https://social-links-search.p.rapidapi.com/search-social-links"
SOCIAL_LINKS_API_KEY = "525a6a5a93msh3b9d06f41651572p16ef82jsnfb8eeb3cc004"
BREACH_API = "https://doxit.me/?key=icodeinbinary&breach="

# Conversation states

ENTER_MOBILE = 10
ENTER_AADHAR = 20
ENTER_SOCIAL = 30
ENTER_AGE = 40
ENTER_EMAIL = 50
ENTER_VEHICLE = 60

# User data dictionary to store temporary data
user_data_dict = {}

# Helper function to get data with retry mechanism
async def get_api_data(url, max_retries=5, delay=1):
    retries = 0
    last_error = None
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Connection': 'keep-alive',
    }
    
    while retries < max_retries:
        try:
            # Use synchronous requests instead of httpx for better compatibility
            response = requests.get(url, headers=headers, timeout=10.0)
            
            # Log the response for debugging
            logger.info(f"API Response: Status={response.status_code}, Content={response.text[:100]}...")
            
            if response.status_code == 200:
                try:
                    # Check if response is a JSON array
                    if response.text.strip().startswith('['):
                        # Parse as array and wrap in data object
                        data_array = response.json()
                        return {"data": data_array}
                    else:
                        # Try to parse as regular JSON object
                        data = response.json()
                        if "data" in data:
                            return data
                        else:
                            # If no data field but valid JSON, wrap in data object
                            return {"data": [data] if not isinstance(data, list) else data}
                except ValueError as e:
                    # If response is not valid JSON, log error
                    logger.error(f"Invalid JSON response: {response.text[:200]}, Error: {str(e)}")
                    return {"error": "Invalid JSON response from API"}
            
            # If API returned error, try again
            logger.error(f"API returned error {response.status_code}, retrying {retries+1}/{max_retries}...")
            
            # Increase delay with each retry (exponential backoff)
            await asyncio.sleep(delay)
            delay *= 2
            retries += 1
            
        except Exception as e:
            last_error = str(e)
            logger.error(f"Error fetching data: {last_error}, retrying {retries+1}/{max_retries}...")
            await asyncio.sleep(delay)
            delay *= 2
            retries += 1
    
    # If all retries failed, return error
    return {"error": f"Failed after {max_retries} attempts. Last error: {last_error}"}

# Channel membership verification
async def check_channel_membership(context: ContextTypes.DEFAULT_TYPE, user_id: int):
    """Check if user is a member of all required channels"""
    # Admin bypass
    if user_id in ADMIN_IDS:
        return True
    
    try:
        for channel in REQUIRED_CHANNELS:
            chat_id = channel["chat_id"]
            
            # Check membership status
            try:
                member = await context.bot.get_chat_member(chat_id, user_id)
                
                # Check if user is a valid member (not left or kicked)
                if member.status not in ['member', 'administrator', 'creator']:
                    logger.info(f"User {user_id} is not a member of {channel['username']}")
                    return False
                    
            except Exception as e:
                error_msg = str(e).lower()
                logger.error(f"Error checking membership for channel {channel['username']}: {str(e)}")
                
                # If we can't check membership, assume user is not a member
                return False
        
        return True
        
    except Exception as e:
        logger.error(f"Error in channel membership check: {str(e)}")
        return False

async def send_join_channels_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message asking user to join required channels"""
    try:
        # Create inline keyboard with channel join buttons
        keyboard = []
        for channel in REQUIRED_CHANNELS:
            keyboard.append([InlineKeyboardButton(f"Join @{channel['username']}", url=channel['url'])])
        
        # Add check membership button
        keyboard.append([InlineKeyboardButton("✅ I've joined all channels", callback_data="check_membership")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message_text = "🔒 To use this bot, you need to join our channels first:"
        
        await update.message.reply_text(
            message_text,
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error sending join channels message: {str(e)}")
        await update.message.reply_text("Error: Could not verify channel membership. Please try again later.")

async def verify_membership_middleware(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Middleware to check channel membership before processing any request"""
    user_id = update.effective_user.id
    
    # Admin bypass
    if user_id in ADMIN_IDS:
        return True
    
    # Check membership
    is_member = await check_channel_membership(context, user_id)
    if not is_member:
        await send_join_channels_message(update, context)
        return False
    
    return True

# Handle callback queries for membership check
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks"""
    query = update.callback_query
    
    if query.data == "check_membership":
        user_id = query.from_user.id
        chat_id = query.message.chat.id
        
        # Check if user joined all channels
        is_member = await check_channel_membership(context, user_id)
        
        if is_member:
            # Delete the join channels message
            try:
                await query.message.delete()
            except Exception as e:
                logger.error(f"Error deleting message: {str(e)}")
            
            # Create reply keyboard with bot features
            keyboard = [
                ["Mobile Search 📱", "Aadhar Search 🔎"],
                ["Social Media Search 🌐", "Breach Check 🔒"],
                ["Age Check 👶", "Vehicle Info 🚗"]
            ]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            
            # Send welcome message with keyboard
            await context.bot.send_message(
                chat_id,
                "🔥 Welcome to NumInfo Bot 🔥\n\n"
                "🔍 Features:\n"
                "• Mobile Number Search\n"
                "• Aadhar Number Search\n"
                "• Social Media Profiles\n"
                "• Email Breach Check\n"
                "• Age Check from Aadhar\n"
                "• Vehicle RC Information\n\n"
                "👨‍💻 Developer: @icodeinbinary\n\n"
                "Select an option below👇",
                reply_markup=reply_markup
            )
            
            await query.answer()
        else:
            # Send alert that they need to join all channels
            await query.answer(
                "❌ You need to join all channels to use this bot.",
                show_alert=True
            )

# Search functions
async def mobile_search(update: Update, mobile: str):
    # If the mobile is "Back to Menu", ignore it
    if mobile == "⬅️ Back to Menu":
        return
        
    try:
        # Send a "searching" message
        searching_message = await update.message.reply_text("🔍 Searching... This may take a moment.")
        
        # Log the API URL for debugging
        api_url = f"{MOBILE_SEARCH_API}{mobile}"
        logger.info(f"Calling API: {api_url}")
        
        # Use the async retry mechanism
        data = await get_api_data(api_url)
        
        # Delete the "searching" message
        await searching_message.delete()
        
        if "error" in data:
            await update.message.reply_text(f"Error: {data['error']}")
            return
        
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
            # Try direct API call as fallback
            try:
                logger.info("Trying direct API call as fallback")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                }
                response = requests.get(api_url, headers=headers)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if "data" in data and data["data"]:
                            count = len(data["data"])
                            await update.message.reply_text(f"Found {count} result(s) for mobile: {mobile}")
                            
                            # Process data as before
                            for i, person in enumerate(data["data"]):
                                mobile_num = person.get('mobile', 'N/A')
                                alt_mobile = person.get('alt', 'N/A')
                                person_id = person.get('id', 'N/A')
                                
                                result = (
                                    f"Person Information ({i+1}/{count}):\n\n"
                                    f"👤 *Name*: {person.get('name', 'N/A')}\n"
                                    f"👨‍👦 *Father's Name*: {person.get('fname', 'N/A')}\n"
                                    f"🏠 *Address*: `{person.get('address', 'N/A').replace('!', ', ')}`\n"
                                    f"🌎 *Circle*: {person.get('circle', 'N/A')}\n\n"
                                )
                                
                                result += f"📱 *Mobile*: `{mobile_num}`\n"
                                result += f"📞 *Alt Mobile*: `{alt_mobile}`\n"
                                result += f"🆔 *ID*: `{person_id}`"
                                
                                if 'email' in person and person.get('email'):
                                    email = person.get('email')
                                    result += f"\n📧 *Email*: `{email}`"
                                
                                await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                            return
                    except Exception as e:
                        logger.error(f"Error parsing fallback response: {str(e)}")
            except Exception as e:
                logger.error(f"Fallback API call failed: {str(e)}")
            
            await update.message.reply_text("No information found for this mobile number.")
    except Exception as e:
        logger.error(f"Error in mobile search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

async def aadhar_search(update: Update, aadhar: str):
    # If the aadhar is "Back to Menu", ignore it
    if aadhar == "⬅️ Back to Menu":
        return
        
    try:
        # Send a "searching" message
        searching_message = await update.message.reply_text("🔍 Searching... This may take a moment.")
        
        # Log the API URL for debugging
        api_url = f"{AADHAR_SEARCH_API}{aadhar}"
        logger.info(f"Calling API: {api_url}")
        
        # Use the async retry mechanism
        data = await get_api_data(api_url)
        
        # Delete the "searching" message
        await searching_message.delete()
        
        if "error" in data:
            await update.message.reply_text(f"Error: {data['error']}")
            return
            
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
            # Try direct API call as fallback
            try:
                logger.info("Trying direct API call as fallback")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                }
                response = requests.get(api_url, headers=headers)
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if "data" in data and data["data"]:
                            count = len(data["data"])
                            await update.message.reply_text(f"Found {count} result(s) for Aadhar: {aadhar}")
                            
                            # Process data as before
                            for i, person in enumerate(data["data"]):
                                mobile_num = person.get('mobile', 'N/A')
                                alt_mobile = person.get('alt', 'N/A')
                                person_id = person.get('id', 'N/A')
                                
                                result = (
                                    f"Person Information ({i+1}/{count}):\n\n"
                                    f"👤 *Name*: {person.get('name', 'N/A')}\n"
                                    f"👨‍👦 *Father's Name*: {person.get('fname', 'N/A')}\n"
                                    f"🏠 *Address*: `{person.get('address', 'N/A').replace('!', ', ')}`\n"
                                    f"🌎 *Circle*: {person.get('circle', 'N/A')}\n\n"
                                )
                                
                                result += f"📱 *Mobile*: `{mobile_num}`\n"
                                result += f"📞 *Alt Mobile*: `{alt_mobile}`\n"
                                result += f"🆔 *ID*: `{person_id}`"
                                
                                if 'email' in person and person.get('email'):
                                    email = person.get('email')
                                    result += f"\n📧 *Email*: `{email}`"
                                
                                await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                            return
                    except Exception as e:
                        logger.error(f"Error parsing fallback response: {str(e)}")
            except Exception as e:
                logger.error(f"Fallback API call failed: {str(e)}")
            
            await update.message.reply_text("No information found for this Aadhar number.")
    except Exception as e:
        logger.error(f"Error in Aadhar search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

# Age range search function using doxit.me API
async def age_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if an argument was provided
    if not context.args:
        await update.message.reply_text("Please provide an Aadhaar number after the /age command.")
        return
    
    aadhar_number = context.args[0]
    
    # If the aadhar number is "Back to Menu", ignore it
    if aadhar_number == "⬅️ Back to Menu":
        return
    
    # Validate Aadhaar number format (12 digits)
    if not aadhar_number.isdigit() or len(aadhar_number) != 12:
        await update.message.reply_text("Please provide a valid 12-digit Aadhaar number.")
        return
    
    try:
        # Send a "searching" message
        searching_message = await update.message.reply_text("🔍 Searching for age information... This may take a moment.")
        
        # doxit.me API endpoint
        api_url = f"{AGE_API}{aadhar_number}"
        logger.info(f"Calling age API: {api_url}")
        
        # Make direct API call
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
        }
        
        response = requests.get(api_url, headers=headers, timeout=10.0)
        
        # Delete the "searching" message
        await searching_message.delete()
        
        if response.status_code == 200:
            try:
                data = response.json()
                
                # Check if the response is successful and contains data
                if data.get("success") and "data" in data:
                    age_data = data["data"]
                    
                    # Extract information from the response
                    age_range = age_data.get("age_range", "Not available")
                    state = age_data.get("state", "Not available")
                    gender = age_data.get("gender", "Not available")
                    last_digits = age_data.get("last_digits", "Not available")
                    is_mobile = age_data.get("is_mobile", False)
                    aadhaar_masked = age_data.get("aadhaar_number", "Not available")
                    
                    # Format gender
                    gender_text = "Male" if gender == "M" else "Female" if gender == "F" else gender
                    
                    # Format mobile status
                    mobile_status = "Yes" if is_mobile else "No"
                    
                    # Create detailed result message
                    result = f"🔍 *Aadhaar Information Found*\n\n"
                    result += f"👤 *Aadhaar*: `{aadhaar_masked}`\n"
                    result += f"🎂 *Age Range*: `{age_range}`\n"
                    result += f"🚻 *Gender*: `{gender_text}`\n"
                    result += f"🏛️ *State*: `{state}`\n"
                    result += f"🔢 *Last Digits*: `{last_digits}`\n"
                    result += f"📱 *Mobile Linked*: `{mobile_status}`"
                    
                    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                    
                else:
                    # If there's an error or no data
                    error_msg = data.get("message", "Could not retrieve age information")
                    await update.message.reply_text(f"❌ {error_msg}")
                    
            except ValueError as e:
                logger.error(f"Invalid JSON response: {response.text[:200]}")
                await update.message.reply_text("Error: Invalid response from age API")
        else:
            await update.message.reply_text(f"Error checking age data: Status code {response.status_code}")
    
    except Exception as e:
        logger.error(f"Error in age search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")



# Cancel conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data_dict:
        del user_data_dict[user_id]
    
    await update.message.reply_text("Operation cancelled.")
    return ConversationHandler.END

# Social links search function
async def social_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if an argument was provided
    if not context.args:
        await update.message.reply_text("Please provide a username or person name after the /social command.")
        return
    
    # Join all arguments to handle names with spaces
    query = " ".join(context.args)
    
    # If the query is "Back to Menu", ignore it
    if query == "⬅️ Back to Menu":
        return
    
    try:
        # Define social networks to search
        social_networks = "facebook,tiktok,instagram,snapchat,twitter,youtube,linkedin,github,pinterest"
        
        # Prepare API request
        querystring = {
            "query": query,
            "social_networks": social_networks
        }
        
        headers = {
            "x-rapidapi-key": SOCIAL_LINKS_API_KEY,
            "x-rapidapi-host": "social-links-search.p.rapidapi.com"
        }
        
        # Make the API request
        response = requests.get(SOCIAL_LINKS_API, headers=headers, params=querystring)
        data = response.json()
        
        # Check if the response is successful
        if response.status_code == 200 and data.get("status") == "OK" and "data" in data:
            result_data = data["data"]
            
            # Create a formatted message with all social media links using HTML formatting
            result_message = f"🔍 <b>Social Media Profiles for '{query}'</b>\n\n"
            
            # Check if any social media profiles were found
            profiles_found = False
            
            # Process each social network
            for network, links in result_data.items():
                if links:  # If there are links for this network
                    profiles_found = True
                    # Add network name with proper capitalization
                    result_message += f"<b>{network.capitalize()}</b>:\n"
                    
                    # Add all links for each network as normal text (clickable)
                    for link in links:
                        result_message += f"• {link}\n"
                    
                    result_message += "\n"
            
            # Split the message if it's too long (Telegram has a 4096 character limit)
            if len(result_message) > 4000:
                # Send results platform by platform
                await update.message.reply_text(f"🔍 <b>Social Media Profiles for '{query}'</b>\n\nFound profiles on multiple platforms. Sending results separately for each platform.", parse_mode=ParseMode.HTML)
                
                for network, links in result_data.items():
                    if links:
                        platform_message = f"<b>{network.capitalize()}</b> profiles for '{query}':\n\n"
                        for link in links:
                            platform_message += f"• {link}\n"
                        
                        # Send each platform's results as a separate message
                        if len(platform_message) > 4000:
                            # If even a single platform has too many links, split it further
                            chunks = [links[i:i+30] for i in range(0, len(links), 30)]
                            for i, chunk in enumerate(chunks):
                                chunk_msg = f"<b>{network.capitalize()}</b> profiles for '{query}' (part {i+1}/{len(chunks)}):\n\n"
                                for link in chunk:
                                    chunk_msg += f"• {link}\n"
                                await update.message.reply_text(chunk_msg, parse_mode=ParseMode.HTML)
                        else:
                            await update.message.reply_text(platform_message, parse_mode=ParseMode.HTML)
            else:
                # If the message is not too long, send it as one message
                if profiles_found:
                    await update.message.reply_text(result_message, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text(f"No social media profiles found for '{query}'.")
        else:
            # If there's an error or no data
            error_msg = data.get("message", "Unknown error occurred")
            await update.message.reply_text(f"Could not retrieve social media profiles: {error_msg}")
    
    except Exception as e:
        logger.error(f"Error in social search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

# Breach check function using doxit.me API
async def breach_check(update: Update, email: str):
    # If the email is "Back to Menu", ignore it
    if email == "⬅️ Back to Menu":
        return
        
    try:
        # Send a "searching" message
        searching_message = await update.message.reply_text("🔍 Checking for breaches... This may take a moment.")
        
        # doxit.me API endpoint
        api_url = f"{BREACH_API}{email}"
        logger.info(f"Calling breach API: {api_url}")
        
        # Make direct API call since doxit.me returns the data directly
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
        }
        
        response = requests.get(api_url, headers=headers, timeout=10.0)
        
        # Delete the "searching" message
        await searching_message.delete()
        
        if response.status_code == 200:
            try:
                breach_data = response.json()
                
                # Check if the response contains breach information
                if 'breaches' in breach_data and breach_data['breaches']:
                    breaches = breach_data['breaches']
                    breach_count = len(breaches)
                    
                    # Create message with breach information
                    result = f"⚠️ *Email Breach Alert* ⚠️\n\n"
                    result += f"The email `{email}` has been found in *{breach_count} data breaches*:\n\n"
                    
                    # Display breach information with more details
                    for i, breach in enumerate(breaches):
                        breach_name = breach.get('Name', 'Unknown')
                        breach_date = breach.get('BreachDate', 'Unknown')
                        description = breach.get('Description', 'No description available')
                        data_classes = breach.get('DataClasses', [])
                        
                        result += f"🔴 *{breach_name}*\n"
                        result += f"📅 Date: `{breach_date}`\n"
                        result += f"📝 Info: {description}\n"
                        
                        if data_classes:
                            data_types = ", ".join(data_classes)
                            result += f"💾 Data: `{data_types}`\n"
                        
                        result += "\n"
                        
                        # Split message if it gets too long (Telegram limit is 4096 chars)
                        if len(result) > 3500:
                            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                            result = f"*Continued breaches for {email}:*\n\n"
                    
                    # Send final message if there's remaining content
                    if result.strip() and not result.startswith("*Continued breaches"):
                        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                    elif result.startswith("*Continued breaches") and len(result) > 50:
                        await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                        
                else:
                    # No breaches found
                    await update.message.reply_text(f"✅ Good news! The email `{email}` has NOT been found in any known data breaches.", parse_mode=ParseMode.MARKDOWN)
                    
            except ValueError as e:
                logger.error(f"Invalid JSON response: {response.text[:200]}")
                await update.message.reply_text("Error: Invalid response from breach API")
        else:
            await update.message.reply_text(f"Error checking breach data: Status code {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error in breach check: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

# Vehicle info search function
async def vehicle_search(update: Update, vehicle_number: str):
    # If the vehicle number is "Back to Menu", ignore it
    if vehicle_number == "⬅️ Back to Menu":
        return
        
    try:
        # Send a "searching" message
        searching_message = await update.message.reply_text("🔍 Searching for vehicle information... This may take a moment.")
        
        # Clean vehicle number (remove spaces and hyphens)
        cleaned_vehicle_number = vehicle_number.replace(" ", "").replace("-", "").upper()
        
        # Vehicle API endpoint
        api_url = f"{VEHICLE_API}{cleaned_vehicle_number}?api_key={VEHICLE_API_KEY}"
        logger.info(f"Calling vehicle API: {api_url}")
        
        # Make direct API call
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json',
        }
        
        response = requests.get(api_url, headers=headers, timeout=10.0)
        
        # Delete the "searching" message
        await searching_message.delete()
        
        if response.status_code == 200:
            try:
                vehicle_data = response.json()
                
                # Check if vehicle data was found
                if vehicle_data.get("RegistrationNumber"):
                    # Extract key information
                    reg_number = vehicle_data.get("VehicleNumber", "N/A")
                    owner_name = vehicle_data.get("OwnerName", "N/A")
                    father_name = vehicle_data.get("FatherName", "N/A")
                    mobile_number = vehicle_data.get("MobileNumber", "N/A")
                    vehicle_class = vehicle_data.get("VehicleClass", "N/A")
                    vehicle_model = vehicle_data.get("VehicleModel", "N/A")
                    maker_desc = vehicle_data.get("MakerDesc", "N/A")
                    fuel = vehicle_data.get("Fuel", "N/A")
                    color = vehicle_data.get("Color", "N/A")
                    reg_date = vehicle_data.get("RegistrationDate", "N/A")
                    rc_expiry = vehicle_data.get("RCExpiryDate", "N/A")
                    vehicle_status = vehicle_data.get("VehicleStatus", "N/A")
                    permanent_address = vehicle_data.get("PermanentAddress", "N/A")
                    present_address = vehicle_data.get("PresentAddress", "N/A")
                    insurance_company = vehicle_data.get("InsuranceCompany", "N/A")
                    insurance_upto = vehicle_data.get("InsuranceUpto", "N/A")
                    pucc_upto = vehicle_data.get("PUCCUpto", "N/A")
                    rto_name = vehicle_data.get("RTOName", "N/A")
                    chasi_no = vehicle_data.get("ChasiNo", "N/A")
                    engine_no = vehicle_data.get("EngineNo", "N/A")
                    
                    # Create comprehensive result message
                    result = f"🚗 *Vehicle Information Found*\n\n"
                    
                    # Owner Details
                    result += f"👤 *Owner Information:*\n"
                    result += f"• Name: `{owner_name}`\n"
                    result += f"• Father's Name: `{father_name}`\n"
                    result += f"• Mobile: `{mobile_number}`\n\n"
                    
                    # Vehicle Details
                    result += f"🚙 *Vehicle Details:*\n"
                    result += f"• Number: `{reg_number}`\n"
                    result += f"• Status: `{vehicle_status}`\n"
                    result += f"• Class: `{vehicle_class}`\n"
                    result += f"• Model: `{vehicle_model}`\n"
                    result += f"• Manufacturer: `{maker_desc}`\n"
                    result += f"• Fuel: `{fuel}`\n"
                    result += f"• Color: `{color}`\n\n"
                    
                    # Registration & Dates
                    result += f"📅 *Registration & Validity:*\n"
                    result += f"• Reg Date: `{reg_date}`\n"
                    result += f"• RC Expiry: `{rc_expiry}`\n"
                    result += f"• RTO: `{rto_name}`\n\n"
                    
                    await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
                    
                    # Send second message with additional details
                    result2 = f"📍 *Address Information:*\n"
                    result2 += f"• Permanent: `{permanent_address}`\n"
                    result2 += f"• Present: `{present_address}`\n\n"
                    
                    result2 += f"🔢 *Technical Details:*\n"
                    result2 += f"• Chassis No: `{chasi_no}`\n"
                    result2 += f"• Engine No: `{engine_no}`\n\n"
                    
                    result2 += f"🛡️ *Insurance & PUC:*\n"
                    result2 += f"• Insurance: `{insurance_company}`\n"
                    result2 += f"• Insurance Valid Till: `{insurance_upto}`\n"
                    result2 += f"• PUC Valid Till: `{pucc_upto}`"
                    
                    await update.message.reply_text(result2, parse_mode=ParseMode.MARKDOWN)
                    
                else:
                    # No vehicle data found
                    await update.message.reply_text(f"❌ No vehicle information found for: {vehicle_number}")
                    
            except ValueError as e:
                logger.error(f"Invalid JSON response: {response.text[:200]}")
                await update.message.reply_text("Error: Invalid response from vehicle API")
        else:
            await update.message.reply_text(f"Error checking vehicle data: Status code {response.status_code}")
            
    except Exception as e:
        logger.error(f"Error in vehicle search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

# Main menu function with full welcome message
async def show_welcome_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Create reply keyboard with only necessary buttons
    keyboard = [
        ["Mobile Search 📱", "Aadhar Search 🔎"],
        ["Social Media Search 🌐", "Breach Check 🔒"],
        ["Age Check 👶", "Vehicle Info 🚗"]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # Send the welcome message with the keyboard
    await update.message.reply_text(
        text="*🔥 Welcome to NumInfo Bot 🔥*\n\n"
        "*🔍 Features:*\n"
        "• Mobile Number Search\n"
        "• Aadhar Number Search\n"
        "• Social Media Profiles\n"
        "• Email Breach Check\n"
        "• Age Check from Aadhar\n"
        "• Vehicle RC Information\n\n"
        "*👨‍💻 Developer:* @icodeinbinary\n\n"
        "*Select an option below👇*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    
    return ConversationHandler.END

# Show menu with simple message
async def show_simple_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Create reply keyboard with only necessary buttons
    keyboard = [
        ["Mobile Search 📱", "Aadhar Search 🔎"],
        ["Social Media Search 🌐", "Breach Check 🔒"],
        ["Age Check 👶", "Vehicle Info 🚗"]
    ]
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    # If this is from a command, send as a new message
    if update.message:
        await update.message.reply_text(
            text="*Select options to search more👇*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    # Otherwise, send as a regular message
    else:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="*Select options to search more👇*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=reply_markup
        )
    
    return ConversationHandler.END

# Main message handler
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Check channel membership first
    if not await verify_membership_middleware(update, context):
        return ConversationHandler.END
    
    # Handle first-time users with welcome message
    if text.lower() in ['/start', 'start', 'hi', 'hello']:
        return await show_welcome_menu(update, context)
    
    # Handle end command
    if text.lower() in ['/end', 'end']:
        return await show_simple_menu(update, context)
    
    # Handle back to menu button
    if text == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Handle help request
    if text.lower() in ['/help', 'help']:
        await update.message.reply_text(
            f"📋 *How to use this bot*:\n\n"
            f"Click on the buttons at the bottom of the chat to access different features:\n"
            f"• Mobile Search - Search by 10-digit mobile number\n"
            f"• Aadhar Search - Search by 12-digit Aadhar number\n"
            f"• Social Media Search - Find social profiles by name/username\n"
            f"• Breach Check - Check if email was in data breaches\n"
            f"• Age Check - Get age range from Aadhar number\n"
            f"• Vehicle Info - Get RC details by vehicle number\n\n"
            f"Use /start to see the welcome message\n"
            f"Use /end to show the menu buttons\n\n"
            f"Developer: @icodeinbinary",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    # Handle button presses
    if text == "Mobile Search 📱":
        # Create keyboard with back button
        keyboard = [["⬅️ Back to Menu"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please enter a 10-digit mobile number to search:",
            reply_markup=reply_markup
        )
        user_data_dict[update.effective_user.id] = {"next_action": "mobile_search"}
        return ENTER_MOBILE
    
    elif text == "Aadhar Search 🔎":
        # Create keyboard with back button
        keyboard = [["⬅️ Back to Menu"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please enter a 12-digit Aadhar number to search:",
            reply_markup=reply_markup
        )
        user_data_dict[update.effective_user.id] = {"next_action": "aadhar_search"}
        return ENTER_AADHAR
    
    elif text == "Social Media Search 🌐":
        # Create keyboard with back button
        keyboard = [["⬅️ Back to Menu"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please enter a username or person name to search for social media profiles:",
            reply_markup=reply_markup
        )
        user_data_dict[update.effective_user.id] = {"next_action": "social_search"}
        return ENTER_SOCIAL
    
    elif text == "Age Check 👶":
        # Create keyboard with back button
        keyboard = [["⬅️ Back to Menu"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please enter a 12-digit Aadhar number to check age range:",
            reply_markup=reply_markup
        )
        user_data_dict[update.effective_user.id] = {"next_action": "age_search"}
        return ENTER_AGE
    
    elif text == "Vehicle Info 🚗":
        # Create keyboard with back button
        keyboard = [["⬅️ Back to Menu"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please enter a vehicle number (e.g., DL10AD7414, DL-10-AD-7414):",
            reply_markup=reply_markup
        )
        user_data_dict[update.effective_user.id] = {"next_action": "vehicle_search"}
        return ENTER_VEHICLE
    
    elif text == "Breach Check 🔒":
        # Create keyboard with back button
        keyboard = [["⬅️ Back to Menu"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please enter an email address to check for data breaches:",
            reply_markup=reply_markup
        )
        user_data_dict[update.effective_user.id] = {"next_action": "breach_check"}
        return ENTER_EMAIL
    
    # Check if the message is a number
    if text.isdigit():
        # If it's 10 digits, treat as mobile number
        if len(text) == 10:
            await mobile_search(update, text)
            # Show simple menu after search
            await show_simple_menu(update, context)
            return
        # If it's 12 digits, treat as Aadhar number
        elif len(text) == 12:
            await aadhar_search(update, text)
            # Show simple menu after search
            await show_simple_menu(update, context)
            return
        # If it's 11 digits, might be a mobile with country code
        elif len(text) == 11 and text.startswith('0'):
            # Remove leading 0
            await mobile_search(update, text[1:])
            # Show simple menu after search
            await show_simple_menu(update, context)
            return
    
    # For other text messages, show the simple menu
    return await show_simple_menu(update, context)

# Handle mobile number input
async def handle_mobile_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Check channel membership first
    if not await verify_membership_middleware(update, context):
        return ConversationHandler.END
    
    # Check if user wants to go back to menu
    if text == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Check if it's a valid mobile number
    if text.isdigit() and len(text) == 10:
        # Send a message that we're processing
        await update.message.reply_text(f"Searching for mobile: {text}...")
        
        # Call the existing mobile search function
        await mobile_search(update, text)
        
        # Show the simple menu after search is complete
        await show_simple_menu(update, context)
    else:
        await update.message.reply_text("Invalid number! Please enter a 10-digit mobile number.")
    
    return ConversationHandler.END

# Handle Aadhar number input
async def handle_aadhar_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Check channel membership first
    if not await verify_membership_middleware(update, context):
        return ConversationHandler.END
    
    # Check if user wants to go back to menu
    if text == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Check if it's a valid Aadhar number
    if text.isdigit() and len(text) == 12:
        user_id = update.effective_user.id
        if user_id in user_data_dict:
            next_action = user_data_dict[user_id].get("next_action")
            
            if next_action == "aadhar_search":
                # Send a message that we're processing
                await update.message.reply_text(f"Searching for Aadhar: {text}...")
                
                # Call the existing aadhar search function
                await aadhar_search(update, text)
            

        
        # Show the simple menu after search is complete
        await show_simple_menu(update, context)
    else:
        await update.message.reply_text("Invalid number! Please enter a 12-digit Aadhar number.")
    
    return ConversationHandler.END

# Handle social search input
async def handle_social_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.message.text
    
    # Check channel membership first
    if not await verify_membership_middleware(update, context):
        return ConversationHandler.END
    
    # Check if user wants to go back to menu
    if query == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Send a message that we're processing
    await update.message.reply_text(f"Searching for social media profiles for: {query}...")
    
    # Create a context.args-like structure for the existing function
    context.args = query.split()
    
    # Call the existing social search function
    await social_search(update, context)
    
    # Show the simple menu after search is complete
    await show_simple_menu(update, context)
    
    return ConversationHandler.END

# Handle age check input
async def handle_age_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    # Check channel membership first
    if not await verify_membership_middleware(update, context):
        return ConversationHandler.END
    
    # Check if user wants to go back to menu
    if text == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Check if it's a valid Aadhar number
    if text.isdigit() and len(text) == 12:
        # Send a message that we're processing
        await update.message.reply_text(f"Searching for age range with Aadhaar: {text}...")
        
        # Create a context.args-like structure for the existing function
        context.args = [text]
        
        # Call the existing age search function
        await age_search(update, context)
        
        # Show the simple menu after search is complete
        await show_simple_menu(update, context)
    else:
        await update.message.reply_text("Invalid number! Please enter a 12-digit Aadhar number.")
    
    return ConversationHandler.END

# Handle email input for breach check
async def handle_email_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text
    
    # Check channel membership first
    if not await verify_membership_middleware(update, context):
        return ConversationHandler.END
    
    # Check if user wants to go back to menu
    if email == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Basic email validation
    if '@' in email and '.' in email:
        # Send a message that we're processing
        await update.message.reply_text(f"Checking if email has been compromised: {email}...")
        
        # Call the breach check function
        await breach_check(update, email)
        
        # Show the simple menu after search is complete
        await show_simple_menu(update, context)
    else:
        await update.message.reply_text("Invalid email address! Please enter a valid email.")
    
    return ConversationHandler.END

# Handle vehicle number input
async def handle_vehicle_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    vehicle_number = update.message.text
    
    # Check channel membership first
    if not await verify_membership_middleware(update, context):
        return ConversationHandler.END
    
    # Check if user wants to go back to menu
    if vehicle_number == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Basic vehicle number validation (should have alphanumeric characters)
    if len(vehicle_number.replace(" ", "").replace("-", "")) >= 8:
        # Send a message that we're processing
        await update.message.reply_text(f"Searching for vehicle: {vehicle_number}...")
        
        # Call the vehicle search function
        await vehicle_search(update, vehicle_number)
        
        # Show the simple menu after search is complete
        await show_simple_menu(update, context)
    else:
        await update.message.reply_text("Invalid vehicle number! Please enter a valid vehicle registration number.")
    
    return ConversationHandler.END

if __name__ == "__main__":
    # Clear existing updates and build application
    requests.get(f"https://api.telegram.org/bot{TOKEN}/getUpdates?offset=-1")
    
    # Create application and add handlers
    app = ApplicationBuilder().token(TOKEN).build()
    
    # Add conversation handlers
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", show_welcome_menu),
            CommandHandler("end", show_simple_menu),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
        ],
        states={
            ENTER_MOBILE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mobile_input)],
            ENTER_AADHAR: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_aadhar_input)],
            ENTER_SOCIAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_social_input)],
            ENTER_AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_age_input)],
            ENTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_input)],
            ENTER_VEHICLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vehicle_input)]
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)]
    )
    
    app.add_handler(conv_handler)
    
    # Add callback query handler for membership verification
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Run the bot
    print("Starting bot...")
    app.run_polling(drop_pending_updates=True) 
