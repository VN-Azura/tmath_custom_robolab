# =============================================================================
# TMATH Deploy to Azure VM - PowerShell Script
# =============================================================================

param(
    [string]$KeyPath = "C:\Users\Leo\Downloads\Robolab_key.pem",
    [string]$VMUser = "azureuser",
    [string]$VMIP = "20.24.210.162",
    [string]$AppDir = "/opt/tmath"
)

$ErrorActionPreference = "Stop"

function Write-Info($msg) { Write-Host "[INFO] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[WARN] $msg" -ForegroundColor Yellow }
function Write-Err($msg) { Write-Host "[ERROR] $msg" -ForegroundColor Red }

$SSH = "ssh -i `"$KeyPath`" -o StrictHostKeyChecking=no"
$SCP = "scp -i `"$KeyPath`" -o StrictHostKeyChecking=no"
$SSHTarget = "$VMUser@$VMIP"

Write-Host ""
Write-Host "=============================================================================" -ForegroundColor Cyan
Write-Host "     TMATH - Deploy to Azure VM" -ForegroundColor Cyan
Write-Host "=============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "VM: $VMIP"
Write-Host "User: $VMUser"
Write-Host "Key: $KeyPath"
Write-Host ""

# =============================================================================
# STEP 1: Test SSH Connection
# =============================================================================
Write-Info "Testing SSH connection..."
$testResult = Invoke-Expression "$SSH $SSHTarget 'echo connected'"
if ($testResult -ne "connected") {
    Write-Err "Cannot connect to VM. Check your SSH key and IP address."
    exit 1
}
Write-Info "SSH connection OK ✓"

# =============================================================================
# STEP 2: Run Setup Script on VM
# =============================================================================
Write-Info "Running setup script on VM..."

# Upload setup script first
$setupScript = "azure/setup-vm.sh"
Invoke-Expression "$SCP $setupScript ${SSHTarget}:/tmp/setup-vm.sh"

# Run setup
Invoke-Expression "$SSH $SSHTarget 'chmod +x /tmp/setup-vm.sh && sudo /tmp/setup-vm.sh $VMIP'"

Write-Info "VM setup completed ✓"

# =============================================================================
# STEP 3: Upload Source Code
# =============================================================================
Write-Info "Uploading source code to VM..."

# Create a temporary zip file (excluding unnecessary files)
$excludePatterns = @(
    ".git",
    "venv",
    "node_modules",
    "__pycache__",
    "*.pyc",
    "*.sqlite3",
    "staticfiles",
    ".env",
    "db.sqlite3"
)

# Create tar archive
$tarFile = "tmath-deploy.tar.gz"
Write-Info "Creating archive..."

# Use Git to get list of tracked files, then tar them
git archive --format=tar.gz --output=$tarFile HEAD

# Upload archive
Write-Info "Uploading archive (~30-60 seconds)..."
Invoke-Expression "$SCP $tarFile ${SSHTarget}:/tmp/"

# Extract on server
Write-Info "Extracting on server..."
Invoke-Expression "$SSH $SSHTarget 'cd $AppDir && sudo tar -xzf /tmp/$tarFile && sudo chown -R $VMUser`:$VMUser .'"

# Clean up local archive
Remove-Item $tarFile -ErrorAction SilentlyContinue

Write-Info "Source code uploaded ✓"

# =============================================================================
# STEP 4: Install Dependencies & Configure
# =============================================================================
Write-Info "Installing Python dependencies..."

$remoteCommands = @"
cd $AppDir
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn psycopg2-binary

# Load environment and run Django setup
set -a && source .env && set +a
export DJANGO_SETTINGS_MODULE=tmath.settings_production

python manage.py migrate --noinput
python manage.py collectstatic --noinput --clear

# Restart services
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart all
sudo systemctl restart nginx
"@

Invoke-Expression "$SSH $SSHTarget '$remoteCommands'"

Write-Info "Dependencies installed and configured ✓"

# =============================================================================
# STEP 5: Create Superuser (Interactive)
# =============================================================================
Write-Host ""
$createAdmin = Read-Host "Do you want to create a superuser now? (y/n)"
if ($createAdmin -eq "y") {
    Write-Info "Creating superuser (follow prompts)..."
    Invoke-Expression "$SSH -t $SSHTarget 'cd $AppDir && source venv/bin/activate && export DJANGO_SETTINGS_MODULE=tmath.settings_production && python manage.py createsuperuser'"
}

# =============================================================================
# DONE
# =============================================================================
Write-Host ""
Write-Host "=============================================================================" -ForegroundColor Cyan
Write-Host "DEPLOYMENT COMPLETED!" -ForegroundColor Green
Write-Host "=============================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "🌐 Website: http://$VMIP" -ForegroundColor White
Write-Host "📋 Admin: http://$VMIP/admin" -ForegroundColor White
Write-Host ""
Write-Host "SSH Access: ssh -i `"$KeyPath`" $SSHTarget" -ForegroundColor Gray
Write-Host ""
Write-Host "View logs:" -ForegroundColor Gray
Write-Host "  ssh -i `"$KeyPath`" $SSHTarget 'sudo tail -f /var/log/tmath/gunicorn.log'" -ForegroundColor Gray
Write-Host ""
Write-Host "Restart services:" -ForegroundColor Gray
Write-Host "  ssh -i `"$KeyPath`" $SSHTarget 'sudo supervisorctl restart all'" -ForegroundColor Gray
Write-Host ""
Write-Host "=============================================================================" -ForegroundColor Cyan
