# Atualiza o kit pela versao publica. Troca so o motor, skills, modelos e docs. NAO toca em perfis, .env, logs.
# Uso (na raiz do kit):  powershell -ExecutionPolicy Bypass -File _sistema\atualizar.ps1
$ErrorActionPreference = "Stop"
$Raiz = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Raiz
$url = "https://github.com/usmidiadark-dot/instagrans-kit/archive/refs/heads/main.zip"
$tmp = Join-Path $env:TEMP ("kit-update-" + [guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Force $tmp | Out-Null
Write-Host "Baixando a versao nova..."
Invoke-WebRequest -Uri $url -OutFile "$tmp\kit.zip" -UseBasicParsing
Expand-Archive "$tmp\kit.zip" -DestinationPath $tmp -Force
$novo = (Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName
# o que e do kit (some e reaparece a cada versao). Perfis do usuario ficam de fora.
foreach ($d in "_sistema", "_modelo-perfil", "GUIA", ".claude") {
  if (Test-Path "$novo\$d") {
    # preserva o que o usuario criou dentro de _sistema (avisos, travas, logs locais)
    robocopy "$novo\$d" "$Raiz\$d" /E /XD node_modules out avisos travas __pycache__ /NFL /NDL /NJH /NJS /NP | Out-Null
  }
}
foreach ($f in "CLAUDE.md","REGRAS-UNIVERSAIS.md","COMECE-AQUI.md","instalar.ps1",".env.example",".mcp.json",".gitignore") {
  if (Test-Path "$novo\$f") { Copy-Item "$novo\$f" "$Raiz\$f" -Force }
}
# perfis.yaml: nao sobrescreve (tem a lista de perfis do usuario)
Remove-Item $tmp -Recurse -Force
Write-Host "Atualizado. Rodando o verificador..." -ForegroundColor Green
python _sistema\verificar.py
