#!/usr/bin/env python3
"""
Session String Generator untuk Userbot Pyrogram
Dibuat untuk menghasilkan session string yang diperlukan untuk menjalankan userbot
"""

import asyncio
import os
import sys
from pyrogram import Client
from pyrogram.errors import (
    ApiIdInvalid,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)

# Warna untuk output terminal
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
    """Menampilkan logo/banner aplikasi"""
    logo = f"""
{Colors.CYAN}{Colors.BOLD}
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║          🔑 PYROGRAM SESSION STRING GENERATOR 🔑             ║
║                                                              ║
║              Untuk Telegram Userbot Development             ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
{Colors.END}
    """
    print(logo)

def get_api_credentials():
    """Mendapatkan API credentials dari user"""
    print(f"{Colors.YELLOW}📋 Untuk mendapatkan API ID dan API Hash:{Colors.END}")
    print(f"{Colors.WHITE}1. Buka https://my.telegram.org{Colors.END}")
    print(f"{Colors.WHITE}2. Login dengan nomor telepon Anda{Colors.END}")
    print(f"{Colors.WHITE}3. Pergi ke 'API Development Tools'{Colors.END}")
    print(f"{Colors.WHITE}4. Buat aplikasi baru dan dapatkan API ID & Hash{Colors.END}")
    print(f"{Colors.WHITE}5. Jangan pernah bagikan kredensial ini kepada siapapun!{Colors.END}\n")
    
    try:
        api_id = int(input(f"{Colors.GREEN}📱 Masukkan API ID Anda: {Colors.END}"))
        if api_id <= 0:
            raise ValueError("API ID harus berupa angka positif")
    except ValueError as e:
        print(f"{Colors.RED}❌ Error: {e}{Colors.END}")
        return None, None
    
    api_hash = input(f"{Colors.GREEN}🔐 Masukkan API Hash Anda: {Colors.END}").strip()
    if not api_hash:
        print(f"{Colors.RED}❌ Error: API Hash tidak boleh kosong{Colors.END}")
        return None, None
    
    return api_id, api_hash

def get_phone_number():
    """Mendapatkan nomor telepon dari user"""
    phone = input(f"{Colors.GREEN}📞 Masukkan nomor telepon (format internasional, contoh: +628123456789): {Colors.END}").strip()
    
    if not phone.startswith('+'):
        print(f"{Colors.YELLOW}⚠️  Menambahkan '+' di depan nomor...{Colors.END}")
        phone = '+' + phone
    
    return phone

