# INSTAGRANS-KIT - instalador para Windows. Rode no PowerShell, dentro da pasta do kit:
#   powershell -ExecutionPolicy Bypass -File .\instalar.ps1
# A pasta do kit e onde VOCE colocou (o caminho e gravado em .kit-local.json). Nao mova depois sem rodar de novo.
$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Raiz
Write-Host "Kit em: $Raiz" -ForegroundColor Cyan
if ($Raiz.Length -gt 90) {
  throw "O caminho do kit e longo demais ($($Raiz.Length) caracteres). O Windows limita caminhos a 260 e o Remotion/Chrome falha. Mova o kit para algo curto, como C:\INSTAGRANS-KIT, e rode de novo."
}
if ($Raiz -match '\s' -or $Raiz -match '[^\x00-\x7F]') {
  Write-Host "ATENCAO: o caminho tem espaco ou acento. Funciona, mas prefira algo como C:\INSTAGRANS-KIT." -ForegroundColor Yellow
}

function Tem($c) { return [bool](Get-Command $c -ErrorAction SilentlyContinue) }
function Winget($id) { winget install -e --id $id --accept-source-agreements --accept-package-agreements }

Write-Host "`n1/6 Ferramentas (Node, Python, ffmpeg)"
if (-not (Tem "winget")) { throw "winget nao encontrado. Atualize o 'Instalador de Aplicativo' na Microsoft Store." }
if (-not (Tem "node"))   { Winget "OpenJS.NodeJS.LTS" }
if (-not (Tem "python")) { Winget "Python.Python.3.12" }
if (-not (Tem "ffmpeg")) { Winget "Gyan.FFmpeg" }
if (-not (Tem "claude")) { Write-Host "Claude Code nao encontrado. Instale: https://claude.com/claude-code e entre com sua conta (comando: claude)." -ForegroundColor Yellow }
$env:Path = [Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [Environment]::GetEnvironmentVariable("Path","User")
foreach ($c in "node","python","ffmpeg") { if (-not (Tem $c)) { throw "'$c' ainda nao aparece. Feche e reabra o PowerShell e rode de novo." } }

Write-Host "`n2/6 Pacotes Python"
python -m pip install --upgrade pip
python -m pip install -r _sistema\orquestrador\requirements.txt yt-dlp

Write-Host "`n3/6 Pastas de trabalho"
foreach ($d in "logs") { New-Item -ItemType Directory -Force $d | Out-Null }

Write-Host "`n4/6 .env (chaves) e configuracao do Claude neste PC"
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host "Criei .env. Preencha so o que for usar (veja o guia)." }
$cfg = @{ raiz = $Raiz; instalado_em = (Get-Date -Format "s"); python = (Get-Command python).Source } | ConvertTo-Json
Set-Content -Encoding UTF8 .kit-local.json $cfg
# hooks do Claude com caminho relativo ao projeto: nao precisa ajustar nada

Write-Host "`n5/6 Dependencias dos modelos de video (Remotion)"
foreach ($p in Get-ChildItem -Directory | Where-Object { Test-Path (Join-Path $_.FullName "remotion\package.json") }) {
  Write-Host "  npm install em $($p.Name)\remotion"
  Push-Location (Join-Path $p.FullName "remotion"); npm install; npx remotion browser ensure; Pop-Location
}

Write-Host "`n6/6 Tarefas automaticas (producao, post) - criadas DESLIGADAS"
if (Test-Path _sistema\agendador.ps1) { powershell -ExecutionPolicy Bypass -File _sistema\agendador.ps1 }

Write-Host "`nPronto. Proximos passos:" -ForegroundColor Green
Write-Host "  1) cd $Raiz ; claude        (abra o Claude Code DENTRO da pasta do kit)"
Write-Host "  2) diga:  quero criar um perfil novo     (a skill criar-perfil guia tudo)"
Write-Host "  3) guia visual: abra GUIA\index.html"
python _sistema\orquestrador\orquestrador.py status
