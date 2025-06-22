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

# Get environment variables
TOKEN = ("7990227150:AAFOjim0xdbLJi_cWo14mMlP0rNiHTiai90")
MOBILE_SEARCH_API = os.getenv("MOBILE_SEARCH_API", "https://measure-placement-maximize-pension.trycloudflare.com/search?mobile=")
AADHAR_SEARCH_API = os.getenv("AADHAR_SEARCH_API", "https://measure-placement-maximize-pension.trycloudflare.com/search?aadhar=")
AADHAAR_AGE_API = "https://kyc-api.aadhaarkyc.io/api/v1/aadhaar-validation/aadhaar-validation"
AADHAAR_API_KEY = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJmcmVzaCI6ZmFsc2UsImlhdCI6MTY0MTIxNDczNSwianRpIjoiMmE4MWZkMTUtNWU0Yy00NjY1LWE0NTItYTE4ZDRmZTRkOTdkIiwidHlwZSI6ImFjY2VzcyIsImlkZW50aXR5IjoiZGV2LmtyNGFsbEBhYWRoYWFyYXBpLmlvIiwibmJmIjoxNjQxMjE0NzM1LCJleHAiOjE5NTY1NzQ3MzUsInVzZXJfY2xhaW1zIjp7InNjb3BlcyI6WyJyZWFkIl19fQ.xq-191hmb69EjYkJ5r4c2yAJNf2lMqnA_3PhfnCrzNY"
AADHAAR_TO_PAN_API = "https://aadhaar-to-full-pan.p.rapidapi.com/Aadhaar_to_pan"
SOCIAL_LINKS_API = "https://social-links-search.p.rapidapi.com/search-social-links"
SOCIAL_LINKS_API_KEY = "525a6a5a93msh3b9d06f41651572p16ef82jsnfb8eeb3cc004"
HIBP_API_KEY = "6d704d3eccc0484ca7777ccdf6ed02f2"
HIBP_API_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/"

# Conversation states
ENTER_API_KEY = 0
PROCESS_PAN = 1
ENTER_MOBILE = 10
ENTER_AADHAR = 20
ENTER_SOCIAL = 30
ENTER_AGE = 40
ENTER_EMAIL = 50

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

