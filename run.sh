#!/bin/bash

# Enhanced TgMusicBotFork Startup Script
# Copyright (c) 2025 Devin

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BOT_NAME="HybridVCBot"
LOG_DIR="logs"
BACKUP_DIR="backups"
MAX_LOG_SIZE="50M"
MAX_BACKUPS=5

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}================================${NC}"
    echo -e "${BLUE}  TgMusicBot Enhanced Startup${NC}"
    echo -e "${BLUE}================================${NC}"
}

# Function to check dependencies
check_dependencies() {
    print_status "Checking dependencies..."
    
    # Check Python version
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed"
        exit 1
    fi
    
    python_version=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
    required_version="3.10"
    
    if [ "$(printf '%s\n' "$required_version" "$python_version" | sort -V | head -n1)" != "$required_version" ]; then
        print_error "Python $required_version or higher is required. Found: $python_version"
        exit 1
    fi
    
    print_status "Python version: $python_version ✓"
    
    # Check for virtual environment
    if [[ "$VIRTUAL_ENV" == "" ]]; then
        print_warning "Not running in a virtual environment"
    else
        print_status "Virtual environment: $VIRTUAL_ENV ✓"
    fi
    
    # Check for required files
    if [ ! -f "pyproject.toml" ]; then
        print_error "pyproject.toml not found"
        exit 1
    fi
    
    if [ ! -f "sample.env" ]; then
        print_error "sample.env not found"
        exit 1
    fi
    
    print_status "Dependencies check completed ✓"
}

# Function to setup environment
setup_environment() {
    print_status "Setting up environment..."
    
    # Create necessary directories
    mkdir -p "$LOG_DIR"
    mkdir -p "$BACKUP_DIR"
    mkdir -p "database"
    mkdir -p "database/photos"
    
    print_status "Directories created ✓"
    
    # Check for .env file
    if [ ! -f ".env" ]; then
        print_warning ".env file not found, copying from sample.env"
        cp sample.env .env
        print_warning "Please configure your .env file before running the bot"
        exit 1
    fi
    
    print_status "Environment setup completed ✓"
}

# Function to backup logs
backup_logs() {
    print_status "Backing up old logs..."
    
    if [ -d "$LOG_DIR" ] && [ "$(ls -A $LOG_DIR 2>/dev/null)" ]; then
        timestamp=$(date +"%Y%m%d_%H%M%S")
        backup_name="${BACKUP_DIR}/logs_backup_${timestamp}.tar.gz"
        
        tar -czf "$backup_name" -C "$LOG_DIR" .
        print_status "Logs backed up to: $backup_name"
        
        # Clean old backups
        backup_count=$(ls -1 "$BACKUP_DIR"/logs_backup_*.tar.gz 2>/dev/null | wc -l)
        if [ "$backup_count" -gt "$MAX_BACKUPS" ]; then
            oldest_backup=$(ls -t "$BACKUP_DIR"/logs_backup_*.tar.gz | tail -n +$((MAX_BACKUPS + 1)))
            if [ -n "$oldest_backup" ]; then
                rm $oldest_backup
                print_status "Cleaned old backup: $(basename $oldest_backup)"
            fi
        fi
    else
        print_status "No logs to backup"
    fi
}

# Function to check system resources
check_system_resources() {
    print_status "Checking system resources..."
    
    # Check available memory
    available_memory=$(free -m | awk 'NR==2{printf "%.0f", $7}')
    if [ "$available_memory" -lt 512 ]; then
        print_warning "Low memory available: ${available_memory}MB (recommended: 512MB+)"
    else
        print_status "Available memory: ${available_memory}MB ✓"
    fi
    
    # Check disk space
    available_disk=$(df . | awk 'NR==2{printf "%.0f", $4}')
    if [ "$available_disk" -lt 1024 ]; then
        print_warning "Low disk space: ${available_disk}MB (recommended: 1GB+)"
    else
        print_status "Available disk space: ${available_disk}MB ✓"
    fi
    
    # Check CPU load
    cpu_load=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    print_status "Current CPU load: $cpu_load"
}

# Function to install/update dependencies
install_dependencies() {
    print_status "Installing/updating dependencies..."
    
    if command -v uv &> /dev/null; then
        print_status "Using uv for dependency management"
        uv sync
    elif command -v pip &> /dev/null; then
        print_status "Using pip for dependency management"
        pip install -e .
    else
        print_error "Neither uv nor pip found"
        exit 1
    fi
    
    print_status "Dependencies installed ✓"
}

# Function to start the bot
start_bot() {
    print_status "Starting TgMusicBot..."
    
    # Set environment variables for better performance
    export PYTHONUNBUFFERED=1
    export PYTHONPATH="${PYTHONPATH}:$(pwd)"
    
    # Start the bot with enhanced error handling
    if command -v uv &> /dev/null; then
        uv run python -m TgMusic
    else
        python -m TgMusic
    fi
}

# Function to handle signals
cleanup() {
    print_status "Shutting down gracefully..."
    # Add any cleanup tasks here
    exit 0
}

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Main execution
main() {
    print_header
    
    # Check if running as root
    if [ "$EUID" -eq 0 ]; then
        print_warning "Running as root is not recommended"
    fi
    
    # Run all setup functions
    check_dependencies
    setup_environment
    backup_logs
    check_system_resources
    install_dependencies
    
    print_status "All checks completed successfully!"
    print_status "Starting TgMusicBot..."
    echo ""
    
    # Start the bot
    start_bot
}

# Run main function
main "$@" 