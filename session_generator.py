#!/usr/bin/env python3
"""
Enhanced Pyrogram Session String Generator
Creates session strings for Telegram userbot development with improved stability
"""

import asyncio
import getpass
import os
import sys
import time
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid,
    FloodWait,
    BadRequest
)

# Colors for terminal output
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_logo():
    """Display application logo/banner"""
    logo = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║          🔑 ENHANCED PYROGRAM SESSION GENERATOR 🔑          ║
║                                                              ║
║            For Stable Telegram Userbot Development          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}
    """
    print(logo)

def get_api_credentials():
    """Get API credentials from user with validation"""
    print(f"{Colors.YELLOW}📋 To get API ID and API Hash:{Colors.END}")
    print(f"{Colors.WHITE}1. Visit https://my.telegram.org{Colors.END}")
    print(f"{Colors.WHITE}2. Login with your phone number{Colors.END}")
    print(f"{Colors.WHITE}3. Go to 'API Development Tools'{Colors.END}")
    print(f"{Colors.WHITE}4. Create a new application and get API ID & Hash{Colors.END}")
    print(f"{Colors.WHITE}5. Never share these credentials with anyone!{Colors.END}\n")
    
    max_attempts = 3
    for attempt in range(max_attempts):
        try:
            api_id = int(input(f"{Colors.GREEN}📱 Enter your API ID: {Colors.END}"))
            if api_id <= 0:
                raise ValueError("API ID must be a positive number")
            break
        except ValueError as e:
            print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
            if attempt == max_attempts - 1:
                return None, None
            print(f"{Colors.YELLOW}🔄 Please try again ({attempt + 1}/{max_attempts}){Colors.END}")
    
    api_hash = input(f"{Colors.GREEN}🔐 Enter your API Hash: {Colors.END}").strip()
    if not api_hash or len(api_hash) < 32:
        print(f"{Colors.RED}❌ Error: API Hash cannot be empty and must be valid{Colors.END}")
        return None, None
    
    return api_id, api_hash

def get_phone_number():
    """Get phone number from user with validation"""
    max_attempts = 3
    for attempt in range(max_attempts):
        phone = input(f"{Colors.GREEN}📞 Enter phone number (international format, e.g., +1234567890): {Colors.END}").strip()
        
        # Remove spaces and dashes
        phone = phone.replace(' ', '').replace('-', '')
        
        if not phone.startswith('+'):
            print(f"{Colors.YELLOW}⚠️  Adding '+' prefix to number...{Colors.END}")
            phone = '+' + phone
        
        # Basic validation
        if len(phone) < 10 or len(phone) > 16:
            print(f"{Colors.RED}❌ Invalid phone number length{Colors.END}")
            if attempt == max_attempts - 1:
                return None
            continue
        
        return phone
    
    return None

def get_device_info():
    """Get device information for better session stability"""
    print(f"\n{Colors.BLUE}🔧 Device Information (for better session stability):{Colors.END}")
    
    device_model = input(f"{Colors.GREEN}📱 Device model (default: PC): {Colors.END}").strip()
    if not device_model:
        device_model = "PC"
    
    system_version = input(f"{Colors.GREEN}💻 System version (default: Windows 10): {Colors.END}").strip()
    if not system_version:
        system_version = "Windows 10"
    
    app_version = input(f"{Colors.GREEN}📦 App version (default: 4.2.4): {Colors.END}").strip()
    if not app_version:
        app_version = "4.2.4"
    
    return device_model, system_version, app_version

async def handle_2fa(app, max_attempts=3):
    """Handle Two-Factor Authentication properly"""
    for attempt in range(max_attempts):
        try:
            print(f"{Colors.YELLOW}🔐 Your account has Two-Factor Authentication (2FA) enabled{Colors.END}")
            password = getpass.getpass(f"{Colors.GREEN}🔑 Enter your 2FA password: {Colors.END}")
            
            await app.check_password(password)
            print(f"{Colors.GREEN}✅ 2FA authentication successful!{Colors.END}")
            return True
            
        except PasswordHashInvalid:
            print(f"{Colors.RED}❌ Invalid 2FA password{Colors.END}")
            if attempt == max_attempts - 1:
                print(f"{Colors.RED}❌ Maximum attempts reached. Please try again later.{Colors.END}")
                return False
            print(f"{Colors.YELLOW}🔄 Please try again ({attempt + 1}/{max_attempts}){Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}❌ 2FA error: {e}{Colors.END}")
            return False
    
    return False

async def validate_session(session_string, api_id, api_hash):
    """Validate the generated session string"""
    try:
        print(f"{Colors.BLUE}🔍 Validating session string...{Colors.END}")
        
        async with Client(
            name="session_validator",
            api_id=api_id,
            api_hash=api_hash,
            session_string=session_string,
            in_memory=True
        ) as app:
            me = await app.get_me()
            print(f"{Colors.GREEN}✅ Session validation successful!{Colors.END}")
            print(f"{Colors.CYAN}👤 Logged in as: {me.first_name} ({me.username or 'No username'}){Colors.END}")
            return True
            
    except Exception as e:
        print(f"{Colors.RED}❌ Session validation failed: {e}{Colors.END}")
        return False

async def generate_session():
    """Main function to generate session string with enhanced stability"""
    session_string = None
    
    try:
        print_logo()
        
        # Get API credentials
        api_id, api_hash = get_api_credentials()
        if not api_id or not api_hash:
            return
        
        # Get phone number
        phone = get_phone_number()
        if not phone:
            print(f"{Colors.RED}❌ Failed to get valid phone number{Colors.END}")
            return
        
        # Get device information for better stability
        device_model, system_version, app_version = get_device_info()
        
        print(f"\n{Colors.BLUE}🔄 Creating Pyrogram client with enhanced settings...{Colors.END}")
        
        # Create Pyrogram client with enhanced settings for stability
        client_config = {
            "name": "session_generator",
            "api_id": api_id,
            "api_hash": api_hash,
            "phone_number": phone,
            "device_model": device_model,
            "system_version": system_version,
            "app_version": app_version,
            "lang_code": "en",
            "in_memory": True,
            "sleep_threshold": 60,  # Handle flood waits automatically
        }
        
        async with Client(**client_config) as app:
            print(f"{Colors.GREEN}✅ Successfully connected to Telegram!{Colors.END}")
            
            # Generate session string
            session_string = await app.export_session_string()
            
            # Validate the session
            if await validate_session(session_string, api_id, api_hash):
                # Display results
                print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
                print(f"{Colors.GREEN}{Colors.BOLD}🎉 SESSION STRING SUCCESSFULLY CREATED! 🎉{Colors.END}")
                print(f"{Colors.CYAN}{'='*60}{Colors.END}")
                print(f"\n{Colors.YELLOW}{Colors.BOLD}📋 Your Session String:{Colors.END}")
                print(f"{Colors.WHITE}{Colors.BOLD}{session_string}{Colors.END}")
                print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
                
                # Save to file option
                save_choice = input(f"\n{Colors.BLUE}💾 Save session string to file? (y/n): {Colors.END}").lower().strip()
                
                if save_choice in ['y', 'yes']:
                    filename = input(f"{Colors.GREEN}📄 Filename (default: session_string.txt): {Colors.END}").strip()
                    if not filename:
                        filename = "session_string.txt"
                    
                    if not filename.endswith('.txt'):
                        filename += '.txt'
                    
                    try:
                        with open(filename, 'w', encoding='utf-8') as f:
                            f.write(f"# Telegram Session String\n")
                            f.write(f"# Generated on: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"# Device: {device_model}\n")
                            f.write(f"# System: {system_version}\n")
                            f.write(f"# App Version: {app_version}\n\n")
                            f.write(session_string)
                        
                        print(f"{Colors.GREEN}✅ Session string successfully saved to {filename}{Colors.END}")
                    except Exception as e:
                        print(f"{Colors.RED}❌ Failed to save file: {e}{Colors.END}")
                
                print(f"\n{Colors.YELLOW}⚠️  IMPORTANT SECURITY WARNINGS:{Colors.END}")
                print(f"{Colors.RED}• NEVER share this session string with anyone!{Colors.END}")
                print(f"{Colors.RED}• Store it securely and don't upload to public repositories{Colors.END}")
                print(f"{Colors.RED}• This session string provides full access to your Telegram account{Colors.END}")
                print(f"{Colors.RED}• If compromised, immediately revoke it by logging out from all devices{Colors.END}")
            else:
                print(f"{Colors.RED}❌ Session validation failed. Please try again.{Colors.END}")
            
    except ApiIdInvalid:
        print(f"{Colors.RED}❌ Error: Invalid API ID{Colors.END}")
    except PhoneNumberInvalid:
        print(f"{Colors.RED}❌ Error: Invalid phone number{Colors.END}")
    except PhoneCodeInvalid:
        print(f"{Colors.RED}❌ Error: Invalid verification code{Colors.END}")
    except PhoneCodeExpired:
        print(f"{Colors.RED}❌ Error: Verification code has expired{Colors.END}")
    except SessionPasswordNeeded:
        print(f"{Colors.YELLOW}🔐 Two-Factor Authentication required{Colors.END}")
        try:
            # Recreate client for 2FA handling
            async with Client(
                name="session_generator_2fa",
                api_id=api_id,
                api_hash=api_hash,
                phone_number=phone,
                device_model=device_model,
                system_version=system_version,
                app_version=app_version,
                in_memory=True
            ) as app:
                if await handle_2fa(app):
                    session_string = await app.export_session_string()
                    
                    if await validate_session(session_string, api_id, api_hash):
                        print(f"\n{Colors.GREEN}✅ Session created successfully with 2FA!{Colors.END}")
                        print(f"{Colors.YELLOW}📋 Your Session String:{Colors.END}")
                        print(f"{Colors.WHITE}{session_string}{Colors.END}")
                
        except Exception as e:
            print(f"{Colors.RED}❌ Error during 2FA handling: {e}{Colors.END}")
    except FloodWait as e:
        print(f"{Colors.YELLOW}⏳ Rate limited. Please wait {e.value} seconds and try again.{Colors.END}")
    except BadRequest as e:
        print(f"{Colors.RED}❌ Bad request: {e}{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Unexpected error: {e}{Colors.END}")
    finally:
        # Cleanup temporary session files
        for session_file in ["session_generator.session", "session_generator_2fa.session", "session_validator.session"]:
            if os.path.exists(session_file):
                try:
                    os.remove(session_file)
                except:
                    pass

def check_requirements():
    """Check if Pyrogram is installed"""
    try:
        import pyrogram
        print(f"{Colors.GREEN}✅ Pyrogram is installed (version: {pyrogram.__version__}){Colors.END}")
        return True
    except ImportError:
        print(f"{Colors.RED}❌ Pyrogram is not installed!{Colors.END}")
        print(f"{Colors.YELLOW}📦 Install with: pip install pyrogram{Colors.END}")
        print(f"{Colors.YELLOW}📦 Or for development: pip install pyrogram[dev]{Colors.END}")
        return False
    except AttributeError:
        print(f"{Colors.GREEN}✅ Pyrogram is installed{Colors.END}")
        return True

def show_tips():
    """Show tips for better session stability"""
    print(f"\n{Colors.CYAN}💡 TIPS FOR BETTER SESSION STABILITY:{Colors.END}")
    print(f"{Colors.WHITE}• Use consistent device information across sessions{Colors.END}")
    print(f"{Colors.WHITE}• Don't create too many sessions in short time periods{Colors.END}")
    print(f"{Colors.WHITE}• Keep the same app version for multiple sessions{Colors.END}")
    print(f"{Colors.WHITE}• Avoid using sessions from different locations simultaneously{Colors.END}")
    print(f"{Colors.WHITE}• Enable 2FA for better account security{Colors.END}")
    print(f"{Colors.WHITE}• Regularly check for unauthorized sessions in Telegram settings{Colors.END}")

if __name__ == "__main__":
    try:
        # Check Python version first
        if sys.version_info < (3, 7):
            print(f"{Colors.RED}❌ Python 3.7+ is required to run this script{Colors.END}")
            print(f"{Colors.YELLOW}Current version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}{Colors.END}")
            sys.exit(1)
        
        print(f"{Colors.GREEN}✅ Python version check passed{Colors.END}")
        
        # Check requirements
        if not check_requirements():
            sys.exit(1)
        
        print(f"{Colors.GREEN}✅ All requirements satisfied{Colors.END}")
        
        # Show stability tips
        show_tips()
        
        # Run the session generator
        print(f"\n{Colors.BLUE}🚀 Starting session generator...{Colors.END}")
        asyncio.run(generate_session())
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Script interrupted by user{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Fatal error: {e}{Colors.END}")
        print(f"{Colors.YELLOW}💡 If this error persists, please check your internet connection and API credentials{Colors.END}")
    finally:
        print(f"\n{Colors.CYAN}👋 Thank you for using Enhanced Session Generator!{Colors.END}")
        print(f"{Colors.CYAN}🔐 Remember to keep your session strings secure!{Colors.END}")