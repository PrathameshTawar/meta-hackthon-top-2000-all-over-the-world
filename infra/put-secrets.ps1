# infra/put-secrets.ps1
# Securely uploads .env secrets to AWS Systems Manager Parameter Store under /saath/
# Usage: powershell -ExecutionPolicy Bypass -File infra\put-secrets.ps1 [-DryRun]

[CmdletBinding()]
param(
    [string]$EnvFile = ".env",
    [string]$Region = "ap-south-1",
    [string]$Profile = "saath",
    [string]$PathPrefix = "/saath",
    [switch]$DryRun = $false
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path $EnvFile)) {
    Write-Error "Could not find env file at '$EnvFile'. Please run from the repository root."
    exit 1
}

Write-Host "=======================================================" -ForegroundColor Cyan
Write-Host "   UPLOADING SAATH SECRETS TO AWS PARAMETER STORE      " -ForegroundColor Cyan
Write-Host "   Region: $Region | Profile: $Profile | Prefix: $PathPrefix" -ForegroundColor Cyan
if ($DryRun) {
    Write-Host "   MODE: DRY-RUN (No changes will be made to AWS)      " -ForegroundColor Yellow
}
Write-Host "=======================================================" -ForegroundColor Cyan

# Keys managed by CloudFormation / Server environment directly (skip uploading)
$ServerManagedKeys = @("BASE_URL", "FRONTEND_URL", "DATABASE_URL", "CHECKPOINTS_DB_PATH", "ENVIRONMENT")

$Placeholders = @(
    "your_meta_api_key_here",
    "your_admin_secret_token",
    "saath_admin_secret_demo",
    "your_whatsapp_token_here",
    "your_verify_token_here",
    "your_app_secret_here",
    "your_telegram_bot_token_here",
    "your_webhook_secret_here",
    "your_secret_here",
    "test_auth_secret_xyz"
)

$lines = Get-Content $EnvFile
$storedCount = 0
$skippedCount = 0

foreach ($line in $lines) {
    $trimmed = $line.Trim()
    if ($trimmed -eq "" -or $trimmed.StartsWith("#")) {
        continue
    }

    if ($trimmed -match '^([A-Za-z_0-9]+)\s*=\s*(.*)$') {
        $key = $matches[1]
        $val = $matches[2].Trim()

        # Strip surrounding quotes
        if (($val.StartsWith('"') -and $val.EndsWith('"')) -or ($val.StartsWith("'") -and $val.EndsWith("'"))) {
            $val = $val.Substring(1, $val.Length - 2)
        }

        # Skip server managed keys
        if ($ServerManagedKeys -contains $key) {
            Write-Host "  [-] Skipping $key (managed by server / CloudFormation)" -ForegroundColor DarkGray
            continue
        }

        # Check for empty or placeholder
        if ([string]::IsNullOrWhiteSpace($val) -or $val -eq '""' -or $val -eq "''") {
            Write-Host "  [!] Warning: Skipping $key (empty value)" -ForegroundColor Yellow
            $skippedCount++
            continue
        }

        $isPlaceholder = $false
        foreach ($ph in $Placeholders) {
            if ($val -like "*$ph*") {
                $isPlaceholder = $true
                break
            }
        }
        if ($isPlaceholder) {
            Write-Host "  [!] Warning: Skipping $key (matches placeholder '$val')" -ForegroundColor Yellow
            $skippedCount++
            continue
        }

        # Upload as SecureString to SSM
        $paramName = "$PathPrefix/$key"
        if ($DryRun) {
            Write-Host "  [~] Would store $paramName (length: $($val.Length))" -ForegroundColor Cyan
            $storedCount++
        }
        else {
            try {
                aws ssm put-parameter `
                    --name $paramName `
                    --value $val `
                    --type "SecureString" `
                    --overwrite `
                    --region $Region `
                    --profile $Profile | Out-Null
                Write-Host "  [+] Stored $paramName" -ForegroundColor Green
                $storedCount++
            }
            catch {
                Write-Host "  [x] Error storing $paramName : $_" -ForegroundColor Red
            }
        }
    }
}

Write-Host ""
Write-Host "Done! Successfully processed $storedCount key(s), skipped $skippedCount." -ForegroundColor Cyan