# Age range search function
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
        # Prepare API request
        payload = {
            "id_number": aadhar_number
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AADHAAR_API_KEY}"
        }
        
        # Make the API request
        response = requests.post(AADHAAR_AGE_API, json=payload, headers=headers)
        data = response.json()
        
        # Check if the response contains age_range
        if response.status_code == 200 and "data" in data and "age_range" in data["data"]:
            age_range = data["data"]["age_range"]
            await update.message.reply_text(
                f"🔍 *Age Range Result*\n\n"
                f"Aadhaar Number: `{aadhar_number}`\n"
                f"Age Range: *{age_range}*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # If there's an error or age_range is not available
            error_msg = data.get("message", "Unknown error occurred")
            await update.message.reply_text(f"Could not retrieve age range: {error_msg}")
    
    except Exception as e:
        logger.error(f"Error in age search: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

# PAN search function - start conversation
async def pan_search_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Check if an argument was provided
    if not context.args:
        await update.message.reply_text("Please provide an Aadhaar number after the /pan command.")
        return ConversationHandler.END
    
    aadhar_number = context.args[0]
    
    # Validate Aadhaar number format (12 digits)
    if not aadhar_number.isdigit() or len(aadhar_number) != 12:
        await update.message.reply_text("Please provide a valid 12-digit Aadhaar number.")
        return ConversationHandler.END
    
    # Store the Aadhaar number in user_data for later use
    user_id = update.effective_user.id
    user_data_dict[user_id] = {"aadhar_number": aadhar_number}
    
    await update.message.reply_text(
        "Please enter your Special Key🔑 for the Aadhaar to PAN API.\n\n"
        "If you don't have one, you can get it from 👉  @icodeinbinary\n"  
    )
    
    return ENTER_API_KEY

# Process API key and fetch PAN data
async def process_api_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    api_key = update.message.text.strip()
    
    # Delete the message with the API key for security
    try:
        await update.message.delete()
    except Exception as e:
        logger.error(f"Could not delete message: {str(e)}")
    
    if user_id not in user_data_dict:
        await update.message.reply_text("Session expired. Please start again with /pan command.")
        return ConversationHandler.END
    
    aadhar_number = user_data_dict[user_id]["aadhar_number"]
    
    # Store API key in user data
    user_data_dict[user_id]["api_key"] = api_key
    
    try:
        # Prepare API request
        payload = {
            "aadhaar_no": aadhar_number
        }
        
        headers = {
            "x-rapidapi-key": api_key,
            "x-rapidapi-host": "aadhaar-to-full-pan.p.rapidapi.com",
            "Content-Type": "application/json"
        }
        
        # Make the API request
        response = requests.post(AADHAAR_TO_PAN_API, json=payload, headers=headers)
        data = response.json()
        
        # Check if the response contains PAN information
        if response.status_code == 200 and data.get("status") == "success":
            pan_number = data["result"]["pan"]
            aadhaar_link_status = data["result"]["aadhaar_link_status"]
            
            status_text = "Linked" if aadhaar_link_status == "Y" else "Not Linked"
            
            await update.message.reply_text(
                f"🔍 *PAN Details Found*\n\n"
                f"Aadhaar Number: `{aadhar_number}`\n"
                f"PAN Number: `{pan_number}`\n"
                f"Link Status: *{status_text}*",
                parse_mode=ParseMode.MARKDOWN
            )
        else:
            # If there's an error or PAN is not available
            error_msg = data.get("message", "Unknown error occurred")
            
            # Check if the error is related to quota exceeded
            if "exceeded the MONTHLY quota" in error_msg or "quota" in error_msg.lower():
                await update.message.reply_text("SPECIAL KEY EXPIRED💀")
            else:
                await update.message.reply_text(f"Could not retrieve PAN information: {error_msg}")
    
    except Exception as e:
        logger.error(f"Error in PAN search: {str(e)}")
        error_str = str(e)
        
        # Check if the error is related to quota exceeded
        if "exceeded the MONTHLY quota" in error_str or "quota" in error_str.lower():
            await update.message.reply_text("SPECIAL KEY EXPIRED💀")
        else:
            await update.message.reply_text(f"Error: {error_str}")
    
    # Clean up user data
    if user_id in user_data_dict:
        del user_data_dict[user_id]
    
    # Show the simple menu after search is complete
    await show_simple_menu(update, context)
    
    return ConversationHandler.END

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

# Breach check function
async def breach_check(update: Update, email: str):
    # If the email is "Back to Menu", ignore it
    if email == "⬅️ Back to Menu":
        return
        
    try:
        # HIBP API endpoint
        url = f'{HIBP_API_URL}{email}'
        
        # Headers
        headers = {
            'hibp-api-key': HIBP_API_KEY,
            'User-Agent': 'TelegramBot'
        }
        
        # Make the API request
        response = requests.get(url, headers=headers)
        
        # Handle the response
        if response.status_code == 200:
            breaches = response.json()
            breach_count = len(breaches)
            
            # Create message with breach information
            result = f"⚠️ *Email Breach Alert* ⚠️\n\n"
            result += f"The email `{email}` has been found in *{breach_count} data breaches*:\n\n"
            
            # Add only breach platform names in a simple list
            for i, breach in enumerate(breaches):
                breach_name = breach.get('Name', 'Unknown')
                result += f"• `{breach_name}`\n"
            
            await update.message.reply_text(result, parse_mode=ParseMode.MARKDOWN)
        elif response.status_code == 404:
            await update.message.reply_text(f"✅ Good news! The email `{email}` has NOT been found in any known data breaches.", parse_mode=ParseMode.MARKDOWN)
        else:
            await update.message.reply_text(f"Error checking breach data: Status code {response.status_code}")
    except Exception as e:
        logger.error(f"Error in breach check: {str(e)}")
        await update.message.reply_text(f"Error: {str(e)}")

# Main menu function with full welcome message
async def show_welcome_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Create reply keyboard with only necessary buttons
    keyboard = [
        ["Mobile Search 📱", "Aadhar Search 🔎"],
        ["Social Media Search 🌐", "Breach Check 🔒"],
        ["Age Check 👶", "PAN Details 💳"]
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
        "• PAN Details from Aadhar\n\n"
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
        ["Age Check 👶", "PAN Details 💳"]
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
            f"• PAN Details - Get PAN details from Aadhar number\n\n"
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
    
    elif text == "PAN Details 💳":
        # Create keyboard with back button
        keyboard = [["⬅️ Back to Menu"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please enter a 12-digit Aadhar number to get PAN details:",
            reply_markup=reply_markup
        )
        user_data_dict[update.effective_user.id] = {"next_action": "pan_search"}
        return ENTER_AADHAR
    
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
    user_id = update.effective_user.id
    text = update.message.text
    
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
    user_id = update.effective_user.id
    text = update.message.text
    
    # Check if user wants to go back to menu
    if text == "⬅️ Back to Menu":
        return await show_simple_menu(update, context)
    
    # Check if it's a valid Aadhar number
    if text.isdigit() and len(text) == 12:
        if user_id in user_data_dict:
            next_action = user_data_dict[user_id].get("next_action")
            
            if next_action == "aadhar_search":
                # Send a message that we're processing
                await update.message.reply_text(f"Searching for Aadhar: {text}...")
                
                # Call the existing aadhar search function
                await aadhar_search(update, text)
            
            elif next_action == "pan_search":
                # Store the Aadhar number for PAN search
                user_data_dict[user_id]["aadhar_number"] = text
                
                # Ask for the API key
                await update.message.reply_text(
                    "Please enter your Special Key🔑 for the Aadhaar to PAN API.\n\n"
                    "If you don't have one, you can get it from 👉  @icodeinbinary\n"
                )
                
                return ENTER_API_KEY
        
        # Show the simple menu after search is complete
        await show_simple_menu(update, context)
    else:
        await update.message.reply_text("Invalid number! Please enter a 12-digit Aadhar number.")
    
    return ConversationHandler.END

# Handle social search input
async def handle_social_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    query = update.message.text
    
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
    user_id = update.effective_user.id
    text = update.message.text
    
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
    user_id = update.effective_user.id
    email = update.message.text
    
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
            ENTER_API_KEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_api_key)],
            ENTER_EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_email_input)]
        },
        fallbacks=[MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)]
    )
    
    app.add_handler(conv_handler)
    
    # Run the bot
    print("Starting bot...")
    app.run_polling(drop_pending_updates=True) 