async def generate_session():
    """Fungsi utama untuk generate session string"""
    try:
        print_logo()
        
        # Get API credentials
        api_id, api_hash = get_api_credentials()
        if not api_id or not api_hash:
            return
        
        # Get phone number
        phone = get_phone_number()
        
        print(f"\n{Colors.BLUE}🔄 Membuat client Pyrogram...{Colors.END}")
        
        # Create Pyrogram client
        async with Client(
            name="session_generator",
            api_id=api_id,
            api_hash=api_hash,
            phone_number=phone,
            in_memory=True
        ) as app:
            
            print(f"{Colors.GREEN}✅ Berhasil terhubung ke Telegram!{Colors.END}")
            
            # Generate session string
            session_string = await app.export_session_string()
            
            # Display results
            print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
            print(f"{Colors.GREEN}{Colors.BOLD}🎉 SESSION STRING BERHASIL DIBUAT! 🎉{Colors.END}")
            print(f"{Colors.CYAN}{'='*60}{Colors.END}")
            print(f"\n{Colors.YELLOW}{Colors.BOLD}📋 Session String Anda:{Colors.END}")
            print(f"{Colors.WHITE}{Colors.BOLD}{session_string}{Colors.END}")
            print(f"\n{Colors.CYAN}{'='*60}{Colors.END}")
            
            # Save to file option
            save_choice = input(f"\n{Colors.BLUE}💾 Simpan session string ke file? (y/n): {Colors.END}").lower().strip()
            
            if save_choice in ['y', 'yes', 'ya']:
                filename = input(f"{Colors.GREEN}📄 Nama file (default: session_string.txt): {Colors.END}").strip()
                if not filename:
                    filename = "session_string.txt"
                
                if not filename.endswith('.txt'):
                    filename += '.txt'
                
                with open(filename, 'w') as f:
                    f.write(session_string)
                
                print(f"{Colors.GREEN}✅ Session string berhasil disimpan ke {filename}{Colors.END}")
            
            print(f"\n{Colors.YELLOW}⚠️  PENTING:{Colors.END}")
            print(f"{Colors.RED}• Jangan pernah bagikan session string ini kepada siapapun!{Colors.END}")
            print(f"{Colors.RED}• Simpan dengan aman dan jangan upload ke repository public{Colors.END}")
            print(f"{Colors.RED}• Session string ini memberikan akses penuh ke akun Telegram Anda{Colors.END}")
            
    except ApiIdInvalid:
        print(f"{Colors.RED}❌ Error: API ID tidak valid{Colors.END}")
    except PhoneNumberInvalid:
        print(f"{Colors.RED}❌ Error: Nomor telepon tidak valid{Colors.END}")
    except PhoneCodeInvalid:
        print(f"{Colors.RED}❌ Error: Kode verifikasi tidak valid{Colors.END}")
    except PhoneCodeExpired:
        print(f"{Colors.RED}❌ Error: Kode verifikasi sudah kedaluwarsa{Colors.END}")
    except SessionPasswordNeeded:
        print(f"{Colors.YELLOW}🔐 Akun Anda menggunakan 2FA (Two-Factor Authentication){Colors.END}")
        try:
            password = input(f"{Colors.GREEN}🔑 Masukkan password 2FA Anda: {Colors.END}")
            # Note: Dalam implementasi nyata, Anda perlu handle 2FA dengan benar
            print(f"{Colors.RED}❌ 2FA handling belum diimplementasikan dalam script ini{Colors.END}")
            print(f"{Colors.YELLOW}💡 Silakan nonaktifkan sementara 2FA atau gunakan method lain{Colors.END}")
        except Exception as e:
            print(f"{Colors.RED}❌ Error saat handling 2FA: {e}{Colors.END}")
    except PasswordHashInvalid:
        print(f"{Colors.RED}❌ Error: Password 2FA tidak valid{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Error yang tidak terduga: {e}{Colors.END}")
    finally:
        # Cleanup temporary session file if exists
        if os.path.exists("session_generator.session"):
            os.remove("session_generator.session")

def check_requirements():
    """Memeriksa apakah Pyrogram sudah terinstall"""
    try:
        import pyrogram
        return True
    except ImportError:
        print(f"{Colors.RED}❌ Pyrogram belum terinstall!{Colors.END}")
        print(f"{Colors.YELLOW}📦 Install dengan perintah: pip install pyrogram{Colors.END}")
        print(f"{Colors.YELLOW}📦 Atau untuk development: pip install pyrogram[dev]{Colors.END}")
        return False

if __name__ == "__main__":
    try:
        if not check_requirements():
            sys.exit(1)
        
        # Check Python version
        if sys.version_info < (3, 7):
            print(f"{Colors.RED}❌ Python 3.7+ diperlukan untuk menjalankan script ini{Colors.END}")
            sys.exit(1)
        
        print(f"{Colors.GREEN}✅ Semua requirements terpenuhi{Colors.END}")
        
        # Run the session generator
        asyncio.run(generate_session())
        
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}⚠️  Script dihentikan oleh user{Colors.END}")
    except Exception as e:
        print(f"{Colors.RED}❌ Error fatal: {e}{Colors.END}")
    finally:
        print(f"\n{Colors.CYAN}👋 Terima kasih telah menggunakan Session Generator!{Colors.END}")