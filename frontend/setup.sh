#!/bin/bash
set -euo pipefail

# SubtitleTranslatorAI GUI Setup Script
echo "🚀 Setting up SubtitleTranslatorAI GUI..."

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: package.json not found. Please run this script from the frontend directory."
    exit 1
fi

# Check Node.js version
echo "📋 Checking Node.js version..."
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16 or higher."
    echo "   Download from: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$NODE_VERSION" -lt 16 ]; then
    echo "❌ Node.js version $NODE_VERSION is too old. Please install Node.js 16 or higher."
    exit 1
fi

echo "✅ Node.js $(node --version) detected"

# Check npm
echo "📋 Checking npm..."
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm."
    exit 1
fi

echo "✅ npm $(npm --version) detected"

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Check backend directory
echo "📋 Checking backend directory..."
if [ ! -d "../backend" ]; then
    echo "❌ Backend directory not found at ../backend"
    echo "   Please ensure the backend directory exists in the parent directory."
    exit 1
fi

if [ ! -f "../backend/main.sh" ]; then
    echo "❌ main.sh not found in ../backend directory"
    exit 1
fi

echo "✅ Backend directory found"

# Set up backend permissions
echo "🔧 Setting up backend permissions..."
chmod +x ../backend/main.sh 2>/dev/null || echo "⚠️  Could not set execute permissions (may need sudo)"

# Check optional prerequisites
echo "📋 Checking optional prerequisites..."

# Check Docker
if command -v docker &> /dev/null; then
    if docker --version &> /dev/null; then
        echo "✅ Docker detected: $(docker --version)"
    else
        echo "⚠️  Docker is installed but not running"
    fi
else
    echo "⚠️  Docker not found (required for script execution)"
fi

# Check Docker Compose
if command -v docker &> /dev/null; then
    if docker compose version &> /dev/null 2>&1; then
        echo "✅ Docker Compose detected: $(docker compose version --short 2>/dev/null || echo 'available')"
    else
        echo "⚠️  Docker Compose not available"
    fi
else
    echo "⚠️  Docker Compose not checked (Docker not available)"
fi

# Check Bash
if command -v bash &> /dev/null; then
    echo "✅ Bash detected: $(bash --version | head -n1)"
else
    echo "⚠️  Bash not found (required for script execution)"
fi

# Create icons directory if it doesn't exist
echo "🎨 Setting up assets..."
mkdir -p assets

# Create a simple placeholder icon if none exists
if [ ! -f "assets/icon.png" ]; then
    echo "📝 Creating placeholder icon..."
    # This creates a placeholder text file - in production, replace with actual icon
    cat > assets/icon.png << 'EOF'
# PNG Icon Placeholder
# Replace this file with an actual 256x256 PNG icon
# You can create one online or use any image editor
EOF
fi

# Check build tools
echo "📋 Checking build tools..."
if npm list electron-builder &> /dev/null; then
    echo "✅ Electron Builder available"
else
    echo "⚠️  Electron Builder not available - run 'npm install' to fix"
fi

# Success message
echo ""
echo "🎉 Setup completed successfully!"
echo ""
echo "Next steps:"
echo "1. Replace assets/icon.png with your actual icon (256x256 PNG)"
echo "2. Run 'npm start' to launch the application in development mode"
echo "3. Run 'npm run build' to create distributable packages"
echo ""

# Optional: Run the app if requested
read -p "Do you want to start the application now? (y/N): " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Starting SubtitleTranslatorAI GUI..."
    npm start
fi 