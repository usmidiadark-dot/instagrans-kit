# Agendador do Windows para o INSTAGRANS (automacao.md §6).
#   .\_sistema\agendador.ps1 -Criar     cria as tarefas DESLIGADAS
#   .\_sistema\agendador.ps1 -Ligar     liga as duas tarefas (só depois do post.py checar dar ok)
#   .\_sistema\agendador.ps1 -Desligar  desliga sem apagar
#   .\_sistema\agendador.ps1 -Estado    mostra estado e próxima execução
# Produção: a cada 30 min, nos perfis com producao_auto (perfis.yaml), só quando a fila está abaixo de fila_alvo.
# Post: a cada 30 min; o post.py só publica o que já venceu no horário de Nova York de cada perfil.
# DM: a cada 15 min; responde por DM quem comentou a palavra-chave (só nos perfis com oferta.dm_ativa e link_gratis = link do produto de $1,99).
param([switch]$Criar, [switch]$Ligar, [switch]$Desligar, [switch]$Estado)
$raiz = Split-Path -Parent $PSScriptRoot
$py = (Get-Command python).Source
$tarefas = @{
  'INSTAGRANS Producao' = @{ args = '_sistema\orquestrador\orquestrador.py produzir';                 gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 30) }
  'INSTAGRANS Post'     = @{ args = '_sistema\orquestrador\orquestrador.py publicar';                  gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 30) }
  'INSTAGRANS DM'       = @{ args = '_sistema\orquestrador\dm.py';                                       gatilho = New-ScheduledTaskTrigger -Once -At (Get-Date).Date -RepetitionInterval (New-TimeSpan -Minutes 15) }
}
if ($Criar) {
  foreach ($nome in $tarefas.Keys) {
    $t = $tarefas[$nome]
    $acao = New-ScheduledTaskAction -Execute $py -Argument $t.args -WorkingDirectory $raiz
    $cfg = New-ScheduledTaskSettingsSet -StartWhenAvailable -WakeToRun -ExecutionTimeLimit (New-TimeSpan -Hours 12) -MultipleInstances IgnoreNew
    Register-ScheduledTask -TaskName $nome -Action $acao -Trigger $t.gatilho -Settings $cfg -Description 'INSTAGRANS (ver _sistema/automacao.md §6)' -Force | Out-Null
    Disable-ScheduledTask -TaskName $nome | Out-Null
  }
}
if ($Ligar)    { $tarefas.Keys | ForEach-Object { Enable-ScheduledTask -TaskName $_ | Out-Null } }
if ($Desligar) { $tarefas.Keys | ForEach-Object { Disable-ScheduledTask -TaskName $_ | Out-Null } }
$tarefas.Keys | ForEach-Object { $i = Get-ScheduledTask -TaskName $_ -ErrorAction SilentlyContinue; if ($i) { $n = (Get-ScheduledTaskInfo -TaskName $_).NextRunTime; "{0,-22} {1,-9} proxima: {2}" -f $_, $i.State, $n } else { "{0,-22} (nao existe)" -f $_ } }
