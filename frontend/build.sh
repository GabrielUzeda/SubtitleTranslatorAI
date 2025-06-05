#!/bin/bash
set -euo pipefail

# SubtitleTranslatorAI GUI Build Script
echo "🏗️  SubtitleTranslatorAI GUI Build Script"
echo "=================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Parse command line arguments
BUILD_TARGET="all"
SKIP_DEPS=false
CLEAN_BUILD=false
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --target|-t)
            BUILD_TARGET="$2"
            shift 2
            ;;
        --skip-deps|-s)
            SKIP_DEPS=true
            shift
            ;;
        --clean|-c)
            CLEAN_BUILD=true
            shift
            ;;
        --verbose|-v)
            VERBOSE=true
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -t, --target <target>   Build target: all, win, mac, linux (default: all)"
            echo "  -s, --skip-deps        Skip dependency installation"
            echo "  -c, --clean            Clean build (remove node_modules and dist)"
            echo "  -v, --verbose          Verbose output"
            echo "  -h, --help             Show this help"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate build target
case $BUILD_TARGET in
    all|win|mac|linux)
        ;;
    *)
        print_error "Invalid build target: $BUILD_TARGET"
        echo "Valid targets: all, win, mac, linux"
        exit 1
        ;;
esac

print_info "Build target: $BUILD_TARGET"

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    print_error "package.json not found. Please run this script from the frontend directory."
    exit 1
fi

# Clean build if requested
if [ "$CLEAN_BUILD" = true ]; then
    print_info "Cleaning previous build..."
    rm -rf node_modules dist
    print_status "Clean completed"
fi

# Check Node.js
print_info "Checking Node.js..."
if ! command -v node &> /dev/null; then
    print_error "Node.js is not installed. Please install Node.js 16 or higher."
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ]; then
    print_error "Node.js version $NODE_VERSION is too old. Please install Node.js 16 or higher."
    exit 1
fi

print_status "Node.js $(node --version) detected"

# Check backend
print_info "Checking backend directory..."
if [ ! -d "../backend" ]; then
    print_error "Backend directory not found at ../backend"
    exit 1
fi

if [ ! -f "../backend/main.sh" ]; then
    print_error "main.sh not found in ../backend directory"
    exit 1
fi

print_status "Backend directory validated"

# Install dependencies
if [ "$SKIP_DEPS" = false ]; then
    print_info "Installing dependencies..."
    if [ "$VERBOSE" = true ]; then
        npm install
    else
        npm install --silent
    fi
    print_status "Dependencies installed"
else
    print_warning "Skipping dependency installation"
fi

# Check for icons
print_info "Checking application icons..."
ICON_WARNINGS=false

if [ ! -f "assets/icon.png" ] || [ ! -s "assets/icon.png" ] || grep -q "PNG Icon Placeholder" assets/icon.png 2>/dev/null; then
    print_warning "PNG icon is missing or placeholder. Using default."
    ICON_WARNINGS=true
fi

if [ "$BUILD_TARGET" = "all" ] || [ "$BUILD_TARGET" = "win" ]; then
    if [ ! -f "assets/icon.ico" ]; then
        print_warning "ICO icon missing for Windows build"
        ICON_WARNINGS=true
    fi
fi

if [ "$BUILD_TARGET" = "all" ] || [ "$BUILD_TARGET" = "mac" ]; then
    if [ ! -f "assets/icon.icns" ]; then
        print_warning "ICNS icon missing for macOS build"
        ICON_WARNINGS=true
    fi
fi

if [ "$ICON_WARNINGS" = true ]; then
    print_warning "Consider adding proper icons for better user experience"
fi

# Set backend permissions
print_info "Setting backend permissions..."
chmod +x ../backend/main.sh 2>/dev/null || print_warning "Could not set execute permissions"

# Build function
build_for_target() {
    local target=$1
    local start_time=$(date +%s)
    
    print_info "Building for $target..."
    
    case $target in
        win)
            if [ "$VERBOSE" = true ]; then
                npm run build:win
            else
                npm run build:win --silent
            fi
            ;;
        mac)
            if [ "$VERBOSE" = true ]; then
                npm run build:mac
            else
                npm run build:mac --silent
            fi
            ;;
        linux)
            if [ "$VERBOSE" = true ]; then
                npm run build:linux
            else
                npm run build:linux --silent
            fi
            ;;
    esac
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    print_status "$target build completed in ${duration}s"
}

# Build based on target
case $BUILD_TARGET in
    all)
        print_info "Building for all platforms..."
        if [ "$VERBOSE" = true ]; then
            npm run build
        else
            npm run build --silent
        fi
        ;;
    win)
        build_for_target "win"
        ;;
    mac)
        build_for_target "mac"
        ;;
    linux)
        build_for_target "linux"
        ;;
esac

# Check build results
print_info "Checking build results..."

if [ ! -d "dist" ]; then
    print_error "Build failed - dist directory not created"
    exit 1
fi

# List built files
print_status "Build completed successfully!"
echo ""
print_info "Built files:"

if [ -d "dist" ]; then
    find dist -maxdepth 2 -type f \( -name "*.exe" -o -name "*.dmg" -o -name "*.AppImage" -o -name "*.deb" -o -name "*.rpm" \) -exec ls -lh {} \; | while read -r line; do
        file_info=$(echo "$line" | awk '{print $9 " (" $5 ")"}')
        echo "  📦 $file_info"
    done
else
    print_warning "No distributable files found"
fi

# Final information
echo ""
print_info "Build Summary:"
echo "  Target: $BUILD_TARGET"
echo "  Output: ./dist/"
echo "  Backend: Included from ../backend/"

if [ "$ICON_WARNINGS" = true ]; then
    echo ""
    print_warning "Icon Recommendations:"
    echo "  • Replace assets/icon.png with a 256x256 PNG icon"
    echo "  • For Windows: Convert to assets/icon.ico"
    echo "  • For macOS: Convert to assets/icon.icns"
    echo "  • Online tools: favicon.io, convertio.co, or iconverticons.com"
fi

echo ""
print_status "Build process completed!"

# Optional: Open dist folder
if command -v xdg-open &> /dev/null; then
    read -p "Open dist folder? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        xdg-open dist
    fi
elif command -v open &> /dev/null; then
    read -p "Open dist folder? (y/N): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open dist
    fi
fi 