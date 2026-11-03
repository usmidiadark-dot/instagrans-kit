# Vigia do Painel (30/10/2026): confere http://127.0.0.1:8765 e, se não responder 200, mata só o processo do painel.py e sobe de novo.
# Tarefa do Windows "INSTAGRANS Painel" roda isto ao entrar no Windows e a cada 5 min. Log: logs\vigia-painel.log
$raiz = Split-Path -Parent $PSScriptRoot
$log = Join-Path $raiz 'logs\vigia-painel.log'
function Escreve($m) { Add-Content -Path $log -Value ("{0:yyyy-MM-dd HH:mm:ss} {1}" -f (Get-Date), $m) -Encoding utf8 }
function Responde {
  try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8765/' -UseBasicParsing -TimeoutSec 5; return ($r.StatusCode -eq 200) } catch { return $false }
}
if (Responde) { exit 0 }
Start-Sleep -Seconds 10                       # 2ª chance: o Painel pode estar só ocupado
if (Responde) { Escreve 'respondeu na 2a tentativa; nada a fazer'; exit 0 }
$pids = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'painel\.py' } | ForEach-Object { $_.ProcessId })
foreach ($p in $pids) { Escreve "Painel nao responde; matando processo $p"; Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
if (-not $pids) { Escreve 'Painel nao responde e nao ha processo dele; subindo' }
Start-Sleep -Seconds 2
$pyw = (Get-Command pythonw -ErrorAction SilentlyContinue).Source
if (-not $pyw) { $pyw = Join-Path (Split-Path (Get-Command python).Source) 'pythonw.exe' }
Start-Process -FilePath $pyw -ArgumentList 'painel.py', '--sem-abrir' -WorkingDirectory (Join-Path $raiz '_sistema\painel') -WindowStyle Hidden
Start-Sleep -Seconds 8
if (Responde) { Escreve 'Painel subiu e responde 200' } else { Escreve 'ATENCAO: subi o Painel mas ele ainda nao responde' }
