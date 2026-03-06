# Arc GPU Activator
# Waits for the LM Studio model download to finish, then loads the model
# on the Vulkan (Arc GPU) backend and starts the OpenAI-compatible server on port 1234.
# Run this in a separate window and leave overnight alongside the main queue.

$lms = "C:\Users\msunw\.lmstudio\bin\lms.exe"
$ModelName = "lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF"
$Port = 1234

Write-Host "Arc GPU Activator — waiting for model download to complete..."

# Poll until qwen2.5 GGUF appears in lms ls
while ($true) {
    $lsOutput = & $lms ls 2>&1 | Out-String
    if ($lsOutput -match "Qwen2.5") {
        Write-Host "Model found! Proceeding to load on Vulkan (Arc GPU)..."
        break
    }
    Write-Host "  Model not ready yet. Sleeping 60s... ($(Get-Date -Format 'HH:mm:ss'))"
    Start-Sleep -Seconds 60
}

# Start LM Studio server
Write-Host "Starting LM Studio server on port $Port..."
& $lms server start --port $Port 2>&1

# Load the model on Vulkan backend (Arc GPU)
Write-Host "Loading $ModelName on Vulkan backend..."
& $lms load $ModelName --gpu max --context-length 4096 2>&1

Write-Host ""
Write-Host "Arc GPU server ready on http://localhost:$Port"
Write-Host "The overnight queue will use it automatically for future lanes."
